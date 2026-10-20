"""MCP（Model Context Protocol）客户端 —— 零第三方依赖。

只实现"把 MCP server 的工具注册成 Skill"所需的最小子集：
`initialize` / `tools/list` / `tools/call`，支持两种传输：

- stdio：启动子进程，按行读写 JSON-RPC 2.0（`mcpServers` 里最常见的形式）
- http：Streamable HTTP，POST JSON-RPC，兼容 `application/json` 与 `text/event-stream` 两种响应

配置写法与主流 MCP 配置保持一致，例如：

```python
await registry.register_mcp({
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
})
await registry.register_mcp({"name": "remote", "url": "http://127.0.0.1:8000/mcp"})
```
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.skill.model import Skill, SkillKind, SkillSource

# 多数 server 都兼容的老版本协议号
PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "rpg-agent", "version": "0.1.0"}


class McpError(RuntimeError):
    """MCP 协议层错误（连接断开 / JSON-RPC error / 工具返回 isError）。"""


@dataclass
class McpServerConfig:
    """一个 MCP server 的连接参数。"""
    name: str
    transport: str = "stdio"          # "stdio" | "http"
    command: Optional[str] = None     # stdio：可执行文件
    args: list[str] = field(default_factory=list)
    env: Optional[dict[str, str]] = None
    cwd: Optional[str] = None
    url: Optional[str] = None         # http：Streamable HTTP 端点
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self.transport = (self.transport or "stdio").lower()
        if self.transport not in ("stdio", "http"):
            raise ValueError(f"不支持的 MCP transport：{self.transport}")
        if self.transport == "stdio" and not self.command:
            raise ValueError(f"MCP server {self.name}：stdio 传输必须提供 command")
        if self.transport == "http" and not self.url:
            raise ValueError(f"MCP server {self.name}：http 传输必须提供 url")

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "McpServerConfig":
        """兼容 `mcpServers` 的两种写法：command 型与 url 型。"""
        transport = data.get("transport") or data.get("type")
        if transport == "sse":
            transport = "http"
        if not transport:
            transport = "http" if data.get("url") else "stdio"
        return cls(
            name=name,
            transport=transport,
            command=data.get("command"),
            args=list(data.get("args") or []),
            env=data.get("env"),
            cwd=data.get("cwd"),
            url=data.get("url"),
            headers=dict(data.get("headers") or {}),
            timeout=float(data.get("timeout", 30.0)),
        )

    @classmethod
    def from_mapping(cls, servers: dict[str, dict[str, Any]]) -> list["McpServerConfig"]:
        return [cls.from_dict(name, cfg) for name, cfg in (servers or {}).items()]


@dataclass
class McpTool:
    """`tools/list` 返回的一项。"""
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class McpResult:
    """`tools/call` 的结果。"""
    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        parts = [c.get("text", "") for c in self.content if c.get("type") == "text"]
        text = "\n".join(p for p in parts if p)
        if not text and self.content:
            text = json.dumps(self.content, ensure_ascii=False)
        return text

    def raise_for_error(self) -> "McpResult":
        if self.is_error:
            raise McpError(self.text or "MCP 工具调用失败")
        return self


class McpClient:
    """极简 MCP 客户端：连接 / 列工具 / 调工具 / 关闭。"""

    def __init__(self, config: McpServerConfig):
        self.config = config
        self.server_info: Optional[dict[str, Any]] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._session_id: Optional[str] = None
        self._next_id = 0
        self._lock = asyncio.Lock()

    # ---------- 生命周期 ----------
    async def __aenter__(self) -> "McpClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def connect(self) -> dict[str, Any]:
        if self.config.transport == "stdio":
            await self._spawn()
        try:
            result = await self.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": CLIENT_INFO,
                },
            )
        except Exception:
            await self.close()
            raise
        self.server_info = result
        await self.notify("notifications/initialized")
        return result

    async def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        if proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                return
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (asyncio.TimeoutError, TimeoutError):
            proc.kill()

    # ---------- 能力 ----------
    async def list_tools(self) -> list[McpTool]:
        result = await self.request("tools/list")
        tools = []
        for t in result.get("tools", []) or []:
            tools.append(
                McpTool(
                    name=t.get("name", ""),
                    description=t.get("description") or "",
                    input_schema=t.get("inputSchema") or {},
                    raw=t,
                )
            )
        return [t for t in tools if t.name]

    async def call_tool(self, name: str, arguments: Optional[dict[str, Any]] = None) -> McpResult:
        result = await self.request("tools/call", {"name": name, "arguments": arguments or {}})
        return McpResult(
            content=list(result.get("content") or []),
            is_error=bool(result.get("isError", False)),
            raw=result,
        )

    # ---------- JSON-RPC ----------
    async def request(self, method: str, params: Optional[dict[str, Any]] = None,
                      timeout: Optional[float] = None) -> dict[str, Any]:
        async with self._lock:
            self._next_id += 1
            mid = self._next_id
            message = await self._exchange(
                {"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}},
                expect_response=True,
                timeout=timeout,
            )
            # http 传输一次 POST 就能拿到结果；stdio 需要跳过通知报文
            while True:
                if message is None:
                    raise McpError("MCP 连接已关闭，未收到响应")
                if message.get("id") == mid:
                    error = message.get("error")
                    if error:
                        raise McpError(f"{method} 失败：{error.get('message', error)}")
                    return message.get("result") or {}
                message = await self._recv(timeout)

    async def notify(self, method: str, params: Optional[dict[str, Any]] = None) -> None:
        async with self._lock:
            await self._exchange({"jsonrpc": "2.0", "method": method, "params": params or {}},
                                 expect_response=False)

    async def _exchange(self, payload: dict[str, Any], *, expect_response: bool,
                        timeout: Optional[float] = None) -> Optional[dict[str, Any]]:
        if self.config.transport == "stdio":
            await self._send_stdio(payload)
            return await self._recv(timeout) if expect_response else None
        return await asyncio.to_thread(self._exchange_http, payload, expect_response)

    # ---------- stdio 传输 ----------
    async def _spawn(self) -> None:
        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in (self.config.env or {}).items()})
        self._proc = await asyncio.create_subprocess_exec(
            self.config.command, *[str(a) for a in self.config.args],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self.config.cwd,
        )

    async def _send_stdio(self, payload: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise McpError("MCP stdio 子进程未启动")
        proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        await proc.stdin.drain()

    async def _recv(self, timeout: Optional[float] = None) -> Optional[dict[str, Any]]:
        if self.config.transport == "http":
            raise McpError("http 传输不支持被动接收消息")
        proc = self._proc
        if proc is None:
            raise McpError("MCP stdio 子进程未启动")
        if proc.stdout is None:
            raise McpError("MCP stdio 子进程不可读")

        wait = timeout or self.config.timeout
        while True:
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=wait)
            if not raw:
                return None
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue  # 忽略 server 打印的噪声日志

    # ---------- http 传输 ----------
    def _exchange_http(self, payload: dict[str, Any], expect_response: bool) -> Optional[dict[str, Any]]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        headers.update({str(k): str(v) for k, v in self.config.headers.items()})
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        req = urllib.request.Request(self.config.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                session = resp.headers.get("Mcp-Session-Id")
                if session:
                    self._session_id = session
                if not expect_response:
                    return None
                ctype = resp.headers.get("Content-Type", "")
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            raise McpError(f"MCP HTTP 请求失败：{e}") from e

        if "text/event-stream" in ctype:
            return _parse_sse(body, payload.get("id"))
        if not body.strip():
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise McpError(f"MCP 返回非法 JSON：{e}") from e


def _parse_sse(body: str, wanted_id: Any) -> Optional[dict[str, Any]]:
    """从 SSE 文本里挑出目标 id 的报文；找不到就返回最后一条。"""
    last: Optional[dict[str, Any]] = None
    buffer: list[str] = []
    for line in body.splitlines():
        if line.startswith("data:"):
            buffer.append(line[5:].strip())
        elif not line.strip() and buffer:
            msg = _loads_or_none("".join(buffer))
            buffer = []
            if msg is not None:
                last = msg
                if wanted_id is not None and msg.get("id") == wanted_id:
                    return msg
    if buffer:
        msg = _loads_or_none("".join(buffer))
        if msg is not None:
            last = msg
    return last


def _loads_or_none(text: str) -> Optional[dict[str, Any]]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


# ---------- MCP 工具 -> Skill ----------
def mcp_tool_to_skill(server: str, tool: McpTool, tags: Optional[list[str]] = None,
                      *, auto_tag: bool = True) -> Skill:
    """把 MCP 工具包装成 Skill（工具型）。"""
    tags = list(tags or [])
    if auto_tag:
        for auto in (server, "mcp"):
            if auto and auto not in tags:
                tags.append(auto)

    return Skill(
        name=_mcp_skill_name(server, tool.name),
        description=tool.description or f"MCP 工具 {server}/{tool.name}",
        tags=tags,
        source=SkillSource.MCP,
        kind=SkillKind.TOOL,
        body=render_mcp_body(server, tool),
        input_schema=dict(tool.input_schema or {"type": "object", "properties": {}}),
        server=server,
        tool=tool.name,
    )


def _mcp_skill_name(server: str, tool: str) -> str:
    """MCP 工具名可能带 `/`、空格等，统一成 kebab-case 便于 USE_SKILL 与 function calling。"""
    raw = f"mcp-{server}-{tool}"
    slug = "".join(c if c.isalnum() else "-" for c in raw).lower()
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "mcp-tool"


def render_mcp_body(server: str, tool: McpTool) -> str:
    """工具型技能没有 SKILL.md，用 schema 生成一份可读正文，供注入上下文。"""
    import json as _json

    lines = [
        f"# {tool.name}",
        "",
        f"- 来源：MCP server `{server}`",
        "",
        tool.description or "（该工具没有描述）",
        "",
        "## 参数",
        "",
        "```json",
        _json.dumps(tool.input_schema or {"type": "object", "properties": {}},
                    ensure_ascii=False, indent=2),
        "```",
    ]
    return "\n".join(lines)

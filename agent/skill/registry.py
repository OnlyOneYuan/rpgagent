"""技能注册中心（SkillRegistry）。

一个 Registry 收拢三种来源的技能，并提供按 tag 分组 / 筛选、注入 system prompt、
懒加载正文、调用工具型技能的能力：

```python
registry = SkillRegistry()
registry.register_directory(Paths.SKILLS)          # 本地 SKILL.md
registry.register_qwen()                           # .qwen/skills + ~/.qwen/skills
await registry.register_mcp({"name": "fs", "command": "npx", "args": [...]})  # MCP

groups = registry.group_by_tag()                   # {"设计": [Skill, ...], ...}
prompt = registry.build_system_prompt("你是 DM", tag=["世界"], grouped=True)
tools  = registry.to_tools()                       # 给 Qwen 的 function calling 定义
await registry.dispatch("mcp-fs-read-file", {"path": "a.txt"})
```

与 `SkillsManager` 的分工：Manager 仍是"只按 tag 过滤一批本地技能"的轻量入口，
Registry 是"注册 + 分组 + 多来源 + 可调用"的总入口。
"""

from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from agent.config.setting import Paths
from agent.skill.loader import load_reference
from agent.skill.manager import MatchMode, matches, normalize_tags
from agent.skill.model import Skill, SkillKind, SkillSource
from agent.skill.parser import parse_skill
from agent.skill.prompt import USAGE_TMPL, render_grouped_block, render_skill_block, render_system_prompt

# 从函数签名推 JSON Schema 用的类型映射
_JSON_TYPES = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


class SkillRegistry:
    """技能注册中心。"""

    def __init__(self,
                 tag: Optional[str | Iterable[str]] = None,
                 match_mode: MatchMode | str = MatchMode.ANY,
                 *,
                 skills_directory: str | Path | None = None):
        self.match_mode = MatchMode(match_mode)
        self.default_tag = normalize_tags(tag)      # 全局默认过滤标签，None = 不过滤
        self.skills_directory = Path(skills_directory or Paths.SKILLS)
        self.skills: dict[str, Skill] = {}
        self.mcp_clients: dict[str, Any] = {}       # server 名 -> McpClient

    # ==================== 注册 ====================
    def register(self, skill: Skill, *, overwrite: bool = True) -> Skill:
        """注册单个技能，同名默认覆盖。"""
        if not isinstance(skill, Skill):
            raise TypeError(f"需要 Skill 实例，收到 {type(skill).__name__}")
        if skill.name in self.skills and not overwrite:
            raise ValueError(f"技能已注册：{skill.name}（如需覆盖请 overwrite=True）")
        self.skills[skill.name] = skill
        return skill

    def register_many(self, skills: Iterable[Skill], *, overwrite: bool = True) -> list[Skill]:
        return [self.register(s, overwrite=overwrite) for s in skills]

    def unregister(self, name: str) -> bool:
        return self.skills.pop(name, None) is not None

    def clear(self) -> None:
        self.skills.clear()

    def register_file(self, skill_file: str | Path, *,
                      source: SkillSource | str = SkillSource.LOCAL,
                      tags: Optional[Iterable[str]] = None,
                      overwrite: bool = True) -> Skill:
        """注册单个 SKILL.md。"""
        s = parse_skill(Path(skill_file))
        s.source = SkillSource(source)
        if tags:
            s.tags = list(s.tags) + [t for t in tags if t not in s.tags]
        return self.register(s, overwrite=overwrite)

    def register_directory(self, directory: str | Path | None = None, *,
                           source: SkillSource | str = SkillSource.LOCAL,
                           tag: Optional[str | Iterable[str]] = None,
                           tags: Optional[Iterable[str]] = None,
                           overwrite: bool = True) -> list[Skill]:
        """扫描目录注册全部技能；tag=None 表示不筛选（全部注册）。"""
        base = Path(directory or self.skills_directory)
        wanted = normalize_tags(tag) if tag is not None else self.default_tag
        extra = [t for t in (tags or [])]

        registered: list[Skill] = []
        if not base.is_dir():
            return registered
        for f in sorted(base.glob("*/SKILL.md")):
            try:
                s = parse_skill(f)
            except Exception as e:
                print(f"[Skill Warning] {f}: {e}")
                continue
            if wanted and not matches(s.tags, wanted, self.match_mode):
                continue
            s.source = SkillSource(source)
            s.tags = list(s.tags) + [t for t in extra if t not in s.tags]
            registered.append(self.register(s, overwrite=overwrite))
        return registered

    def register_callable(self, func: Callable[..., Any], *,
                          name: Optional[str] = None,
                          description: Optional[str] = None,
                          tags: Optional[Iterable[str]] = None,
                          input_schema: Optional[dict[str, Any]] = None,
                          overwrite: bool = True) -> Skill:
        """把一个 Python 函数注册成工具型技能（同步或异步皆可）。"""
        fname = _slug(name or getattr(func, "__name__", "") or "tool")
        doc = (description or (inspect.getdoc(func) or "")).strip()
        desc = doc.splitlines()[0] if doc else f"调用本地工具 {fname}"
        schema = input_schema or _schema_from_signature(func)

        skill = Skill(
            name=fname,
            description=desc,
            tags=list(tags or []),
            source=SkillSource.LOCAL,
            kind=SkillKind.TOOL,
            input_schema=schema,
            handler=lambda arguments, _f=func: _f(**(arguments or {})),
        )
        return self.register(skill, overwrite=overwrite)

    def register_qwen(self, directory: Optional[str | Path | Iterable[str | Path]] = None, *,
                      project_root: Optional[Path] = None,
                      tags: Optional[Iterable[str]] = None,
                      overwrite: bool = True) -> list[Skill]:
        """注册 Qwen 技能目录里的技能，默认扫项目 `.qwen/skills` 与 `~/.qwen/skills`。"""
        from agent.skill import qwen as qwen_source

        dirs = [directory] if isinstance(directory, (str, Path)) else directory
        found = qwen_source.discover_qwen_skills(dirs, project_root=project_root)
        extra = [t for t in (tags or [])]
        out = []
        for s in found:
            s.tags = [t for t in s.tags if t not in extra] + extra
            out.append(self.register(s, overwrite=overwrite))
        return out

    async def register_mcp(self,
                           server: "Any",
                           *,
                           tags: Optional[Iterable[str]] = None,
                           auto_tag: bool = True,
                           overwrite: bool = True) -> list[Skill]:
        """连接一个 MCP server 并把它的全部工具注册成工具型技能。

        server 可以是 McpServerConfig、dict（单个 server，键里带 name），
        或 `{"name": ..., ...}` 形式的配置字典。
        """
        from agent.skill.mcp import McpClient, McpServerConfig, mcp_tool_to_skill

        cfg = _as_server_config(server)
        client = McpClient(cfg)
        try:
            await client.connect()
            tools = await client.list_tools()
        except Exception:
            await client.close()
            raise

        old = self.mcp_clients.get(cfg.name)
        if old is not None:
            await old.close()
        self.mcp_clients[cfg.name] = client

        extra = list(tags or [])
        registered = []
        for t in tools:
            s = mcp_tool_to_skill(cfg.name, t, tags=extra, auto_tag=auto_tag)
            s.handler = _mcp_handler(client, t.name)
            s.name = _unique_name(s.name, self.skills, overwrite)
            registered.append(self.register(s, overwrite=overwrite))
        return registered

    async def aclose(self) -> None:
        """关闭全部 MCP 连接。"""
        for name, client in list(self.mcp_clients.items()):
            try:
                await client.close()
            except Exception:
                pass
            self.mcp_clients.pop(name, None)

    # ==================== 查询 / 按 tag 分组 ====================
    def get(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def names(self) -> list[str]:
        return list(self.skills)

    def select(self, *, tag: Optional[str | Iterable[str]] = None,
               source: Optional[SkillSource | str | Iterable[SkillSource | str]] = None,
               kind: Optional[SkillKind | str] = None,
               match_mode: MatchMode | str | None = None,
               enabled_only: bool = True) -> dict[str, Skill]:
        """按 tag / 来源 / 形态筛选。tag=None 表示不按标签过滤。"""
        wanted = normalize_tags(tag)
        mode = self.match_mode if match_mode is None else MatchMode(match_mode)
        sources = _as_str_set(source)
        kind_v = SkillKind(kind) if kind is not None else None

        out: dict[str, Skill] = {}
        for name, s in self.skills.items():
            if enabled_only and not s.enabled:
                continue
            if kind_v is not None and s.kind is not kind_v:
                continue
            if sources and str(s.source) not in sources:
                continue
            if wanted and not matches(s.tags, wanted, mode):
                continue
            out[name] = s
        return out

    def group_by_tag(self, *, tag: Optional[str | Iterable[str]] = None,
                     source: Optional[SkillSource | str | Iterable[SkillSource | str]] = None,
                     kind: Optional[SkillKind | str] = None,
                     match_mode: MatchMode | str | None = None,
                     untagged_key: str = "未分组") -> dict[str, list[Skill]]:
        """按 tag 分组：一个技能带 N 个标签就会出现在 N 个分组里。"""
        groups: dict[str, list[Skill]] = defaultdict(list)
        for s in self.select(tag=tag, source=source, kind=kind, match_mode=match_mode).values():
            own = [t.strip() for t in s.tags if str(t).strip()]
            if not own:
                groups[untagged_key].append(s)
                continue
            for t in dict.fromkeys(own):     # 保持顺序、去重
                groups[t].append(s)
        return dict(groups)

    def tag_index(self, *, tag: Optional[str | Iterable[str]] = None) -> dict[str, list[str]]:
        """tag -> 技能名列表（轻量版，便于对外暴露成 JSON）。"""
        return {k: [s.name for s in v] for k, v in self.group_by_tag(tag=tag).items()}

    # ==================== 注入 system prompt ====================
    def build_prompt_block(self, *, tag: Optional[str | Iterable[str]] = None,
                           source: Optional[SkillSource | str | Iterable[SkillSource | str]] = None,
                           kind: Optional[SkillKind | str] = None,
                           match_mode: MatchMode | str | None = None,
                           with_tags: bool = False,
                           with_meta: bool = False,
                           grouped: bool = False) -> str:
        """渲染 `<available_skills>` 索引块；grouped=True 时按 tag 分组渲染。"""
        wanted = normalize_tags(tag)
        hint = "、".join(sorted(wanted)) if wanted else ""

        if grouped:
            groups = self.group_by_tag(tag=tag, source=source, kind=kind, match_mode=match_mode)
            return render_grouped_block(groups, with_tags=with_tags, empty_hint=hint)

        skills = self.select(tag=tag, source=source, kind=kind, match_mode=match_mode)
        return render_skill_block(skills, with_tags=with_tags, with_meta=with_meta, empty_hint=hint)

    def build_system_prompt(self, base_prompt: str, *,
                            tag: Optional[str | Iterable[str]] = None,
                            source: Optional[SkillSource | str | Iterable[SkillSource | str]] = None,
                            match_mode: MatchMode | str | None = None,
                            style: str = "default",
                            grouped: bool = False,
                            with_tags: bool = False) -> str:
        """基础人设 + 技能索引 + 使用协议。style="qwen" 时切换到 Qwen 版协议。"""
        block = self.build_prompt_block(tag=tag, source=source, match_mode=match_mode,
                                        with_tags=with_tags, grouped=grouped,
                                        with_meta=(style == "qwen"))
        usage = USAGE_TMPL
        if style == "qwen":
            from agent.skill import qwen as qwen_source

            usage = qwen_source.QWEN_USAGE_TMPL
        return render_system_prompt(base_prompt, block, usage)

    def to_tools(self, *, tag: Optional[str | Iterable[str]] = None,
                 source: Optional[SkillSource | str | Iterable[SkillSource | str]] = None,
                 with_meta: bool = True) -> list[dict[str, Any]]:
        """导出 Qwen / OpenAI 兼容的 function calling 工具定义。"""
        from agent.skill import qwen as qwen_source

        skills = self.select(tag=tag, source=source).values()
        return qwen_source.build_tools(skills, with_meta=with_meta)

    # ==================== 加载 / 调用 ====================
    def load(self, name: str) -> dict[str, Any]:
        """懒加载技能正文；工具型技能返回可读的 schema 正文。"""
        s = self.get(name)
        if s is None:
            return {"success": False, "error": f"Skill 不存在：{name}"}
        if s.body is None and s.path is not None:
            try:
                s.body = parse_skill(s.path).body
            except Exception as e:
                return {"success": False, "error": f"加载失败：{e}"}
        return {"success": True, "name": s.name, "instructions": s.body or "",
                "kind": str(s.kind), "source": str(s.source)}

    def load_reference(self, name: str, rel: str) -> dict[str, Any]:
        """读取技能目录下 references/ 的附属文档（含越界防护）。"""
        s = self.get(name)
        if s is None:
            return {"success": False, "error": f"Skill 不存在：{name}"}
        if s.path is None:
            return {"success": False, "error": f"技能 {name} 没有本地目录，无法读取附属文档"}
        return load_reference(self.skills, name, rel)

    async def call(self, name: str, arguments: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """调用工具型技能（本地函数或 MCP tools/call）。"""
        s = self.get(name)
        if s is None:
            return {"success": False, "error": f"Skill 不存在：{name}"}
        if s.kind is not SkillKind.TOOL or s.handler is None:
            return {"success": False, "error": f"技能 {name} 是提示词型，不可直接调用"}

        try:
            result = s.handler(dict(arguments or {}))
            if asyncio.iscoroutine(result):
                result = await result
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}
        return {"success": True, "name": s.name, "result": _normalize_result(result)}

    async def dispatch(self, name: str, arguments: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """统一分派：先把 `use_skill` / `read_skill_file` 元工具路由到对应能力。"""
        args = dict(arguments or {})
        if name == "use_skill":
            return self.load(args.get("name", ""))
        if name == "read_skill_file":
            return self.load_reference(args.get("name", ""), args.get("path", ""))
        return await self.call(name, args)

    # ==================== 调试 ====================
    def describe(self) -> str:
        lines = [f"SkillRegistry: {len(self.skills)} 个技能，{len(self.mcp_clients)} 个 MCP server"]
        for tag, skills in sorted(self.group_by_tag().items()):
            lines.append(f"  [{tag}] " + "、".join(s.name for s in skills))
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.skills)

    def __contains__(self, name: object) -> bool:
        return name in self.skills

    def __iter__(self):
        return iter(self.skills.values())


# ==================== 内部工具 ====================
def _slug(text: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in str(text)).lower()
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "skill"


def _as_str_set(value: Any) -> Optional[set[str]]:
    """把 source 入参（枚举 / 字符串 / 可迭代）归一成字符串集合。"""
    if value is None:
        return None
    raw = [value] if isinstance(value, (str, SkillSource)) else list(value)
    out = set()
    for v in raw:
        try:
            out.add(str(SkillSource(str(v))))
        except ValueError:
            out.add(str(v))
    return out


def _as_server_config(server: Any):
    from agent.skill.mcp import McpServerConfig

    if isinstance(server, McpServerConfig):
        return server
    if isinstance(server, dict):
        name = server.get("name")
        if not name:
            raise ValueError("MCP server 配置缺少 name")
        return McpServerConfig.from_dict(name, server)
    raise TypeError(f"无法识别的 MCP server 配置：{type(server).__name__}")


def _mcp_handler(client, tool_name: str):
    async def _handler(arguments: dict[str, Any]):
        result = await client.call_tool(tool_name, arguments or {})
        result.raise_for_error()
        return result
    return _handler


def _unique_name(name: str, existing: dict[str, Skill], overwrite: bool) -> str:
    if overwrite or name not in existing:
        return name
    i = 2
    while f"{name}-{i}" in existing:
        i += 1
    return f"{name}-{i}"


def _normalize_result(result: Any) -> Any:
    if hasattr(result, "text") and hasattr(result, "content"):   # McpResult
        return result.text
    if isinstance(result, (str, int, float, bool, list, dict)) or result is None:
        return result
    return str(result)


def _schema_from_signature(func: Callable[..., Any]) -> dict[str, Any]:
    """从函数签名推一份简单 JSON Schema（只处理基础类型）。"""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return {"type": "object", "properties": {}}

    properties: dict[str, Any] = {}
    required: list[str] = []
    for pname, p in sig.parameters.items():
        if pname in ("self", "cls") or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        if p.annotation is not p.empty:
            tname = getattr(p.annotation, "__name__", None)
            properties[pname] = {"type": _JSON_TYPES.get(tname, "string")}
        else:
            properties[pname] = {}
        if p.default is p.empty:
            required.append(pname)
    return {"type": "object", "properties": properties, "required": required}

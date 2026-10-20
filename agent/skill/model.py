"""技能数据模型。

在原有 SKILL.md 技能的基础上扩展两类信息：
- 来源（source）：local / qwen / mcp
- 形态（kind）：prompt（提示词型，注入上下文）/ tool（工具型，可真正调用）
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Optional
import re


class SkillSource(StrEnum):
    """技能来源。"""
    LOCAL = "local"   # 项目内的 SKILL.md
    QWEN = "qwen"     # Qwen Code 技能目录（.qwen/skills、~/.qwen/skills）
    MCP = "mcp"       # MCP server 暴露出来的工具


class SkillKind(StrEnum):
    """技能形态。"""
    PROMPT = "prompt"  # 提示词型：把正文注入上下文即可
    TOOL = "tool"      # 工具型：需要真正执行（MCP tools/call 或本地函数）


# function calling 的工具名只允许 [a-zA-Z0-9_-]
_TOOL_NAME_STRIP = re.compile(r"[^a-zA-Z0-9_-]+")


@dataclass
class Skill:
    name: str
    description: str
    path: Optional[Path] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    body: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    source: SkillSource | str = SkillSource.LOCAL
    kind: SkillKind | str = SkillKind.PROMPT
    enabled: bool = True
    allowed_tools: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable[..., Any]] = None
    server: Optional[str] = None   # MCP server 名
    tool: Optional[str] = None     # MCP 原始工具名

    def __post_init__(self) -> None:
        if self.path is not None and not isinstance(self.path, Path):
            self.path = Path(self.path)
        self.source = SkillSource(self.source)
        self.kind = SkillKind(self.kind)
        self.tags = [str(t) for t in (self.tags or [])]
        self.allowed_tools = [str(t) for t in (self.allowed_tools or [])]

    # ---------- 便捷属性 ----------
    @property
    def tool_name(self) -> str:
        """function calling 用的安全名字。"""
        safe = _TOOL_NAME_STRIP.sub("_", self.name).strip("_")
        return (safe or "skill")[:64]

    @property
    def qualified_name(self) -> str:
        """带来源前缀的全名，MCP 技能形如 `server::tool`。"""
        if self.server and self.tool:
            return f"{self.server}::{self.tool}"
        return self.name

    @property
    def is_callable(self) -> bool:
        return self.kind is SkillKind.TOOL and self.handler is not None

    # ---------- 对外序列化 ----------
    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "source": str(self.source),
            "kind": str(self.kind),
            "enabled": self.enabled,
        }

    def to_tool_schema(self, name: Optional[str] = None,
                       description: Optional[str] = None) -> dict[str, Any]:
        """导出 OpenAI / Qwen 兼容的 function calling 工具定义。"""
        params = dict(self.input_schema or {})
        params.setdefault("type", "object")
        params.setdefault("properties", {})
        return {
            "type": "function",
            "function": {
                "name": name or self.tool_name,
                "description": description or self.description,
                "parameters": params,
            },
        }

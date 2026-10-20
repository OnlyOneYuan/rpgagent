"""技能系统对外入口。

- `SkillRegistry`：注册中心（多来源注册 + 按 tag 分组 + 可调用）
- `SkillsManager`：轻量入口（只按 tag 过滤一批本地 SKILL.md）
"""

from agent.skill.model import Skill, SkillKind, SkillSource
from agent.skill.manager import SkillsManager, MatchMode, normalize_tags, matches
from agent.skill.parser import parse_skill
from agent.skill.registry import SkillRegistry
from agent.skill.mcp import (
    McpClient,
    McpError,
    McpResult,
    McpServerConfig,
    McpTool,
    mcp_tool_to_skill,
)
from agent.skill import qwen

__all__ = [
    "Skill",
    "SkillKind",
    "SkillSource",
    "SkillRegistry",
    "SkillsManager",
    "MatchMode",
    "normalize_tags",
    "matches",
    "parse_skill",
    "McpClient",
    "McpServerConfig",
    "McpTool",
    "McpResult",
    "McpError",
    "mcp_tool_to_skill",
    "qwen",
]

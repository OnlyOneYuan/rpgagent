"""Qwen skill 支持。

覆盖三件事：

1. **发现**：Qwen Code 风格技能目录（项目 `.qwen/skills/`、用户 `~/.qwen/skills/`），
   frontmatter 与本地 SKILL.md 一致（`name` / `description` / `tags`），额外兼容
   `allowed-tools` / `allowed_tools` 字段；解析放宽：name 与目录名不一致或缺少
   description 时自动兜底，不会因为格式小瑕疵丢技能。
2. **调用**：导出 Qwen / OpenAI 兼容的 function calling 工具定义
   （`to_qwen_tools()`），工具型技能（MCP / 本地函数）直接暴露原始签名，
   提示词型技能暴露 `use_skill` / `read_skill_file` 两个元工具实现渐进式加载。
3. **注入**：Qwen 版 system prompt（`<available_skills>` + 使用协议）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from agent.config.setting import Paths
from agent.skill.model import Skill, SkillKind, SkillSource
from agent.skill.parser import parse_skill

# Qwen Code 的技能目录（项目级 + 用户级）
QWEN_PROJECT_DIR = str(Paths.QWEN_SKILLS)
QWEN_USER_DIR = "~/.qwen/skills"


# ---------------- 发现 ----------------
def default_qwen_dirs(project_root: Optional[Path] = None) -> list[Path]:
    root = Path(project_root) if project_root else Path.cwd()
    return [root / QWEN_PROJECT_DIR, Path(QWEN_USER_DIR).expanduser()]


def discover_qwen_skills(dirs: Optional[Iterable[str | Path]] = None,
                         *, project_root: Optional[Path] = None) -> list[Skill]:
    """扫描 Qwen 技能目录，返回去重后的技能列表（目录级 > 单文件级）。"""
    targets = [Path(d) for d in dirs] if dirs is not None else default_qwen_dirs(project_root)

    found: dict[str, Skill] = {}
    for base in targets:
        base = base.expanduser()
        if not base.is_dir():
            continue
        candidates = sorted(base.glob("*/SKILL.md")) + [
            f for f in sorted(base.glob("*.md")) if f.name.lower() != "qwen.md"
        ]
        for f in candidates:
            try:
                s = parse_qwen_skill(f)
            except Exception as e:  # 单文件坏不影响其他技能
                print(f"[Qwen Skill Warning] {f}: {e}")
                continue
            found.setdefault(s.name, s)
    return list(found.values())


def parse_qwen_skill(skill_file: Path) -> Skill:
    """解析 Qwen 技能：先走严格解析，失败则退化为宽松解析。"""
    try:
        s = parse_skill(skill_file)
    except ValueError:
        s = _parse_lenient(skill_file)

    s.source = SkillSource.QWEN
    s.allowed_tools = _read_allowed_tools(s.metadata)
    if "qwen" not in s.tags:
        s.tags.append("qwen")
    return s


def _parse_lenient(skill_file: Path) -> Skill:
    """宽松解析：目录名兜底 name，首行标题兜底 description。"""
    import re

    text = skill_file.read_text(encoding="utf-8-sig")
    meta: dict[str, Any] = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        loaded = yaml.safe_load(m.group(1))
        if isinstance(loaded, dict):
            meta = loaded
        body = m.group(2)

    name = _slug(str(meta.get("name") or skill_file.parent.name))
    desc = str(meta.get("description") or "").strip()
    if not desc:
        for line in body.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                desc = line
                break
    desc = desc or f"{name} 技能"

    tags = meta.get("tags")
    if tags is None:
        tags = []
    elif isinstance(tags, str):
        tags = [tags]
    elif isinstance(tags, list):
        tags = [str(t) for t in tags]
    else:
        tags = []

    return Skill(
        name=name,
        description=desc,
        path=skill_file,
        metadata=meta,
        body=body.strip(),
        tags=tags,
        source=SkillSource.QWEN,
        allowed_tools=_read_allowed_tools(meta),
    )


def _read_allowed_tools(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("allowed-tools") or meta.get("allowed_tools") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(t) for t in raw]
    return []


def _slug(text: str) -> str:
    import re

    slug = "".join(c if c.isalnum() else "-" for c in str(text)).lower()
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "skill"


# ---------------- function calling（Qwen / OpenAI 兼容） ----------------
USE_SKILL_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "use_skill",
        "description": "加载指定提示词技能的完整正文到上下文，name 必须取自 <available_skills>",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "技能名"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}

READ_SKILL_FILE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_skill_file",
        "description": "读取技能目录下 references/ 等附属文档的相对路径内容",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名"},
                "path": {"type": "string", "description": "技能目录内的相对路径，如 references/xxx.md"},
            },
            "required": ["name", "path"],
            "additionalProperties": False,
        },
    },
}


def build_tools(skills: Iterable[Skill], *, with_meta: bool = True) -> list[dict[str, Any]]:
    """导出 Qwen / OpenAI 兼容的工具定义列表。

    工具型技能（MCP、本地函数）暴露自身签名；提示词型技能额外提供
    `use_skill` / `read_skill_file` 两个元工具做渐进式加载。
    """
    items = list(skills)
    tools = [s.to_tool_schema() for s in items if s.kind is SkillKind.TOOL and s.enabled]
    print(items[0].to_tool_schema())
    print(tools)
    if with_meta and any(s.kind is SkillKind.PROMPT for s in items):
        tools.append(USE_SKILL_TOOL)
        tools.append(READ_SKILL_FILE_TOOL)
    return tools


def parse_tool_calls(message: Any) -> list[tuple[str, dict[str, Any]]]:
    """从 Qwen 返回的 message（dict 或对象）里取出 (工具名, 参数)。"""
    calls = message.get("tool_calls") if isinstance(message, dict) else getattr(message, "tool_calls", None)
    if not calls:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for c in calls:
        fn = c.get("function") if isinstance(c, dict) else getattr(c, "function", None)
        if fn is None:
            continue
        name = fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", None)
        raw = fn.get("arguments") if isinstance(fn, dict) else getattr(fn, "arguments", None)
        if isinstance(raw, str) and raw.strip():
            import json

            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                args = {"_raw": raw}
        else:
            args = raw or {}
        if name:
            out.append((name, args if isinstance(args, dict) else {"value": args}))
    return out


# ---------------- system prompt ----------------
QWEN_USAGE_TMPL = """<skill_usage>
    - 上面每项是一个可用技能，name 是唯一标识，必须原样引用，不得臆造。
    - 工具型技能：直接按给定的函数签名发起 tool_calls 调用。
    - 提示词型技能：先调用 use_skill({"name": "..."}) 载入正文，再按正文执行。
    - 只能使用上面列出的 name；不需要技能时直接正常回复。
    </skill_usage>"""

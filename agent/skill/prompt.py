"""技能索引块的渲染（注入 system prompt）。

SkillsManager 与 SkillRegistry 共用这里的渲染逻辑，避免两处输出格式漂移。
"""

from collections.abc import Iterable, Mapping
from typing import Any, Optional
from xml.sax.saxutils import escape as _xml_escape

from agent.skill.model import Skill


# 提示词型技能的调用协议（USE_SKILL 文本协议，适用于 local / qwen）
USAGE_TMPL = """<skill_usage>
                    - 上面每项是一个可加载的技能，name 是唯一标识，必须原样引用，不得臆造。
                    - 需要某个技能时，在回复第一行输出：USE_SKILL: <name>
                    - 只能选上面列出的 name；不需要时直接正常回复。
                    </skill_usage>"""


def render_skill_block(skills: Iterable[Skill] | Mapping[str, Skill],
                       *,
                       with_tags: bool = False,
                       with_meta: bool = False,
                       empty_hint: str = "") -> str:
    """扁平索引块：一个 <skill> 一项。"""
    items = skills.values() if isinstance(skills, Mapping) else skills
    items = list(items)

    if not items:
        tip = f" {_xml_escape(empty_hint)} " if empty_hint else " "
        return f"<available_skills>\n  <!-- 无可用技能{tip}-->\n</available_skills>"

    parts = ["<available_skills>"]
    for s in items:
        parts.append("  <skill>")
        parts.append(f"    <name>{_xml_escape(s.name)}</name>")
        parts.append(f"    <description>{_xml_escape(s.description.strip())}</description>")
        if with_tags and s.tags:
            parts.append(f"    <tags>{_xml_escape('、'.join(s.tags))}</tags>")
        if with_meta:
            parts.append(f"    <source>{_xml_escape(str(s.source))}</source>")
            parts.append(f"    <kind>{_xml_escape(str(s.kind))}</kind>")
        parts.append("  </skill>")
    parts.append("</available_skills>")
    return "\n".join(parts)


def render_grouped_block(groups: Mapping[str, list[Skill]],
                         *,
                         with_tags: bool = False,
                         empty_hint: str = "") -> str:
    """按 tag 分组的索引块：<group tag="..."> 下挂若干 <skill>。"""
    groups = {k: v for k, v in groups.items() if v}
    if not groups:
        tip = f" {_xml_escape(empty_hint)} " if empty_hint else " "
        return f"<available_skills>\n  <!-- 无可用技能{tip}-->\n</available_skills>"

    parts = ["<available_skills>"]
    for tag in sorted(groups):
        parts.append(f'  <group tag="{_xml_escape(tag)}">')
        for s in groups[tag]:
            parts.append("    <skill>")
            parts.append(f"      <name>{_xml_escape(s.name)}</name>")
            parts.append(f"      <description>{_xml_escape(s.description.strip())}</description>")
            if with_tags and s.tags:
                parts.append(f"      <tags>{_xml_escape('、'.join(s.tags))}</tags>")
            parts.append("    </skill>")
        parts.append("  </group>")
    parts.append("</available_skills>")
    return "\n".join(parts)


def render_system_prompt(base_prompt: str, block: str,
                         usage_tmpl: str = USAGE_TMPL) -> str:
    """基础人设 + 索引块 + 使用协议。"""
    return "\n\n".join([base_prompt.strip(), block, usage_tmpl])

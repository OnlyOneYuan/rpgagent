import re
import yaml
from pathlib import Path
from agent.skill.model import Skill

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LEN = 64
MAX_DESC_LEN = 1024
MAX_BODY_BYTES = 50_000


def parse_skill(skill_file: Path) -> Skill:
    text = skill_file.read_text(encoding="utf-8-sig")

    if not text.startswith("---"):
        raise ValueError("缺少 YAML frontmatter")

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        raise ValueError("frontmatter 未正确闭合")

    meta = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()

    if not isinstance(meta, dict):
        raise ValueError("frontmatter 不是合法的映射结构")

    name = meta.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ValueError("name 缺失或格式不合法（kebab-case）")
    if len(name) > MAX_NAME_LEN:
        raise ValueError(f"name 超过 {MAX_NAME_LEN} 字符")
    if name != skill_file.parent.name:
        raise ValueError(f"name({name}) 与父目录名({skill_file.parent.name}) 不一致")

    desc = meta.get("description")
    if not isinstance(desc, str) or not desc.strip():
        raise ValueError("description 不能为空")
    if len(desc) > MAX_DESC_LEN:
        raise ValueError(f"description 超过 {MAX_DESC_LEN} 字符")

    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ValueError("正文过大，建议拆分到 references/")

    tags = meta.get("tags")
    if tags is None:
        tags = []
    elif isinstance(tags, str):
        tags = [tags]
    elif isinstance(tags, list):
        tags = [str(t) for t in tags]
    else:
        raise ValueError("tags 格式不合法")

    return Skill(
        name=name,
        description=desc.strip(),
        path=skill_file,
        metadata=meta,
        body=body,
        tags=tags
    )

from pathlib import Path
from agent.skill.model import Skill


def load_skill(skills: dict[str, Skill], name: str) -> dict:
    s = skills.get(name)
    if s is None:
        return {"success": False, "error": f"Skill 不存在：{name}"}

    if s.body is None:
        skill_file = s.path if s.path.is_file() else s.path / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8-sig")

        # 如果只需要正文，可以重新解析；也可以直接缓存全文
        from .parser import parse_skill
        parsed = parse_skill(skill_file)
        s.body = parsed.body

    return {"success": True, "name": s.name, "instructions": s.body}


def load_reference(skills: dict[str, Skill], name: str, rel: str) -> dict:
    s = skills.get(name)
    if s is None:
        return {"success": False, "error": f"Skill 不存在：{name}"}

    base = (s.path.parent / "references").resolve()
    target = (base / rel).resolve()

    if base not in target.parents and target != base:
        return {"success": False, "error": "路径越界"}

    if not target.is_file():
        return {"success": False, "error": "文件不存在"}

    return {"success": True, "content": target.read_text(encoding="utf-8")}

# skill_loader.py
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LEN = 64
MAX_DESC_LEN = 1024
MAX_BODY_BYTES = 50_000


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    body: str = ""


def parse_skill(skill_file: Path) -> Skill:
    """解析并校验单个 SKILL.md，不合法则抛 ValueError。"""
    text = skill_file.read_text(encoding="utf-8-sig")  # 兼容 BOM

    if not text.startswith("---"):
        raise ValueError("缺少 YAML frontmatter")

    # 用正则切，避免正文里出现 --- 被误切
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

    return Skill(name=name, description=desc.strip(), path=skill_file,
                 metadata=meta, body=body)


def discover(skills_dir: Path) -> dict[str, Skill]:
    """扫描目录，跳过格式错误的技能并打印告警。"""
    skills: dict[str, Skill] = {}
    skills_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            s = parse_skill(f)
            skills[s.name] = s
        except Exception as e:
            print(f"[Skill Warning] {f.relative_to(skills_dir)}: {e}")
    return skills


def build_index(skills: dict[str, Skill]) -> str:
    """第一层：只把 name + description 注入系统提示。"""
    if not skills:
        return "当前没有可用 Skill。"
    lines = ["可用 Skills："]
    for s in skills.values():
        lines.append(f"- {s.name}: {s.description}")
    return "\n".join(lines)


def load_skill(skills: dict[str, Skill], name: str) -> dict[str, Any]:
    """第二层：按名加载完整正文。"""
    s = skills.get(name)
    if s is None:
        return {"success": False, "error": f"Skill 不存在：{name}"}
    return {"success": True, "name": s.name, "instructions": s.body}


def load_reference(skills: dict[str, Skill], name: str, rel: str) -> dict[str, Any]:
    """第三层：读取 references/ 下的附属文档，并做越界防护。"""
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


if __name__ == "__main__":
    import argparse, json
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="./agent/tools")
    p.add_argument("--name", help="指定技能名，加载完整正文")
    p.add_argument("--ref", help="references 下的相对路径")
    args = p.parse_args()
    skills = discover(Path(args.dir).resolve())
    if args.name and args.ref:
        print(json.dumps(load_reference(skills, args.name, args.ref), ensure_ascii=False, indent=2))
    elif args.name:
        print(json.dumps(load_skill(skills, args.name), ensure_ascii=False, indent=2))
    else:
        print(build_index(skills))
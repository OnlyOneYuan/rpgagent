from agent.config.setting import Path
from os import listdir
import yaml
import re
from pathlib import Path as Ph
from typing import Dict, Optional
from dataclasses import dataclass

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LEN = 64
MAX_DESC_LEN = 1024
MAX_BODY_BYTES = 50_000


@dataclass
class Skill:
    name: str
    description: str
    path: Ph
    content: Optional[str] = None

skills = Path.SKILLS

class SkillsManager:
    def __init__(self, skills_directory: str = Path.SKILLS):
        self.skills_directory = Ph(skills_directory)
        self.skills: Dict[str, Skill] = {}
        self._discover_skills()

    def _discover_skills(self):
        """启动时扫描目录，仅加载元数据（YAML Frontmatter）"""
        if not self.skills_directory.exists():
            return
        for item in self.skills_directory.iterdir():
            skill_file = item / "SKILL.md"
            if item.is_dir() and skill_file.exists():
                with open(skill_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 解析 YAML 元数据
                    if content.startswith('---'):
                        parts = content.split('---', 2)
                        metadata = yaml.safe_load(parts[1])
                        self.skills[metadata['name']] = Skill(
                            name=metadata['name'],
                            description=metadata['description'],
                            path=item,
                            content=None  # 启动时不加载完整内容，节省 Token
                        )

    def get_skill_summaries(self):
        """返回所有技能的摘要，供 Agent 初始上下文使用"""
        return [{"name": s.name, "description": s.description} for s in self.skills.values()]

    def activate_skill(self, skill_name: str) -> Optional[str]:
        """按需加载技能的完整指令"""
        skill = self.skills.get(skill_name)
        if skill and skill.content is None:
            skill_file = skill.path / "SKILL.md"
            with open(skill_file, 'r', encoding='utf-8') as f:
                skill.content = f.read()
        return skill.content if skill else None

    @staticmethod
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


    def discover(self,skills_dir: Path) -> dict[str, Skill]:
        """扫描目录，跳过格式错误的技能并打印告警。"""
        skills: dict[str, Skill] = {}
        skills_dir.mkdir(parents=True, exist_ok=True)
        for f in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                s = self.parse_skill(f)
                skills[s.name] = s
            except Exception as e:
                print(f"[Skill Warning] {f.relative_to(skills_dir)}: {e}")
        return skills

    @staticmethod
    def build_index(skills: dict[str, Skill]) -> str:
        """第一层：只把 name + description 注入系统提示。"""
        if not skills:
            return "当前没有可用 Skill。"
        lines = ["可用 Skills："]
        for s in skills.values():
            lines.append(f"- {s.name}: {s.description}")
        return "\n".join(lines)

    @staticmethod
    def load_skill(skills: dict[str, Skill], name: str) -> dict[str, Any]:
        """第二层：按名加载完整正文。"""
        s = skills.get(name)
        if s is None:
            return {"success": False, "error": f"Skill 不存在：{name}"}
        return {"success": True, "name": s.name, "instructions": s.body}

    @staticmethod
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


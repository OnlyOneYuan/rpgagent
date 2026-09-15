from agent.config.setting import Path 
from os import listdir
import yaml
from pathlib import Path as Ph
from typing import Dict, Optional
from dataclasses import dataclass


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


class skillLoader:

    def __init__(self):
        skills = listdir(Path.SKILLS)

    def read():
        '''
            读取skill.md
        '''
        pass


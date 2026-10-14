from pathlib import Path
from agent.skill.model import Skill
from agent.skill.parser import parse_skill
from agent.config.setting import Path


class SkillsManager:
    def __init__(self, skills_directory: str | Path = Path.SKILLS):
        self.skills_directory = Path(skills_directory)
        self.skills: dict[str, Skill] = {}
        self.discover()

    def discover(self):
        self.skills = self._discover(self.skills_directory)

    @staticmethod
    def _discover(skills_dir: Path) -> dict[str, Skill]:
        skills: dict[str, Skill] = {}
        skills_dir.mkdir(parents=True, exist_ok=True)

        for f in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                s = parse_skill(f)
                skills[s.name] = s
            except Exception as e:
                print(f"[Skill Warning] {f.relative_to(skills_dir)}: {e}")

        return skills

    def get_skill_summaries(self):
        return [
            {"name": s.name, "description": s.description}
            for s in self.skills.values()
        ]

    def build_index(self,skills=None,tag=None) -> str:
        if not self.skills:
            return "当前没有可用 Skill。"
        if skills == None:
            skills = self.skills

        lines = [f"可用{tag}Skills："]
        for s in self.skills.values():
            lines.append(f"- {s.name}: {s.description}")
        return "\n".join(lines)

    def _bulid_index_bytag(self,tag) -> str:

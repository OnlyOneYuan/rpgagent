from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path
import re
from agent.skill.model import Skill
from agent.skill.parser import parse_skill
from agent.config.setting import Paths
from agent.skill.prompt import USAGE_TMPL as _USAGE_TMPL
from agent.skill.prompt import render_skill_block


class MatchMode(StrEnum):
    """多标签匹配模式。"""
    ANY = "any"   # 任一标签命中即可（并集）
    ALL = "all"   # 全部标签都要命中（交集）


def normalize_tags(tag: str | Iterable[str] | None) -> frozenset[str] | None:
    """把任意形态的标签入参归一成 frozenset（去空白、去重、忽略大小写）。

    None 或空集合表示"没有指定标签"，沿用调用方的既有语义处理。
    """
    if tag is None:
        return None
    if isinstance(tag, str):
        raw = [tag]
    elif isinstance(tag, Iterable):
        raw = list(tag)
    else:
        raw = [tag]

    cleaned = {str(t).strip().casefold() for t in raw if str(t).strip()}
    return frozenset(cleaned) or None


def matches(skill_tags: Iterable[str] | None,
            wanted: frozenset[str] | None,
            match_mode: MatchMode | str = MatchMode.ANY) -> bool:
    """判断某个 Skill 的 tags 是否命中期望标签集。"""
    if not wanted:
        # 未指定标签：保持与改动前一致的行为（不命中）
        return False

    own = {str(t).strip().casefold() for t in (skill_tags or ()) if str(t).strip()}
    if not own:
        return False

    mode = MatchMode(match_mode)
    if mode is MatchMode.ALL:
        return wanted <= own
    return bool(wanted & own)


class SkillsManager:
    def __init__(self, skills_directory: str | Path = Paths.SKILLS, tag = None,
                 match_mode: MatchMode | str = MatchMode.ANY):
        self.skills_directory = Path(skills_directory)
        self.match_mode = MatchMode(match_mode)
        self.skills: dict[str, Skill] = {}
        self.discover(tag, self.match_mode)

    def discover(self, tag = None, match_mode: MatchMode | str | None = None):
        mode = self.match_mode if match_mode is None else MatchMode(match_mode)
        self.skills = self._discover(self.skills_directory, tag, mode)

    @staticmethod
    def _discover(skills_dir: Path = Paths.SKILLS, tag = None,
                  match_mode: MatchMode | str = MatchMode.ANY) -> dict[str, Skill]:
        wanted = normalize_tags(tag)
        skills: dict[str, Skill] = {}
        skills_dir.mkdir(parents=True, exist_ok=True)

        for f in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                s = parse_skill(f)
                if matches(s.tags, wanted, match_mode):
                    skills[s.name] = s
            except Exception as e:
                print(f"[Skill Warning] {f.relative_to(skills_dir)}: {e}")

        return skills

    def get_skill_summaries(self):
        return [
            {"name": s.name, "description": s.description}
            for s in self.skills.values()
        ]

    def build_prompt_block(self, skills=None, tag=None,
                           match_mode: MatchMode | str | None = None,
                           with_tags: bool = False) -> str:
        """生成注入 system prompt 的技能索引块（XML）。tag 支持字符串或标签列表。"""
        skills = self.skills if skills is None else skills
        wanted = normalize_tags(tag)
        mode = self.match_mode if match_mode is None else MatchMode(match_mode)

        if wanted:
            skills = {n: s for n, s in skills.items() if matches(s.tags, wanted, mode)}

        hint = "、".join(sorted(wanted)) if wanted else ""
        return render_skill_block(skills, with_tags=with_tags, empty_hint=hint)

    USAGE_TMPL = _USAGE_TMPL

    def build_system_prompt(self, base_prompt: str, tag=None,
                            match_mode: MatchMode | str | None = None) -> str:
        """拼装完整 system prompt：基础人设 + 技能索引 + 使用协议。"""
        block = self.build_prompt_block(tag=tag, match_mode=match_mode)
        return "\n\n".join([base_prompt.strip(), block, self.USAGE_TMPL])

    SKILL_CALL_RE = re.compile(r"^USE_SKILL:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$", re.M)

    @staticmethod
    def parse_skill_call(text: str) -> str | None:
        """从模型输出里提取技能名；拿到后用 loader.load_skill 注入正文。"""
        m = SkillsManager.SKILL_CALL_RE.search(text or "")
        return m.group(1) if m and m.group(1) else None



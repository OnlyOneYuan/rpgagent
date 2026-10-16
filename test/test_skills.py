"""agent.skill 模块测试：解析 / 多标签匹配 / 索引渲染 / 正文加载。

运行：  d:/code/RPG 目录下执行  python -m pytest test/test_skill.py -v
说明：全部用 tmp_path 造临时技能目录，不依赖真实的 agent/skills。
"""
import re
import pytest
from pathlib import Path

from agent.skill.parser import parse_skill
from agent.skill.manager import (
    SkillsManager, MatchMode, normalize_tags, matches,
)
from agent.skill.loader import load_skill, load_reference


# ==================== 辅助：造 SKILL.md ====================
def write_raw(root: Path, name: str, text: str) -> Path:
    """在 root/name/SKILL.md 写入原始文本"""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SKILL.md"
    p.write_text(text, encoding="utf-8")
    return p


def write_skill(root: Path, name: str, description: str, tags=None, body="正文内容") -> Path:
    """写一个合法技能：name 必须与目录名一致（parse_skill 的硬性约束）"""
    lines = ["---", f"name: {name}", f"description: {description}"]
    if tags:
        lines.append("tags:")
        lines.extend(f"- {t}" for t in tags)
    lines.append("---")
    return write_raw(root, name, "\n".join(lines) + "\n\n" + body + "\n")


@pytest.fixture
def skills_dir(tmp_path):
    """两个技能：怪物技能[设计]，背景生成[世界, 设计]"""
    write_skill(tmp_path, "rpg-monster-skill", "生成怪物技能时使用", ["设计"])
    write_skill(tmp_path, "rpg-backgroundgenerater", "生成世界背景时使用", ["世界", "设计"])
    return tmp_path


# ==================== parser ====================
def test_parse_skill_basic(skills_dir):
    '''正常解析：name / description / tags / body / path'''
    s = parse_skill(skills_dir / "rpg-monster-skill" / "SKILL.md")
    assert s.name == "rpg-monster-skill"
    assert s.description == "生成怪物技能时使用"
    assert s.tags == ["设计"]
    assert s.body == "正文内容"
    assert s.metadata["name"] == "rpg-monster-skill"


def test_parse_skill_multi_tags(skills_dir):
    '''多个标签全部保留，顺序与 YAML 一致'''
    s = parse_skill(skills_dir / "rpg-backgroundgenerater" / "SKILL.md")
    assert s.tags == ["世界", "设计"]


def test_parse_skill_tags_as_string(tmp_path):
    '''tags 写成单个字符串时，被归一成单元素列表'''
    p = write_raw(tmp_path, "solo-tag", "---\nname: solo-tag\ndescription: 单标签\ntags: 设计\n---\n\n正文\n")
    assert parse_skill(p).tags == ["设计"]


def test_parse_skill_without_tags(tmp_path):
    '''没有 tags 字段时为 []，而不是 None'''
    p = write_skill(tmp_path, "no-tag", "无标签技能", tags=None)
    assert parse_skill(p).tags == []


def test_parse_skill_rejects_bad_name(tmp_path):
    '''name 不是 kebab-case 时报错'''
    p = write_raw(tmp_path, "bad-name", "---\nname: Bad_Name\ndescription: 非法名\n---\n\n正文\n")
    with pytest.raises(ValueError):
        parse_skill(p)


def test_parse_skill_rejects_name_mismatch(tmp_path):
    '''name 必须与父目录名一致，否则报错'''
    p = write_raw(tmp_path, "dir-a", "---\nname: dir-b\ndescription: 不一致\n---\n\n正文\n")
    with pytest.raises(ValueError, match="不一致"):
        parse_skill(p)


def test_parse_skill_rejects_no_frontmatter(tmp_path):
    '''缺少 YAML frontmatter 时报错'''
    p = write_raw(tmp_path, "plain-md", "没有 frontmatter 的正文")
    with pytest.raises(ValueError, match="frontmatter"):
        parse_skill(p)


def test_parse_skill_rejects_unclosed_frontmatter(tmp_path):
    '''frontmatter 未闭合时报错'''
    p = write_raw(tmp_path, "unclosed", "---\nname: unclosed\ndescription: 没闭合\n")
    with pytest.raises(ValueError):
        parse_skill(p)


def test_parse_skill_rejects_empty_description(tmp_path):
    '''description 缺失或为空时报错'''
    p = write_raw(tmp_path, "no-desc", "---\nname: no-desc\n---\n\n正文\n")
    with pytest.raises(ValueError):
        parse_skill(p)


def test_parse_skill_rejects_non_mapping(tmp_path):
    '''frontmatter 不是映射结构（是列表）时报错'''
    p = write_raw(tmp_path, "list-meta", "---\n- a\n- b\n---\n\n正文\n")
    with pytest.raises(ValueError, match="映射"):
        parse_skill(p)


# ==================== 多标签匹配（纯函数，不碰文件系统） ====================
def test_normalize_tags_none_and_empty():
    '''None / 空列表 / 全空白 都表示"没有指定标签"'''
    assert normalize_tags(None) is None
    assert normalize_tags([]) is None
    assert normalize_tags(["", "   "]) is None


def test_normalize_tags_dedupe_and_casefold():
    '''去空白、去重、忽略大小写'''
    assert normalize_tags("设计") == frozenset({"设计"})
    assert normalize_tags(["设计 ", "设计", "世界"]) == frozenset({"设计", "世界"})
    assert normalize_tags(["Fire", "fire"]) == frozenset({"fire"})


def test_matches_any_and_all():
    '''ANY 取并集，ALL 取交集；字符串和枚举都可以传'''
    wanted = normalize_tags(["世界", "设计"])
    assert matches(["设计"], wanted)                       # ANY：命中一个即可
    assert not matches(["设计"], wanted, MatchMode.ALL)     # ALL：缺"世界"
    assert matches(["世界", "设计"], wanted, "all")         # 字符串模式
    assert matches(["设计"], normalize_tags("设计"), "any")


def test_matches_edge_cases():
    '''无标签的技能不命中；wanted 为空时沿用"不命中"的既有语义'''
    assert not matches([], normalize_tags("设计"))
    assert not matches(["设计"], None)
    assert not matches(["设计"], frozenset())


def test_matches_tolerates_space_and_case():
    '''技能自带标签含空格 / 大小写不同也应命中'''
    assert matches([" 设计 ", "Fire"], normalize_tags(["fire", "设计"]), "all")


# ==================== SkillsManager ====================
def test_discover_single_tag(skills_dir):
    '''单标签：两个技能都带"设计"'''
    m = SkillsManager(skills_dir)
    m.discover("设计")
    assert set(m.skills) == {"rpg-monster-skill", "rpg-backgroundgenerater"}


def test_discover_multi_tag_any(skills_dir):
    '''多标签 ANY（默认）：任一命中即收录'''
    m = SkillsManager(skills_dir, tag=["世界", "设计"])
    assert len(m.skills) == 2


def test_discover_multi_tag_all(skills_dir):
    '''多标签 ALL：只有同时带"世界"和"设计"的背景技能'''
    m = SkillsManager(skills_dir, tag=["世界", "设计"], match_mode="all")
    assert set(m.skills) == {"rpg-backgroundgenerater"}


def test_discover_none_keeps_legacy_behavior(skills_dir):
    '''tag=None 时不命中任何技能（既有语义，未修的已知行为）'''
    m = SkillsManager(skills_dir)
    assert m.skills == {}


def test_discover_skips_broken_skill(tmp_path, capsys):
    '''解析失败的技能被跳过并打印告警，不影响其他技能'''
    write_skill(tmp_path, "good-one", "正常技能", ["设计"])
    write_raw(tmp_path, "broken-one", "没有 frontmatter")
    m = SkillsManager(tmp_path, tag="设计")
    assert set(m.skills) == {"good-one"}
    assert "Skill Warning" in capsys.readouterr().out


def test_get_skill_summaries(skills_dir):
    '''摘要只含 name + description'''
    m = SkillsManager(skills_dir, tag="设计")
    rows = m.get_skill_summaries()
    assert {r["name"] for r in rows} == {"rpg-monster-skill", "rpg-backgroundgenerater"}
    assert all(set(r) == {"name", "description"} for r in rows)


# ==================== 索引渲染（注入 LLM） ====================
def test_build_prompt_block_basic(skills_dir):
    '''XML 块包含 name / description，默认不带 tags'''
    m = SkillsManager(skills_dir, tag="设计")
    block = m.build_prompt_block()
    assert block.startswith("<available_skills>")
    assert block.endswith("</available_skills>")
    assert "<name>rpg-monster-skill</name>" in block
    assert "生成怪物技能时使用" in block
    assert "<tags>" not in block


def test_build_prompt_block_with_tags(skills_dir):
    '''with_tags=True 时输出标签'''
    m = SkillsManager(skills_dir, tag="设计")
    assert "<tags>世界、设计</tags>" in m.build_prompt_block(with_tags=True)


def test_build_prompt_block_filter_by_tag(skills_dir):
    '''传入 tag 可在渲染时二次筛选'''
    m = SkillsManager(skills_dir, tag="设计")
    block = m.build_prompt_block(tag=["世界", "设计"], match_mode="all")
    assert "<name>rpg-backgroundgenerater</name>" in block
    assert "<name>rpg-monster-skill</name>" not in block


def test_build_prompt_block_empty(skills_dir):
    '''无匹配技能时返回空块提示，而不是抛异常'''
    m = SkillsManager(skills_dir, tag="设计")
    assert "无可用技能" in m.build_prompt_block(tag="不存在的标签")


def test_build_prompt_block_escapes_xml(tmp_path):
    '''描述里的 & < > 必须转义，否则会污染 XML 结构'''
    write_skill(tmp_path, "escape-skill", "A & B <C> 时使用", ["设计"])
    m = SkillsManager(tmp_path, tag="设计")
    block = m.build_prompt_block()
    assert "A &amp; B &lt;C&gt;" in block
    assert "<C>" not in block


def test_build_system_prompt(skills_dir):
    '''system prompt = 基础人设 + 索引块 + 使用协议'''
    m = SkillsManager(skills_dir, tag="设计")
    prompt = m.build_system_prompt("你是 RPG 主持人")
    assert prompt.startswith("你是 RPG 主持人")
    assert "<available_skills>" in prompt
    assert prompt.endswith("</skill_usage>")


# ==================== 模型输出解析 ====================
def test_parse_skill_call():
    '''从回复中半角冒号行提取技能名'''
    assert SkillsManager.parse_skill_call("USE_SKILL: rpg-monster-skill") == "rpg-monster-skill"
    assert SkillsManager.parse_skill_call("开场白\nUSE_SKILL: rpg-monster-skill\n") == "rpg-monster-skill"
    assert SkillsManager.parse_skill_call("不需要技能") is None


def test_parse_skill_call_fullwidth_colon_unsupported():
    '''现状：全角冒号匹配不到（已知待改进点，改正则时同步放开）'''
    assert SkillsManager.parse_skill_call("USE_SKILL：rpg-monster-skill") is None


# ==================== loader ====================
def test_load_skill(skills_dir):
    '''加载正文：success=True 且带 instructions'''
    m = SkillsManager(skills_dir, tag="设计")
    r = load_skill(m.skills, "rpg-monster-skill")
    assert r["success"] is True
    assert r["name"] == "rpg-monster-skill"
    assert "正文内容" in r["instructions"]


def test_load_skill_missing(skills_dir):
    '''技能不存在时返回失败，不抛异常'''
    m = SkillsManager(skills_dir, tag="设计")
    r = load_skill(m.skills, "not-exist")
    assert r["success"] is False
    assert "Skill 不存在" in r["error"]


def test_load_reference_outside(skills_dir):
    '''越界路径被拒绝，防止读到 references/ 之外'''
    m = SkillsManager(skills_dir, tag="设计")
    r = load_reference(m.skills, "rpg-monster-skill", "../SKILL.md")
    assert r["success"] is False
    assert r["error"] == "路径越界"

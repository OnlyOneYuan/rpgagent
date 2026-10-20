"""SkillRegistry 测试：多来源注册 / 按 tag 分组 / MCP / Qwen 工具导出。

运行：  d:/code/RPG 目录下执行  python -m pytest test/test_skill_registry.py -v
"""
import asyncio
import sys
from pathlib import Path

import pytest

from agent.skill.model import Skill, SkillKind, SkillSource
from agent.skill.registry import SkillRegistry
from agent.skill import qwen

FAKE_MCP_SERVER = '''
import json, sys

TOOLS = [{
    "name": "read_file",
    "description": "读取指定文件",
    "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
}]

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\\n")
    sys.stdout.flush()

while True:
    line = sys.stdin.readline()
    if not line:
        break
    req = json.loads(line)
    method, rid = req.get("method"), req.get("id")
    if rid is None:            # notification，不回包
        continue
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05",
             "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1.0"}}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        args = req.get("params", {}).get("arguments", {})
        send({"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": "内容:" + str(args.get("path"))}], "isError": False}})
    else:
        send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "unknown method"}})
'''


def write_skill(root: Path, name: str, description: str, tags=None, body="正文内容") -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"name: {name}", f"description: {description}"]
    if tags:
        lines.append("tags:")
        lines.extend(f"- {t}" for t in tags)
    lines.append("---")
    (d / "SKILL.md").write_text("\n".join(lines) + "\n\n" + body + "\n", encoding="utf-8")
    return d / "SKILL.md"


@pytest.fixture
def local_dir(tmp_path):
    write_skill(tmp_path, "rpg-monster-skill", "生成怪物技能", ["设计"])
    write_skill(tmp_path, "rpg-backgroundgenerater", "生成世界背景", ["世界", "设计"])
    write_skill(tmp_path, "no-tag-skill", "没有标签的技能")
    return tmp_path


# ==================== 注册 ====================
def test_register_directory_keeps_all_without_tag(local_dir):
    """不传 tag 时全部注册（Registry 语义），未分组技能也保留"""
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    assert set(r.names()) == {"rpg-monster-skill", "rpg-backgroundgenerater", "no-tag-skill"}


def test_register_directory_filters_by_tag(local_dir):
    """传 tag 时按标签过滤，ANY 命中任一即可"""
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory(tag="世界")
    assert set(r.names()) == {"rpg-backgroundgenerater"}
    assert r.get("rpg-backgroundgenerater").source is SkillSource.LOCAL


def test_register_callable_and_call(local_dir):
    """Python 函数注册成工具型技能后可被 dispatch 调用"""
    def roll(sides: int = 6, times: int = 1):
        """掷骰子"""
        return {"sides": sides, "times": times}

    def heal(target: str, amount: int):
        """治疗目标"""
        return f"{target}+{amount}"

    r = SkillRegistry(skills_directory=local_dir)
    s = r.register_callable(roll, tags=["战斗"])
    assert s.kind is SkillKind.TOOL
    assert s.input_schema["properties"]["sides"] == {"type": "integer"}
    # 有默认值的参数不进 required，没有默认值的才进
    assert r.register_callable(heal).input_schema["required"] == ["target", "amount"]

    out = asyncio.run(r.dispatch("roll", {"sides": 20, "times": 2}))
    assert out == {"success": True, "name": "roll", "result": {"sides": 20, "times": 2}}


def test_register_duplicate_name(local_dir):
    """同名默认覆盖，overwrite=False 时报错"""
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    dup = Skill(name="rpg-monster-skill", description="重复项")
    r.register(dup)
    assert r.get("rpg-monster-skill").description == "重复项"
    with pytest.raises(ValueError, match="已注册"):
        r.register(dup, overwrite=False)


def test_load_and_reference(local_dir):
    """正文懒加载 + references 越界防护"""
    d = local_dir / "rpg-monster-skill"
    (d / "references").mkdir()
    (d / "references" / "detail.md").write_text("细则", encoding="utf-8")

    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    r.get("rpg-monster-skill").body = None      # 强制重新加载
    assert "正文内容" in r.load("rpg-monster-skill")["instructions"]
    assert r.load_reference("rpg-monster-skill", "detail.md")["content"] == "细则"
    assert r.load_reference("rpg-monster-skill", "../SKILL.md")["error"] == "路径越界"
    assert r.load("not-exist")["success"] is False


# ==================== tag 分组 ====================
def test_group_by_tag(local_dir):
    """多标签技能会出现在多个分组里，无标签的进"未分组" """
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    groups = r.group_by_tag()
    assert {k: sorted(s.name for s in v) for k, v in groups.items()} == {
        "设计": ["rpg-backgroundgenerater", "rpg-monster-skill"],
        "世界": ["rpg-backgroundgenerater"],
        "未分组": ["no-tag-skill"],
    }


def test_group_by_tag_with_filter_and_mode(local_dir):
    """分组时可叠加 tag 过滤与 ALL 模式"""
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    groups = r.group_by_tag(tag=["世界", "设计"], match_mode="all")
    assert set(groups) == {"世界", "设计"}
    assert [s.name for s in groups["设计"]] == ["rpg-backgroundgenerater"]


def test_tag_index(local_dir):
    """tag_index 输出 tag -> 技能名，便于对外暴露 JSON"""
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    assert r.tag_index()["世界"] == ["rpg-backgroundgenerater"]


def test_build_prompt_block_grouped(local_dir):
    """grouped=True 时渲染 <group tag=...>"""
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    block = r.build_prompt_block(grouped=True)
    assert '<group tag="世界">' in block
    assert "<name>rpg-backgroundgenerater</name>" in block


def test_build_system_prompt_qwen_style(local_dir):
    """qwen 风格附带 source/kind 元信息，并使用 Qwen 版使用协议"""
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    prompt = r.build_system_prompt("你是 DM", style="qwen")
    assert prompt.startswith("你是 DM")
    assert "<source>local</source>" in prompt
    assert prompt.endswith("</skill_usage>")


# ==================== Qwen ====================
def test_register_qwen(tmp_path):
    """Qwen 目录（含 name/目录不一致的宽松解析）能被发现并打上 qwen 标签"""
    base = tmp_path / ".qwen" / "skills"
    write_skill(base, "qwen-story", "讲一个故事", ["叙事"])
    loose = base / "loose-one"
    loose.mkdir(parents=True)
    (loose / "SKILL.md").write_text("---\nname: renamed\n---\n\n# 兜底标题\n\n正文\n", encoding="utf-8")

    r = SkillRegistry()
    found = r.register_qwen(base)
    assert {s.name for s in found} == {"qwen-story", "renamed"}
    assert all(s.source is SkillSource.QWEN for s in found)
    assert all("qwen" in s.tags for s in found)
    assert r.get("renamed").description == "兜底标题"
    assert qwen.QWEN_USER_DIR == "~/.qwen/skills"


def test_to_tools_for_qwen(local_dir):
    """导出的工具定义符合 OpenAI/Qwen function calling 结构"""
    def roll(sides: int = 6):
        """掷骰子"""
        return sides

    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    r.register_callable(roll)
    tools = r.to_tools()
    names = [t["function"]["name"] for t in tools]
    assert "roll" in names and "use_skill" in names
    assert tools[0]["type"] == "function"
    assert set(tools[0]["function"]) == {"name", "description", "parameters"}


def test_parse_tool_calls():
    """从 Qwen 返回体里取出 (工具名, 参数)"""
    msg = {"tool_calls": [{"function": {"name": "use_skill", "arguments": '{"name": "rpg-monster-skill"}'}}]}
    assert qwen.parse_tool_calls(msg) == [("use_skill", {"name": "rpg-monster-skill"})]
    assert qwen.parse_tool_calls({"tool_calls": []}) == []


def test_dispatch_use_skill_meta_tool(local_dir):
    """use_skill 元工具被路由到正文加载"""
    r = SkillRegistry(skills_directory=local_dir)
    r.register_directory()
    out = asyncio.run(r.dispatch("use_skill", {"name": "rpg-monster-skill"}))
    assert out["success"] is True and "正文内容" in out["instructions"]


# ==================== MCP ====================
def test_register_mcp_and_call(tmp_path):
    """MCP server 的工具被注册成可调用技能，并能通过 tools/call 执行"""
    script = tmp_path / "fake_mcp_server.py"
    script.write_text(FAKE_MCP_SERVER, encoding="utf-8")

    async def main():
        r = SkillRegistry()
        skills = await r.register_mcp({"name": "fake", "command": sys.executable, "args": [str(script)]})
        try:
            assert [s.name for s in skills] == ["mcp-fake-read-file"]
            s = r.get("mcp-fake-read-file")
            assert s.source is SkillSource.MCP and s.kind is SkillKind.TOOL
            assert set(s.tags) >= {"fake", "mcp"}
            assert s.tool == "read_file" and s.server == "fake"

            out = await r.dispatch("mcp-fake-read-file", {"path": "a.txt"})
            assert out == {"success": True, "name": "mcp-fake-read-file", "result": "内容:a.txt"}

            assert "mcp-fake-read-file" in r.build_prompt_block()
            tools = r.to_tools()
            assert any(t["function"]["name"] == "mcp-fake-read-file" for t in tools)
            assert r.group_by_tag()["mcp"][0].name == "mcp-fake-read-file"
            return True
        finally:
            await r.aclose()

    assert asyncio.run(main())


def test_register_mcp_bad_config():
    """缺少 command 的配置直接报错，不会静默注册"""
    r = SkillRegistry()
    with pytest.raises(ValueError, match="command"):
        asyncio.run(r.register_mcp({"name": "broken", "transport": "stdio"}))

"""执行 rpg-backgroundgenerater 技能：生成 RPG 世界观（国家画像）并存档到 storys/。

流程：加载技能正文 -> 拼装 system prompt -> 调 LLM -> 解析 JSON -> 存档。

用法（任意目录均可运行）：
    python agent/skills/rpg-backgroundgenerater/scripts/generate_world.py
    python agent/skills/rpg-backgroundgenerater/scripts/generate_world.py `
        --topic "被远古裂隙分割的破碎大陆，魔法与蒸汽并存" --count 8 --title 破碎大陆
    python agent/skills/rpg-backgroundgenerater/scripts/generate_world.py --dry-run  # 只检查链路，不调模型

前置：
    pip install openai python-dotenv pyyaml
    项目根目录建 .env：API_KEY=xxx / API_BASE=http://host:port/v1 / MODEL_NAME=xxx
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # .../RPG
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.skill.manager import SkillsManager, MatchMode
from agent.skill.loader import load_skill
from agent.skill.parser import parse_skill

SKILL_NAME = "rpg-backgroundgenerater"
SKILL_DIR = Path(__file__).resolve().parents[1]
SKILLS_DIR = SKILL_DIR.parent
STORYS_DIR = SKILL_DIR / "storys"
DEFAULT_TOPIC = "被远古裂隙分割的破碎大陆，魔法与蒸汽并存"
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def load_instructions() -> str:
    """加载技能正文。优先走 SkillsManager，扫不到时回退到直接解析文件。

    disk 上的文件名是小写 skill.md，而 discover 只 glob "*/SKILL.md"，
    在非 Windows 上会扫不到，所以保留回退分支。
    """
    mgr = SkillsManager(SKILLS_DIR, tag=["世界", "设计"], match_mode=MatchMode.ANY)
    if SKILL_NAME in mgr.skills:
        result = load_skill(mgr.skills, SKILL_NAME)
        if result["success"]:
            return result["instructions"]
        print(f"[warn] load_skill 失败：{result.get('error')}")

    for filename in ("SKILL.md", "skill.md"):
        f = SKILL_DIR / filename
        if f.is_file():
            return parse_skill(f).body

    raise SystemExit(f"未找到技能 {SKILL_NAME}，检查目录：{SKILL_DIR}")


def build_messages(instructions: str, topic: str, count: int) -> list[dict]:
    system = (
        "你是 RPG 冒险世界的主持人（DM）与世界观设计师。下面是本领域的技能指令，必须严格遵守。\n\n"
        f"{instructions}\n\n"
        "## 本次任务\n"
        f"- 主题：{topic}\n"
        f"- 设计 {count} 个国家，彼此在地理、资源、政治与文化上形成明显差异与冲突点。\n"
        "- 所有字段用中文填写，内容具体（包含专有名词、数据感描述），禁止占位符与空字符串。\n"
        "- 只输出一个 JSON 对象，结构严格遵循指令中的输出模板；可用 ```json 代码块包裹，不要附加解释。"
    )
    user = f"请按主题「{topic}」生成 {count} 个国家的世界观设定，输出 JSON。"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def call_llm(messages: list[dict], model: str | None,
             temperature: float, max_tokens: int) -> str:
    from agent.config.setting import Authorize
    from agent.http.api import OpenaiApi

    model = model or os.getenv("MODEL_NAME")
    if not model:
        raise SystemExit("未配置模型名：在项目根 .env 中设置 MODEL_NAME=...，或用 --model 指定")

    base_url = os.getenv("API_BASE") or str(Authorize.URL)
    if base_url and not base_url.startswith(("http://", "https://")):
        base_url = "http://" + base_url  # setting.py 默认值缺 scheme

    api = OpenaiApi(
        api_key=os.getenv("API_KEY") or Authorize.KEY,
        base_url=base_url,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    resp = api.chat()
    return resp.message.content or ""


def extract_json(text: str) -> tuple[dict | None, str]:
    """从模型输出里剥出 JSON，失败时返回 (None, 原始文本)。"""
    m = JSON_BLOCK_RE.search(text)
    raw = (m.group(1) if m else text).strip()
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return None, text
        raw = raw[start:end + 1]
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as e:
        print(f"[warn] JSON 解析失败：{e}")
        return None, raw


def countries_of(data: dict | None) -> list[dict]:
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("countries"), list):
        return data["countries"]
    output = data.get("output")
    if isinstance(output, dict) and isinstance(output.get("countries"), list):
        return output["countries"]
    return []


def brief(country: dict) -> str:
    for group, field in (("national_conditions", "cultural_tradition"),
                         ("natural_geography", "terrain"),
                         ("location_and_territory", "relative_location")):
        text = (country.get(group) or {}).get(field)
        if text:
            return str(text)[:40].replace("\n", " ")
    return ""


def save(title: str, topic: str, data: dict | None, raw: str) -> list[Path]:
    STORYS_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if data is None:
        raw_path = STORYS_DIR / f"{title}.raw.txt"
        raw_path.write_text(raw, encoding="utf-8")
        print(f"[warn] 未解析出合法 JSON，原始输出已保存：{raw_path}")
        return [raw_path]

    json_path = STORYS_DIR / f"{title}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(json_path)

    rows = "\n".join(
        f"| {c.get('name', '?')} | {c.get('region', '')} | "
        f"{(c.get('location_and_territory') or {}).get('capital', '')} | {brief(c)} |"
        for c in countries_of(data)
    )
    md_path = STORYS_DIR / f"{title}.md"
    md_path.write_text(
        f"# {title}\n\n"
        f"- 主题：{topic}\n"
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M}\n"
        f"- 技能：{SKILL_NAME}\n"
        f"- 结构化数据：`{json_path.name}`\n\n"
        f"## 世界观摘要\n\n| 国家 | 区域 | 首都 | 简介 |\n| --- | --- | --- | --- |\n{rows}\n\n"
        f"## 关键场景\n\n（待 DM 补充）\n\n"
        f"## 主要 NPC\n\n（待补充）\n\n"
        f"## 已发生事件\n\n（待补充）\n\n"
        f"## 悬念清单\n\n- \n",
        encoding="utf-8",
    )
    written.append(md_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="执行 rpg-backgroundgenerater 技能生成世界观")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="世界观主题/需求")
    parser.add_argument("--count", type=int, default=7, help="国家数量，指令建议 7-9 个")
    parser.add_argument("--title", default=None, help="存档文件名，默认取主题前 12 字")
    parser.add_argument("--model", default=None, help="覆盖 .env 的 MODEL_NAME")
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--dry-run", action="store_true", help="只加载技能并打印提示词，不调用模型")
    parser.add_argument("--print", dest="show", action="store_true", help="打印模型原始输出")
    args = parser.parse_args()

    instructions = load_instructions()
    messages = build_messages(instructions, args.topic, args.count)
    print(f"[ok] 已加载技能 {SKILL_NAME}（正文 {len(instructions)} 字），system prompt {len(messages[0]['content'])} 字")

    if args.dry_run:
        print("\n----- system -----\n" + messages[0]["content"][:1200] + "\n...\n----- user -----\n" + messages[1]["content"])
        return

    text = call_llm(messages, args.model, args.temperature, args.max_tokens)
    if args.show:
        print(text)

    data, raw = extract_json(text)
    title = args.title or re.sub(r'[\\/:*?"<>|]', "", args.topic)[:12] or "世界观"
    for path in save(title, args.topic, data, raw):
        print(f"[ok] 已保存：{path}")


if __name__ == "__main__":
    main()

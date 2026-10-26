"""Function Calling 冒烟脚本：Qwen + SkillRegistry 跑一轮工具调用。

运行：  python test/test.py
强制调用某个工具（验证服务端是否真的支持 tools）：
        $env:FORCE_TOOL="use_skill"; python test/test.py

两条通道：
1. function calling：to_tools() 导出 use_skill / read_skill_file 元工具
2. 文本协议兜底：system prompt 里的 <available_skills> + 模型输出 USE_SKILL: <name>
   （服务端不支持 tools 时用这条，Qwen Code 本身也是这个渐进加载思路）
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.config.setting import Authorize
from agent.http.api import QwenApi
from agent.skill import SkillRegistry
from agent.skill.manager import SkillsManager

FORCE_TOOL = os.getenv("FORCE_TOOL", "").strip()   # 调试用：强制模型调用某个工具


def _base_url() -> str:
    """Authorize.URL 默认没有 scheme，openai SDK 要求带 http:// 前缀。"""
    url = str(Authorize.URL)
    return url if "://" in url else "http://" + url


def _as_message(message) -> dict:
    """SDK 返回的 message 对象转成可以回传给下一轮的 dict。"""
    if isinstance(message, dict):
        return message
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", "") or "",
    }


async def call_model(api, messages, tools):
    """发一次请求，并把诊断信息打出来。"""
    tool_choice = {"type": "function", "function": {"name": FORCE_TOOL}} if FORCE_TOOL else "auto"
    payload = api.build_payload(messages=messages, tools=tools, tool_choice=tool_choice, stream=False)
    print(f"[debug] 请求已带 tools: {[t['function']['name'] for t in payload.get('tools', [])]}"
          f"  tool_choice={payload.get('tool_choice')}")

    resp = await api.achat(messages=messages, tools=tools, tool_choice=tool_choice)
    print(f"[debug] finish_reason={resp.finish_reason} tool_calls={resp.tool_calls}")
    return resp


async def main(max_rounds: int = 1) -> str:
    registry = SkillRegistry()
    # registry.register_directory()                 # 本地 agent/skills/*/SKILL.md
    registry.register_qwen(overwrite=False)       # .qwen/skills：不覆盖已注册的同名本地技能

    print(registry.describe())

    # 文本协议也需要索引块，所以 system prompt 里注入 <available_skills>
    system = registry.build_system_prompt("你是 RPG 主持人，需要专业技能时先加载再回答。")
    api = QwenApi(
        model=str(Authorize.MODEL or "qwen-plus"),
        base_url=_base_url(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "设计一个怪物技能"},
        ],
    )
    tools = registry.to_tools()
    print("导出工具：" + "、".join(t["function"]["name"] for t in tools))

    text = ""
    try:
        for _ in range(max_rounds):
            messages = api.SUPPORTED_ARGS["messages"]
            resp = await call_model(api, messages, tools)
            text = resp.content

            # ---------- 通道 1：function calling ----------
            if resp.has_tool_calls():
                messages.append(_as_message(resp.message))
                for call in resp.tool_calls:
                    name = call["function"]["name"]
                    args = json.loads(call["function"]["arguments"] or "{}")
                    print(f"[tool] {name} <- {args}")
                    out = await registry.dispatch(name, args)
                    print(f"[tool] {name} -> {str(out)[:200]}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(out, ensure_ascii=False),
                    })
                continue

            # ---------- 通道 2：USE_SKILL 文本协议 ----------
            name = SkillsManager.parse_skill_call(resp.content)
            if name:
                print(f"[fallback] 解析到 USE_SKILL: {name}")
                out = registry.load(name)
                if out["success"]:
                    messages.append({"role": "assistant", "content": resp.content})
                    messages.append({"role": "user",
                                     "content": f"已加载技能 {name} 的正文，严格按它执行：\n{out['instructions']}"})
                    continue
                print(f"[fallback] 加载失败：{out['error']}")

            if not resp.content:
                print("[warn] content 与 tool_calls 都为空 —— 服务端可能没有把 tools 透传给模型")
            break
    finally:
        await registry.aclose()

    return text


if __name__ == "__main__":
    print(asyncio.run(main()))

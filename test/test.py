"""Function Calling 冒烟脚本：Qwen + SkillRegistry 跑一轮工具调用。

运行：  python test/test.py
需要：  .env 里配置 API_KEY / API_BASE / MODEL_NAME

注意：await 只能写在 async 函数里，脚本顶层用 asyncio.run(main()) 启动。
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.config.setting import Authorize
from agent.http.api import QwenApi
from agent.skill import SkillRegistry


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


async def main(max_rounds: int = 4) -> str:
    registry = SkillRegistry()
    registry.register_directory()      # 本地 agent/skills/*/SKILL.md
    registry.register_qwen()           # .qwen/skills（不存在则跳过）
    print(registry.describe())

    api = QwenApi(
        model=str(Authorize.MODEL or "qwen-plus"),
        base_url=_base_url(),
        messages=[{"role": "user", "content": "设计一个怪物技能"}],
    )
    tools = registry.to_tools()
    print(f"导出 {len(tools)} 个工具：" + "、".join(t["function"]["name"] for t in tools))

    text = ""
    try:
        for _ in range(max_rounds):
            resp = await api.achat(tools=tools, tool_choice="auto")
            text = resp.content
            if not resp.has_tool_calls():
                break

            # 把 assistant 的工具调用消息 + 工具结果追加回上下文，再问一轮
            messages = api.SUPPORTED_ARGS["messages"]
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
    finally:
        await registry.aclose()

    return text


if __name__ == "__main__":
    print(asyncio.run(main()))

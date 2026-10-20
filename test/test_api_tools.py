"""agent.http.api 测试：tools/tool_choice 入参 + 流式 chunk（文本 / tool_calls 分片 / usage）。

运行：  d:/code/RPG 目录下执行  python -m pytest test/test_api_tools.py -v
说明：用假客户端替掉 OpenAI / AsyncOpenAI，不发真实请求。
"""
import asyncio
from types import SimpleNamespace

import pytest

from agent.http import api as api_mod
from agent.http.api import OpenaiApi, QwenApi, Responses, StreamEvent

TOOLS = [{
    "type": "function",
    "function": {"name": "use_skill", "description": "加载技能",
                 "parameters": {"type": "object", "properties": {"name": {"type": "string"}}}},
}]


# ==================== 假客户端 ====================
class _AsyncIterator:
    """把 chunk 列表包成异步迭代器，模拟 SDK 的 Stream。"""
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


class FakeAsyncCompletions:
    def __init__(self, completion=None, chunks=None):
        self.completion = completion
        self.chunks = chunks or []
        self.payload = None

    async def create(self, **kwargs):
        self.payload = kwargs
        # 真实 SDK：stream=True 返回可异步迭代的 Stream，否则返回 ChatCompletion
        return _AsyncIterator(self.chunks) if kwargs.get("stream") else self.completion


class FakeAsyncClient:
    def __init__(self, completion=None, chunks=None):
        self.chat = SimpleNamespace(completions=FakeAsyncCompletions(completion, chunks))
        self.closed = False

    async def close(self):
        self.closed = True


class FakeSyncCompletions:
    def __init__(self, completion):
        self.completion = completion
        self.payload = None

    def create(self, **kwargs):
        self.payload = kwargs
        return self.completion


class FakeSyncClient:
    def __init__(self, completion):
        self.chat = SimpleNamespace(completions=FakeSyncCompletions(completion))


def make_api(monkeypatch, chunks=None, completion=None, **kwargs):
    """构造 OpenaiApi，但把 SDK 客户端换成假的。"""
    async_client = FakeAsyncClient(completion=completion, chunks=chunks or [])
    sync_client = FakeSyncClient(completion)
    monkeypatch.setattr(api_mod, "OpenAI", lambda **kw: sync_client)
    monkeypatch.setattr(api_mod, "AsyncOpenAI", lambda **kw: async_client)
    api = OpenaiApi(api_key="test", base_url="http://localhost", **kwargs)
    return api, sync_client, async_client


# ==================== chunk 构造器 ====================
def text_chunk(text):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=text, tool_calls=None), finish_reason=None)], usage=None)


def tool_chunk(index=0, id=None, type_=None, name=None, arguments=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(
            content=None,
            tool_calls=[SimpleNamespace(
                index=index, id=id, type=type_,
                function=SimpleNamespace(name=name, arguments=arguments))],
        ), finish_reason=None)], usage=None)


def usage_chunk(usage=None):
    return SimpleNamespace(choices=[], usage=usage or {"total_tokens": 42})


def fake_completion(content="你好", tool_calls=None):
    message = SimpleNamespace(content=content, role="assistant",
                              tool_calls=tool_calls or [])
    return SimpleNamespace(
        id="chat-1", object="chat.completion", created=0, model="fake",
        system_fingerprint=None,
        choices=[SimpleNamespace(message=message, finish_reason="stop")],
    )


# ==================== 请求构造 ====================
def test_build_payload_with_tools(monkeypatch):
    """显式传 tools/tool_choice 时进入请求体"""
    api, _, _ = make_api(monkeypatch)
    payload = api.build_payload(tools=TOOLS, tool_choice="auto", stream=False)
    assert payload["tools"] == TOOLS
    assert payload["tool_choice"] == "auto"
    assert payload["stream"] is False


def test_build_payload_without_tools(monkeypatch):
    """没有工具时不带 tools/tool_choice 键，避免服务端报错"""
    api, _, _ = make_api(monkeypatch)
    payload = api.build_payload(stream=True)
    assert "tools" not in payload and "tool_choice" not in payload


def test_build_payload_uses_registered_tools(monkeypatch):
    """构造时注册的默认 tools 会被 build_payload 采纳"""
    api, _, _ = make_api(monkeypatch, tools=TOOLS, tool_choice="required")
    payload = api.build_payload(stream=False)
    assert payload["tools"] == TOOLS
    assert payload["tool_choice"] == "required"


def test_build_payload_kwargs_override(monkeypatch):
    """kwargs 覆盖 SUPPORTED_ARGS"""
    api, _, _ = make_api(monkeypatch)
    payload = api.build_payload(model="qwen-plus", temperature=0.2)
    assert payload["model"] == "qwen-plus" and payload["temperature"] == 0.2


def test_supported_args_not_shared(monkeypatch):
    """实例各持一份 SUPPORTED_ARGS，不再互相污染"""
    a, _, _ = make_api(monkeypatch)
    b, _, _ = make_api(monkeypatch)
    a.SUPPORTED_ARGS["model"] = "aaa"
    assert b.SUPPORTED_ARGS["model"] == ""
    assert OpenaiApi.SUPPORTED_ARGS["model"] == ""


# ==================== 非流式 ====================
def test_chat_passes_tools(monkeypatch):
    """同步 chat() 把 tools / tool_choice 传给 SDK"""
    api, sync, _ = make_api(monkeypatch, completion=fake_completion())
    resp = api.chat(tools=TOOLS, tool_choice="auto")
    assert sync.chat.completions.payload["tools"] == TOOLS
    assert sync.chat.completions.payload["tool_choice"] == "auto"
    assert sync.chat.completions.payload["stream"] is False
    assert isinstance(resp, Responses) and resp.content == "你好"


def test_achat_passes_tools(monkeypatch):
    """异步 achat() 同样支持 tools"""
    api, _, _ = make_api(monkeypatch, completion=fake_completion())
    resp = asyncio.run(api.achat(tools=TOOLS))
    assert resp.content == "你好"
    assert api._aclient.chat.completions.payload["tools"] == TOOLS


def test_responses_tool_calls(monkeypatch):
    """Responses 暴露 tool_calls，content 为 None 时返回空串而不是抛错"""
    call = SimpleNamespace(id="call_1", type="function",
                           function=SimpleNamespace(name="use_skill", arguments='{"name":"dm"}'))
    completion = fake_completion(content=None, tool_calls=[call])
    api, _, _ = make_api(monkeypatch, completion=completion)
    resp = api.chat(tools=TOOLS)

    assert resp.has_tool_calls() is True
    assert resp.tool_calls[0]["function"]["name"] == "use_skill"
    assert resp.content == ""
    assert resp.finish_reason == "stop"


def test_responses_without_tool_calls(monkeypatch):
    """没有工具调用时 tool_calls 为空列表"""
    api, _, _ = make_api(monkeypatch, completion=fake_completion())
    resp = api.chat()
    assert resp.tool_calls == [] and resp.has_tool_calls() is False


# ==================== 流式 ====================
def test_stream_yields_text_only(monkeypatch):
    """stream() 只吐文本增量"""
    chunks = [text_chunk("你"), text_chunk("好"), usage_chunk()]
    api, _, async_c = make_api(monkeypatch, chunks=chunks)

    async def main():
        return [p async for p in api.stream()]

    assert asyncio.run(main()) == ["你", "好"]


def test_astream_aggregates_tool_calls(monkeypatch):
    """工具调用的 name / arguments 分片被正确拼接，usage 单独成事件"""
    chunks = [
        text_chunk("先想想"),
        tool_chunk(index=0, id="call_1", type_="function", name="use_skill", arguments='{"na'),
        tool_chunk(index=0, arguments='me":"dm"}'),
        usage_chunk({"total_tokens": 7}),
    ]
    api, _, async_c = make_api(monkeypatch, chunks=chunks)

    async def main():
        events = [e async for e in api.astream(tools=TOOLS)]
        assert async_c.chat.completions.payload["tools"] == TOOLS
        assert async_c.chat.completions.payload["stream_options"] == {"include_usage": True}
        return events

    events = asyncio.run(main())
    assert [e.type for e in events] == ["text", "tool_call", "usage"]
    assert events[0].text == "先想想"
    assert events[1].tool_call == {
        "index": 0, "id": "call_1", "type": "function",
        "function": {"name": "use_skill", "arguments": '{"name":"dm"}'},
    }
    assert events[2].usage == {"total_tokens": 7}


def test_astream_multiple_tool_calls(monkeypatch):
    """同一轮里的多个工具调用按 index 归并"""
    chunks = [
        tool_chunk(index=0, id="c0", name="use_skill", arguments="{}"),
        tool_chunk(index=1, id="c1", name="read_skill_file", arguments='{"p":1}'),
    ]
    api, _, _ = make_api(monkeypatch, chunks=chunks)

    async def main():
        return [e async for e in api.astream(tools=TOOLS)]

    events = asyncio.run(main())
    assert [e.tool_call["function"]["name"] for e in events] == ["use_skill", "read_skill_file"]


def test_acomplete_result(monkeypatch):
    """acomplete() 一次拿到 文本 + 工具调用 + 用量"""
    chunks = [text_chunk("ok"), tool_chunk(index=0, id="c0", name="roll", arguments='{"a":1}'),
              usage_chunk({"total_tokens": 3})]
    api, _, _ = make_api(monkeypatch, chunks=chunks)

    result = asyncio.run(api.acomplete(tools=TOOLS))
    assert result.text == "ok"
    assert result.has_tool_calls is True
    assert result.tool_calls[0]["function"]["arguments"] == '{"a":1}'
    assert result.usage == {"total_tokens": 3}


def test_complete_returns_text(monkeypatch):
    """complete() 仍返回聚合文本"""
    api, _, _ = make_api(monkeypatch, chunks=[text_chunk("a"), text_chunk("b")])
    assert asyncio.run(api.complete()) == "ab"


def test_aclose(monkeypatch):
    """aclose() 关闭异步客户端"""
    api, _, async_c = make_api(monkeypatch)
    api._aclient = async_c
    asyncio.run(api.aclose())
    assert async_c.closed is True and api._aclient is None


# ==================== Qwen ====================
def test_qwen_api_accepts_tools_kwarg(monkeypatch):
    """QwenApi 走 OpenAI 兼容协议，tools 通过 kwargs 注册进 SUPPORTED_ARGS"""
    monkeypatch.setattr(api_mod, "OpenAI", lambda **kw: FakeSyncClient(fake_completion()))
    monkeypatch.setattr(api_mod, "AsyncOpenAI", lambda **kw: FakeAsyncClient())
    api = QwenApi(api_key="test", base_url="http://localhost", model="qwen-plus", tools=TOOLS)
    assert api.SUPPORTED_ARGS["model"] == "qwen-plus"
    assert api.build_payload(stream=False)["tools"] == TOOLS

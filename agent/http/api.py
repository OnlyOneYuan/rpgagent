from abc import abstractmethod, ABC
import asyncio
import json
from dataclasses import dataclass, field
from agent.memory.memory import Message
from typing import Any, Dict, List, Literal, Optional, AsyncIterator
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel
from agent.config.setting import Authorize

# tool_choice：可以是 "none" / "auto" / "required"，或 {"type":"function","function":{"name":...}}
ToolChoice = str | Dict[str, Any]
Tools = List[Dict[str, Any]]


class API(ABC):

    def __init__(self):
        pass

    @abstractmethod
    async def stream(self, **kwargs) -> AsyncIterator[Message]:
        """
            This method is used to stream the response from the API.
        """
        pass


def _to_plain(obj: Any) -> Any:
    """把 SDK 对象（pydantic / SimpleNamespace）尽量转成纯 dict，便于序列化。"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return obj


def _tool_call_to_dict(tc: Any) -> Dict[str, Any]:
    """把单条 tool_call（SDK 对象或 dict）统一成 OpenAI 结构。"""
    if isinstance(tc, dict):
        return tc
    fn = getattr(tc, "function", None)
    return {
        "id": getattr(tc, "id", None),
        "type": getattr(tc, "type", "function"),
        "function": {
            "name": getattr(fn, "name", None),
            "arguments": getattr(fn, "arguments", "") or "",
        },
    }


class StreamEvent(BaseModel):
    """流式事件：文本增量 / 一个完整的工具调用 / 用量统计。"""
    type: Literal["text", "tool_call", "usage"]
    text: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None


@dataclass
class StreamResult:
    """流式结果聚合：一次拿到文本、工具调用与用量。"""
    text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class Responses(BaseModel):
    """
    标准化的 OpenAI Chat Completion Response 抽象类
    """
    id: str
    object: Literal["chat.completion", "chat.completion.chunk"] = "chat.completion"
    created: int
    model: str
    choices: list
    # 系统级指纹或元数据
    system_fingerprint: Optional[str] = None

    # --- 业务层便捷方法 (Facade) ---

    @property
    def message(self) -> Message:
        """获取主回复消息 (通常是 choices[0].message)"""
        if not self.choices:
            raise ValueError("Response contains no choices.")
        choice = self.choices[0]
        # chunk 结构在 delta 上，completion 结构在 message 上
        return choice.message if hasattr(choice, "message") else choice.delta

    @property
    def content(self) -> str:
        """快捷获取纯文本回复（纯工具调用时 content 可能为 None）"""
        msg = self.message
        text = getattr(msg, "content", None) or getattr(msg, "text", None)
        return text or ""

    @property
    def finish_reason(self) -> Optional[str]:
        """获取结束原因 (stop, length, tool_calls 等)"""
        if not self.choices:
            return None
        return self.choices[0].finish_reason

    @property
    def tool_calls(self) -> List[Dict[str, Any]]:
        """工具调用列表（OpenAI / Qwen 结构），没有则为空列表"""
        return [_tool_call_to_dict(tc) for tc in (getattr(self.message, "tool_calls", None) or [])]

    def has_tool_calls(self) -> bool:
        """判断模型是否请求了工具调用"""
        return bool(self.tool_calls)

    def to_dict(self) -> Dict[str, Any]:
        """将对象转换为 OpenAI 兼容的字典格式"""
        return self.model_dump(exclude_none=True)


class OpenaiApi(API):

    SUPPORTED_ARGS = {
        "model": "",
        "messages": [],
        "stream": True,
        "temperature": 1.0,
        "max_tokens": 4096,
        "top_p": 1.0,
        "frequency_penalty": 1.0,
        "presence_penalty": 1.0
    }

    def __init__(self,
                 api_key=Authorize.KEY,
                 base_url=Authorize.URL,
                 max_concurrency=5,
                 **kwargs
                 ):
        self._api_key = api_key
        self._base_url = base_url
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self._aclient: Optional[AsyncOpenAI] = None

        # 类属性是默认值模板，实例各持一份副本，避免互相污染
        self.SUPPORTED_ARGS = dict(type(self).SUPPORTED_ARGS)
        if kwargs:
            self.SUPPORTED_ARGS.update(kwargs)
        self._sem = asyncio.Semaphore(max_concurrency)
        self.last_usage: Optional[Any] = None

    # ---------------- 请求构造 ----------------
    def build_payload(self, *, tools: Optional[Tools] = None,
                      tool_choice: Optional[ToolChoice] = None,
                      stream: Optional[bool] = None,
                      **kwargs) -> Dict[str, Any]:
        """组装请求参数：SUPPORTED_ARGS 为底，kwargs 覆盖，空值不上传。"""
        payload = dict(self.SUPPORTED_ARGS)
        payload.update(kwargs)

        if stream is not None:
            payload["stream"] = stream

        # 工具相关：没传就用实例上已配置的，最后统一丢掉空值
        tools = tools if tools is not None else payload.pop("tools", None)
        tool_choice = tool_choice if tool_choice is not None else payload.pop("tool_choice", None)
        if tools:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
        elif tool_choice is not None:
            payload["tool_choice"] = tool_choice

        return {k: v for k, v in payload.items() if v is not None}

    def _async_client(self) -> AsyncOpenAI:
        if self._aclient is None:
            self._aclient = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._aclient

    # ---------------- 非流式 ----------------
    def chat(self, tools: Optional[Tools] = None,
             tool_choice: Optional[ToolChoice] = None,
             **kwargs) -> Responses:
        """同步非流式调用，支持 function calling。"""
        payload = self.build_payload(tools=tools, tool_choice=tool_choice, stream=False, **kwargs)
        chat = self.client.chat.completions.create(**payload)
        return self._to_responses(chat)

    async def achat(self, tools: Optional[Tools] = None,
                    tool_choice: Optional[ToolChoice] = None,
                    **kwargs) -> Responses:
        """异步非流式调用，支持 function calling。"""
        payload = self.build_payload(tools=tools, tool_choice=tool_choice, stream=False, **kwargs)
        async with self._sem:
            chat = await self._async_client().chat.completions.create(**payload)
        return self._to_responses(chat)

    @staticmethod
    def _to_responses(chat: Any) -> Responses:
        return Responses(
            id=chat.id,
            object=chat.object,
            created=chat.created,
            model=chat.model,
            system_fingerprint=chat.system_fingerprint,
            choices=chat.choices
        )

    # ---------------- 流式 ----------------
    async def astream(self, tools: Optional[Tools] = None,
                      tool_choice: Optional[ToolChoice] = None,
                      **kwargs) -> AsyncIterator[StreamEvent]:
        """结构化流式：文本增量 / 工具调用（分片自动拼接）/ 用量。

        chunk 与 chat.completion 结构不同：文本在 `choices[0].delta.content`，
        工具调用在 `choices[0].delta.tool_calls`（name 与 arguments 都按分片到达）。
        """
        payload = self.build_payload(tools=tools, tool_choice=tool_choice, stream=True, **kwargs)
        payload.setdefault("stream_options", {"include_usage": True})

        async with self._sem:
            stream = await self._async_client().chat.completions.create(**payload)
            pending: Dict[int, Dict[str, Any]] = {}
            usage_event: Optional[StreamEvent] = None

            async for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage:
                    # usage 通常出现在收尾 chunk，留到工具调用归并完再发
                    self.last_usage = usage
                    usage_event = StreamEvent(type="usage", usage=_to_plain(usage))
                    continue

                if not getattr(chunk, "choices", None):
                    continue  # 只有 usage 的收尾 chunk
                delta = chunk.choices[0].delta

                if getattr(delta, "content", None):
                    yield StreamEvent(type="text", text=delta.content)

                for tc in getattr(delta, "tool_calls", None) or []:
                    idx = getattr(tc, "index", 0) or 0
                    cur = pending.setdefault(idx, {
                        "index": idx,
                        "id": None,
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    })
                    if getattr(tc, "id", None):
                        cur["id"] = tc.id
                    if getattr(tc, "type", None):
                        cur["type"] = tc.type
                    fn = getattr(tc, "function", None)
                    if fn is None:
                        continue
                    if getattr(fn, "name", None):
                        cur["function"]["name"] += fn.name
                    if getattr(fn, "arguments", None):
                        cur["function"]["arguments"] += fn.arguments

            for idx in sorted(pending):
                yield StreamEvent(type="tool_call", tool_call=pending[idx])
            if usage_event is not None:
                yield usage_event

    async def stream(self, prompt: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        """逐块产出增量文本（工具调用会走 astream，这里只吐文本）。"""
        async for event in self.astream(**kwargs):
            if event.type == "text":
                yield event.text

    async def complete(self, prompt: Optional[str] = None, **kwargs) -> str:
        """把流式结果聚合成完整字符串。"""
        parts = []
        async for piece in self.stream(prompt, **kwargs):
            parts.append(piece)
        return "".join(parts)

    async def acomplete(self, tools: Optional[Tools] = None,
                        tool_choice: Optional[ToolChoice] = None,
                        **kwargs) -> StreamResult:
        """流式跑完并聚合：文本 + 工具调用 + 用量。"""
        result = StreamResult()
        async for event in self.astream(tools=tools, tool_choice=tool_choice, **kwargs):
            if event.type == "text":
                result.text += event.text or ""
            elif event.type == "tool_call":
                result.tool_calls.append(event.tool_call)
            elif event.type == "usage":
                result.usage = event.usage
        return result

    async def batch(self, prompts) -> list:
        """并发处理多个 prompt，保持返回顺序。"""
        return await asyncio.gather(*(self.complete(p) for p in prompts))

    async def aclose(self) -> None:
        """关闭异步客户端（同步客户端不管）。"""
        if self._aclient is not None:
            await self._aclient.close()
            self._aclient = None


class QwenApi(OpenaiApi):
    """Qwen 走 OpenAI 兼容协议，function calling 与 OpenAI 结构一致。"""

    def __init__(self, api_key=Authorize.KEY, base_url=Authorize.URL,
                 max_concurrency=5, messages=None, model="", **kwargs):
        super().__init__(
            api_key,
            base_url,
            max_concurrency=max_concurrency,
            messages=messages if messages is not None else [],
            model=model,
            **kwargs
        )

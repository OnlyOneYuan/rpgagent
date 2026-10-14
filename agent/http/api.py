from abc import abstractmethod,ABC
import asyncio
import json
from agent.memory.memory import Message
from typing import List, Dict, Any, Literal, Optional, AsyncIterator
from openai import OpenAI
from pydantic import BaseModel, Field
from agent.config.setting import Authorize

class API(ABC):

    def __init__(self):
        pass

    @abstractmethod
    async def stream(self,**kwargs) -> AsyncIterator[Message]:
        """
            This method is used to stream the response from the API.
        """
        pass

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
        return self.choices[0].message

    @property
    def content(self) -> str:
        """快捷获取纯文本回复"""
        return self.message.text

    @property
    def finish_reason(self) -> Optional[str]:
        """获取结束原因 (stop, length, tool_calls 等)"""
        if not self.choices:
            return None
        return self.choices[0].finish_reason

    def has_tool_calls(self) -> bool:
        """判断模型是否请求了工具调用"""
        return bool(self.message.tool_calls)

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
                 api_key  = Authorize.KEY,
                 base_url = Authorize.URL,
                 max_concurrency=5,
                 **kwargs
                 ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        if kwargs:
            self.SUPPORTED_ARGS.update(kwargs)
        self._sem = asyncio.Semaphore(max_concurrency)

    async def stream(
        self,prompt,**kwargs
    ) -> AsyncIterator[str]:
        """逐块产出增量文本。"""
        async with self._sem:
            stream = self.client.chat.completions.create(
                **self.SUPPORTED_ARGS
            )
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    # 首尾 chunk 的 content 可能为 None，必须判空
                    if delta and delta.content:
                        yield delta.content
                elif chunk.usage:
                    # 用量信息可通过回调或单独属性获取，这里仅示例
                    self.last_usage = chunk.usage

    async def complete(self, prompt: str, **kwargs) -> str:
        """把流式结果聚合成完整字符串。"""
        parts = []
        async for piece in self.stream(prompt, **kwargs):
            parts.append(piece)
        return "".join(parts)

    async def batch(self, prompts) -> list:
        """并发处理多个 prompt，保持返回顺序。"""
        return await asyncio.gather(*(self.complete(p) for p in prompts))

    def chat(self):
        chat = self.client.chat.completions.create(
            model   = self.SUPPORTED_ARGS.get("model"),
            messages= self.SUPPORTED_ARGS.get("messages"),
            stream  = False,
            extra_body  = self.SUPPORTED_ARGS.get("extra_body", {})
        )

        return Responses(
            id=chat.id,
            object=chat.object,
            created=chat.created,
            model=chat.model,
            system_fingerprint=chat.system_fingerprint,
            choices=chat.choices
        )

class QwenApi(OpenaiApi):

    def __init__(self,api_key=Authorize.KEY ,base_url=Authorize.URL ,max_concurrency = 5,messages = [],model = ""):
        super().__init__(
                        api_key  ,
                        base_url ,
                        max_concurrency = max_concurrency,
                        messages = messages,
                        model    = model
                        )


from abc import abstractmethod,ABC
from agent.memory.memory import Message
from typing import List, Dict, Any, Literal, Optional, AsyncIterator
from openai import OpenAI
from pydantic import BaseModel, Field


class API(ABC):
    def __init__(self,base_key,base_url):
        self.base_key = base_key
        self.base_url = base_url

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
        "model": str,
        "messages": list,
        "stream": True,
        "temperature": float,
        "max_tokens": int,
        "top_p": float,
        "frequency_penalty": float,
        "presence_penalty": float
    }

    def __init__(self, base_key, base_url,**kwargs):
        self.client = OpenAI(
            api_key = base_key,
            base_url= base_url
            )
        if kwargs:
            self.SUPPORTED_ARGS.update(kwargs)
    
    def stream(self):
        kwargs = self.SUPPORTED_ARGS
        # 准备消息格式
        stream = self.client.chat.completions.create(
            model   = kwargs.get("model"),
            messages= kwargs.get("messages"),
            stream  = True,
            extra_body  = kwargs.get("extra_body", {})
        )

        return Responses(
            id=stream["id"],
            object=stream["object"],
            created=stream["created"],
            model=stream["model"],
            system_fingerprint=stream.get("system_fingerprint"),
        )
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

    def __init__(self, base_key, base_url, **kwargs):
        super().__init__(base_key, base_url, **kwargs)

    def stream(self):
        stream = super().stream().message.content
        return stream
    
    def chat(self):
        chat = super().chat().message.content
        return chat
        

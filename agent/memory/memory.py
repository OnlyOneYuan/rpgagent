
from typing import Iterable, List, Union
from enum import Enum, auto

class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Message:
    """
        This class is used to store the messages that are sent between the agent and the environment.
    """
    def __init__(self, role:str, content:str,**kwargs) -> None:
        if role not in [i.value for i in Role]:
            raise ValueError(f"Invalid role: {role}")
        self.role = role
        self.content = content
        
    def __str__(self):
        return f"{{{self.role}:{self.content}}}"
    
class Memory:
    """
        This class is used to store the messages that are sent between the agent and the environment.
    """
    def __init__(self):
        self.content = []

    def _message(self, message: Union[Message, dict]) -> Message:
        """将输入转换为Message对象"""
        if isinstance(message, Message):
            return {message.role: message.content}
        elif isinstance(message, dict):
            return message
        else:
            raise TypeError(f"Expected Message or dict, got {type(message)}")


    def add(self, messages: Union[Message, dict, List[Union[Message, dict]]]) -> None:
        """
        添加消息到存储中，支持多种输入类型
        :param messages: 可以是单个Message对象、字典或它们的列表
        """
        if isinstance(messages, (Message, dict)):
            # 处理单个消息
            self.content.append(self._message(messages))
        elif isinstance(messages, Iterable):
            # 处理可迭代对象（列表、元组等）
            self.content.extend(
                [self._message(message) for message in messages]
            )
        else:
            raise TypeError(f"Expected Message, dict, or iterable, got {type(messages)}")
    
    def __str__(self):
        return self.content.__str__()
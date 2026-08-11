from functools import total_ordering
import json
from enum import Enum,auto
from abc import ABC, abstractmethod
from typing import Dict, Any
from agent.config.path import Path
import os

class LabelType(Enum):
    """标签类型枚举"""
    PERSONALITY = auto()
    SKILL       = auto()
    TALENT      = auto()
    EVENT       = auto()

@total_ordering
class Label(ABC):
    """"标签类"""

    _cache = {} # 缓存已创建的标签实例,用于快速查找标签
    _registry = {} # 标签类的注册表
    _max_size = 128 # 缓存最大数量

    def __init__(self,**kwargs):
        self._name = kwargs.get('name')
        # self._level = kwargs.get('level')

    def __str__(self):
        return f'{self.name}'

    def __repr__(self):
        return f'{self.name}'

    def __eq__(self, other:Label):
        if isinstance(other, Label):
            return self.name == other.name
        return False
    
    def __lt__(self, other:Label):
        if isinstance(other, Label):
            return self.name < other.name
        elif isinstance(other, str):
            return self.name < other
        return NotImplemented
    
    @property
    def name(self):
        return self._name

    # @property
    # def level(self):
    #     return self._level

    @property
    @abstractmethod
    def type(self):
        """返回标签类型"""
        pass

    @classmethod
    def labels(cls)-> Dict[str, Any]:
        """加载标签"""
        with open(Path.LABELS.value, 'r', encoding='utf-8') as f:
            labels = json.load(f)
            return labels[cls.type]

    @classmethod
    def register(cls, label_type: LabelType):
        """注册标签类的装饰器"""
        def decorator(subclass):
            cls._registry[label_type] = subclass
            return subclass
        return decorator

    @classmethod
    def get(cls,name,type:LabelType):
        """根据标签读取存放在文件中对应的描述"""
        with open(Path.LABELS.value, 'r', encoding='utf-8') as f:
            label_info = json.load(f)
            return label_info[type][name]
        
class LabelFactory:
    """标签工厂类"""
    @classmethod
    def create_label(cls, label_type: LabelType, **kwargs):
        """创建标签的工厂方法"""
        if label_type not in Label._registry:
            raise ValueError(f"Unsupported label type: {label_type}")
        
        # 检查缓存
        cache_key = (label_type, kwargs.get('name'))
        if cache_key in Label._cache:
            return Label._cache[cache_key]
        
        # 创建新标签
        label_class = Label._registry[label_type]
        label = label_class(**kwargs)
        
        # 更新缓存
        if len(Label._cache) >= Label._max_size:
            Label._cache.clear()
        Label._cache[cache_key] = label
     
        return label    

@Label.register(LabelType.PERSONALITY)
class PersonalityLabel(Label):
    """个性标签类"""
    _personality = []
    def __init__(self, *args, **kwargs):
        """
        初始化方法，支持两种输入方式：
        1. 字典形式：直接传入包含"name"键的字典
        2. 关键字参数形式：传入name关键字参数
        """
        # 处理字典输入
        if len(args) == 1 and isinstance(args[0], dict):
            data = args[0]  # 获取输入的字典数据
            name = data.get("name")  # 从字典中获取name值
        else:
            # 处理关键字参数输入
            name = kwargs.get("name")  # 从关键字参数中获取name值
        
        # 调用父类初始化，传入name参数
        super().__init__(name=name)
        
        # 设置标签类型为PERSONALITY
        self._type = LabelType.PERSONALITY
        
        # 设置个性属性
        if name not in self._personality:
            self._personality.append(name)

    @property
    def type(self):
        return self._type
    
@Label.register(LabelType.SKILL)
class SkillLabel(Label):
    """技能标签类"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._type = LabelType.SKILL

    @property
    def type(self):
        return self._type
    
@Label.register(LabelType.TALENT)
class TalentLabel(Label):
    """天赋标签类"""
    _talent = []
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._type = LabelType.TALENT
        self._talent.append(kwargs.get('name'))

    @property
    def type(self):
        return self._type

class LabelSet(ABC):
    """"标签集合类"""
    def __init__(self, **kwargs):
        self.labels = kwargs

    def __str__(self):

        # 该方法是Python的特殊方法，用于定义对象的字符串表示形式
        # 当使用print()函数或str()函数转换对象时会自动调用此方法
        return f'{self.labels}'  # 使用f-string格式返回对象的labels属性值

    def __repr__(self):
        return f'{self.labels}'

class LabelMap(ABC):
    """标签映射抽象基类，定义映射的通用行为"""
    
    def __init__(self, map: Dict[str, Any] = None):
        # 使用 _map 作为内部存储，避免与外部属性冲突
        self._map: Dict[str, Any] = map or {}

    # ================= 抽象方法 =================
    @abstractmethod
    def load(self, source: str):
        """抽象方法：子类必须实现具体的数据加载逻辑"""
        pass

    # ================= 字典代理行为 =================
    def __getitem__(self, key: str):
        return self._map[key]

    def __setitem__(self, key: str, value: Any):
        self._map[key] = value

    def __contains__(self, key: str):
        return key in self._map

    def __len__(self):
        return len(self._map)

    def add(self, key: str, value: Any):
        self._map[key] = value

    def get(self, key: str, default=None):
        return self._map.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return self._map
    
    def __str__(self):
        return str(self._map)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._map})"

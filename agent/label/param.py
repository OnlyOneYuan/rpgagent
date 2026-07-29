from agent.label.base import Label
from typing import Optional, Dict, Any


class Param(Label):
    """
    Param label
    """
    def __init__(self, name: str, value: int,level: int = 0):
        super().__init__(name, level)
        self.value = value
        self.diffcult = 1.00
    
    def __eq__(self, other):
        if isinstance(other, Param):
            return self.name == other.name and self.value == other.value

    def __lt__(self, other):
        if isinstance(other, Param):
            return self.value < other.value
        pass

    def setdiffcutlt(self, diffcult: float):
        self.diffcult = diffcult
        
    def __str__(self):
        return f"{self.name}[{self.level}]:{self.value}"
    
    def _levelUp(self):
        if self.value > self.diffcult*10^(self.level) :
            self.level += 1
            self.value = self.value - self.diffcult*10^(self.level)
            return True
        return False
    
    def juel_addless(self, value: int):
        self.value += value

from typing import Optional, Dict, Any
from agent.label.base import Label

class ParamFactory:
    """
    Param工厂类，用于创建和配置Param实例
    """
    
    @staticmethod
    def create_param(name: str, value: int, level: int = 0, diffcult: float = 1.00) -> 'Param':
        """
        创建一个新的Param实例
        
        参数:
            name: 参数名称
            value: 参数值
            level: 参数等级，默认为0
            diffcult: 参数难度系数，默认为1.00
            
        返回:
            Param: 配置好的Param实例
        """
        param = Param(name, value, level)
        param.setdiffcutlt(diffcult)
        return param
    
    @staticmethod
    def create_from_dict(data: Dict[str, Any]) -> 'Param':
        """
        从字典数据创建Param实例
        
        参数:
            data: 包含Param配置的字典，应包含name, value等必要字段
            
        返回:
            Param: 配置好的Param实例
        """
        name = data.get('name')
        value = data.get('value')
        level = data.get('level', 0)
        diffcult = data.get('diffcult', 1.00)
        
        if name is None or value is None:
            raise ValueError("字典中必须包含name和value字段")
            
        return ParamFactory.create_param(name, value, level, diffcult)
    
    @staticmethod
    def create_default_param(name: str, value: int) -> 'Param':
        """
        创建一个使用默认配置的Param实例
        
        参数:
            name: 参数名称
            value: 参数值
            
        返回:
            Param: 配置好的Param实例
        """
        return ParamFactory.create_param(name, value)

from agent.label.base import Label
from typing import Optional, Dict, Any
from enum import Enum

class ParamStats(Enum):
    ATK = 1
    DEF = 2
    SPD = 3
    MEG = 4


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
        if diffcult > 0:
            self.diffcult = diffcult
        else:
            raise ValueError("diffcult must be greater than 0")
        
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

class ParamSet:

    def __init__(self, **kwargs):
        self.params: Dict[str, Param] = {
            ParamStats.ATK: Param(ParamStats.ATK.name, kwargs.get(ParamStats.ATK.name, 0)),
            ParamStats.DEF: Param(ParamStats.DEF.name, kwargs.get(ParamStats.DEF.name, 0)),
            ParamStats.SPD: Param(ParamStats.SPD.name, kwargs.get(ParamStats.SPD.name, 0)),
            ParamStats.MEG: Param(ParamStats.MEG.name, kwargs.get(ParamStats.MEG.name, 0))
        }
        for par in self.params.values():
            if par.level < 0:
                raise ValueError("param level must be greater or equal than 0")

    def add_value(self, name: str, value: int) -> None:
        param = self.params.get(name)
        if param:
            param.add_value(value)

    def level_up(self, name: str, diffculty: float) -> bool:
        param = self.params.get(name)
        if param:
            need_juel = (10 * diffculty)^(param.level + 1)
            if param.value >= need_juel:
                param.level += 1
                param.value -= need_juel
                return True
        
        return False

    def __getitem__(self, name: str) -> Optional[Param]:
        """获取指定参数"""
        return self.params.get(name)

    def __setitem__(self, name: str, value: int) -> None:
        """设置指定参数的值"""
        param = self.params.get(name)
        if param:
            param.value = value

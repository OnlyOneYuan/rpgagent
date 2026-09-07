from agent.label.base import Label, LabelType
from typing import Optional, Dict, Any
from enum import Enum, StrEnum, IntFlag, auto

class BaseStats(StrEnum):
    ATK = "attack"
    DEF = "defense"
    SPD = "speed"
    MEG = "magic"
    HP  = "health"

class ParamStats(StrEnum):
    comm = "communicate"    # 沟通
    stre = "strength"       # 力量
    inte = "intelligence"   # 智力
    luck = "luck"           # 幸运
    dexp = "dexterity"      # 敏捷  

# 原ResStates修改为Ability
# use intflag to caculate damage * res
class Ability(IntFlag):
    NONE    = 0
    bleed   = auto()
    poison  = auto()
    disease = auto()
    curse   = auto()
    fire    = auto()
    ice     = auto()
    light   = auto()
    dark    = auto()

class Param(Label):
    """
    Param label
    """
    def __init__(self, name: str, value: int,level: int = 0):
        super().__init__(name=name)
        self.level = level
        self.value = value
        self.difficult = 1.00
    
    @property
    def type(self):
        return LabelType.PARAM

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
        if self.value > self.diffcult*10**(self.level) :
            self.level += 1
            self.value = self.value - self.diffcult*10**(self.level)
            return True
        return False
    
    def juel_addless(self, value: int):
        self.value += value

class ParamSet:

    def __init__(self, **kwargs):
        self.params: Dict[str, Param] = {
            # ParamStats.ATK: Param(ParamStats.ATK.name, kwargs.get(ParamStats.ATK.name, 1)),
            # ParamStats.DEF: Param(ParamStats.DEF.name, kwargs.get(ParamStats.DEF.name, 1)),
            # ParamStats.SPD: Param(ParamStats.SPD.name, kwargs.get(ParamStats.SPD.name, 1)),
            # ParamStats.MEG: Param(ParamStats.MEG.name, kwargs.get(ParamStats.MEG.name, 1))
            pname : Param(pname, kwargs.get(pname, 1)) for pname in ParamStats
        }
        self.res: Dict[str, Param] = {
            rname : Param(rname, kwargs.get(rname, 1)) for rname in ResStats
        }
        for par in self.params.values():
            if par.level < 0:
                raise ValueError("param level must be greater or equal than 0")
        for par in self.res.values():
            if par.level < 0:
                raise ValueError("res level must be greater or equal than 0")

    def add_value(self, name: str, value: int) -> None:
        param = self.params.get(name)
        if param:
            param.juel_addless(value)

    def level_up(self, name: str, difficult: Optional[float] = None) -> bool:
        param = self.params.get(name)
        if param:
            # 未指定难度系数时，使用参数当前的难度系数（含天赋加成）
            difficult = difficult if difficult is not None else param.difficult
            need = (10 * difficult) ** (param.level + 1)
            if param.value >= need:
                param.level += 1
                param.value -= need
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
        else:
            raise ValueError(f"param {name} not found")

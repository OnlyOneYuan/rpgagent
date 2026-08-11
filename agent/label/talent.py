from agent.label.base import LabelSet, LabelMap, Label, TalentLabel
from typing import Dict, Any
from abc import ABC, abstractmethod
from enum import Enum
from agent.label.param import Param
from typing import List, Dict, Optional, Union
from dataclasses import dataclass

@dataclass
class TalentEffect:
    """
    能力效果类
    """
    param_name: str  # 影响的参数名称
    difficulty_modifier: float  # 难度系数修改值（带小数）
    description: str  # 效果描述

class Talent(TalentLabel):
    """
    能力类
    """
    def __init__(self, name: str, description: str = "", effects: Optional[List[TalentEffect]] = None):

        self.name = name
        self.description = description
        self.effects = effects or []
        self.active = True  # 才能是否激活
    
    def add_effect(self, param_name: str, difficulty_modifier: float, description: str = "") -> None:

        effect = TalentEffect(param_name, difficulty_modifier, description)
        self.effects.append(effect)
    
    def apply_to_params(self, params: Dict[str, Param]) -> None:

        if not self.active:
            return
            
        for effect in self.effects:
            param = params.get(effect.param_name)
            if param:
                param.difficulty *= effect.difficulty_modifier
                # 确保难度系数不会变为负数
                param.difficulty = max(0.001, param.difficulty)
    
    
    def toggle(self) -> None:

        self.active = not self.active
        if self.active:
            self.apply_to_params()

    def __str__(self) -> str:

        status = "激活" if self.active else "未激活"
        return f"{self.name} ({status}): {self.description}"


    # 返回难度产生效果系数字典（最小0.001）
    @property
    def difficulty(self) -> float:
        if not self.effect:
            return 1.0
        diffcultyDict = {}
        for effect in self.effects:
            self.difficulty = 1.0
            if effect.status == True and self.active:        
                diffculty *= effect.difficulty_modifier
                diffcultyDict[effect.param_name] = diffculty*effect.difficulty_modifier
        return diffcultyDict
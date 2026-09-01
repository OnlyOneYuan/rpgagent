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
    description: str = ""  # 效果描述
    original_difficult: Optional[float] = None  # 应用前的难度系数，用于取消天赋时恢复

class Talent(TalentLabel):
    """
    能力类
    """
    def __init__(self, name: str, description: str = "", effects: Optional[List[TalentEffect]] = None):

        super().__init__(name=name)
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
                effect.original_difficult = param.difficult
                param.difficult *= effect.difficulty_modifier
                # 确保难度系数不会变为负数
                param.difficult = max(0.001, param.difficult)
    
    def unapply_to_params(self, params: Dict[str, Param]) -> None:
        """撤销天赋对参数的效果，恢复为应用前的难度系数"""
        if not self.active:
            return
        for effect in self.effects:
            param = params.get(effect.param_name)
            if param and effect.original_difficult is not None:
                param.difficult = effect.original_difficult
                effect.original_difficult = None
    
    
    def toggle(self) -> None:

        self.active = not self.active

    def __str__(self) -> str:

        status = "激活" if self.active else "未激活"
        return f"{self.name} ({status}): {self.description}"

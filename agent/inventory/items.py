from typing import Dict, Optional
from agent.label.chara import Player
from agent.label.param import ParamSet
from agent.label.effect import Effect
from enum import Enum,StrEnum,IntEnum,auto
from abc import ABC
from __future__ import annotations
from pydantic import BaseModel, Field
from uuid import uuid1

class Rarity(Enum):

    iron    = 1
    copper  = 2
    sliver  = 3
    gold    = 4
    diamond = 5

class Item(BaseModel, ABC):

    uuid    : int
    name    : str
    number  : int = 1
    note    : str = ""
    effect  : Dict[str, any] = Field(default_factory=dict)
    params  : Optional[ParamSet]  = None
    rarity  : Optional[Rarity]    = 1

class Equipment(Item):

    Restricted_attribute :ParamSet

class Armor(Equipment):

    defed:float

#后续改为agent生成武器职业
class Weapon_type_job(IntEnum):
    Anybody = auto()
    Ranger  = auto()
    Warrior = auto()
    Wizard  = auto()

class Weapon(Equipment):

    # 手持类型
    _onehand = 0
    _twohand = 1

    handheld_type:int

    job_type:Weapon_type_job

    def __init__(
        self,
        name: str,
        handheld_type: int = _onehand,
        job_type: Weapon_type_job = Weapon_type_job.Anybody,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.handheld_type = handheld_type
        self.job_type      = job_type
    
    
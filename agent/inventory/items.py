from typing import Dict, Optional

from agent.label.param import ParamSet
from agent.label.effect import Effect
from enum import Enum,StrEnum
from abc import ABC
from pydantic import BaseModel, Field
from uuid import uuid1

class Rarity(Enum):
    iron    = 1
    copper  = 2
    sliver  = 3
    gold    = 4
    diamond = 5

class Item(BaseModel, ABC):
    uuid    : int = uuid1
    name    : str
    number  : int = 1
    note    : str = ""
    effect  : Dict[str, any] = Field(default_factory=dict)
    params  : Optional['ParamSet']  = None
    rarity  : Optional['Rarity']    = Rarity.iron

class Armor(Item):
    Restricted_attribute :ParamSet

    def __init__(self, name, bases, dict, /, **kwds):
        super().__init__(name, bases, dict, **kwds)
    
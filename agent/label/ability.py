from agent.label.param import ParamSet
from enum import Enum,IntFlag,auto

class Attribute(IntFlag):
    NONE    = 0
    bleed   = auto()
    poison  = auto()
    disease = auto()
    curse   = auto()
    fire    = auto()
    ice     = auto()
    light   = auto()
    dark    = auto()

class RSkill:

    def __init__(self,*args:list[Attribute]):
        self.attributes = sum(args)

    @classmethod
    def damage_calculator(cls,skill,*args):
        pass
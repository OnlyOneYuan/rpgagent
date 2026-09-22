# from agent.label.param import ParamSet
from enum import Enum

# class Item:
#     uuid    :int
#     name    :str
#     note    :str
#     effect  :dict
#     params  :ParamSet
#     pass

class Rarity(Enum):
    iron    = 1
    copper  = 2
    sliver  = 3
    gold    = 4
    diamond = 5

print(Rarity.value)
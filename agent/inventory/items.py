from agent.label.param import ParamSet

class Item:
    uuid    :int
    name    :str
    note    :str
    effect  :dict
    params  :ParamSet
    pass

class Armor(Item):
    limit:int
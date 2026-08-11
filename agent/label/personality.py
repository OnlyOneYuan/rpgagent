from agent.label.base import PersonalityLabel

class Personality(PersonalityLabel):
    """
    Personality label
    """
    def __init__(self, name: str,level: int = 0):
        super.__init__(name, level)

    def __eq__(self, other):
        ...

    def __lt__(self, other):
        ...

    def setdiffcutlt(self, diffcult: float):
        ...

    def __str__(self):
        ...
from agent.label.base import Label

class Param(Label):
    """
    Param label
    """
    def __init__(self, name: str, value: int,level: int = 0):
        super().__init__(name, level)
        self.value = value
        self.diffcult = 1.00
    
    def __eq__(self, other):
        
        pass

    def setdiffcutlt(self, diffcult: float):
        self.diffcult = diffcult
        
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
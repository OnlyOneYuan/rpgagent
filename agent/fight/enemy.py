"""敌人系统：敌人定义、模板库与按等级生成"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from agent.fight.base import BattleUnit, DamageType, Skill, StatusEffect
# from agent.player.equipment import Equipment, EquipmentSlot, Rarity


class Enemy:
    """敌人：基础属性 + 技能 + 掉落，可缩放等级"""

    def __init__(self, name: str, level: int, stats: Dict[str, int],
                 skills: Optional[List[Skill]] = None,
                 drops: Optional[List[dict]] = None, boss: bool = False):
        self.name = name
        self.level = level
        self.stats = stats               # health/attack/defense/speed/magic/luck/resistance
        self.skills = skills or []       # List[Skill]
        self.drops = drops or []         # [{"item": Equipment, "chance": float}]
        self.boss = boss

    def build_unit(self) -> BattleUnit:
        """构建战斗单位（供 Battle 使用）"""
        return BattleUnit(
            name        =self.name,
            level       =self.level,
            max_hp      =self.stats.get("health", 30 + self.level * 10),
            attack      =self.stats.get("attack", 6 + self.level),
            defense     =self.stats.get("defense", 3 + self.level // 2),
            speed       =self.stats.get("speed", 5 + self.level),
            magic       =self.stats.get("magic", 2 + self.level // 2),
            resistance  =self.stats.get("resistance", {}),
            luck        =self.stats.get("luck", 1),
        )

    def scaled(self, level: int) -> "Enemy":
        """按目标等级等比缩放属性（用于动态生成合适难度的敌人）"""
        ratio = level / max(1, self.level)
        stats = {k: max(1, int(v * ratio)) for k, v in self.stats.items()}
        return Enemy(self.name, level, stats, skills=self.skills,
                     drops=self.drops, boss=self.boss)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "level": self.level,
            "boss": self.boss,
            "stats": self.stats,
            "skills": [s.to_dict() for s in self.skills],
            "drops": [{"item": d["item"].to_dict(), "chance": d["chance"]} for d in self.drops],
        }

    def __str__(self) -> str:
        return f"{self.name}(Lv.{self.level})"

def _drop(item: Equipment, chance: float) -> dict:
    return {"item": item, "chance": chance}





# def get_enemy(name: str) -> Optional[Enemy]:
#     """按名字获取敌人模板"""
#     return ENEMY_TEMPLATES.get(name)


# def spawn_enemy(level: int) -> Enemy:
#     """按玩家等级随机生成合适难度的敌人（属性已按等级缩放）"""
#     pool = [e for e in ENEMY_TEMPLATES.values() if abs(e.level - level) <= 2]
#     if not pool:
#         pool = [e for e in ENEMY_TEMPLATES.values() if not e.boss]
#     if not pool:
#         pool = list(ENEMY_TEMPLATES.values())
#     return random.choice(pool).scaled(level)

"""敌人系统：敌人定义、模板库与按等级生成"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from agent.fight.base import BattleUnit, DamageType, Skill, StatusEffect
from agent.player.equipment import Equipment, EquipmentSlot, Rarity


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


# ==================== 敌人模板 ====================

def _drop(item: Equipment, chance: float) -> dict:
    return {"item": item, "chance": chance}


ENEMY_TEMPLATES: Dict[str, Enemy] = {
    "史莱姆": Enemy("史莱姆", 1,
        {"health": 32, "attack": 5, "defense": 2, "speed": 3, "magic": 1, "luck": 1},
        skills=[Skill("酸液溅射", "喷出腐蚀性酸液", DamageType.PHYSICAL, 1.1)],
        drops=[_drop(Equipment("史莱姆凝胶", EquipmentSlot.RING, Rarity.COMMON,
                               {"health": 8}, "粘稠的凝胶，可勉强当作饰品"), 0.35)]),
    "野狼": Enemy("野狼", 2,
        {"health": 48, "attack": 8, "defense": 3, "speed": 8, "magic": 1, "luck": 2},
        skills=[Skill("撕咬", "锋利的牙齿撕开皮肉", DamageType.PHYSICAL, 1.4,
                      effect=StatusEffect.BLEED, effect_chance=0.3)],
        drops=[_drop(Equipment("狼牙项链", EquipmentSlot.NECKLACE, Rarity.UNCOMMON,
                               {"attack": 3, "luck": 1}, "以狼牙串成的项链"), 0.25)]),
    "巨鼠": Enemy("巨鼠", 2,
        {"health": 40, "attack": 7, "defense": 2, "speed": 7, "magic": 1, "luck": 1},
        skills=[Skill("啃咬", "带着病菌的啃咬", DamageType.PHYSICAL, 1.2,
                      effect=StatusEffect.POISON, effect_chance=0.3)],
        drops=[_drop(Equipment("鼠尾皮带", EquipmentSlot.BOOTS, Rarity.UNCOMMON,
                               {"speed": 3}, "以鼠尾编成的皮带"), 0.2)]),
    "哥布林": Enemy("哥布林", 3,
        {"health": 55, "attack": 9, "defense": 4, "speed": 6, "magic": 2, "luck": 3},
        skills=[Skill("偷袭", "从背后发起偷袭", DamageType.PHYSICAL, 1.5)],
        drops=[_drop(Equipment("哥布林短刀", EquipmentSlot.WEAPON, Rarity.UNCOMMON,
                               {"attack": 8}, "粗糙但锋利的短刀"), 0.2)]),
    "强盗": Enemy("强盗", 4,
        {"health": 70, "attack": 11, "defense": 5, "speed": 6, "magic": 2, "luck": 3},
        skills=[Skill("背刺", "阴险的背刺", DamageType.PHYSICAL, 1.6)],
        drops=[_drop(Equipment("强盗兜帽", EquipmentSlot.HELMET, Rarity.RARE,
                               {"defense": 4, "dexterity": 2}, "蒙面兜帽"), 0.18)]),
    "骷髅兵": Enemy("骷髅兵", 5,
        {"health": 85, "attack": 13, "defense": 6, "speed": 5, "magic": 3, "luck": 2,
         "resistance": {"dark_res": 20, "curse_res": 30}},
        skills=[Skill("骨刃斩", "挥动骨刃斩击", DamageType.PHYSICAL, 1.5,
                      effect=StatusEffect.BLEED, effect_chance=0.25)],
        drops=[_drop(Equipment("骸骨护符", EquipmentSlot.NECKLACE, Rarity.RARE,
                               {"dark_res": 12, "curse_res": 10}, "附有亡者气息的护符"), 0.2)]),
    "石像鬼": Enemy("石像鬼", 9,
        {"health": 160, "attack": 18, "defense": 14, "speed": 4, "magic": 5, "luck": 3,
         "resistance": {"light_res": 20, "fire_res": 10}},
        skills=[Skill("石化凝视", "令人僵硬的凝视", DamageType.DARK, 1.2,
                      effect=StatusEffect.STUN, effect_chance=0.35),
                Skill("石爪", "坚硬的石质利爪", DamageType.PHYSICAL, 1.4)],
        drops=[_drop(Equipment("石肤胸甲", EquipmentSlot.ARMOR, Rarity.EPIC,
                               {"defense": 12, "health": 25}, "坚硬如磐石的胸甲"), 0.15)]),
    "狼王": Enemy("狼王", 8,
        {"health": 180, "attack": 17, "defense": 8, "speed": 10, "magic": 4, "luck": 5,
         "resistance": {"bleed_res": 20}},
        skills=[Skill("狼嚎", "仰天长啸削弱猎物", DamageType.DARK, 0.8,
                      effect=StatusEffect.WEAKEN, effect_chance=0.5),
                Skill("致命扑击", "蓄力后猛扑", DamageType.PHYSICAL, 1.8,
                      effect=StatusEffect.BLEED, effect_chance=0.4)],
        drops=[_drop(Equipment("狼王鬃毛甲", EquipmentSlot.ARMOR, Rarity.EPIC,
                               {"defense": 10, "health": 30, "speed": 3}, "以狼王鬃毛缝制的铠甲"), 0.3),
               _drop(Equipment("狼王爪刃", EquipmentSlot.WEAPON, Rarity.EPIC,
                               {"attack": 14, "dexterity": 3}, "锋利无比的狼王利爪"), 0.25)],
        boss=True),
    "火龙": Enemy("火龙", 12,
        {"health": 300, "attack": 24, "defense": 15, "speed": 8, "magic": 12, "luck": 6,
         "resistance": {"fire_res": 40, "ice_res": -20}},
        skills=[Skill("烈焰吐息", "喷吐炽热的龙息", DamageType.FIRE, 2.2,
                      effect=StatusEffect.BURN, effect_chance=0.6),
                Skill("龙爪撕裂", "撕裂一切的龙爪", DamageType.PHYSICAL, 1.7)],
        drops=[_drop(Equipment("龙鳞铠", EquipmentSlot.ARMOR, Rarity.LEGENDARY,
                               {"defense": 18, "health": 50, "fire_res": 25}, "以龙鳞打造的无上铠甲"), 0.4),
               _drop(Equipment("龙牙剑", EquipmentSlot.WEAPON, Rarity.LEGENDARY,
                               {"attack": 22, "fire_res": 10}, "以龙牙锻造的神兵"), 0.3)],
        boss=True),
}


def get_enemy(name: str) -> Optional[Enemy]:
    """按名字获取敌人模板"""
    return ENEMY_TEMPLATES.get(name)


def spawn_enemy(level: int) -> Enemy:
    """按玩家等级随机生成合适难度的敌人（属性已按等级缩放）"""
    pool = [e for e in ENEMY_TEMPLATES.values() if abs(e.level - level) <= 2]
    if not pool:
        pool = [e for e in ENEMY_TEMPLATES.values() if not e.boss]
    if not pool:
        pool = list(ENEMY_TEMPLATES.values())
    return random.choice(pool).scaled(level)

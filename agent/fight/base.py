"""战斗基础模块：伤害类型、状态效果、技能与战斗单位抽象，以及伤害计算公式。

作为 agent/fight 的核心基础，供 enemy（敌人系统）与 battle（战斗引擎）复用。
"""
from __future__ import annotations

import random
from enum import StrEnum
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from agent.player.player import Player

from agent.player.player import RES_NAMES, compute_stats


class DamageType(StrEnum):
    """伤害类型：物理受防御减免，元素 / 异常受对应抗性减免"""
    PHYSICAL = "physical"   # 物理
    FIRE     = "fire"       # 火焰
    ICE      = "ice"        # 冰霜
    LIGHT    = "light"      # 光明
    DARK     = "dark"       # 黑暗
    BLEED    = "bleed"      # 流血
    POISON   = "poison"     # 中毒
    DISEASE  = "disease"    # 疾病
    CURSE    = "curse"      # 诅咒

_damageTypelist = list(DamageType)
damageTypeBin = {
    _damageTypelist[i]:2**i for i in range(len(_damageTypelist))
}

# 伤害类型 -> 减免抗性属性名（物理无对应抗性，由防御减免）
RESISTANCE_MAP: Dict[DamageType, Optional[str]] = {
    DamageType.PHYSICAL: None,
    DamageType.FIRE: "fire_res",
    DamageType.ICE: "ice_res",
    DamageType.LIGHT: "light_res",
    DamageType.DARK: "dark_res",
    DamageType.BLEED: "bleed_res",
    DamageType.POISON: "poison_res",
    DamageType.DISEASE: "disease_res",
    DamageType.CURSE: "curse_res",
}

DAMAGE_LABELS: Dict[DamageType, str] = {
    DamageType.PHYSICAL: "物理",
    DamageType.FIRE: "火焰",
    DamageType.ICE: "冰霜",
    DamageType.LIGHT: "光明",
    DamageType.DARK: "黑暗",
    DamageType.BLEED: "流血",
    DamageType.POISON: "中毒",
    DamageType.DISEASE: "疾病",
    DamageType.CURSE: "诅咒",
}


class StatusEffect(StrEnum):
    """持续状态效果"""
    POISON  = "poison"    # 中毒：回合结束掉血上限（不同技能可叠加）
    BLEED   = "bleed"     # 流血：回合结束掉血，根据程度不同，决定流血是否治愈（可叠加）
    BURN    = "burn"      # 灼烧：回合结束持续掉血
    FREEZE  = "freeze"    # 冰冻：行动受限
    STUN    = "stun"      # 眩晕：无法行动
    WEAKEN  = "weaken"    # 虚弱：攻击降低 30%
    FRAGILE = "fragile"   # 易碎：防御降低 30%


STATUS_LABELS: Dict[StatusEffect, str] = {
    StatusEffect.POISON: "中毒",
    StatusEffect.BLEED: "流血",
    StatusEffect.BURN: "灼烧",
    StatusEffect.FREEZE: "冰冻",
    StatusEffect.STUN: "眩晕",
    StatusEffect.WEAKEN: "虚弱",
    StatusEffect.FRAGILE: "易碎",
}


class Skill:
    """技能：造成伤害或恢复生命，可附带状态效果"""

    def __init__(self, name: str, description: str, dmg_type: Optional[DamageType],
                 power: float, effect: Optional[StatusEffect] = None,
                 effect_chance: float = 0.0):
        self.name = name
        self.description = description
        self.dmg_type = dmg_type            # None 表示治疗技能
        self.power = power                  # 伤害倍率（基于攻击）或治疗倍率（基于魔法）
        self.effect = effect                # 附加的状态效果
        self.effect_chance = effect_chance  # 附加状态的概率

    def to_dict(self) -> dict:
        return {
            "name"          : self.name,
            "description"   : self.description,
            "dmg_type"      : self.dmg_type.value if self.dmg_type else None,
            "power"         : self.power,
            "effect"        : self.effect.value if self.effect else None,
            "effect_chance" : self.effect_chance,
        }

    def __str__(self) -> str:
        return f"{self.name}:{self.description}"


class BattleUnit:
    """战斗单位：从玩家 / 敌人提取战斗数据，负责生命与状态管理"""

    def __init__(self, name: str, level: int, max_hp: int, attack: int,
                 defense: int, speed: int, magic: int,
                 resistance: Optional[Dict[str, int]] = None, luck: int = 0):
        self.name   = name
        self.level  = level
        self.max_hp = max_hp
        self.hp     = max_hp
        self.attack  = attack
        self.defense = defense
        self.speed  = speed
        self.magic  = magic
        self.luck   = luck
        self.resistance: Dict[str, int]      = resistance or {k: 0 for k in RES_NAMES}
        self.status: Dict[StatusEffect, int] = {}  # 效果 -> 剩余回合数

    # ---------- 构建 ----------
    @classmethod
    def from_player(cls, player: "Player") -> "BattleUnit":
        """从玩家构建战斗单位（复用 compute_stats，包含装备与天赋加成）"""
        stats = compute_stats(player)
        return cls(
            name    =player.name,
            level   =player.level,
            max_hp  =stats["health"]["total"],
            attack  =stats["attack"]["total"],
            defense =stats["defense"]["total"],
            speed   =stats["speed"]["total"],
            magic   =stats["magic"]["total"],
            resistance ={k: stats[k]["total"] for k in RES_NAMES},
            luck    =stats["luck"]["total"],
        )

    # ---------- 生命 ----------
    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        """受到伤害，返回实际扣除的生命"""
        if amount <= 0:
            return 0
        real = min(amount, self.hp)
        self.hp -= real
        return real

    def heal(self, amount: int) -> int:
        """恢复生命，返回实际恢复量"""
        if amount <= 0:
            return 0
        real = min(amount, self.max_hp - self.hp)
        self.hp += real
        return real

    # ---------- 抗性 ----------
    def resist(self, dmg_type: DamageType) -> int:
        """对指定伤害类型的抗性值（0-100）"""
        res_name = RESISTANCE_MAP.get(dmg_type)
        if res_name is None:
            return 0
        return self.resistance.get(res_name, 0)

    # ---------- 状态效果 ----------
    def has_status(self, effect: StatusEffect) -> bool:
        return effect in self.status

    #! need repair FREEZE BLEE STUN
    def can_act(self) -> bool:
        """冰冻 / 眩晕状态下无法行动"""
        return not (self.has_status(StatusEffect.FREEZE) or self.has_status(StatusEffect.STUN))

    def effective_attack(self) -> float:
        """虚弱状态下攻击降低 30%"""
        return self.attack * 0.7 if self.has_status(StatusEffect.WEAKEN) else float(self.attack)

    def effective_defense(self) -> float:
        """易碎状态下防御降低 30%"""
        return self.defense * 0.7 if self.has_status(StatusEffect.FRAGILE) else float(self.defense)

    def add_status(self, effect: StatusEffect, turns: int) -> bool:
        """附加状态效果；异常类受对应抗性影响（抗性 ≥ 50 免疫）"""
        status_res = {
            StatusEffect.POISON : "poison_res",
            StatusEffect.BLEED  : "bleed_res",
            StatusEffect.BURN   : "fire_res",
            StatusEffect.FREEZE : "ice_res",
        }
        # ! need to change status logic 
        # res_name = status_res.get(effect)
        # if res_name and self.resistance.get(res_name, 0) >= 50:
        #     return False
        # if effect in (StatusEffect.FREEZE, StatusEffect.STUN):
        #     turns = 1  # 硬控最多 1 回合
        # self.status[effect] = max(self.status.get(effect, 0), turns)
        # return True

    def tick_status(self) -> List[str]:
        """回合结束：结算持续伤害并刷新状态回合数，返回日志"""
        logs: List[str] = []
        # ! need change
        # for effect in (StatusEffect.POISON, StatusEffect.BLEED, StatusEffect.BURN):
        #     if effect in self.status:
        #         dmg = max(1, self.max_hp // 20)
        #         real = self.take_damage(dmg)
        #         logs.append(f"{self.name} 因{STATUS_LABELS[effect]}损失 {real} 点生命")
        # for effect in list(self.status):
        #     if self.status[effect] <= 1:
        #         del self.status[effect]
        #     else:
        #         self.status[effect] -= 1
        return logs


def calc_damage(attacker: BattleUnit, defender: BattleUnit, power: float = 1.0,
                dmg_type: DamageType = DamageType.PHYSICAL) -> dict:
    """计算一次攻击并应用伤害，返回 {"damage", "critical", "miss", "log"}

    公式：
      - 命中率：90% + 双方速度差微调（下限 65%，上限 98%）
      - 暴击率：5% + 幸运×0.4%（上限 40%），暴击伤害 ×1.5
      - 物理伤害：max(1, 攻击×倍率 - 防御×0.6)，再乘随机浮动 ±15%
      - 元素 / 异常伤害：max(1, 攻击×倍率×(1 - 抗性/100))，再乘随机浮动 ±15%
    """
    hit_rate = min(0.98, max(0.65, 0.9 + (attacker.speed - defender.speed) * 0.01))
    if random.random() > hit_rate:
        return {"damage": 0, "critical": False, "miss": True,
                "log": f"{attacker.name} 的攻击被 {defender.name} 闪避了！"}

    atk = attacker.effective_attack()
    if dmg_type is DamageType.PHYSICAL:
        raw = atk * power - defender.effective_defense() * 0.6
    else:
        raw = atk * power * (1 - defender.resist(dmg_type) / 100.0)
    raw *= random.uniform(0.85, 1.15)

    crit_rate = min(0.40, 0.05 + attacker.luck * 0.004)
    critical = random.random() < crit_rate
    if critical:
        raw *= 1.5

    damage = defender.take_damage(max(1, int(round(raw))))
    log = f"{attacker.name} 对 {defender.name} 造成 {damage} 点{DAMAGE_LABELS[dmg_type]}伤害"
    if critical:
        log += "（暴击！）"
    return {"damage": damage, "critical": critical, "miss": False, "log": log}

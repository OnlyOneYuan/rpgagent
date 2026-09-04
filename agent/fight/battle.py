"""回合制战斗引擎：玩家 vs 敌人，支持技能 / 状态效果 / 逃跑与奖励结算"""
from __future__ import annotations

import random
from typing import List, Optional

from agent.fight.base import (
    STATUS_LABELS,
    BattleUnit,
    DamageType,
    Skill,
    StatusEffect,
    calc_damage,
)
from agent.fight.enemy import Enemy
from agent.player.player import Player

# 玩家可用的内置技能（后续可随职业 / 等级扩展）
PLAYER_SKILLS: List[Skill] = [
    Skill("重击", "奋力一击，造成 1.6 倍物理伤害", DamageType.PHYSICAL, 1.6),
    Skill("火球术", "凝聚火球，造成 1.5 倍火焰伤害", DamageType.FIRE, 1.5),
    Skill("寒冰箭", "射出冰矢，造成 1.4 倍冰霜伤害，概率冰冻目标", DamageType.ICE, 1.4,
          effect=StatusEffect.FREEZE, effect_chance=0.35),
    Skill("治疗术", "调动魔力恢复生命（2 倍魔法 + 等级×5）", None, 2.0),
]


class Battle:
    """一场战斗：管理行动顺序、回合日志与结果结算"""

    def __init__(self, player: Player, enemy: Enemy):
        self.player = player
        self.enemy = enemy
        self.player_unit = BattleUnit.from_player(player)
        self.enemy_unit = enemy.build_unit()
        self.turn: int = 0
        self.logs: List[str] = []
        self.finished: bool = False
        self.victory: Optional[bool] = None   # True 胜利 / False 失败或逃跑
        self.escaped: bool = False

    # ---------- 战斗主循环（每次调用推进一个完整回合） ----------
    def player_action(self, action: str, skill_name: Optional[str] = None) -> List[str]:
        """执行一个完整回合：玩家行动 → 敌人行动 → 回合结算，返回本回合日志。

        action 取值：
          - "attack"：普通攻击
          - "skill"：释放技能（需传入 skill_name）
          - "flee"：尝试逃跑
        """
        if self.finished:
            return ["战斗已结束"]
        logs: List[str] = []
        enemy_first = self.turn == 0 and self.enemy_unit.speed > self.player_unit.speed

        # —— 敌人行动（敌人先手 / 玩家被控制）——
        if enemy_first or not self.player_unit.can_act():
            if not enemy_first:
                logs.append(f"{self.player.name} 被控制，无法行动！")
            logs += self.enemy_turn()
        if self.finished:
            self.logs.extend(logs)
            return logs

        # —— 玩家行动 ——
        if self.player_unit.can_act():
            logs += self._do_player_action(action, skill_name)
            if self.finished:
                self.logs.extend(logs)
                return logs
            # —— 敌人行动（玩家先手）——
            logs += self.enemy_turn()
            if self.finished:
                self.logs.extend(logs)
                return logs

        # —— 回合结算 ——
        logs += self._end_turn()
        self.logs.extend(logs)
        return logs

    # ---------- 内部行动 ----------
    def _do_player_action(self, action: str, skill_name: Optional[str]) -> List[str]:
        """玩家单个行动：攻击 / 技能 / 逃跑"""
        logs: List[str] = []
        if action == "flee":
            rate = min(0.95, max(0.20, 0.5 + (self.player_unit.speed - self.enemy_unit.speed) * 0.02))
            if random.random() < rate:
                self.finished = True
                self.victory = False
                self.escaped = True
                logs.append(f"{self.player.name} 成功逃脱了战斗！")
            else:
                logs.append("逃跑失败！")
            return logs

        if action == "attack":
            logs.append(calc_damage(self.player_unit, self.enemy_unit)["log"])
        elif action == "skill":
            skill = next((s for s in PLAYER_SKILLS if s.name == skill_name), None)
            if skill is None:
                logs.append(f"没有「{skill_name}」这个技能")
                return logs
            logs += self._use_skill(self.player_unit, self.enemy_unit, skill)
        else:
            logs.append(f"未知行动：{action}")
            return logs

        if not self.enemy_unit.alive:
            self.finished = True
            self.victory = True
            logs.append(f"战斗胜利！{self.enemy.name} 已被击败！")
        return logs

    def enemy_turn(self) -> List[str]:
        """敌人行动回合"""
        if self.finished or not self.enemy_unit.alive:
            return []
        if not self.enemy_unit.can_act():
            return [f"{self.enemy.name} 被控制，无法行动！"]
        logs: List[str] = []
        skill = random.choice(self.enemy.skills) if self.enemy.skills else None
        if skill:
            logs += self._use_skill(self.enemy_unit, self.player_unit, skill)
        else:
            logs.append(calc_damage(self.enemy_unit, self.player_unit)["log"])
        if not self.player_unit.alive:
            self.finished = True
            self.victory = False
            logs.append(f"战斗失败……{self.player.name} 被击败了")
        return logs

    def _use_skill(self, source: BattleUnit, target: BattleUnit, skill: Skill) -> List[str]:
        """释放技能：治疗或伤害（可附带状态效果）"""
        logs = [f"{source.name} 使用了「{skill.name}」！"]
        if skill.dmg_type is None:
            healed = source.heal(int(source.magic * skill.power) + source.level * 5)
            logs.append(f"{source.name} 恢复了 {healed} 点生命")
            return logs
        result = calc_damage(source, target, power=skill.power, dmg_type=skill.dmg_type)
        logs.append(result["log"])
        if (skill.effect and not target.has_status(skill.effect)
                and random.random() < skill.effect_chance):
            if target.add_status(skill.effect, 2):
                logs.append(f"{target.name} 陷入了{STATUS_LABELS[skill.effect]}状态！")
        return logs

    def _end_turn(self) -> List[str]:
        """回合结束：结算双方持续伤害并再次判定胜负"""
        self.turn += 1
        logs: List[str] = []
        for unit in (self.player_unit, self.enemy_unit):
            if unit.alive:
                logs += unit.tick_status()
        if not self.enemy_unit.alive and not self.finished:
            self.finished = True
            self.victory = True
            logs.append(f"战斗胜利！{self.enemy.name} 倒下了！")
        elif not self.player_unit.alive and not self.finished:
            self.finished = True
            self.victory = False
            logs.append(f"战斗失败……{self.player.name} 被击败了")
        return logs

    # ---------- 结算 ----------
    def settle(self) -> dict:
        """战斗结算：发放经验 / 金币 / 掉落（仅胜利时生效）"""
        reward = {
            "victory": self.victory,
            "escaped": self.escaped,
            "exp": 0,
            "gold": 0,
            "drops": [],
            "level_ups": 0,
        }
        if not self.victory:
            return reward
        exp = self.enemy.level * (80 if self.enemy.boss else 40)
        gold = self.enemy.level * 12 + random.randint(0, self.enemy.level * 6)
        ups = self.player.add_exp(exp)
        self.player.gold += gold
        reward["exp"] = exp
        reward["gold"] = gold
        reward["level_ups"] = ups
        for drop in self.enemy.drops:
            if random.random() < drop["chance"]:
                item = drop["item"].clone()
                self.player.give(item)
                reward["drops"].append(item)
        return reward

    def to_dict(self) -> dict:
        """战斗状态快照（供前端轮询 / 调试）"""
        return {
            "finished": self.finished,
            "victory": self.victory,
            "escaped": self.escaped,
            "turn": self.turn,
            "player": {
                "name": self.player_unit.name,
                "hp": self.player_unit.hp,
                "max_hp": self.player_unit.max_hp,
                "status": {k.value: v for k, v in self.player_unit.status.items()},
            },
            "enemy": {
                "name": self.enemy_unit.name,
                "hp": self.enemy_unit.hp,
                "max_hp": self.enemy_unit.max_hp,
                "status": {k.value: v for k, v in self.enemy_unit.status.items()},
            },
            "logs": self.logs,
        }


def auto_fight(player: Player, enemy: Enemy) -> dict:
    """自动战斗：玩家自动普攻直至分出胜负。

    返回：{"victory", "escaped", "logs", "reward"}，胜利时 reward 含经验 / 金币 / 掉落。
    """
    battle = Battle(player, enemy)
    while not battle.finished:
        battle.player_action("attack")
    reward = battle.settle() if battle.victory else None
    return {
        "victory": battle.victory,
        "escaped": battle.escaped,
        "logs": battle.logs,
        "reward": reward,
    }

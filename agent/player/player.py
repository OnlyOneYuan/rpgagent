"""玩家系统：多人玩家模型 + JSON 持久化 + 属性/装备/任务管理"""
from __future__ import annotations

import hashlib
import json
import os
import random
import threading
from pathlib import Path
from typing import Dict, List, Optional

from agent.label.chara import RACE, Chara
from agent.label.param import ParamSet
from agent.label.talent import Talent, TalentEffect
from agent.player.equipment import Equipment, EquipmentSlot, Inventory
from agent.task.task import Task

DEFAULT_SAVE_DIR = os.path.join(os.path.dirname(__file__), "data", "players")


# ==================== 序列化（Chara / ParamSet / Talent / RACE） ====================

def param_to_dict(p) -> dict:
    return {"name": p.name, "value": p.value, "level": p.level, "difficult": p.difficult}


def paramset_to_dict(ps: ParamSet) -> dict:
    return {
        "params": {k: param_to_dict(v) for k, v in ps.params.items()},
        "res": {k: param_to_dict(v) for k, v in ps.res.items()},
    }


def param_from_dict(d: dict):
    from agent.label.param import Param
    return Param(d["name"], d.get("value", 1), level=d.get("level", 0))


def paramset_from_dict(d: dict) -> ParamSet:
    ps = ParamSet()
    for k, v in d.get("params", {}).items():
        if k in ps.params:
            ps.params[k] = param_from_dict(v)
    for k, v in d.get("res", {}).items():
        if k in ps.res:
            ps.res[k] = param_from_dict(v)
    return ps


def talent_to_dict(t: Talent) -> dict:
    return {
        "name": t.name,
        "description": t.description,
        "active": t.active,
        "effects": [
            {
                "param_name": e.param_name,
                "difficulty_modifier": e.difficulty_modifier,
                "description": e.description,
                "original_difficult": e.original_difficult,
            }
            for e in t.effects
        ],
    }


def talent_from_dict(d: dict) -> Talent:
    effects = [
        TalentEffect(
            param_name=e.get("param_name"),
            difficulty_modifier=e.get("difficulty_modifier", 1.0),
            description=e.get("description", ""),
            original_difficult=e.get("original_difficult"),
        )
        for e in d.get("effects", [])
    ]
    t = Talent(d.get("name", "?"), d.get("description", ""), effects)
    t.active = d.get("active", True)
    return t


def race_to_dict(r: RACE) -> dict:
    return {"name": r.name, "param": paramset_to_dict(r.param), "talents": [talent_to_dict(t) for t in r.talents]}


def race_from_dict(d: dict) -> RACE:
    return RACE(name=d.get("name", "?"), param=paramset_from_dict(d.get("param", {})),
                talents=[talent_from_dict(t) for t in d.get("talents", [])])


def chara_to_dict(c: Chara) -> dict:
    return {
        "name": c.name,
        "param": paramset_to_dict(c.param),
        "talents": [talent_to_dict(t) for t in c.talents],
        "race": race_to_dict(c.race),
    }


def chara_from_dict(d: dict) -> Chara:
    """重建 Chara。为避免重复应用天赋，先以空天赋构建，再还原精确数值。"""
    ps = paramset_from_dict(d.get("param", {}))
    race = race_from_dict(d.get("race", {"name": "?", "param": {}, "talents": []}))
    talents = [talent_from_dict(t) for t in d.get("talents", [])]
    chara = Chara(name=d.get("name", "?"), params=ps, talents=[], race=race)
    chara.talents = talents
    # 还原存储的精确数值（已含天赋效果，避免重复乘算）
    pdata = d.get("param", {})
    for k, v in pdata.get("params", {}).items():
        if k in ps.params:
            ps.params[k].value = v.get("value", ps.params[k].value)
            ps.params[k].level = v.get("level", ps.params[k].level)
            ps.params[k].difficult = v.get("difficult", ps.params[k].difficult)
    for k, v in pdata.get("res", {}).items():
        if k in ps.res:
            ps.res[k].value = v.get("value", ps.res[k].value)
            ps.res[k].level = v.get("level", ps.res[k].level)
            ps.res[k].difficult = v.get("difficult", ps.res[k].difficult)
    return chara


# ==================== 属性计算 ====================

BASE_STATS = ["health", "attack", "defense", "speed", "magic"]
PARAM_NAMES = ["communicate", "strength", "intelligence", "luck", "dexterity"]
RES_NAMES = ["bleed_res", "poison_res", "disease_res", "curse_res",
             "fire_res", "ice_res", "light_res", "dark_res"]


def compute_stats(player: "Player") -> dict:
    """计算展示用属性：基础属性 + 能力属性 + 抗性（均含装备加成）"""
    p = player.chara.param
    level = player.level
    base = {
        "health": 100 + level * 30,
        "attack": 8 + p.params["strength"].value * 2,
        "defense": 5 + level * 2,
        "speed": 8 + p.params["dexterity"].value * 2,
        "magic": 5 + p.params["intelligence"].value * 2,
    }
    bonuses = {k: 0 for k in BASE_STATS + PARAM_NAMES + RES_NAMES}
    for item in player.equipped.values():
        for k, v in item.stats.items():
            if k in bonuses:
                bonuses[k] += v

    result = {}
    for k, v in base.items():
        result[k] = {"base": v, "bonus": bonuses.get(k, 0), "total": v + bonuses.get(k, 0)}
    for k in PARAM_NAMES:
        result[k] = {
            "base": p.params[k].value,
            "level": p.params[k].level,
            "bonus": bonuses.get(k, 0),
            "total": p.params[k].value + bonuses.get(k, 0),
        }
    for k in RES_NAMES:
        result[k] = {
            "base": p.res[k].value,
            "bonus": bonuses.get(k, 0),
            "total": p.res[k].value + bonuses.get(k, 0),
        }
    return result


# ==================== 玩家模型 ====================

class Player:
    def __init__(self, name: str, password_hash: str, chara: Chara):
        self.name = name
        self.password_hash = password_hash
        self.chara = chara
        self.level: int = 1
        self.exp: int = 0
        self.gold: int = 100
        self.inventory: Inventory = Inventory()
        self.equipped: Dict[EquipmentSlot, Equipment] = {}
        self.tasks: List[Task] = []
        self.online: bool = False

    # ---------- 装备 ----------
    def give(self, item: Equipment) -> None:
        """给予物品：绑定持有者（依赖 Chara）后放入背包"""
        item.bind(self.chara)
        self.inventory.add(item)

    def equip(self, item_id: str) -> tuple[bool, str]:
        item = self.inventory.get(item_id)
        if item is None:
            return False, "背包中没有该物品"
        if not item.can_wield(self.chara, self.level):
            reqs = [f"等级≥{item.required_level}"] if item.required_level > 1 else []
            reqs += [f"{k}≥{v}" for k, v in item.require.items()]
            return False, f"无法装备 {item.name}（需求：{'，'.join(reqs)}）"
        if item.slot in self.equipped:
            old = self.equipped[item.slot]
            self.inventory.add(old)
        self.equipped[item.slot] = item
        item.bind(self.chara)
        self.inventory.remove(item)
        return True, f"已装备 {item.name}"

    def unequip(self, slot: str) -> tuple[bool, str]:
        try:
            es = EquipmentSlot(slot)
        except ValueError:
            return False, f"无效的槽位: {slot}"
        item = self.equipped.pop(es, None)
        if item is None:
            return False, f"{slot} 槽位没有装备"
        self.inventory.add(item)
        return True, f"已卸下 {item.name}"

    # ---------- 偷窃（多人交互） ----------
    def steal_from(self, target: "Player", cost: int = 20) -> tuple[bool, str, Optional[Equipment]]:
        """偷窃：尝试从目标玩家身上偷取一件物品（背包或已装备），成功后装备归属转移。

        成功率由小偷的（敏捷+幸运）与目标的（幸运+等级×2）对比决定。
        """
        if target is self:
            return False, "不能偷自己", None
        if self.gold < cost:
            return False, f"金币不足（偷窃需 {cost} 金币）", None
        pool = list(target.inventory.items) + list(target.equipped.values())
        if not pool:
            return False, "对方身上没有可偷的物品", None
        thief = self.chara.param.params["dexterity"].value + self.chara.param.params["luck"].value
        guard = target.chara.param.params["luck"].value + target.level * 2
        rate = min(0.85, max(0.15, 0.5 + (thief - guard) * 0.02))
        if random.random() > rate:
            self.gold -= cost
            return False, f"偷窃失败（成功率 {rate:.0%}，损失 {cost} 金币）", None
        item = random.choice(pool)
        if target.equipped.get(item.slot) is item:
            del target.equipped[item.slot]  # 从目标装备栏卸下
        else:
            target.inventory.remove(item)
        item.bind(self.chara)  # 装备归属转移到小偷
        self.inventory.add(item)
        self.gold -= cost
        return True, f"偷窃成功，获得「{item.name}」！", item

    # ---------- 成长 ----------
    def add_exp(self, amount: int) -> int:
        """增加经验，自动升级；返回升级次数"""
        self.exp += amount
        ups = 0
        while self.exp >= self.level * 100:
            self.exp -= self.level * 100
            self.level += 1
            ups += 1
        return ups

    def train(self, param_name: str, cost_gold: int = 10) -> tuple[bool, str]:
        """训练属性：消耗金币为指定属性增加积累值（可升级）"""
        p = self.chara.param.params.get(param_name)
        if p is None:
            return False, f"未知属性: {param_name}"
        if self.gold < cost_gold:
            return False, f"金币不足（需要 {cost_gold}）"
        self.gold -= cost_gold
        gain = 5 + self.level * 5
        p.value += gain
        leveled = False
        while self.chara.params_levelup(param_name):
            leveled = True
        msg = f"{param_name} +{gain}"
        if leveled:
            msg += "，属性升级！"
        return True, msg

    # ---------- 任务 ----------
    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

    def accept_task(self, task_id: str) -> tuple[bool, str]:
        t = self.get_task(task_id)
        if t is None:
            return False, "任务不存在"
        if t.accept():
            return True, f"已接受任务：{t.name}"
        return False, f"任务当前状态无法接受（{t.status.value}）"

    def complete_task(self, task_id: str) -> tuple[bool, dict, str]:
        t = self.get_task(task_id)
        if t is None:
            return False, {}, "任务不存在"
        reward = t.complete()
        if not reward["gold"] and not reward["exp"] and not reward["param"]:
            return False, {}, f"任务当前状态无法完成（{t.status.value}）"
        self.gold += reward["gold"]
        ups = self.add_exp(reward["exp"])
        for k, v in reward["param"].items():
            p = self.chara.param.params.get(k)
            if p:
                p.value += v
        msg = f"完成「{t.name}」，获得 {reward['gold']} 金币、{reward['exp']} 经验"
        if ups:
            msg += f"，等级提升至 {self.level}！"
        if reward["param"]:
            msg += f"，属性奖励 {reward['param']}"
        return True, reward, msg

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "level": self.level,
            "exp": self.exp,
            "gold": self.gold,
            "online": self.online,
            "chara": chara_to_dict(self.chara),
            "stats": compute_stats(self),
            "equipped": {slot.value: item.to_dict() for slot, item in self.equipped.items()},
            "inventory": self.inventory.to_dict(),
            "tasks": [t.to_dict() for t in self.tasks],
        }

    def save_dict(self) -> dict:
        """完整持久化数据（含密码哈希）"""
        return {
            "name": self.name,
            "password_hash": self.password_hash,
            "level": self.level,
            "exp": self.exp,
            "gold": self.gold,
            "chara": chara_to_dict(self.chara),
            "equipped": {slot.value: item.to_dict() for slot, item in self.equipped.items()},
            "inventory": self.inventory.to_dict(),
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_save(cls, data: dict) -> "Player":
        player = cls(
            name=data["name"],
            password_hash=data["password_hash"],
            chara=chara_from_dict(data["chara"]),
        )
        player.level = data.get("level", 1)
        player.exp = data.get("exp", 0)
        player.gold = data.get("gold", 100)
        player.inventory = Inventory.from_dict(data.get("inventory", []))
        player.equipped = {
            EquipmentSlot(k): Equipment.from_dict(v)
            for k, v in data.get("equipped", {}).items()
        }
        player.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        # 还原装备持有者引用（owner_name 匹配当前玩家则绑定其 Chara）
        for item in list(player.inventory.items) + list(player.equipped.values()):
            if item.owner_name == player.name:
                item.owner = player.chara
        return player

    def __str__(self):
        return f"Player({self.name}, Lv.{self.level})"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ==================== 玩家管理器（多人 + 持久化） ====================

class PlayerManager:
    """负责玩家的注册/登录、内存缓存、线程安全的 JSON 持久化"""

    def __init__(self, save_dir: str = DEFAULT_SAVE_DIR):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._players: Dict[str, Player] = {}
        self._lock = threading.RLock()
        self._load_all()

    def _player_path(self, name: str) -> Path:
        return self.save_dir / f"{name}.json"

    def _load_all(self) -> None:
        for f in self.save_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                p = Player.from_save(data)
                self._players[p.name] = p
            except Exception as e:
                print(f"[PlayerManager] 加载 {f.name} 失败: {e}")

    def _save(self, player: Player) -> None:
        path = self._player_path(player.name)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(player.save_dict(), fp, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def exists(self, name: str) -> bool:
        return name in self._players

    def register(self, name: str, password: str, chara: Chara, gold: int = 100) -> tuple[bool, str]:
        with self._lock:
            if not name.strip():
                return False, "名字不能为空"
            if len(name) > 12:
                return False, "名字过长（最多 12 字）"
            if self.exists(name):
                return False, "该名字已被使用"
            player = Player(name, hash_password(password), chara)
            player.gold = gold
            self._players[name] = player
            self._save(player)
            return True, "注册成功"

    def login(self, name: str, password: str) -> tuple[bool, str, Optional[Player]]:
        with self._lock:
            player = self._players.get(name)
            if player is None:
                return False, "玩家不存在", None
            if player.password_hash != hash_password(password):
                return False, "密码错误", None
            player.online = True
            self._save(player)
            return True, "登录成功", player

    def get(self, name: str) -> Optional[Player]:
        with self._lock:
            return self._players.get(name)

    def all_players(self) -> List[Player]:
        with self._lock:
            return list(self._players.values())

    def save(self, player: Player) -> None:
        with self._lock:
            self._save(player)

    def set_online(self, name: str, online: bool) -> Optional[Player]:
        with self._lock:
            player = self._players.get(name)
            if player:
                player.online = online
                self._save(player)
            return player

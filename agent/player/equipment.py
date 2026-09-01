from enum import StrEnum
from typing import TYPE_CHECKING, Dict, Optional
import uuid

if TYPE_CHECKING:
    from agent.label.chara import Chara


class Rarity(StrEnum):
    """物品稀有度"""
    COMMON = "common"        # 普通
    UNCOMMON = "uncommon"    # 优秀
    RARE = "rare"            # 稀有
    EPIC = "epic"            # 史诗
    LEGENDARY = "legendary"  # 传说


class EquipmentSlot(StrEnum):
    """装备槽位"""
    WEAPON = "weapon"        # 武器
    ARMOR = "armor"          # 铠甲
    HELMET = "helmet"        # 头盔
    BOOTS = "boots"          # 靴子
    NECKLACE = "necklace"    # 项链
    RING = "ring"            # 戒指


class Equipment:
    """装备：可穿戴在装备槽上，提供属性加成。

    依赖 Chara：
      - owner：持有者引用（偷窃/交易时转移归属）
      - can_wield / required_level：针对角色的使用条件校验
      - apply_to / remove_from：将属性加成直接应用到角色的属性/抗性
    """

    # 稀有度 -> 装备等级需求
    _RARITY_REQ = {
        Rarity.COMMON: 1,
        Rarity.UNCOMMON: 3,
        Rarity.RARE: 6,
        Rarity.EPIC: 10,
        Rarity.LEGENDARY: 15,
    }

    def __init__(self, name: str, slot: EquipmentSlot, rarity: Rarity,
                 stats: Optional[Dict[str, int]] = None,
                 description: str = "", level: int = 1, item_id: Optional[str] = None,
                 owner: Optional["Chara"] = None, require: Optional[Dict[str, int]] = None):
        self.item_id = item_id or uuid.uuid4().hex[:10]
        self.name = name
        self.slot = EquipmentSlot(slot)
        self.rarity = Rarity(rarity)
        # 属性加成：键为属性名（attack/defense/speed/magic/health/strength/luck/.../fire_res 等）
        self.stats: Dict[str, int] = stats or {}
        self.description = description
        self.level = level
        # 使用需求：属性名 -> 最低数值（如 {"strength": 12}）
        self.require: Dict[str, int] = require or {}
        # 持有者：owner 为内存中的 Chara 引用；owner_name 用于 JSON 持久化
        self.owner: Optional["Chara"] = owner
        self.owner_name: Optional[str] = owner.name if owner else None

    # ---------- 持有者绑定（依赖 Chara） ----------
    def bind(self, chara: Optional["Chara"]) -> None:
        """绑定/转移装备持有者（偷窃、交易、赠送时调用）"""
        self.owner = chara
        self.owner_name = chara.name if chara else None

    def unbind(self) -> None:
        """解除持有者绑定（装备被销毁/掉落时）"""
        self.owner = None
        self.owner_name = None

    def is_owned_by(self, chara: "Chara") -> bool:
        return self.owner is chara

    # ---------- 使用条件（依赖 Chara） ----------
    @property
    def required_level(self) -> int:
        """装备等级需求：随稀有度提升"""
        return self._RARITY_REQ.get(self.rarity, 1)

    def can_wield(self, chara: "Chara", level: Optional[int] = None) -> bool:
        """该装备是否满足角色的使用条件：等级（可选）+ 属性需求"""
        if level is not None and level < self.required_level:
            return False
        for key, need in self.require.items():
            p = chara.param.params.get(key)
            if p is None or p.value < need:
                return False
        return True

    # ---------- 属性加成应用（依赖 Chara） ----------
    def apply_to(self, chara: "Chara") -> None:
        """将装备属性加成应用到角色的属性/抗性上。

        注意：若与 Player.equip 的独立加成显示（compute_stats）配合使用需避免重复计算。
        """
        for key, val in self.stats.items():
            if key in chara.param.params:
                chara.param.params[key].value += val
            elif key in chara.param.res:
                chara.param.res[key].value += val

    def remove_from(self, chara: "Chara") -> None:
        """撤销装备对角色属性/抗性的加成"""
        for key, val in self.stats.items():
            if key in chara.param.params:
                chara.param.params[key].value -= val
            elif key in chara.param.res:
                chara.param.res[key].value -= val

    def clone(self) -> "Equipment":
        """深拷贝模板（含新 item_id），用于为每个玩家实例化独立装备，避免共享对象"""
        return Equipment(
            name=self.name, slot=self.slot, rarity=self.rarity, stats=dict(self.stats),
            description=self.description, level=self.level, require=dict(self.require),
        )

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "slot": self.slot.value,
            "rarity": self.rarity.value,
            "stats": self.stats,
            "description": self.description,
            "level": self.level,
            "require": self.require,
            "required_level": self.required_level,
            "owner": self.owner_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Equipment":
        obj = cls(
            name=data["name"],
            slot=EquipmentSlot(data["slot"]),
            rarity=Rarity(data["rarity"]),
            stats=data.get("stats", {}),
            description=data.get("description", ""),
            level=data.get("level", 1),
            item_id=data.get("item_id"),
            require=data.get("require", {}),
        )
        # owner 引用由 Player.from_save 依据 owner_name 还原（Chara 无法直接反序列化）
        obj.owner_name = data.get("owner")
        return obj

    def __str__(self):
        bonus = ", ".join(f"{k}+{v}" for k, v in self.stats.items()) or "无加成"
        return f"{self.name} [{self.slot.value}/{self.rarity.value}] {bonus}"


class Inventory:
    """背包：普通物品与装备的容器"""

    def __init__(self, items: Optional[list] = None):
        self.items: list = list(items) if items else []

    def add(self, item: Equipment) -> None:
        self.items.append(item)

    def remove(self, item: Equipment) -> None:
        if item in self.items:
            self.items.remove(item)

    def get(self, item_id: str) -> Optional[Equipment]:
        for item in self.items:
            if getattr(item, "item_id", None) == item_id:
                return item
        return None

    def to_dict(self) -> list:
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_dict(cls, data: list) -> "Inventory":
        return cls([Equipment.from_dict(d) for d in data])


RARITY_META = {
    Rarity.COMMON:    {"label": "普通", "color": "#9aa4b2"},
    Rarity.UNCOMMON:  {"label": "优秀", "color": "#4caf7d"},
    Rarity.RARE:      {"label": "稀有", "color": "#4a9eff"},
    Rarity.EPIC:      {"label": "史诗", "color": "#b06cff"},
    Rarity.LEGENDARY: {"label": "传说", "color": "#ffb020"},
}

SLOT_META = {
    EquipmentSlot.WEAPON:   {"label": "武器"},
    EquipmentSlot.ARMOR:    {"label": "铠甲"},
    EquipmentSlot.HELMET:   {"label": "头盔"},
    EquipmentSlot.BOOTS:    {"label": "靴子"},
    EquipmentSlot.NECKLACE: {"label": "项链"},
    EquipmentSlot.RING:     {"label": "戒指"},
}

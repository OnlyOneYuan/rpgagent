"""游戏静态数据：种族、初始装备、任务模板"""
from agent.label.chara import RACE
from agent.label.param import ParamSet
from agent.label.talent import Talent, TalentEffect
from agent.player.equipment import Equipment, EquipmentSlot, Rarity
from agent.task.task import Task

# ==================== 种族 ====================

def _make_race(name: str, talent_defs: list) -> RACE:
    talents = [
        Talent(t_name, t_desc, [TalentEffect(param, modifier, t_desc)])
        for t_name, t_desc, param, modifier in talent_defs
    ]
    return RACE(name=name, param=ParamSet(), talents=talents)


RACES = [
    _make_race("人类", []),
    _make_race("精灵", [("精灵之智", "智力成长提升 20%", "intelligence", 0.8),
                        ("精灵之敏", "敏捷成长提升 10%", "dexterity", 0.9)]),
    _make_race("兽人", [("兽人蛮力", "力量成长提升 20%", "strength", 0.8),
                        ("兽人体魄", "沟通成长提升 10%", "communicate", 0.9)]),
    _make_race("矮人", [("矮人坚韧", "力量成长提升 10%", "strength", 0.9),
                        ("矮人福运", "幸运成长提升 15%", "luck", 0.85)]),
]


def get_race(name: str) -> RACE:
    for r in RACES:
        if r.name == name:
            return r
    return RACES[0]


# ==================== 装备模板 ====================

STARTER_EQUIPMENT = [
    Equipment("铁剑", EquipmentSlot.WEAPON, Rarity.COMMON,
              {"attack": 5}, "新手村铁匠打造的普通铁剑"),
    Equipment("皮甲", EquipmentSlot.ARMOR, Rarity.COMMON,
              {"defense": 4, "health": 10}, "坚韧的皮质护甲"),
    Equipment("铁盔", EquipmentSlot.HELMET, Rarity.COMMON,
              {"defense": 2, "health": 5}, "保护头部的铁质头盔"),
    Equipment("布靴", EquipmentSlot.BOOTS, Rarity.COMMON,
              {"speed": 3}, "轻便的布制靴子"),
    Equipment("生命戒指", EquipmentSlot.RING, Rarity.UNCOMMON,
              {"health": 25}, "蕴含生命之力的戒指"),
    Equipment("护身符", EquipmentSlot.NECKLACE, Rarity.UNCOMMON,
              {"magic": 4, "luck": 2}, "幸运护身符，佩戴者受祝福"),
]

# 背包中额外赠送的装备（用于演示装备界面换装）
BONUS_EQUIPMENT = [
    Equipment("精钢长剑", EquipmentSlot.WEAPON, Rarity.RARE,
              {"attack": 12, "speed": 2}, "锋利的精钢长剑", require={"strength": 12}),
    Equipment("秘银铠甲", EquipmentSlot.ARMOR, Rarity.RARE,
              {"defense": 9, "health": 30, "magic": 3}, "秘银打造的高级铠甲"),
    Equipment("火焰戒指", EquipmentSlot.RING, Rarity.EPIC,
              {"fire_res": 15, "magic": 6}, "蕴藏火焰之力的戒指"),
    Equipment("龙鳞项链", EquipmentSlot.NECKLACE, Rarity.EPIC,
              {"attack": 6, "fire_res": 20, "ice_res": 10}, "以龙鳞制成的珍贵项链", require={"luck": 8}),
    Equipment("风暴战靴", EquipmentSlot.BOOTS, Rarity.RARE,
              {"speed": 9, "dexterity": 3}, "注入风暴之力的战靴"),
    Equipment("圣光头盔", EquipmentSlot.HELMET, Rarity.EPIC,
              {"defense": 6, "light_res": 15, "intelligence": 4}, "沐浴圣光的头盔", require={"intelligence": 10}),
]


# ==================== 任务模板 ====================

def build_quest_templates() -> list:
    """返回一批可接取的任务（每次为玩家生成独立实例）"""
    return [
        Task("初次试炼", "前往村外的训练场，击败 3 只史莱姆，证明你的勇气。",
             reward_gold=30, reward_exp=50, reward_param={"strength": 10}),
        Task("采集草药", "为药师采集 5 株月光草，用于制作治疗药剂。",
             reward_gold=25, reward_exp=40, reward_param={"intelligence": 8}),
        Task("守护粮仓", "击退潜入粮仓的老鼠群，保护村民的过冬粮食。",
             reward_gold=40, reward_exp=60, reward_param={"dexterity": 8}),
        Task("送信任务", "将紧急信件送往邻近的村落，途中注意避开狼群。",
             reward_gold=20, reward_exp=30, reward_param={"luck": 10}),
        Task("矿洞探险", "深入废弃矿洞，带回 3 块铁矿矿石。",
             reward_gold=60, reward_exp=90, reward_param={"strength": 15, "luck": 5}),
        Task("讨伐狼王", "击败袭击商队的狼王，为民除害。",
             reward_gold=100, reward_exp=150, reward_param={"dexterity": 12, "strength": 10}),
    ]

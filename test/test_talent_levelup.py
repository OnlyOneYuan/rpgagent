from agent.label.param import ParamSet
from agent.label.talent import Talent, TalentEffect
from agent.label.chara import RACE, Chara

# 天赋：力量成长 +20%（系数 0.8）
strength_talent = Talent("大力士", "提升力量成长", [TalentEffect("strength", 0.8, "力量成长+20%")])
# 天赋：敏捷成长 +10%（系数 0.9）
speed_talent = Talent("疾风", "提升敏捷成长", [TalentEffect("dexterity", 0.9, "敏捷成长+10%")])

params = ParamSet()
params["strength"].value = 100  # 经验/数值积累

race = RACE(name="人类", param=ParamSet(), talents=[])
chara = Chara(name="测试", params=params, talents=[strength_talent], race=race)

print("初始 strength.difficult:", params["strength"].difficult, "（应为 0.8，天赋已生效）")
print("初始 dexterity.difficult:", params["dexterity"].difficult, "（应为 1.0）")

# 升级：力量 100，系数 0.8，需要 (10*0.8)**1 = 8
print("\n升级前 strength level/value:", params["strength"].level, params["strength"].value)
ok = chara.level_up("strength")
print("升级 strength:", ok)
print("升级后 strength level/value:", params["strength"].level, params["strength"].value)
print("升级后 level 应=1, value 应=92")

# 升级时取消天赋
ok = chara.remove_talent(strength_talent)
print("\n取消天赋[大力士]:", ok)
print("取消后 strength.difficult:", params["strength"].difficult, "（应为 1.0，效果已撤销）")
print("取消后天赋列表:", [t.name for t in chara.talents])

# 升级时添加天赋
ok = chara.add_talent(speed_talent)
print("\n添加天赋[疾风]:", ok)
print("添加后 dexterity.difficult:", params["dexterity"].difficult, "（应为 0.9，效果已生效）")
print("添加后天赋列表:", [t.name for t in chara.talents])

# 重复添加应失败
ok = chara.add_talent(speed_talent)
print("\n重复添加[疾风]:", ok, "（应为 False）")

# 重复取消应失败
ok = chara.remove_talent(strength_talent)
print("重复取消[大力士]:", ok, "（应为 False）")

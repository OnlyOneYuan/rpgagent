from agent.label.ability import Attribute, RES_KEYS, ResStats, RSkill


def test_ResStats_export():
    '''ResStats 由 ability.py 导出，取值与 RES_KEYS / RES_NAMES 对齐'''
    values = [r.value for r in ResStats]
    assert values == ["bleed_res", "poison_res", "disease_res", "curse_res",
                      "fire_res", "ice_res", "light_res", "dark_res"]
    assert set(values) == set(RES_KEYS.values())


def test_ParamSet_uses_ResStats():
    '''ParamSet.res 用导出的 ResStats 构建，不再 NameError'''
    from agent.label.param import ParamSet
    ps = ParamSet()
    assert set(ps.res.keys()) == set(ResStats)


def test_Ability_mix():
    '''
    test bin calculator
    '''
    ability = [i.value for i in Attribute if i]
    for i in range(len(ability) - 1):
        for j in range(i + 1, len(ability)):
            vals = ability[i] + ability[j]
            bins = ability[i] | ability[j]
            assert vals == bins


def test_RSkill_binary_attributes():
    '''技能属性以位掩码存储：组合 / 判交 / 逐位遍历'''
    skill = RSkill("焚骨毒焰", 1.5, Attribute.fire, Attribute.poison)
    assert skill.attributes == (Attribute.fire | Attribute.poison)
    assert skill.has(Attribute.fire)
    assert skill.has(Attribute.poison)
    assert not skill.has(Attribute.ice)
    # 二进制按位遍历：fire=16 在 poison=2 之前取不到，按低位->高位顺序
    assert [a.name for a in skill.each_attribute()] == ["poison", "fire"]
    # 重复传入同一属性不产生重复位（与 sum 不同，位或天然去重）
    dup = RSkill("重复", 1.0, Attribute.fire, Attribute.fire)
    assert dup.attributes == Attribute.fire


def test_RSkill_single_resistance():
    '''单属性伤害：raw × (1 - 抗性/100)，抗性越高伤害越低'''
    skill = RSkill("火球术", 2.0, Attribute.fire)
    result = RSkill.damage_calculator(skill, 100, {"fire_res": 40})
    # 100 × 2.0 × (1 - 40/100) = 120
    assert result["total"] == 120


def test_RSkill_negative_resistance():
    '''抗性为负代表弱点：伤害被放大'''
    skill = RSkill("冰锥术", 1.0, Attribute.ice)
    result = RSkill.damage_calculator(skill, 100, {"ice_res": -50})
    # 100 × (1 - (-50)/100) = 150
    assert result["total"] == 150


def test_RSkill_immune():
    '''抗性 100 及以上完全免疫'''
    skill = RSkill("暗影箭", 1.0, Attribute.dark)
    result = RSkill.damage_calculator(skill, 100, {"dark_res": 100})
    assert result["total"] == 0
    assert "免疫" in result["log"]


def test_RSkill_mixed_attributes():
    '''混合属性：总 raw 均分给每个属性位，各自结算对应抗性后求和'''
    skill = RSkill("焚骨毒焰", 2.0, Attribute.fire, Attribute.poison)
    target = {"fire_res": 50, "poison_res": 0}
    result = RSkill.damage_calculator(skill, 100, target)
    # raw=200 均分：火焰 100×(1-0.5)=50，中毒 100×1=100，合计 150
    assert result["total"] == 150
    assert len(result["parts"]) == 2


def test_RSkill_physical_defense():
    '''无属性技能视为物理打击：raw - 防御×0.6'''
    skill = RSkill("重击", 1.6)
    result = RSkill.damage_calculator(skill, 100, {"defense": 50, "name": "史莱姆"})
    # 160 - 50×0.6 = 130
    assert result["total"] == 130
    assert result["parts"][0]["attribute"] is None


def test_RSkill_multi_targets():
    '''多目标：各目标独立按自身抗性结算，返回列表'''
    skill = RSkill("火球术", 1.0, Attribute.fire)
    results = RSkill.damage_calculator(
        skill, 100, {"name": "史莱姆", "fire_res": 0}, {"name": "火龙", "fire_res": 40}
    )
    assert isinstance(results, list) and len(results) == 2
    assert results[0]["total"] == 100
    assert results[1]["total"] == 60

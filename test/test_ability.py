from agent.label.ability import Ability


def test_Ability_mix():
    '''
    test bin calculator
    '''
    vals = []
    bins = []
    ability = [i.value for i in Ability]
    for i in range(len(ability)-1):
        for j in range(i+1,len(ability)):
            vals = ability[i] + ability[j]
            bins = ability[i] | ability[j]
    assert vals == bins
    
def monty_hall_n_doors(n, switch=True, simulations=100000):
    """
    计算并模拟 n 门问题 (Monty Hall Problem) 的获胜概率。
    
    参数:
        n (int): 门的总数 (必须 >= 3)
        switch (bool): 是否选择换门
        simulations (int): 模拟运行的次数
        
    返回:
        dict: 包含理论概率和模拟概率的结果
    """
    if n < 3:
        raise ValueError("门的数量 n 必须大于等于 3")
    
    # 1. 计算理论概率
    if switch:
        # 换门策略：初始选错的概率是 (n-1)/n，主持人排除空门后，
        # 剩下的 (n-2) 扇门中包含奖品的概率集中在这 (n-2) 扇门上，
        # 随机换到其中一扇的概率是 1/(n-2)
        theoretical_prob = ((n - 1) / n) * (1 / (n - 2))
    else:
        # 不换门策略：概率等于初始选中的概率
        theoretical_prob = 1 / n
        
    # 2. 蒙特卡洛模拟
    import random
    wins = 0
    for _ in range(simulations):
        # 随机设置奖品所在的门 (0 到 n-1)
        prize_door = random.randint(0, n - 1)
        # 玩家初始选择
        initial_choice = random.randint(0, n - 1)
        
        if switch:
            # 主持人需要打开一扇空门 (不能是奖品门，也不能是玩家选的)
            # 在 n 门问题中，主持人通常只打开 1 扇空门
            available_host_doors = [
                d for d in range(n) 
                if d != prize_door and d != initial_choice
            ]
            host_opens = random.choice(available_host_doors)
            
            # 玩家从剩下的未选且未被打开的门中随机换一扇
            remaining_doors = [
                d for d in range(n) 
                if d != initial_choice and d != host_opens
            ]
            final_choice = random.choice(remaining_doors)
        else:
            # 不换门
            final_choice = initial_choice
            
        if final_choice == prize_door:
            wins += 1
            
    simulated_prob = wins / simulations
    
    return {
        "n": n,
        "strategy": "Switch" if switch else "Stay",
        "theoretical_probability": round(theoretical_prob, 6),
        "simulated_probability": round(simulated_prob, 6),
        "simulations": simulations
    }

# --- 测试示例 ---
if __name__ == "__main__":
    # 经典 3 门问题
    print("=== 经典 3 门问题 ===")
    print(monty_hall_n_doors(3, switch=True))
    print(monty_hall_n_doors(3, switch=False))
    print()
    
    # 100 门问题
    print("=== 100 门问题 ===")
    print(monty_hall_n_doors(100, switch=True))
    print(monty_hall_n_doors(100, switch=False))
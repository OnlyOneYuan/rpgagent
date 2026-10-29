from agent.runtime.pirun import PiRuntime
from agent.fight.battle import Battle

def main():
    rt = PiRuntime.instance("battle")
    rt.start()
    try:
        run_game()          # 主循环
    finally:
        rt.shutdown()

if __name__ == "__main__":
    main()

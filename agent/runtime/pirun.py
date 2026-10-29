import atexit, threading
from pathlib import Path
from agent.skill import SkillsManager

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "agent" / "skills"
def profile_dirs(profile):
    skills = SkillsManager._discover(tag=profile)
    return skills

class PiRuntime:
    """进程级 Pi 单例：拉起、探活、重启、优雅关闭。"""
    _singleton: "PiRuntime | None" = None
    _lock = threading.Lock()

    def __init__(self, profile: str = "battle"):
        self.profile = profile
        self.pi = None

    @classmethod
    def instance(cls, profile: str = "battle") -> "PiRuntime":
        with cls._lock:
            if cls._singleton is None:
                cls._singleton = cls(profile)
                atexit.register(cls._singleton.shutdown)
            return cls._singleton

    def _args(self) -> list[str]:
        args = ["--no-skills", "--no-tools"]          # 默认发现全关，只认显式清单
        for p in profile_dirs(self.profile):          # 上一轮的 profiles.json
            args += ["--skill", str(p)]
        args += ["--approve"]                         # 用到 .pi 项目资源时
        return args

    def start(self) -> None:
        if self.pi is not None:
            return
        with self._lock:
            if self.pi is None:
                from pi.rpc import PiRPC
                self.pi = PiRPC(cwd=str(ROOT), extra_args=self._args(), timeout=120)
                self.pi.new_session()
                self.pi.set_model()
                st = self.pi.get_state()              # 探活，失败直接抛
                print(f"[pi] ready: {st.get('data', {}).get('sessionFile')}")

    def alive(self) -> bool:
        return self.pi is not None and self.pi.proc.poll() is None

    def ensure(self) -> None:
        """调用前保活；崩了就重启（最多 N 次）。"""
        if self.alive():
            return
        self.shutdown()
        self.start()

    def shutdown(self) -> None:
        pi, self.pi = self.pi, None
        if pi is not None:
            pi.close()


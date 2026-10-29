import json
import os
import subprocess
import threading
import uuid
from typing import Callable, Optional
from dotenv import load_dotenv
from agent.config.setting import Paths

PI_CMD = Paths.PI
HERE = os.path.dirname(os.path.abspath(__file__))
# 用一个项目内的 agent 目录，避免污染全局 ~/.pi/agent
AGENT_DIR = os.path.join(HERE, ".pi-agent")


def write_models_json(agent_dir: str, api_base: str, model_name: str) -> None:
    """把 .env 里的 OpenAI 兼容端点注册成 Pi 的 provider。"""
    os.makedirs(agent_dir, exist_ok=True)
    cfg = {
        "$schema": "https://pi.dev/schemas/models.schema.json",
        "providers": {
            "qwen": {
                "name": "Qwen (OpenAI-compatible)",
                "baseUrl": api_base,
                "api": "openai-completions",
                "apiKey": "$QWEN_API_KEY",  # 运行时从环境变量插值
                "models": [{"id": model_name, "name": model_name}],
            }
        },
    }
    with open(os.path.join(agent_dir, "models.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class PiRPC:
    def __init__(
        self,
        cwd: Optional[str] = None,
        agent_dir: str = AGENT_DIR,
        provider: str = "qwen",
        model: Optional[str] = None,
        timeout: float = 120.0,
    ):
        load_dotenv()
        self.timeout = timeout
        self.provider = provider
        self.model = model or os.environ.get("MODEL_NAME")

        api_base = os.environ.get("API_BASE", "")
        api_key = os.environ.get("API_KEY", "")
        if self.model and api_base:
            write_models_json(agent_dir, api_base, self.model)

        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = agent_dir
        if api_key:
            env["QWEN_API_KEY"] = api_key  # 供 models.json 的 $QWEN_API_KEY 插值

        # RPC 模式下不能传 @file 参数（如 @pkg@latest），否则进程会立即退出
        self.proc = subprocess.Popen(
            [PI_CMD, "--mode", "rpc"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,  # 二进制管道：只按 LF 分帧，不会误切 U+2028/U+2029
            cwd=cwd,
            env=env,
        )
        self._callbacks: dict[str, Callable] = {}
        self._lock = threading.Lock()

        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    # ---------- 后台读取 ----------
    def _read_stdout(self):
        try:
            for raw in self.proc.stdout:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                with self._lock:
                    cb = self._callbacks.pop(record["id"], None) if record.get("id") else None
                    cbs = list(self._callbacks.items())
                if cb:
                    cb(record)
                for key, fn in cbs:
                    if key.startswith("_"):
                        fn(record)
        except (OSError, ValueError):
            pass

    def _read_stderr(self):
        try:
            for raw in self.proc.stderr:
                line = raw.decode("utf-8", "replace").rstrip()
                if line:
                    print("[pi:stderr]", line)
        except (OSError, ValueError):
            pass

    # ---------- 基础收发 ----------
    def on_event(self, cb: Callable):
        with self._lock:
            self._callbacks["_event_cb"] = cb

    def _send(self, msg: dict, timeout: Optional[float] = None) -> dict:
        req_id = msg.get("id") or uuid.uuid4().hex
        msg["id"] = req_id
        done = threading.Event()
        box: dict = {}

        with self._lock:
            code = self.proc.poll()
            if code is not None:
                raise RuntimeError(
                    f"Pi 进程已退出 (code={code})，无法发送 {msg.get('type')}；请看上面的 [pi:stderr]"
                )
            # 必须先注册回调再写，否则响应可能早于注册到达，导致永远等不到
            self._callbacks[req_id] = lambda e: (box.update(e), done.set())
            try:
                self.proc.stdin.write(json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n")
                self.proc.stdin.flush()
            except OSError as e:  # Windows 上管道已关闭会表现为 Errno 22
                self._callbacks.pop(req_id, None)
                raise RuntimeError(
                    f"写入 stdin 失败 (code={self.proc.poll()}): {e}"
                ) from e

        if not done.wait(timeout or self.timeout):
            with self._lock:
                self._callbacks.pop(req_id, None)
            raise TimeoutError(f"{msg.get('type')} (id={req_id}) 超时")
        return box

    def wait_for(self, event_type: str, timeout: Optional[float] = None) -> Optional[dict]:
        """等待某个流式事件，如 agent_settled / agent_end。"""
        key = "_wait_" + uuid.uuid4().hex
        done = threading.Event()
        box: dict = {}

        def cb(e):
            if e.get("type") == event_type:
                box.update(e)
                done.set()

        with self._lock:
            self._callbacks[key] = cb
        ok = done.wait(timeout or self.timeout)
        with self._lock:
            self._callbacks.pop(key, None)
        return box if ok else None

    # ---------- 命令 ----------
    def new_session(self, session_id: str = "default"):
        return self._send({"type": "new_session", "id": session_id})

    def set_model(self, provider: Optional[str] = None, model_id: Optional[str] = None):
        return self._send(
            {
                "type": "set_model",
                "provider": provider or self.provider,
                "modelId": model_id or self.model,
            }
        )

    def get_state(self):
        return self._send({"type": "get_state"})

    def prompt(self, message: str, req_id: Optional[str] = None):
        return self._send({"type": "prompt", "id": req_id, "message": message})

    def steer(self, message: str, req_id: Optional[str] = None):
        return self._send({"type": "steer", "id": req_id, "message": message})

    def follow_up(self, message: str, req_id: Optional[str] = None):
        return self._send({"type": "follow_up", "id": req_id, "message": message})

    def close(self):
        try:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()  # 关闭 stdin 是 RPC 的正常退出方式
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


if __name__ == "__main__":
    pi = PiRPC(cwd=r"D:\code\RPG")

    chunks: list[str] = []

    def collect(e: dict):
        # 外层只有 message_update 携带正文
        if e.get("type") != "message_update":
            return
        ev = e.get("assistantMessageEvent")
        if not isinstance(ev, dict):
            return
        # 只收正文增量，过滤 thinking_delta / usage 噪音
        if ev.get("type") == "text_delta":
            d = ev.get("delta")
            if isinstance(d, str) and d:
                chunks.append(d)
                print(d, end="", flush=True)  # 流式打字效果

    pi.on_event(collect)

    pi.new_session("weather-1")
    pi.set_model()

    resp = pi.prompt("用中文回答：请告诉我今天的天气情况。")

    answered = False
    if resp.get("success"):
        answered = pi.wait_for("agent_settled", timeout=180) is not None

    answer = "".join(chunks).strip()
    print("\n\n===== 模型回答 =====")
    print(answer if answer else "(未收到正文，可能超时)")
    print(f"\n[结束状态] settled={answered}, 字符数={len(answer)}")
    pi.close()



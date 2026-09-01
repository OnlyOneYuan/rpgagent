"""RPG 网页游戏服务器：FastAPI + REST API + WebSocket 多人联机

运行方式：
    python -m agent.web.main
然后访问 http://127.0.0.1:8000
"""
from __future__ import annotations

import os
import uuid
from typing import Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.label.chara import Chara
from agent.label.param import ParamSet
from agent.player.equipment import RARITY_META, SLOT_META
from agent.player.player import Player, PlayerManager
from agent.web.gamedata import BONUS_EQUIPMENT, RACES, STARTER_EQUIPMENT, build_quest_templates, get_race

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

app = FastAPI(title="RPG 冒险世界", version="1.0.0")
manager = PlayerManager(os.path.join(DATA_DIR, "players"))

# 会话 token -> 玩家名（内存态；重启需重新登录）
_tokens: Dict[str, str] = {}


# ==================== 请求模型 ====================

class RegisterReq(BaseModel):
    name: str
    password: str
    race: str = "人类"


class LoginReq(BaseModel):
    name: str
    password: str


class EquipReq(BaseModel):
    item_id: str


class UnequipReq(BaseModel):
    slot: str


class TrainReq(BaseModel):
    param_name: str


class StealReq(BaseModel):
    target: str


# ==================== 工具函数 ====================

def _player_or_401(token: str) -> Player:
    name = _tokens.get(token)
    if not name:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    player = manager.get(name)
    if player is None:
        raise HTTPException(status_code=404, detail="玩家不存在")
    return player


def _auth_token(authorization: str = Header(default="")) -> str:
    """从 Authorization: Bearer <token> 提取 token"""
    if authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return authorization.strip()


def _make_token(player_name: str) -> str:
    token = uuid.uuid4().hex
    _tokens[token] = player_name
    return token


# ==================== 静态页面 ====================

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ==================== 注册 / 登录 ====================

@app.post("/api/register")
def register(req: RegisterReq):
    race = get_race(req.race)
    # 种族天赋加入角色，真实生效
    talents = list(race.talents)
    chara = Chara(name=req.name, params=ParamSet(), talents=talents, race=race)
    ok, msg = manager.register(req.name, req.password, chara)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    player = manager.get(req.name)
    # 赠送初始装备与任务（clone 避免多玩家共享同一装备对象；give 绑定持有者 Chara）
    for item in STARTER_EQUIPMENT:
        player.give(item.clone())
    for item in BONUS_EQUIPMENT:
        player.give(item.clone())
    for task in build_quest_templates():
        player.add_task(task)
    manager.save(player)
    token = _make_token(player.name)
    return {"token": token, "player": player.to_dict()}


@app.post("/api/login")
def login(req: LoginReq):
    ok, msg, player = manager.login(req.name, req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    token = _make_token(player.name)
    return {"token": token, "player": player.to_dict()}


# ==================== 玩家数据 ====================

@app.get("/api/player")
def get_player(token: str = Depends(_auth_token)):
    player = _player_or_401(token)
    return {"player": player.to_dict()}


@app.post("/api/player/equip")
def equip(req: EquipReq, token: str = Depends(_auth_token)):
    player = _player_or_401(token)
    ok, msg = player.equip(req.item_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    manager.save(player)
    return {"message": msg, "player": player.to_dict()}


@app.post("/api/player/unequip")
def unequip(req: UnequipReq, token: str = Depends(_auth_token)):
    player = _player_or_401(token)
    ok, msg = player.unequip(req.slot)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    manager.save(player)
    return {"message": msg, "player": player.to_dict()}


@app.post("/api/player/steal")
async def steal(req: StealReq, token: str = Depends(_auth_token)):
    """偷窃：从目标玩家身上偷取一件物品（背包或已装备）"""
    player = _player_or_401(token)
    target = manager.get(req.target)
    if target is None:
        raise HTTPException(status_code=404, detail="目标玩家不存在")
    ok, msg, item = player.steal_from(target)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    manager.save(player)
    manager.save(target)
    if item is not None:
        # 通知所有在线玩家刷新数据（受害者/小偷的界面同步）
        await connections.broadcast({"type": "refresh", "time": now_str()})
        await connections.broadcast({
            "type": "system",
            "msg": f"🕵️ {player.name} 偷走了 {target.name} 的「{item.name}」！",
            "time": now_str(),
        })
    return {"message": msg, "player": player.to_dict(), "stolen": item.to_dict() if item else None}


@app.post("/api/player/train")
def train(req: TrainReq, token: str = Depends(_auth_token)):
    player = _player_or_401(token)
    ok, msg = player.train(req.param_name)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    manager.save(player)
    return {"message": msg, "player": player.to_dict()}


@app.post("/api/player/tasks/{task_id}/accept")
def accept_task(task_id: str, token: str = Depends(_auth_token)):
    player = _player_or_401(token)
    ok, msg = player.accept_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    manager.save(player)
    return {"message": msg, "player": player.to_dict()}


@app.post("/api/player/tasks/{task_id}/complete")
def complete_task(task_id: str, token: str = Depends(_auth_token)):
    player = _player_or_401(token)
    ok, reward, msg = player.complete_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    manager.save(player)
    return {"message": msg, "player": player.to_dict()}


# ==================== 多人 / 在线 ====================

@app.get("/api/online")
def online_players():
    players = manager.all_players()
    return {"players": [{"name": p.name, "level": p.level, "online": p.online} for p in players]}


@app.get("/api/races")
def races():
    return {"races": [{"name": r.name,
                       "talents": [{"name": t.name, "description": t.description} for t in r.talents]}
                      for r in RACES]}


@app.get("/api/meta")
def meta():
    return {
        "rarity": {k.value: v for k, v in RARITY_META.items()},
        "slots": {k.value: v for k, v in SLOT_META.items()},
        "param_names": ["communicate", "strength", "intelligence", "luck", "dexterity"],
        "res_names": ["bleed_res", "poison_res", "disease_res", "curse_res",
                      "fire_res", "ice_res", "light_res", "dark_res"],
        "param_labels": {"communicate": "沟通", "strength": "力量", "intelligence": "智力",
                         "luck": "幸运", "dexterity": "敏捷"},
        "res_labels": {"bleed_res": "流血抗性", "poison_res": "中毒抗性", "disease_res": "疾病抗性",
                       "curse_res": "诅咒抗性", "fire_res": "火焰抗性", "ice_res": "冰霜抗性",
                       "light_res": "光明抗性", "dark_res": "黑暗抗性"},
        "base_labels": {"health": "生命", "attack": "攻击", "defense": "防御",
                        "speed": "速度", "magic": "魔法"},
    }


# ==================== WebSocket 多人联机 ====================

class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}  # 玩家名 -> WebSocket

    async def broadcast(self, message: dict):
        dead = []
        for name, ws in list(self.active.items()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(name)
        for name in dead:
            self.active.pop(name, None)

    def online_names(self) -> list:
        return list(self.active.keys())


connections = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    player = _player_or_401(token) if token else None
    if player is None:
        await ws.close(code=4001, reason="未登录")
        return
    await ws.accept()
    name = player.name
    manager.set_online(name, True)
    connections.active[name] = ws
    await connections.broadcast({
        "type": "system",
        "msg": f"⚔️ {name} 加入了冒险世界",
        "time": now_str(),
    })
    await connections.broadcast({
        "type": "online",
        "players": connections.online_names(),
        "time": now_str(),
    })
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "chat":
                msg = str(data.get("msg", "")).strip()
                if msg:
                    await connections.broadcast({
                        "type": "chat",
                        "from": name,
                        "msg": msg[:200],
                        "time": now_str(),
                    })
            elif data.get("type") == "ping":
                await ws.send_json({"type": "pong", "time": now_str()})
    except WebSocketDisconnect:
        pass
    finally:
        connections.active.pop(name, None)
        manager.set_online(name, False)
        await connections.broadcast({
            "type": "system",
            "msg": f"{name} 离开了冒险世界",
            "time": now_str(),
        })
        await connections.broadcast({
            "type": "online",
            "players": connections.online_names(),
            "time": now_str(),
        })


def now_str() -> str:
    import datetime
    return datetime.datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent.web.main:app", host="127.0.0.1", port=8000, reload=True)

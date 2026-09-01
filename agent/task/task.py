from datetime import datetime
from typing import Dict, List, Optional
from enum import StrEnum
import uuid


class _due_date:

    def __init__(self, due_date: str):
        self.due_date = datetime.strptime(due_date, "%Y-%m-%d")

    def __str__(self):
        return self.due_date.strftime("%Y-%m-%d")

    def __repr__(self):
        return f"_due_date('{self.due_date.strftime('%Y-%m-%d')}')"


class TaskStatus(StrEnum):
    """任务状态"""
    AVAILABLE   = "available"   # 可接取
    ACCEPTED    = "accepted"    # 已接受/进行中
    COMPLETED   = "completed"   # 已完成
    FAILED      = "failed"      # 失败


class Task:
    def __init__(self, name: str, description: str = "", due_date: Optional[_due_date] = None,
                 result: Optional[dict] = None, reward_gold: int = 0, reward_exp: int = 0,
                 reward_param: Optional[Dict[str, int]] = None,
                 status: TaskStatus = TaskStatus.AVAILABLE, task_id: Optional[str] = None):
        self.task_id = task_id or uuid.uuid4().hex[:8]
        self.name = name
        self.description = description
        self.due_date = due_date
        self.result = result or {}
        self.reward_gold = reward_gold
        self.reward_exp = reward_exp
        self.reward_param: Dict[str, int] = reward_param or {}  # 奖励属性值，如 {"strength": 20}
        self.status = TaskStatus(status)

    def start(self) -> bool:
        """接受任务（与 accept 等价，兼容旧调用）"""
        return self.accept()

    def accept(self) -> bool:
        """接受任务，返回是否成功"""
        if self.status == TaskStatus.AVAILABLE:
            self.status = TaskStatus.ACCEPTED
            return True
        return False

    def complete(self) -> Dict[str, int]:
        """完成任务，返回发放的奖励；状态不允许时返回空奖励"""
        if self.status == TaskStatus.ACCEPTED:
            self.status = TaskStatus.COMPLETED
            return {
                "gold": self.reward_gold,
                "exp": self.reward_exp,
                "param": dict(self.reward_param),
            }
        return {"gold": 0, "exp": 0, "param": {}}

    def fail(self) -> bool:
        if self.status in (TaskStatus.AVAILABLE, TaskStatus.ACCEPTED):
            self.status = TaskStatus.FAILED
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "due_date": str(self.due_date) if self.due_date else None,
            "status": self.status.value,
            "reward_gold": self.reward_gold,
            "reward_exp": self.reward_exp,
            "reward_param": self.reward_param,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        task = cls(
            name=data["name"],
            description=data.get("description", ""),
            due_date=_due_date(data["due_date"]) if data.get("due_date") else None,
            result=data.get("result"),
            reward_gold=data.get("reward_gold", 0),
            reward_exp=data.get("reward_exp", 0),
            reward_param=data.get("reward_param", {}),
            status=TaskStatus(data.get("status", TaskStatus.AVAILABLE)),
            task_id=data.get("task_id"),
        )
        return task

    def __str__(self):
        return f"Task: {self.name}\nDescription: {self.description}\nDue Date: {self.due_date}\nPriority: {self.result}"


if __name__ == "__main__":
    task = Task("Buy groceries", "Milk, eggs, bread", _due_date("2022-12-31"), {"low": 1, "medium": 2, "high": 3})
    print(task)

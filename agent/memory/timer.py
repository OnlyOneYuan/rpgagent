import datetime
from typing import Callable, Dict, List, Optional
from agent.task.task import Task

class EventTrigger:
    """事件触发器类，用于定义事件的触发条件"""
    def __init__(self, condition: Callable[[], bool], callback: Callable[[], None]):
        """
        初始化事件触发器
        :param condition: 触发条件函数，返回布尔值
        :param callback: 触发后的回调函数
        """
        self.condition = condition
        self.callback = callback
        self.triggered = False

    def check(self) -> bool:
        """检查是否触发条件"""
        if not self.triggered and self.condition():
            self.triggered = True
            self.callback()
            return True
        return False

class Event:
    """事件类，用于表示一个游戏内事件"""
    def __init__(self, name: str, duration: int, task: Optional[Task] = None):
        """
        初始化事件
        :param name: 事件名称
        :param duration: 事件持续时间（游戏内时间单位，如秒）
        :param task: 事件对应的任务
        """
        self.name = name
        self.task = task
        self.duration = duration
        self.start_time = None
        self.end_time = None
        self.completed = False
        self.triggers: List[EventTrigger] = []  # 存储事件触发器

    def add_trigger(self, condition: Callable[[], bool], callback: Callable[[], None]) -> 'Event':
        """
        添加事件触发器
        :param condition: 触发条件函数
        :param callback: 触发后的回调函数
        :return: 事件对象，支持链式调用
        """
        self.triggers.append(EventTrigger(condition, callback))
        return self

    def check_triggers(self) -> List[EventTrigger]:
        """
        检查并触发满足条件的触发器
        :return: 触发的触发器列表
        """
        triggered_triggers = []
        for trigger in self.triggers:
            if trigger.check():
                triggered_triggers.append(trigger)
        return triggered_triggers

    def __str__(self):
        return f"Event(name='{self.name}', duration={self.duration}s, completed={self.completed})"

class GameTimer:
    """游戏计时器类，管理游戏内时间流逝和事件"""
    def __init__(self, start_time: Optional[datetime.datetime] = None):
        """
        初始化游戏计时器
        :param start_time: 游戏开始时间，默认为当前系统时间
        """
        if start_time is None:
            self.cur = datetime.datetime.now()
        else:
            self.cur = start_time
        self.events: Dict[str, Event] = {}  # 存储所有事件，以事件名为键
        self.active_events: List[Event] = []  # 存储当前活跃的事件
        self.event_history: List[Event] = []  # 存储已完成的事件历史

    def add_event(self, event: Event) -> 'GameTimer':
        """
        添加事件到游戏计时器
        :param event: 要添加的事件
        :return: 计时器对象，支持链式调用
        """
        self.events[event.name] = event
        self.active_events.append(event)
        event.start_time = self.cur
        return self

    def get_event(self, event_name: str) -> Optional[Event]:
        """
        获取指定事件
        :param event_name: 事件名称
        :return: 事件对象，如果不存在则返回None
        """
        return self.events.get(event_name)

    def advance_time(self, seconds: int) -> List[Event]:
        """
        推进游戏时间
        :param seconds: 要推进的时间（秒）
        :return: 完成的事件列表
        """
        # 计算新的游戏时间
        time_delta = datetime.timedelta(seconds=seconds)
        new_time = self.cur + time_delta
        self.cur = new_time

        # 检查活跃事件是否完成
        completed_events = []
        for event in self.active_events[:]:  # 使用切片创建副本，避免迭代时修改列表
            # 检查事件是否完成
            if self.cur >= event.start_time + datetime.timedelta(seconds=event.duration):
                event.completed = True
                event.end_time = self.cur
                completed_events.append(event)
                self.active_events.remove(event)
                self.event_history.append(event)
            
            # 检查事件的触发器
            triggered_triggers = event.check_triggers()
            if triggered_triggers:
                print(f"事件 {event.name} 触发器被触发: {[t.callback.__name__ for t in triggered_triggers]}")
        
        return completed_events

    def get_current_time(self) -> datetime.datetime:
        """获取当前游戏时间"""
        return self.cur

    def set_current_time(self, year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> 'GameTimer':
        """设置当前游戏时间"""
        self.cur = datetime.datetime(year, month, day, hour, minute, second)
        return self

    def is_event_active(self, event_name: str) -> bool:
        """检查指定事件是否正在进行"""
        return event_name in [e.name for e in self.active_events]

    def get_event_status(self, event_name: str) -> Optional[Event]:
        """获取指定事件的状态"""
        return self.events.get(event_name)

    def get_event_remaining_time(self, event_name: str) -> Optional[float]:
        """获取指定事件的剩余时间（秒）"""
        for event in self.active_events:
            if event.name == event_name:
                remaining = (event.start_time + datetime.timedelta(seconds=event.duration)) - self.cur
                return remaining.total_seconds()
        return None

    def get_active_events(self) -> List[Event]:
        """获取所有活跃事件"""
        return self.active_events

    def get_event_history(self) -> List[Event]:
        """获取所有已完成事件的历史记录"""
        return self.event_history

    def __str__(self):
        """返回当前游戏时间的字符串表示"""
        return self.cur.strftime("%Y-%m-%d %H:%M:%S")

    def __repr__(self):
        """返回游戏计时器的官方字符串表示"""
        return f"GameTimer(current_time={self.cur}, active_events={len(self.active_events)})"

# 使用示例
if __name__ == "__main__":
    # 创建游戏计时器
    game_start = datetime.datetime(2023, 1, 1, 0, 0, 0)
    timer = GameTimer(start_time=game_start)
    print(f"游戏开始时间: {timer}")

    # 创建任务和事件
    task1 = Task("任务1")
    task2 = Task("任务2")

    # 创建事件并添加触发器
    event1 = Event("任务1事件", 30, task1)
    event2 = Event("任务2事件", 45, task2)

    # 为事件添加触发器
    def condition1():
        return timer.get_current_time().hour >= 2  # 游戏时间达到2点时触发
    
    def callback1():
        print("任务1触发器被激活！")
        task1.start()
    
    def condition2():
        return timer.get_event_remaining_time("任务1事件") <= 10  # 任务1事件剩余时间少于10秒时触发
    
    def callback2():
        print("任务2触发器被激活！")
        task2.start()

    event1.add_trigger(condition1, callback1)
    event2.add_trigger(condition2, callback2)

    # 添加事件到计时器
    timer.add_event(event1).add_event(event2)
    print(f"添加事件: {event1}, {event2}")

    # 模拟游戏时间流逝
    print("\n开始模拟游戏时间流逝...")
    for i in range(20):  # 模拟20次时间推进
        # 每次推进5秒游戏时间
        completed_events = timer.advance_time(5)
        if completed_events:
            print(f"\n在 {timer} 完成: {[e.name for e in completed_events]}")
        
        print(f"当前游戏时间: {timer}")
        print(f"活跃事件: {[e.name for e in timer.active_events]}")
        
        # 显示每个活跃事件的剩余时间
        for event in timer.active_events:
            remaining = timer.get_event_remaining_time(event.name)
            print(f"{event.name} 剩余时间: {remaining}秒")

    # 检查事件状态
    print("\n事件状态:")
    print(f"任务1事件状态: {timer.get_event_status('任务1事件')}")
    print(f"任务2事件状态: {timer.get_event_status('任务2事件')}")
    print(f"任务1事件是否活跃: {timer.is_event_active('任务1事件')}")
    print(f"任务2事件是否活跃: {timer.is_event_active('任务2事件')}")

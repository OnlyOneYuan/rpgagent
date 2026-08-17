from datetime import datetime
from typing import Dict

class _due_date:

    def __init__(self, due_date: str):
        self.due_date = datetime.strptime(due_date, "%Y-%m-%d")

    def __str__(self):
        return self.due_date.strftime("%Y-%m-%d")

    def __repr__(self):
        return f"_due_date('{self.due_date.strftime('%Y-%m-%d')}')"

    


class Task:
    def __init__(self, name: str, description: str, due_date: _due_date, result: dict):
        self.name = name
        self.description = description
        self.due_date = due_date
        self.reult = result

    def __str__(self):
        return f"Task: {self.name}\nDescription: {self.description}\nDue Date: {self.due_date}\nPriority: {self.result}"


if __name__ == "__main__":
    task = Task("Buy groceries", "Milk, eggs, bread", _due_date("2022-12-31"), {"low": 1, "medium": 2, "high": 3})
    print(task)
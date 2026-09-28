# 用于处理skill调用流程（可能用dify解决）
# 目前用于测试skill

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.tools import skill_loader


p = Path(r"agent\tools\rpg-storyteller\skill.md")

a = skill_loader.parse_skill(p)


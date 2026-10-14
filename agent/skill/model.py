from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

@dataclass
class Skill:
    name: str
    description: str
    path: Path
    metadata: dict[str, Any]
    body: Optional[str] = None
    tags: list[str] = field(default_factory=list)

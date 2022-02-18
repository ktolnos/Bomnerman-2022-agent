from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass(eq=False, frozen=True)
class RunningSpeedConfig:
    steps_per_frame: int
    sleep_between_frames: Optional[float] = None
    is_step: bool = False


class RunningSpeed(Enum):
    Slow = RunningSpeedConfig(1, .5)
    Normal = RunningSpeedConfig(1)
    Fast = RunningSpeedConfig(8)
    Step = RunningSpeedConfig(1, is_step=True)

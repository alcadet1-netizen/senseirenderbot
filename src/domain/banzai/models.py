from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field

class BanzaiActionType(str, Enum):
    START = "start"
    STOP = "stop"
    STATUS = "status"
    RULES = "rules"
    ADD_TIME = "add_time"
    SET_TIME = "set_time"
    SET_REWARD = "set_reward"
    UNKNOWN = "unknown"

class BanzaiCommand(BaseModel):
    action: BanzaiActionType
    minutes: Optional[int] = None
    reward: Optional[float] = None
    chat_id: Optional[int] = None
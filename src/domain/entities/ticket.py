"""
🎫 Domain entity: Ticket.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TicketEntity:
    """Доменная сущность билета."""

    id: Optional[int] = None
    user_id: int = 0
    code: str = ""
    is_burned: bool = False
    burned_at: Optional[datetime] = None
    burn_reason: Optional[str] = None
    created_at: Optional[datetime] = None
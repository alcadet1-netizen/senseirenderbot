"""Reminders selected by the existing hourly inactivity monitor."""
from src.texts.donate_prompts import get_inactive_donate_phrase


def get_inactive_reminder() -> str:
    return get_inactive_donate_phrase()

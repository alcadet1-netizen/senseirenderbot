"""Banzai: русские подкоманды и «слепой финал» последней минуты."""

import pytest

from src.bot.parsers.banzai_parser import BanzaiCommandParser
from src.domain.banzai.models import BanzaiActionType


@pytest.mark.parametrize("text,expected", [
    ("стоп", BanzaiActionType.STOP),
    ("остановить", BanzaiActionType.STOP),
    ("статус", BanzaiActionType.STATUS),
    ("правила", BanzaiActionType.RULES),
    ("топ", BanzaiActionType.TOP),
    ("статистика", BanzaiActionType.STATS),
    ("стата", BanzaiActionType.STATS),
    ("СТОП", BanzaiActionType.STOP),
    ("stop", BanzaiActionType.STOP),
    ("stats", BanzaiActionType.STATS),
])
def test_russian_and_english_subcommands_parse(text, expected):
    assert BanzaiCommandParser.parse(text).action is expected


@pytest.mark.parametrize("text,minutes,reward", [
    ("10", 10, None),
    ("10 0.5", 10, 0.5),
    ("set_time 15", 15, None),
])
def test_start_forms_still_parse(text, minutes, reward):
    cmd = BanzaiCommandParser.parse(text)
    assert cmd.action in (BanzaiActionType.SET_TIME, BanzaiActionType.START)
    assert cmd.minutes == minutes
    assert cmd.reward == reward


def test_unknown_gibberish_stays_unknown():
    assert BanzaiCommandParser.parse("абракадабра").action is BanzaiActionType.UNKNOWN

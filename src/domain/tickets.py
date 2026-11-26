"""Shared ticket eligibility rules for the mixed historical schemas.

A ticket is an individual, coded record. Missing burn flags are normal for
older message rewards; either true flag means it has already been spent.
Uncoded aggregate records need a separate audit and are not drawable tickets.
"""


def active_ticket_filter(**extra):
    return {
        'burned': {'$ne': True},
        'is_burned': {'$ne': True},
        'code': {'$type': 'string'},
        **extra,
    }

"""Reserved native inline aliases shared by the two authenticated transports."""
HEDGEHOG_INLINE_QUERIES = frozenset({'ежа', 'ёж', 'еж', 'hedgehog'})


def is_hedgehog_inline_query(value):
    return isinstance(value, str) and value.strip().casefold() in HEDGEHOG_INLINE_QUERIES

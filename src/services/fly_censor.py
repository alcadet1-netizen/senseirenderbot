"""Mask common Russian profanity in outgoing Fly reactions, not user input."""
import re

# Match whole words with known obscene roots/prefixes, not arbitrary substrings
# (e.g. страхуй, корабля, учебник, рубля must remain intact).
_RULES = (
    (r'\b(?:на|по|ни|за|о|до)?ху[йеяюёи]\w*\b', r'х[уУ]', 'х№'),
    (r'(?<!["%#])\b(?:за|вы|до|от|под|на|по|про|пере|раз|съ|объ|въ)?[её]б\w*\b', r'б', '#'),
    (r'\b(?:за|рас|раз|на|по|от|вы|при)?пизд\w*\b', r'и', '%'),
    (r'\bбл[яе]д\w*\b|\bбля(?:ть|т|ха)?\b', r'[яе]', '*'),
    (r'\bсу(?:ка|ки|ку|кой|ке|кам|ками|ках|ч\w*)\b', r'у', '*'),
)


def censor_fly_reply(text: str) -> str:
    def mask(match, root, replacement):
        word = match.group()
        # Keep case outside the masked characters.
        return re.sub(root, lambda m: replacement.upper() if m.group().isupper() else replacement,
                      word, count=1, flags=re.IGNORECASE)

    # Requested stylistic form; handle before the general еб-root rule.
    text = re.sub(r'\bза[её]бал\w*\b',
                  lambda m: re.sub(r'(?<=з)а', '"', re.sub(r'а(?=л)', '%', m.group(), flags=re.I),
                                   count=1, flags=re.I), text, flags=re.I)
    for pattern, root, replacement in _RULES:
        text = re.sub(pattern, lambda m: mask(m, root, replacement), text, flags=re.IGNORECASE)
    return text

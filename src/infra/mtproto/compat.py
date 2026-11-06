"""Bridge pinned Telethon's friendly Message constructor to generated layer 233.

Telethon replaces generated Message/MessageService/MessageEmpty with friendly
subclasses. Regenerating the TL schema does not regenerate that friendly
constructor: from_reader passes new keywords even when their flag is absent.
Preserve new OPTIONAL fields instead of dropping them or disabling decoding.
"""
import functools
import inspect


def adapt_message_constructor(telethon):
    from telethon.tl.custom.message import Message as CustomMessage
    original = CustomMessage.__init__
    if getattr(original, '_sensei_layer233', False):
        return
    known = inspect.signature(original).parameters
    extras = {}
    for name in ('Message', 'MessageService', 'MessageEmpty'):
        patched = getattr(telethon.types, name)
        raw = next(base for base in patched.__mro__
                   if base.__module__ == 'telethon.tl.types' and base.__name__ == name)
        for key, parameter in inspect.signature(raw.__init__).parameters.items():
            if key in known:
                continue
            if parameter.default is inspect.Parameter.empty:
                raise RuntimeError('Unsupported required Message field in generated schema')
            if key in extras and extras[key] != parameter.default:
                raise RuntimeError('Incompatible Message field defaults')
            extras[key] = parameter.default

    @functools.wraps(original)
    def compatible(self, *args, **kwargs):
        fields = {key: kwargs.pop(key, default) for key, default in extras.items()}
        original(self, *args, **kwargs)
        for key, value in fields.items():
            setattr(self, key, value)

    compatible._sensei_layer233 = True
    CustomMessage.__init__ = compatible

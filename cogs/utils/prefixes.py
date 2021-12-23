import re
import typing
import discord
from cogs.utils.base import Bot


def case_insensitive_prefix(prefixes: list[str] = None, *, with_mention: bool = True):
    def inner(bot: Bot, msg: discord.Message):
        nonlocal prefixes

        _prefixes = list(prefixes) if prefixes else None

        if _prefixes is None:
            from config import PREFIXES
            _prefixes = PREFIXES

        _prefixes = list(_prefixes)  # may be a different datatype, so...

        if with_mention:
            _prefixes += [f"<@{bot.user.id}> ", f"<@!{bot.user.id}> "]

        regex = re.compile(r"^(" + r"|".join(map(re.escape, _prefixes)) + r")", flags=re.I)

        match = regex.match(msg.content)

        if match is not None:
            return match.group(1)

        return _prefixes

    return inner


class ApplyPrefix:
    def __init__(self, funcs: typing.Union[
        list[typing.Union[typing.Callable, typing.Coroutine[typing.Any, typing.Any, typing.Any]]],
        typing.Union[typing.Callable, typing.Coroutine[typing.Any, typing.Any, typing.Any]]
    ]):
        if not isinstance(funcs, list):
            self.funcs = [funcs]
        else:
            self.funcs = funcs

    async def __call__(self, bot: Bot, msg: discord.Message):
        l = []

        for func in self.funcs:
            prefix = await discord.utils.maybe_coroutine(func, bot, msg)

            if isinstance(prefix, str):
                l.append(prefix)
            elif isinstance(prefix, list):
                l += prefix
            else:
                l += list(prefix)

        return l

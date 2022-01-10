import re
import typing
import discord
from cogs.utils.base import Bot


def case_insensitive_prefix():
    def inner(bot: Bot, msg: discord.Message, prefixes: list[str] = None):
        _prefixes = list(prefixes) if prefixes else None

        if _prefixes is None:
            from config import PREFIXES
            _prefixes = PREFIXES

        _prefixes = list(_prefixes)  # may be a different datatype, so...

        regex = re.compile(r"^(" + r"|".join(map(re.escape, _prefixes)) + r")", flags=re.I)

        match = regex.match(msg.content)

        if match is not None:
            return match.group(1)

    return inner

def no_prefix_for_owner():
    async def inner(bot: Bot, msg: discord.Message):
        if await bot.is_owner(msg.author):
            return ""

    return inner


class ApplyPrefix:
    def __init__(self, prefixes: list[str] = None, *funcs: typing.Union[typing.Callable, typing.Coroutine]):
        self.prefixes = prefixes
        self.funcs = list(funcs)

    async def __call__(self, bot: Bot, msg: discord.Message):
        l = list(self.prefixes or [])

        for func in self.funcs:
            try:
                prefix = await discord.utils.maybe_coroutine(func, bot, msg, self.prefixes)
            except:
                prefix = await discord.utils.maybe_coroutine(func, bot, msg)

            if isinstance(prefix, str):
                l.append(prefix)
            elif isinstance(prefix, list):
                l += prefix
            else:
                if prefix:
                    l += list(prefix)

        return l

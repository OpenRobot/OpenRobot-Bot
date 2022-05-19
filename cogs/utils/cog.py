import discord
import inspect
from .base import Bot
from discord.ext import commands


class Cog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def _inject(self, bot):
        await super()._inject(bot)
        self.bot.dispatch("cog_load", self)

        return self

    async def _eject(self, bot):
        await super()._eject(bot)
        self.bot.dispatch("cog_unload", self)

    def __init_subclass__(cls, **kwargs):
        cls.emoji = kwargs.pop("emoji", None)
        cls.full_name = (f"{cls.emoji} " if cls.emoji else "") + cls.__cog_name__

        cls.aliases = kwargs.pop("aliases", [])

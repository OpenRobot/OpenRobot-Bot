import discord
import inspect
from .base import Bot
from discord.ext import commands

class Cog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    def cog_load(self):
        """
        A special method that is called when the cog gets loaded.

        This function **cannot** be a coroutine. It must be a regular function.

        Subclasses must replace this if they want special unloading behaviour.
        """

        pass

    def _inject(self, bot):
        super()._inject(bot)
        self.cog_load()
        self.bot.dispatch('cog_load', self)

        return self

    def _eject(self, bot):
        super()._eject(bot)
        self.bot.dispatch('cog_unload', self)

    def __init_subclass__(cls, **kwargs):
        cls.emoji = kwargs.pop('emoji', None)
        cls.full_name = (f'{cls.emoji} ' if cls.emoji else '') + cls.__cog_name__
import discord
import inspect
from discord.ext import commands
from discord.ext.commands._types import _BaseCommand

class Cog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.cog_load()

        self.cog_unload

    def cog_load(self):
        """
        A special method that is called when the cog gets loaded.

        This function **cannot** be a coroutine. It must be a regular function.

        Subclasses must replace this if they want special unloading behaviour.
        """

        pass

    def __init_subclass__(cls, **kwargs):
        cls.emoji = kwargs.pop('emoji', None)
        qualified_name = str(cls.qualified_name) # bad TypeError
        cls.full_name = (f'{cls.emoji} ' if cls.emoji else '') + qualified_name
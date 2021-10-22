import inspect
from discord.ext import commands
from discord.ext.commands._types import _BaseCommand

class Cog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def __init_subclass__(cls, **kwargs):
        cls.emoji = kwargs.pop('emoji', None)
        cls.full_name = (f'{cls.emoji} ' if cls.emoji else '') + cls.qualified_name
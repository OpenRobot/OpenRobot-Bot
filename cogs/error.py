import discord
from discord.ext import commands
from cogs.utils import Cog

class Error(Cog):
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure) and ctx.cog == self.bot.get_cog('API'):
            return
            
        await ctx.send(error)
        raise error

def setup(bot):
    bot.add_cog(Error(bot))
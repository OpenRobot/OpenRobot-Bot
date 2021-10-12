import discord
from discord.ext import commands
from cogs.utils import Cog

class Error(Cog):
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        error = getattr(error, 'original', error)

        if isinstance(error, commands.CheckFailure) and ctx.cog == self.bot.get_cog('API'):
            return
        elif isinstance(error, (commands.NotOwner, commands.CommandNotFound)):
            return
            
        module = type(error).__module__

        if not module == '__main__':
            module += '.'
        else:
            module = ''

        if module.startswith('discord.'):
            await ctx.send(error)
        else:
            await ctx.send('Error:\n' + module + type(error).__qualname__ + f': {error}')
            
        raise error

def setup(bot):
    bot.add_cog(Error(bot))
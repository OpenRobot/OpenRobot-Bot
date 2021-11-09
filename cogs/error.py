import asyncpg
import discord
import traceback_with_variables as custom_traceback
from cogs.utils import OpenRobotFormatter
import string
import random
import traceback
from discord.ext import commands
from cogs.utils import Cog

class Error(Cog):
    async def initiate_tb_pool(self):
        await self.bot.wait_until_ready() # Db is initialted when the bot is ready, so....

        if self.bot.tb_pool:
            await self.bot.error.initiate()

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        if ctx.command == self.bot.get_command('jsk dbg'):
            return
        if hasattr(ctx.command, "on_error"): 
            return
            
        error = getattr(error, 'original', error)

        if isinstance(error, (commands.NotOwner, commands.CommandNotFound)):
            return
        elif isinstance(error, commands.CheckFailure) and ctx.cog == self.bot.get_cog('API'):
            return

        report_channel = self.bot.get_channel(905631512467230790)

        colored_tb = '\n'.join(custom_traceback.iter_exc_lines(error, fmt=custom_traceback.Format(color_scheme=custom_traceback.ColorSchemes.common)))
        #non_colored_tb = '\n'.join(custom_traceback.iter_exc_lines(error, fmt=custom_traceback.Format(color_scheme=custom_traceback.ColorSchemes.none)))

        etype = type(error)
        trace = error.__traceback__

        lines = traceback.format_exception(etype, error, trace)
        original_traceback = ''.join(lines)

        print(colored_tb)

        pretty_traceback = '\n'.join(OpenRobotFormatter(no_color=True).format_exception(etype, error, trace))

        # Do paginator
        paginator = commands.Paginator(max_size=4000, prefix='```py')

        l = pretty_traceback.split('\n')

        for i in l:
            paginator.add_line(i)

        # Generate error ID for DB.
        error_id = ''

        for i in range(random.randint(5, 50)):
            error_id += random.choice(string.ascii_lowercase + string.digits)

        has_set_author = False

        if self.bot.tb_pool:
            url = f'https://traceback.openrobot.xyz/{error_id}'

            while True:
                try:
                    await self.bot.error.create(
                        user_id=ctx.author.id, 
                        error_id=error_id, 
                        guild_id=(ctx.guild.id if ctx.guild else None), 
                        channel_id=ctx.channel.id, 
                        message_id=ctx.message.id, 
                        message_jump_url=ctx.message.jump_url, 
                        pretty_traceback=pretty_traceback, 
                        original_traceback=original_traceback
                    )
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break
        else:
            url = discord.Embed.Empty

        for page in paginator.pages:
            embed = discord.Embed(color=self.bot.color, description=page)

            if (not has_set_author) and self.bot.tb_pool and url is not discord.Embed.Empty:
                embed.set_author(name=f'ID: {error_id}', url=url)
                has_set_author = True

            await report_channel.send(embed=embed)

        await ctx.send(f'Something wen\'t wrong, try again later.' + (f'\nError ID: `{error_id}`\nError: <https://traceback.openrobot.xyz/{error_id}>' if self.bot.tb_pool else ''))

def setup(bot):
    bot.add_cog(Error(bot))
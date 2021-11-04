import asyncpg
import discord
import traceback_with_variables as custom_traceback
import string
import random
import traceback
from discord.ext import commands
from cogs.utils import Cog

class Error(Cog):
    async def initiate_tb_pool(self):
        await self.bot.wait_until_ready() # Db is initialted when the bot is ready, so....

        if self.bot.tb_pool:
            await self.bot.tb_pool.execute("""
            CREATE TABLE IF NOT EXISTS tracebacks(
                user_id BIGINT,
                error_id TEXT,
                guild_id BIGINT DEFAULT NULL,
                channel_id BIGINT,
                message_id BIGNINT,
                message_jump_url TEXT,
                traceback_pretty TEXT,
                traceback_original TEXT
            );
            """)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        if hasattr(ctx.command, "on_error"): 
            return
            
        error = getattr(error, 'original', error)

        if isinstance(error, (commands.NotOwner, commands.CommandNotFound)):
            return
        elif isinstance(error, commands.CheckFailure) and ctx.cog == self.bot.get_cog('API'):
            return

        report_channel = self.bot.get_channel(905631512467230790)

        colored_tb = '\n'.join(custom_traceback.iter_exc_lines(error, format=custom_traceback.Format(color_scheme=custom_traceback.ColorSchemes.common)))
        non_colored_tb = '\n'.join(custom_traceback.iter_exc_lines(error, format=custom_traceback.Format(color_scheme=custom_traceback.ColorSchemes.none)))

        etype = type(error)
        trace = error.__traceback__

        lines = traceback.format_exception(etype, error, trace)
        traceback_original = ''.join(lines)

        print(colored_tb)

        # Do paginator
        paginator = commands.Paginator(max_size=4000)

        l = non_colored_tb.split('\n')

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
                    await self.bot.tb_pool.execute("""
                    INSERT INTO tracebacks VALUES($1, $2, $3, $4, $5, $6, $7, $8)
                    """, ctx.author.id, error_id, (ctx.guild.id if ctx.guild else None), ctx.channel.id, ctx.message.id, ctx.message.jump_url, non_colored_tb, traceback_original)
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break
        else:
            url = discord.Embed.Empty

        for page in paginator.pages:
            embed = discord.Embed(color=self.bot.color, description='```py\n' + page + '```')

            if (not has_set_author) and self.bot.tb_pool and url is not discord.Embed.Empty:
                embed.set_author(name=f'ID: {error_id}', url=url)
                has_set_author = True

            await report_channel.send(embed=embed)

        await ctx.send(f'Something wen\'t wrong, try again later.' + (f'\nError ID: `{error_id}`\nError: <https://traceback.openrobot.xyz/{error_id}>' if self.bot.tb_pool else ''))

def setup(bot):
    bot.add_cog(Error(bot))
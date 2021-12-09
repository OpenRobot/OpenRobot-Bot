import asyncpg
import string
import random
import traceback
import re
import discord
import contextlib
import asyncio
import copy
from discord.ext import commands
from cogs.utils import Cog
from cogs.utils import OpenRobotFormatter
import traceback_with_variables as custom_traceback


class MissingButton(discord.ui.Button):
    def __init__(
        self,
        error: commands.MissingRequiredArgument,
        embed: discord.Embed,
        *args,
        **kwargs,
    ):
        ctx = kwargs.pop("ctx")

        super().__init__(*args, **kwargs)
        self.error = error
        self.embed = embed
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        ctx = self.ctx
        param = self.error.param
        m = f"Please enter your argument for `{param.name}`."
        await interaction.response.edit_message(content=m, embed=None, view=None)

        def check(m: discord.Message) -> bool:
            return m.author == ctx.author and m.channel == ctx.channel

        with contextlib.suppress(asyncio.TimeoutError):
            message = await ctx.bot.wait_for("message", check=check, timeout=60)
            new_message = copy.copy(ctx.message)
            new_message.content += f" {message.content}"
            await ctx.bot.process_commands(new_message)


class View(discord.ui.View):
    async def on_timeout(self) -> None:
        await self.message.delete()


class Error(Cog):
    IGNORED_ERRORS = (commands.NotOwner, commands.CommandNotFound)

    async def initiate_tb_pool(self):
        await self.bot.wait_until_ready()  # Db is initialted when the bot is ready, so....

        if self.bot.tb_pool:
            await self.bot.error.initiate()

    async def generate_missing_required_argument(
        self, ctx: commands.Context, error: commands.MissingRequiredArgument
    ):
        command = ctx.command
        param_name = error.param.name

        signature = command.signature
        sig_split = signature.split(" ")

        end = None
        spaces = 0

        for arg in sig_split:
            if param_name == re.sub(r"<|>|\[|\]", "", arg) or param_name == arg[1:-1]:
                end = spaces + len(arg)
                break

            spaces += 1

        if end is None:
            return None

        signature += (
            "\n"
            + "\u200b " * len(f"{ctx.prefix}{command.qualified_name} ")
            + "\u200b " * spaces
            + "^" * end
        )

        final_signature = f"{ctx.prefix}{command.qualified_name} {signature}"

        return final_signature

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        if ctx.command == self.bot.get_command("jsk dbg"):
            return
        if ctx.command.has_error_handler():
            return
        if cog := ctx.cog:
            if cog.has_error_handler():
                return

        error = getattr(error, "original", error)

        if isinstance(error, self.IGNORED_ERRORS):
            return
        elif isinstance(error, commands.CheckFailure) and ctx.cog == self.bot.get_cog(
            "API"
        ):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            signature = await self.generate_missing_required_argument(ctx, error)

            if signature is None:
                return await ctx.send(
                    f"Missing required argument: `{error.param.name}`. Maybe take a look at the help command by doing `{ctx.prefix}help {ctx.command.qualified_name}`."
                )

            embed = discord.Embed(color=self.bot.color)

            embed.description = f"Missing required argument: `{error.param.name}`. Maybe take a look at the help command by doing `{ctx.prefix}help {ctx.command.qualified_name}`."

            embed.set_footer(
                text=f"Command invoked by: {ctx.author}", icon_url=ctx.author.avatar.url
            )

            embed.description += f"\n\n**Errored At:** ```prolog\n{signature}```"

            view = View(timeout=60)

            async def interaction_check(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message(
                        "This is not your interaction!", ephemeral=True
                    )
                    return False

                return True

            view.interaction_check = interaction_check

            view.add_item(
                MissingButton(
                    error,
                    embed,
                    ctx=ctx,
                    style=discord.ButtonStyle.green,
                    label=f"Enter required argument for '{error.param.name}'",
                )
            )

            view.message = await ctx.send(embed=embed, view=view)

            return

        report_channel = self.bot.get_channel(905631512467230790)

        colored_tb = "\n".join(
            custom_traceback.iter_exc_lines(
                error,
                fmt=custom_traceback.Format(
                    color_scheme=custom_traceback.ColorSchemes.common
                ),
            )
        )

        etype = type(error)
        trace = error.__traceback__

        lines = traceback.format_exception(etype, error, trace)
        original_traceback = "".join(lines)

        #pretty_traceback = "\n".join(
            #OpenRobotFormatter(no_color=True).format_exception(error)
        #)
        pretty_traceback = original_traceback

        paginator = commands.Paginator(max_size=4000, prefix="```py")

        l = pretty_traceback.split("\n")

        for i in l:
            paginator.add_line(i)

        error_id = ""

        for i in range(random.randint(5, 50)):
            error_id += random.choice(string.ascii_lowercase + string.digits)

        has_set_author = False

        if self.bot.tb_pool:
            url = f"https://traceback.openrobot.xyz/{error_id}"

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
                        original_traceback=original_traceback,
                    )
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break
        else:
            url = discord.Embed.Empty

        for page in paginator.pages:
            embed = discord.Embed(color=self.bot.color, description=page)

            if (
                (not has_set_author)
                and self.bot.tb_pool
                and url is not discord.Embed.Empty
            ):
                embed.set_author(name=f"ID: {error_id}", url=url)
                has_set_author = True

            await report_channel.send(embed=embed)

        embed = discord.Embed(color=self.bot.color, title="Error:")

        embed.description = f"```\n{error}```"

        await ctx.send(embed=embed)

        raise error


def setup(bot):
    bot.add_cog(Error(bot))
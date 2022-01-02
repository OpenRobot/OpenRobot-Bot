# Inspired by (Credits to):
# - https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96
# - https://github.com/InterStella0/stella_bot/blob/master/cogs/helpful.py#L167-L361
# - https://mystb.in/EthicalBasketballPoliticians.python
# - LyricMaster#9688 (My old bot) Help Command

import discord
import contextlib
from discord.ext import commands
from cogs.utils import Cog


class OpenRobotHelp(commands.HelpCommand):
    def __init__(self, **options):
        self.options = {"command_attrs": {}, "verify_checks": True, "show_hidden": True}
        self.options.update(options)

        super().__init__(**self.options)

        self.no_category = self.options.get("no_category", "Miscellaneous")
        self.no_category_description = self.options.get(
            "no_category_description", "No description provided."
        )
        self.no_category_emoji = self.options.get("no_category_emoji", "")
        self.no_category_aliases = list(self.options.get("no_category_aliases", []))

    async def send(self, *args, **kwargs):
        return await self.get_destination().send(*args, **kwargs)

    @property
    def ending_note(self):
        return "Use help [command] or help [category] for more information | <> is required | [] is optional"

    @property
    def ctx(self):
        return self.context

    def generate_embed(self):
        ctx = self.ctx

        embed = discord.Embed()

        # Fancy stuff
        embed.color = ctx.bot.color
        embed.timestamp = discord.utils.utcnow()

        embed.set_author(name=f"{ctx.me.name} Help:", icon_url=ctx.author.avatar.url)
        embed.set_thumbnail(url=ctx.me.avatar.url)

        embed.set_footer(text=self.ending_note)

        embed.description = ""

        return embed

    async def send_bot_help(self, mapping: dict[Cog | None, commands.Command]):
        ctx = self.ctx

        embed = self.generate_embed()

        # Do the help command
        useable = 0

        for cog, commands in mapping.items():
            # Only display useable commands. If no commands are useable in that cog, we don't want to display it
            if filtered_commands := await self.filter_commands(commands):
                amount_commands = len(filtered_commands)
                useable += amount_commands

                if cog:
                    name = getattr(cog, "full_name", cog.qualified_name)
                    description = cog.description or "No description provided."
                else:
                    name = (
                        f"{self.no_category_emoji} " if self.no_category_emoji else ""
                    ) + self.no_category
                    description = self.no_category_description

                embed.add_field(name=f"{name} [{amount_commands}]", value=description)

        embed.description = f"{ctx.bot.description}\n\n{len(ctx.bot.commands)} commands | {useable} usable"

        embed.set_image(url=ctx.bot.banner)

        return await self.send(embed=embed)

    def get_command_example(self, command):
        def _get_original_example():
            s = command.qualified_name

            if usage := command.usage:
                s += f" {usage}"

            return s

        return getattr(command, "example", _get_original_example())

    async def get_command_help(self, command: commands.Command):
        ctx = self.ctx

        signature = self.get_command_signature(
            command
        )  # get_command_signature gets the signature of a command in <required> [optional]
        embed = self.generate_embed()

        embed.title = command.qualified_name.title() + " Command"

        embed.description = f"""
        ```yml
{signature}```"""

        embed.description += command.help or ""

        if command.aliases:
            embed.add_field(
                name=f"{len(command.aliases)} Aliases:",
                value="- " + "\n- ".join([f"`{alias}`" for alias in command.aliases]),
                inline=False,
            )

        if cog := command.cog:
            embed.add_field(
                name="Category:",
                value=getattr(cog, "full_name", cog.qualified_name),
                inline=False,
            )
        else:
            embed.add_field(
                name="Category:",
                value=(self.no_category_emoji + ' ' if self.no_category_emoji else '') + self.no_category,
                inline=False,
            )

        embed.add_field(
            name="Example:",
            value=f"```yml\n{ctx.prefix}{self.get_command_example(command)}\n```",
            inline=False,
        )

        if (bucket := command._buckets) and (
            cooldown := command._buckets._cooldown
        ):  # use of internals to get the cooldown of the command
            embed.add_field(
                name="Cooldown",
                value=f"`{cooldown.rate}` command per `{cooldown.per:.0f} seconds`"
                f"for each `{bucket.type.name.title()}`",
                inline=False,
            )

        if (
            max_concurrency := command._max_concurrency
        ):  # use of internals to get the cooldown of the command
            embed.add_field(
                name="Concurrency",
                value=f"`{max_concurrency.number}` command(s) at once per `{max_concurrency.per.name.title()}`",
                inline=False,
            )

        if isinstance(command, commands.Group):
            subcommands = command.commands

            if subcommands:
                filtered_subcommands = await self.filter_commands(subcommands)

                if filtered_subcommands:
                    value = "\n".join(
                        [f"`{subcommand}`" for subcommand in filtered_subcommands]
                    )
                    embed.add_field(name="Subcommand(s):", value=value, inline=False)

        can_run = "<:no:597591030807920660>"
        # command.can_run to test if the cog is usable
        with contextlib.suppress(commands.CommandError):
            if await command.can_run(ctx):
                can_run = "<:yes:597590985802907658>"

        embed.add_field(name="Usable:", value=can_run, inline=False)

        return await self.send(embed=embed)

    async def send_cog_help(self, cog: Cog | None):  # None is for No Category help
        ctx = self.ctx

        if cog is None:
            filtered = await self.filter_commands(
                filter(lambda c: c.cog is None, ctx.bot.commands)
            )
        else:
            filtered = await self.filter_commands(cog.get_commands())

        if not filtered:
            return await self.send(
                "You don't have perms to view the help for this category!"
            )

        embed = self.generate_embed()

        if cog is None:
            embed.title = self.no_category_emoji + " `" + self.no_category + "`"
        else:
            embed.title = cog.emoji + " `" + cog.qualified_name + "`"

        embed.title += " Category:"

        if cog is None:
            embed.description = (
                self.no_category_description + "\n\n"
                if self.no_category_description
                else ""
            )
        else:
            embed.description = cog.description + "\n\n" if cog.description else ""

        if cog:
            embed.description += (
                f"Aliases: {', '.join([f'`{x}`' for x in cog.aliases])}"
                if cog.aliases
                else ""
            )
        else:
            embed.description += (
                f"Aliases: {', '.join([f'`{x}`' for x in self.no_category_aliases])}"
                if self.no_category_aliases
                else ""
            )

        embed.description += ", ".join(
            [f"`{command.qualified_name}`" for command in filtered]
        )

        return await self.send(embed=embed)

    async def handle_help(self, command: commands.Command):
        with contextlib.suppress(commands.CommandError):
            await command.can_run(self.context)
            return await self.get_command_help(command)

        return await self.ctx.send(
            "You don't have perms to view the help for this command!"
        )

    async def send_group_help(self, group: commands.Group):
        return await self.handle_help(group)

    async def send_command_help(self, command: commands.Command):
        return await self.handle_help(command)

    # Embed error message
    async def send_error_message(self, error):
        return await self.send(
            embed=discord.Embed(color=self.ctx.bot.color, description=error)
        )

    async def command_callback(self, ctx, *, command=None):
        if command == self.no_category:
            return await self.send_cog_help(None)
        elif command in self.no_category_aliases:
            return await self.send_cog_help(None)

        for cog in ctx.bot.cogs.values():
            if command in cog.aliases:
                return await self.send_cog_help(cog)

        return await super().command_callback(ctx, command=command)


class Help(Cog, emoji="<:help:901151299284922369>"):
    """
    The help command for the bot.
    """

    def cog_load(self):
        self._original_help_command = self.bot.help_command
        self.bot.help_command = OpenRobotHelp(
            command_attrs={
                "help": "Shows this help command message.",
                "aliases": ["h", "?"],
            }
        )
        self.bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command
        self.bot.help_command.cog = self


def setup(bot):
    bot.add_cog(Help(bot))

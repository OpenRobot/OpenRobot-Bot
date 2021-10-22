# Inspired by (Credits to):
# - https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96
# - https://github.com/InterStella0/stella_bot/blob/master/cogs/helpful.py#L167-L361
# - https://mystb.in/EthicalBasketballPoliticians.python
# - LyricMaster#9688 (My old bot) Help Command

import discord
import typing
import contextlib
from discord.ext import commands
from cogs.utils import Cog

class OpenRobotHelp(commands.HelpCommand):
    def __init__(self, **options):
        self.options = {
            'command_attrs': {
                'help': 'The help command',
                'aliases': [
                    'cooldown'
                ]
            },
            'verify_checks': True,
            'show_hidden': True
        }
        self.options.update(options)

        super().__init__(
            **self.options
        )

        self.no_category = self.options.get('no_category') or 'Miscellaneous'
        self.no_category_description = self.options.get('no_category_description') or 'Commands with no category'
        
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

        embed.set_author(name=f'{ctx.me.name} Help:', icon_url=ctx.author.avatar.url)
        embed.set_thumbnail(url=ctx.me.avatar.url)

        embed.set_footer(text=self.ending_note)

        embed.description = ''

        return embed

    async def send_bot_help(self, mapping: typing.Dict[typing.Optional[Cog], commands.Command]):
        ctx = self.ctx

        embed = self.generate_embed()

        # Do the help command

        for cog, commands in mapping.items():
            useable = 0

            # Only display useable commands. If no commands are useable in that cog, we don't want to display it
            if filtered_commands := await self.filter_commands(commands): 
                amount_commands = len(filtered_commands)
                useable += amount_commands

                if cog:
                    name = cog.full_name
                    description = cog.description or "No description provided."
                else:
                    name = self.no_category
                    description = self.no_category_description

                embed.add_field(name=f'{name} [{len(amount_commands)}]', value=cog.description)

        embed.description = f"{len(ctx.bot.commands)} commands | {useable} usable"

        return await self.send(embed=embed)

    async def get_command_help(self, command: commands.Command):
        ctx = self.ctx

        signature = self.get_command_signature(command) # get_command_signature gets the signature of a command in <required> [optional]
        embed = self.generate_embed()

        embed.title = command.qualified_name.title() + ' Command'

        embed.description = f"""
        ```yml
        {signature}```"""

        embed.description += command.help or ''

        if command.aliases:
            embed.add_field(name=f'{len(command.aliases)} Aliases:', value='- ' + '\n- '.join([f'`{alias}`' for alias in command.aliases]), inline=False)

        if cog := command.cog:
            embed.add_field(name="Category:", value=cog.full_name, inline=False)

        can_run = "<:no:597591030807920660>"
        # command.can_run to test if the cog is usable
        with contextlib.suppress(commands.CommandError):
            if await command.can_run(ctx):
                can_run = "<:yes:597590985802907658>"
            
        embed.add_field(name="Usable:", value=can_run, inline=False)

        if command._buckets and (cooldown := command._buckets._cooldown): # use of internals to get the cooldown of the command
            embed.add_field(
                name="Cooldown",
                value=f"{cooldown.rate} per {cooldown.per:.0f} seconds",
                inline=False
            )

        if isinstance(command, commands.Group):
            subcommands = command.commands
            value = "\n".join([f'{subcommand}' for subcommand in subcommands])
            embed.add_field(name='Subcommand(s):', value=value, inline=False)

        return await self.send(embed=embed)

    async def send_cog_help(self, cog: Cog):
        ctx = self.ctx

        embed = self.generate_embed()

        embed.title = cog.qualified_name

        embed.description = ', '.join([f'`{command}`' for command in self.filter_commands(cog.get_commands())])

        return await self.send(embed=embed)

    async def handle_help(self, command: commands.Command):
        with contextlib.suppress(commands.CommandError):
            await command.can_run(self.context)
            return await self.get_command_help(command)

        return await self.ctx.send('Youu don\'t have perms to view the help for this command!')

    async def send_group_help(self, group: commands.Group):
        return await self.handle_help(group)

    async def send_command_help(self, command: commands.Command):
        return await self.handle_help(command)

    # Embed error message
    async def send_error_message(self, error):
        return await self.send(embed=discord.Embed(color=self.ctx.bot.color, description=error))

class Help(Cog, emoji='<:help:901151299284922369>'):
    def cog_load(self):
        self._original_help_command = self.bot.help_command
        self.bot.help_command = OpenRobotHelp()
        self.bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command
        self.bot.help_command.cog = self

def setup(bot):
    bot.add_cog(Help(bot))
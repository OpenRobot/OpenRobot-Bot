import discord
from discord.ext import commands
from cogs.utils import (
    Cog,
    group,
    Command,
    Context,
    repi,
)


class RePI(Cog):
    """
    [RePI](https://repi.openrobot.xyz) API Management. Owner-Only commands.
    """

    @group(name="repi", invoke_without_command=True)
    @repi.is_admin()
    async def repi_cmd(self, ctx: Context):
        """
        [RePI](https://repi.openrobot.xyz) API Management. Owner-Only commands.
        """

        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command)

    @repi_cmd.command(name="ban", cls=Command, example="repi ban Insert-IP-Here")
    async def ip_ban(self, ctx: Context, ip: str):
        """
        IP bans an IP from accessing the API.
        """

        async with self.bot.session.get('https://repi.openrobot.xyz/admin/ban',
                                        params={'ip': ip, 'key': self.bot.config.REPI_CRIDENTIALS['key']},
                                        headers={'Authorization': self.bot.config.REPI_CRIDENTIALS['token']}) as resp:
            if resp.status == 200:
                return await ctx.send(f"IP banned `{ip}` successfully.")
            else:
                return await ctx.send(f"Failed to ban IP `{ip}`.")

    @repi_cmd.command(name="unban", cls=Command, example="repi unban Insert-IP-Here")
    async def ip_unban(self, ctx: Context, ip: str):
        """
        IP unbans an IP from accessing the API.
        """

        async with self.bot.session.get('https://repi.openrobot.xyz/admin/ban',
                                        params={'ip': ip, 'key': self.bot.config.REPI_CRIDENTIALS['key']},
                                        headers={'Authorization': self.bot.config.REPI_CRIDENTIALS['token']}) as resp:
            if resp.status == 200:
                return await ctx.send(f"IP unbanned `{ip}` successfully.")
            else:
                return await ctx.send(f"Failed to unban IP `{ip}`.")


def setup(bot):
    bot.add_cog(RePI(bot))

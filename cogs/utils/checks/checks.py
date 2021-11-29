from discord.ext import commands
from .error import *


def is_guild_owner():
    def predicate(ctx):
        if ctx.guild.owner:
            return ctx.author == ctx.guild.owner
        else:
            return ctx.author.id == ctx.guild.owner_id

    return commands.check(predicate)


class api:
    @classmethod
    def has_applied(cls, *, applied_tokens=False):
        table = "applied_tokens" if applied_tokens else "tokens"

        async def predicate(ctx):
            if not await ctx.bot.pool.fetchrow(
                f"SELECT * FROM {table} WHERE user_id = $1", ctx.author.id
            ):
                raise APIHasNotApplied("You have not applied for the API.")

            return True

        return commands.check(predicate)

    @classmethod
    def has_not_applied(cls, *, applied_tokens=True):
        table = "applied_tokens" if applied_tokens else "tokens"

        async def predicate(ctx):
            if await ctx.bot.pool.fetchrow(
                f"SELECT * FROM {table} WHERE user_id = $1", ctx.author.id
            ):
                raise APIHasApplied("You already applied for the API.")

            return True

        return commands.check(predicate)

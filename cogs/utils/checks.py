from discord.ext import commands

def is_guild_owner():
    def predicate(ctx):
        if ctx.guild.owner:
            return ctx.author == ctx.guild.owner
        else:
            return ctx.author.id == ctx.guild.owner_id

    return commands.check(predicate)
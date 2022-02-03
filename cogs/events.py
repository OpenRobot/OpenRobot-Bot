import discord
from cogs.utils import Cog
from discord.ext import commands

class Events(Cog):
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        self.bot.sent_messages += 1

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        self.bot.edited_messages += 1

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        self.bot.deleted_messages += len(payload.message_ids)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        self.bot.deleted_messages += 1

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        self.bot.commands_invoked += 1

def setup(bot):
    bot.add_cog(Events(bot))
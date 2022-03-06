import base64
import random
import discord
import asyncpg
from cogs.utils import Cog
from discord.ext.ipc import server
from discord.ext import commands, ipc
from secrets import token_urlsafe as generate_token


class IPCRoutes(Cog):
    @server.route("api-get_token")
    async def api_get_token(self, data):
        userid = data.user_id

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", userid
                )
                if not db:
                    return None
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        return db["token"]

    @server.route("api-apply_submit")
    async def api_apply_submit(self, data):
        userid = data.user_id
        reason = data.reason

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", userid
                )
                if db:
                    return db["token"]
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        user = self.bot.get_user(userid) or await self.bot.fetch_user(userid)
        chan = self.bot.get_channel(857048848900030484)

        embed = discord.Embed()
        embed.color = self.bot.color
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        embed.set_footer(text=f"ID: {user.id}")
        embed.timestamp = discord.utils.utcnow()
        newline = "\n"
        embed.description = f"""
**Reason:** {discord.utils.escape_markdown(reason)}

__**Info:**__
- Username: {user}
- User ID: {user.id}

Method: Requested from API Website.
        """

        await chan.send(embed=embed)

        # Token Generator:
        # tokens = []
        #
        # username_base64 = base64.urlsafe_b64encode(str(user.id).encode("utf-8")).decode(
        #     "utf-8"
        # )
        # tokens.append(username_base64)
        #
        # secret = generate_token(random.randint(25, 50))
        # tokens.append(secret)
        #
        # secret = generate_token(random.randint(25, 50))
        # tokens.append(secret)
        #
        # token = ".".join(tokens)

        token = generate_token(random.randint(35, 75))

        # Add token to db
        while True:
            try:
                await self.bot.pool.execute(
                    "INSERT INTO tokens(user_id, token) VALUES($1, $2)",
                    user.id,
                    token,
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        return token

    @server.route("api-regenerate_token")
    async def api_regenerate_token(self, data):
        userid = data.user_id

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", userid
                )
                if not db:
                    return None
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        return db["token"]


def setup(bot):
    bot.add_cog(IPCRoutes(bot))

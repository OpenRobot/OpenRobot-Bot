import base64
import random
import re
import discord
import aiohttp
import asyncpg
import json
import datetime
import humanize
from secrets import token_urlsafe as generate_token
from discord.ext import commands
from cogs.utils import (
    Cog,
    LegacyFlagItems,
    LegacyFlagConverter,
    FlagConverter,
    APIInfoPaginator,
    MenuPages,
    IPBanListPaginator,
    checks,
    group,
    command,
    Group,
    Command,
)
from thefuzz import process


class APIDenyFlag(FlagConverter):
    user: discord.User
    reason: str = None


class APIIPBan(FlagConverter):
    ip: str
    reason: str = None


class API(Cog, emoji="<:OpenRobotLogo:901132699241168937>"):
    """
    Provide Utility commands for OpenRobot API
    """

    async def cog_check(self, ctx) -> bool:
        if ctx.bot.pool is None:
            return False

        return True

    # def cog_load(self):
    # task = self.bot.loop.create_task(self.api_status_task())
    # task.add_done_callback(self.exception_catching_callback)

    async def api_status_task(self):
        await self.bot.wait_until_ready()

        await self.bot.pool.execute(
            """
        CREATE TABLE IF NOT EXISTS api_status(
            guild_id BIGINT UNIQUE,
            channel_id BIGINT UNIQUE,
            last_updated_status BOOLEAN DEFAULT NULL,
            time_last_updated_status TIMESTAMP DEFAULT NULL
        );
        """
        )

        up_embed = discord.Embed(
            color=discord.Colour.green(),
            title="OpenRobot API Status:",
            description="OpenRobot API (<https://api.openrobot.xyz>) is now up!",
        ).set_footer(text="Uptime at")

        down_embed = discord.Embed(
            color=discord.Colour.red(),
            title="OpenRobot API Status:",
            description="OpenRobot API (<https://api.openrobot.xyz>) is currently down!",
        ).set_footer(text="Downtime at")

        while True:
            up_embed.timestamp = discord.utils.utcnow()
            down_embed.timestamp = discord.utils.utcnow()

            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as sess:
                    async with sess.get(
                        "https://api.openrobot.xyz/_internal/available"
                    ) as resp:
                        is_available = (await resp.json())["is_available"]
            except:
                is_available = False

            while True:
                try:
                    db = await self.bot.pool.fetch("SELECT * FROM api_status")
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break

            for record in db:
                data = dict(record)

                # TODO: maybe use Bot.get_channel instead.

                guild = self.bot.get_guild(data["guild_id"])

                if guild:
                    chan = guild.get_channel(data["channel_id"])

                    if chan:
                        if (
                            (data["last_updated_status"] is not None)
                            and (data["last_updated_status"] != is_available)
                            and (is_available is True)
                        ):
                            embed = up_embed.copy()

                            if data["time_last_updated_status"]:
                                embed.description += f'\nIt was down for `{humanize.precisedelta(embed.timestamp - data["time_last_updated_status"])}`.'

                            await chan.send(embed)

                            while True:
                                try:
                                    await self.bot.pool.execute(
                                        """
                                    UPDATE api_status
                                    SET last_updated_status = $3,
                                        time_last_updated_status = $4
                                    WHERE guild_id = $1 AND channel_id = $2
                                    """,
                                        guild.id,
                                        chan.id,
                                        is_available,
                                        embed.timestamp,
                                    )
                                except asyncpg.exceptions._base.InterfaceError:
                                    pass
                                else:
                                    break
                        elif (data["last_updated_status"] != is_available) and (
                            is_available is False
                        ):
                            embed = down_embed.copy()

                            await chan.send(embed=embed)

                            while True:
                                try:
                                    await self.bot.pool.execute(
                                        """
                                    UPDATE api_status
                                    SET last_updated_status = $3,
                                        time_last_updated_status = $4
                                    WHERE guild_id = $1 AND channel_id = $2
                                    """,
                                        guild.id,
                                        chan.id,
                                        is_available,
                                        embed.timestamp,
                                    )
                                except asyncpg.exceptions._base.InterfaceError:
                                    pass
                                else:
                                    break

    def exception_catching_callback(self, task):
        if task.exception():
            task.print_stack()

    async def cog_command_error(self, ctx, error: Exception) -> None:
        if isinstance(error, commands.NotOwner):
            return
        elif isinstance(error, commands.CheckFailure):
            return await ctx.send(
                "The API seems to be unavailable for some reason, and I may not run commands."
            )

    @group(invoke_without_command=True, example="api")
    async def api(self, ctx: commands.Context):
        """The base API Group Command."""

        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command)

    @api.command("status", cls=Command, example="api status")
    async def api_status(
        self,
        ctx: commands.Context  # ,
        # channel: discord.TextChannel = commands.Option(
        # None, description="Use that channel for OpenRobot API Status updates."
        # ),
    ):
        """
        API status.
        """

        up_embed = discord.Embed(
            color=discord.Colour.green(),
            title="OpenRobot API Status:",
            description="OpenRobot API (<https://api.openrobot.xyz>) is currently up!",
        )

        down_embed = discord.Embed(
            color=discord.Colour.red(),
            title="OpenRobot API Status:",
            description="OpenRobot API (<https://api.openrobot.xyz>) is currently down!",
        )

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as sess:
                async with sess.get(
                    "https://api.openrobot.xyz/_internal/available"
                ) as resp:
                    is_available = (await resp.json())["is_available"]
        except Exception as e:
            if ctx.debug:
                raise e

            is_available = False

        if is_available is False:
            return await ctx.send(embed=down_embed)
        else:
            return await ctx.send(embed=up_embed)

    # @api.command('disable')
    async def api_status_disable(self, ctx: commands.Context):
        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM api_status WHERE guild_id = $1", ctx.guild.id
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        if not db:
            return await ctx.send("You have not activated API status.")

        while True:
            try:
                await self.bot.pool.execute(
                    """
                DELETE FROM api_status
                WHERE guild_id = $1
                """,
                    ctx.guild.id,
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

    @api.command("stats", aliases=["statistics"], cls=Command, example="api stats")
    async def api_stats(self, ctx: commands.Context):
        class SelectOption(discord.SelectOption):
            def __init__(
                self,
                *,
                name: str,
                endpoint: str,
                docs_url: str = None,
                emoji: discord.Emoji | discord.PartialEmoji | str | None = None,
                default: bool = False,
            ) -> None:
                if endpoint:
                    x = f" - {endpoint}"
                else:
                    x = ""

                super().__init__(
                    label=name.title() + x,
                    description=f'Shows {name.title()}{" (All)" if name.lower() == "general" else ""} Stats for the API.',
                    emoji=emoji,
                    default=default,
                )

                self.docs_url = docs_url
                self.name = name
                self.endpoint = endpoint

        class Select(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Select an endpoint to view stats for that endpoint.",
                    options=[
                        SelectOption(name="General", endpoint=None, default=True),
                        SelectOption(
                            name="Lyrics",
                            endpoint="/api/lyrics",
                            docs_url="https://api.openrobot.xyz/api/docs#tag/Lyrics",
                        ),
                        SelectOption(
                            name="Celebrity",
                            endpoint="/api/celebrity",
                            docs_url="https://api.openrobot.xyz/api/docs#tag/Celebrity",
                        ),
                        SelectOption(
                            name="OCR",
                            endpoint="/api/ocr",
                            docs_url="https://api.openrobot.xyz/api/docs#tag/OCR-(Optical-Character-Recognition)",
                        ),
                        SelectOption(
                            name="Translate",
                            endpoint="/api/translate",
                            docs_url="https://api.openrobot.xyz/api/docs#tag/Translate",
                        ),
                        SelectOption(
                            name="NSFW Check",
                            endpoint="/api/nsfw-check",
                            docs_url="https://api.openrobot.xyz/api/docs#tag/NSFW-Check",
                        ),
                    ],
                )

                self.last_selected = None

            def _endpoints_accessed(self, iterable):
                for x in iterable:
                    if isinstance(x, list):
                        yield from self._endpoints_accessed(x)
                    else:
                        yield x

            def get_general_embed(self):
                data = self.view.data

                embed = (
                    discord.Embed(color=self.view.ctx.bot.color)
                    .set_author(
                        name="General", icon_url=self.view.ctx.author.display_avatar.url
                    )
                    .set_footer(
                        text=f'Use "{self.view.ctx.prefix}api info" to view detailed statistics and tracking on your API.'
                    )
                )
                embed.timestamp = utcnow = discord.utils.utcnow()

                count = 0

                for i in data:
                    count += len(
                        list(self._endpoints_accessed(i["endpoints_accessed"]))
                    )

                last_used = sorted(
                    list(
                        self._endpoints_accessed(
                            [d["endpoints_accessed"] for d in data]
                        )
                    ),
                    key=lambda i: i["timestamp"],
                    reverse=True,
                )[0]

                embed.description = f"""
- **Total number of requests today:** `{len(list(filter(lambda r: r['timestamp'] >= utcnow.replace(hour=0, minute=0, second=0, microsecond=0).timestamp(), list(self._endpoints_accessed([d['endpoints_accessed'] for d in data])))))}`
- **Total number of requests this month:** `{len(list(filter(lambda r: r['timestamp'] >= utcnow.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp(), list(self._endpoints_accessed([d['endpoints_accessed'] for d in data])))))}`
- **Total number of reqeusts in total:** `{count}`

- **Last used:**
 \u200b \u200b \u200b- **At:** {discord.utils.format_dt(datetime.datetime.fromtimestamp(last_used['timestamp'], tz=datetime.timezone.utc))}
 \u200b \u200b \u200b- **Endpoint:** `{'/api/lyrics' if last_used['endpoint'].startswith('/api/lyrics/') else last_used['endpoint']}`
                """

                return embed

            def generate_embed(self, selection: SelectOption):
                data = self.view.data

                embed = (
                    discord.Embed(color=self.view.ctx.bot.color)
                    .set_author(
                        name=selection.label,
                        icon_url=self.view.ctx.author.display_avatar.url,
                    )
                    .set_footer(
                        text=f'Use "{self.view.ctx.prefix}api info" to view detailed statistics and tracking on your API.'
                    )
                )
                embed.timestamp = utcnow = discord.utils.utcnow()

                if selection.label == "General":
                    embed = self.get_general_embed()
                else:
                    endpoint_data = []

                    for xx in data:
                        for x in xx["endpoints_accessed"]:
                            if x["endpoint"].startswith(selection.endpoint):
                                print(x["endpoint"] + " - " + selection.endpoint)
                                endpoint_data.append(x)

                    endpoint_data = list(
                        self._endpoints_accessed(endpoint_data)
                    )  # [{endpoint1}, {endpoint2}, {endpoint3}]

                    count = 0

                    # embed.description = str(await self.view.ctx.bot.mystbin.post(json.dumps(list(self._endpoints_accessed([d['endpoints_accessed'] for x in endpoint_data for d in x])), indent=4)))

                    # return embed

                    count = len(endpoint_data)

                    last_used = sorted(
                        endpoint_data, key=lambda i: i["timestamp"], reverse=True
                    )[0]

                    newline = "\n"  # f-strings can't have backslashes, so we will do a little workaround

                    embed.description = f"""
- **Total number of requests today:** `{len(list(filter(lambda r: r['timestamp'] >= utcnow.replace(hour=0, minute=0, second=0, microsecond=0).timestamp(), endpoint_data)))}`
- **Total number of requests this month:** `{len(list(filter(lambda r: r['timestamp'] >= utcnow.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp(), endpoint_data)))}`
- **Total number of reqeusts in total:** `{count}`{f'{newline}- **Lyrics Cached:** `{len(self.view.lyrics_cached)}`' if selection.label == 'Lyrics - /api/lyrics' else ''}

- **Last used:**
 \u200b \u200b \u200b- **At:** {discord.utils.format_dt(datetime.datetime.fromtimestamp(last_used['timestamp'], tz=datetime.timezone.utc))}

- **Docs URL:** <{selection.docs_url}>
                    """

                return embed

            async def callback(self, interaction: discord.Interaction):
                self.options[0].default = False  # Set the general default to False

                if self.last_selected:
                    last_selected: SelectOption = discord.utils.find(
                        lambda v: self.last_selected == v.label, self.options
                    )
                    last_selected.default = (
                        False  # Set the last selected option's default to False
                    )

                selected: SelectOption = discord.utils.find(
                    lambda v: self.values[0] == v.label, self.options
                )

                selected.default = (
                    True  # Set the current selected option's default to True
                )

                self.last_selected = self.values[0]  # Set the new last selected option

                await interaction.response.defer()

                await interaction.message.edit(
                    embed=self.generate_embed(selected), view=self.view
                )

        class View(discord.ui.View):
            def __init__(
                self,
                ctx: commands.Context,
                data,
                lyrics_cached=[],
                *,
                timeout=90,
                message: discord.Message = None,
            ):
                super().__init__(timeout=timeout)
                self.ctx = ctx
                self.data = data
                self.message = message

                self.lyrics_cached = lyrics_cached

                self.add_item(Select())

            async def interaction_check(self, interaction):
                """Only allow the author that invoke the command to be able to use the interaction"""
                if not (
                    interaction.user == self.ctx.author
                    or await self.ctx.bot.is_owner(interaction.user)
                ):
                    await interaction.response.send_message(
                        f"This is not your interaction! Only {self.ctx.author.mention} can respond to this interaction!",
                        ephemeral=True,
                    )
                    return False
                else:
                    return True

            async def on_timeout(self) -> None:
                for child in self.children:
                    child.disabled = True

                await self.message.edit(view=self)

            @discord.ui.button(
                label="Update Statistics",
                style=discord.ButtonStyle.blurple,
                emoji="<:update:898506874398339102>",
            )
            async def update(
                self, button: discord.ui.Button, interaction: discord.Interaction
            ):
                updated = False

                for _ in range(3):
                    try:
                        self.data = list(
                            await self.ctx.bot.pool.fetch("SELECT * FROM tokens")
                        )

                        for i in range(len(self.data)):
                            self.data[i] = dict(self.data[i])
                    except asyncpg.exceptions._base.InterfaceError:
                        pass
                    else:
                        updated = True
                        break

                try:
                    self.lyrics_cached = [
                        k.decode()
                        for k in await self.ctx.bot.redis.execute_command("KEYS *")
                        if not k.decode().startswith("backup")
                    ]
                except Exception as e:
                    if ctx.debug:
                        raise e

                    pass

                if not updated:
                    return await interaction.response.send_message(
                        "Unable to update data. Try again in a few moments.",
                        ephemeral=True,
                    )
                else:
                    for i in range(len(self.data)):
                        self.data[i]["endpoints_accessed"] = json.loads(
                            self.data[i]["endpoints_accessed"]
                        )

                    select = discord.utils.find(
                        lambda i: isinstance(i, Select), self.children
                    )

                    last_selected: SelectOption = discord.utils.find(
                        lambda v: select.last_selected == v.label, select.options
                    )

                    if not last_selected:
                        await interaction.message.edit(view=self)
                    else:
                        try:
                            await interaction.message.edit(
                                embed=select.generate_embed(last_selected), view=self
                            )
                        except Exception as e:
                            if ctx.debug:
                                raise e

                            await interaction.message.edit(view=self)

                    return await interaction.response.send_message(
                        "Updated data.", ephemeral=True
                    )

            @discord.ui.button(
                label="Stop", emoji="\U000023f9", style=discord.ButtonStyle.danger
            )
            async def stop_button(
                self, button: discord.ui.Button, interaction: discord.Interaction
            ):
                await interaction.message.delete()
                self.stop()

        while True:
            try:
                db = await self.bot.pool.fetch("SELECT * FROM tokens")
            except:
                pass
            else:
                break

        for i in range(len(db)):
            db[i] = dict(db[i])
            db[i]["endpoints_accessed"] = json.loads(db[i]["endpoints_accessed"])

        try:
            lyrics_cached = [
                k.decode()
                for k in await self.bot.redis.execute_command("KEYS *")
                if not k.decode().startswith("backup")
            ]
        except Exception as e:
            if ctx.debug:
                raise e

            lyrics_cached = []

        view = View(ctx, db, lyrics_cached)

        select_obj = discord.utils.find(lambda c: isinstance(c, Select), view.children)

        if select_obj:
            embed = select_obj.get_general_embed()
        else:
            embed = None

        msg = view.message = await ctx.send(embed=embed, view=view)
        return msg

    @api.command("apply", cls=Command, example="api apply")
    @checks.api.has_not_applied()
    async def api_apply(
        self,
        ctx: commands.Context,
        *,
        reason: str = commands.Option(
            description="Enter the reason why you want to apply for the API."
        ),
    ):
        """
        Applies yourself for the OpenRobot API.

        Note that you can only apply once, and you cannot edit it afterwards.
        """

        try:
            msg = await ctx.author.send(
                "You have requested an API token to access OpenRobot API. You will get updates here in this DM! Be sure to keep your DMs Open and not to block me so I can send your API token! Note this can take from seconds to days to get your application accepted."
            )
        except discord.Forbidden as e:
            if ctx.debug:
                raise e

            return await ctx.send(
                "You either closed your DMs or block me. Please do not close your DMs or Block me so I can send you your API Token."
            )

        while True:
            try:
                await self.bot.pool.execute(
                    "INSERT INTO applied_tokens VALUES($1, $2, $3)",
                    ctx.author.id,
                    reason,
                    msg.id,
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        chan = self.bot.get_channel(857048848900030484)

        embed = discord.Embed()
        embed.color = self.bot.color
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"ID: {ctx.author.id}")
        embed.timestamp = discord.utils.utcnow()
        newline = "\n"
        embed.description = f"""
**Reason:** {discord.utils.escape_markdown(reason)}

__**Info:**__
- Username: {ctx.author.name}
- User ID: {ctx.author.id}

{f'''- Guild ID: {ctx.guild.id}
- Channel ID: {ctx.channel.id}{newline}''' if ctx.guild else ''}- Message ID: {ctx.message.id}
{f'- Message Jump URL: <{ctx.message.jump_url}>{newline}' if ctx.guild else ''}- Requested At: {discord.utils.format_dt(ctx.message.created_at, 'F')}
        """

        await chan.send(embed=embed)

        await ctx.send(
            "Ok! Your application has been requested to the API Developers of OpenRobot."
        )

    @api.command(
        "approve", aliases=["accept"], cls=Command, example="api approve @user"
    )
    @commands.is_owner()
    async def api_approve(
        self,
        ctx: commands.Context,
        *,
        arguments: str = commands.Option(description="Usage: [user] [--force]"),
    ):
        """
        Approve/Accept a User request to access the API. Owner-Only command.
        """

        converter = LegacyFlagConverter(
            [
                LegacyFlagItems("user", nargs="+"),
                LegacyFlagItems(
                    "--force", "-f", "--f", "-force", action="store_true", default=False
                ),
            ]
        )

        args = converter.convert(arguments)

        user = await commands.UserConverter().convert(ctx, " ".join(args.user))

        if args.force:
            force = True
        else:
            force = False

        tokens = []

        username_base64 = base64.urlsafe_b64encode(str(user.id).encode("utf-8")).decode(
            "utf-8"
        )
        tokens.append(username_base64)

        secret = generate_token(random.randint(25, 50))
        tokens.append(secret)

        secret = generate_token(random.randint(25, 50))
        tokens.append(secret)

        token = ".".join(tokens)

        if force:
            while True:
                try:
                    x = await self.bot.pool.fetchrow(
                        "DELETE FROM applied_tokens WHERE user_id = $1 RETURNING dm_message_id",
                        user.id,
                    )
                except Exception as e:
                    if ctx.debug:
                        raise e

                    x = {"dm_message_id": None}

                break

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
        else:
            while True:
                try:
                    if not await self.bot.pool.fetchrow(
                        "SELECT * FROM applied_tokens WHERE user_id = $1", user.id
                    ):
                        return await ctx.send(f"{user} did not apply for the API.")
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break

            while True:
                try:
                    x = await self.bot.pool.fetchrow(
                        "DELETE FROM applied_tokens WHERE user_id = $1 RETURNING dm_message_id",
                        user.id,
                    )
                except asyncpg.exceptions._base.InterfaceError:
                    x = {"dm_message_id": None}
                else:
                    break

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

        try:
            try:
                msg = await user.fetch_message(x["dm_message_id"])
            except Exception as e:
                if ctx.debug:
                    raise e

                msg = None

            embed = discord.Embed(
                title="Congratulations!",
                description=f"Your API token request has been approved! Your API token is `{token}`",
                color=self.bot.color,
            )

            if msg:
                await msg.reply(embed=embed)
            else:
                await user.send(embed=embed)
        except discord.Forbidden as e:
            if ctx.debug:
                raise e

            await ctx.send(
                f"Cannot send messages to {user}'s DM, but token has been generated."
            )
        else:
            await ctx.send(f"Token has been sent to {user}.")

    @api.command("deny", cls=Command, example="api deny @user")
    @commands.is_owner()
    async def api_deny(
        self,
        ctx: commands.Context,
        *,
        flags: APIDenyFlag = commands.Option(
            description="Usage: --user <@user> [--reason]"
        ),
    ):
        """
        Denies a User request to access the API. Owner-Only command.
        """

        user = flags.user
        reason = flags.reason

        while True:
            try:
                if not await self.bot.pool.fetchrow(
                    "SELECT * FROM applied_tokens WHERE user_id = $1", user.id
                ):
                    return await ctx.send(f"{user} did not apply for the API.")
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        while True:
            try:
                x = await self.bot.pool.fetchrow(
                    "DELETE FROM applied_tokens WHERE user_id = $1 RETURNING dm_message_id",
                    user.id,
                )
            except:
                pass
            else:
                break

        try:
            try:
                msg = await user.fetch_message(x["dm_message_id"])
            except Exception as e:
                if ctx.debug:
                    raise e

                msg = None

            embed = discord.Embed(
                title="OOF!",
                description=f"Your API token request has been denied{f' with reason {reason}' if reason is not None else ''} by `{ctx.author}`.",
                color=self.bot.color,
            )

            if msg:
                await msg.reply(embed=embed)
            else:
                await user.send(embed=embed)
        except discord.Forbidden as e:
            if ctx.debug:
                raise e

            await ctx.send(
                f"Cannot send messages to {user}'s DM, but user has been denied."
            )
        else:
            await ctx.send(f"{user} has been denied.")

    @api.command(
        "deauth",
        aliases=["de-auth", "de_auth", "deauthenticate", "deauthorize", "deauthorise"],
        cls=Command,
        example="api deauth @user",
    )
    @commands.is_owner()
    async def api_deauth(
        self,
        ctx: commands.Context,
        *,
        user: discord.User = commands.Option(
            description="The user you want to deauthorize."
        ),
    ):
        """
        Deauthenticate a user, making the token unuseable. Owner-Only command.
        """

        while True:
            try:
                if not await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", user.id
                ):
                    return await ctx.send(f"{user} did not apply for the API.")
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        while True:
            try:
                await self.bot.pool.fetchrow(
                    """
                UPDATE tokens
                SET authorized = $2
                WHERE user_id = $1
                """,
                    user.id,
                    False,
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        await ctx.send(f"User {user} has been de-authorized.")

    @api.command(
        "reauth",
        aliases=["re-auth", "re_auth", "authenticate", "authorize", "authorise"],
        cls=Command,
        example="api reauth @user",
    )
    @commands.is_owner()
    async def api_reauth(
        self,
        ctx: commands.Context,
        *,
        user: discord.User = commands.Option(
            description="The user you want to reauthorize."
        ),
    ):
        """
        Reauthenticate a user. Owner-Only command.
        """

        while True:
            try:
                if not await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", user.id
                ):
                    return await ctx.send(f"{user} did not apply for the API.")
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        while True:
            try:
                await self.bot.pool.fetchrow(
                    """
                UPDATE tokens
                SET authorized = $2
                WHERE user_id = $1
                """,
                    user.id,
                    True,
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        await ctx.send(f"User {user} has been re-authorized.")

    @api.command(
        "regenerate-token",
        aliases=[
            "regenerate",
            "regen-token",
            "regen_token",
            "regentoken",
            "regeneratetoken",
            "regenerate_token",
        ],
        cls=Command,
        example="api regenerate-token",
    )
    @checks.api.has_applied()
    async def api_regenerate_token(
        self,
        ctx: commands.Context,
        *,
        arguments: str = commands.Option(None, description="Flags: [--force]"),
    ):
        """
        Regenerates your OpenRobot API token.

        Flags:
        - `--force`: Forces to regenerate your API token (Even though you have your DMs closed, it will still regenerate it, useful for quick regeneration).
        """

        converter = LegacyFlagConverter(
            [
                LegacyFlagItems(
                    "--force", "-f", "--f", "-force", action="store_true", default=False
                )
            ]
        )

        args = converter.convert(arguments)

        if args.force:
            force = True
        else:
            force = False

        token = generate_token(50)

        try:
            await ctx.author.send(f"Your new token is `{token}`.")
        except discord.Forbidden as e:
            if ctx.debug:
                raise e

            if not force:
                return await ctx.send(
                    "I cannot send your new token to you, so I will not regenerate the token."
                )
            else:
                await ctx.send(
                    "I cannot send your new token to your DM, but since you forced me to regenerate it, I regenerated the token for you."
                )

        while True:
            try:
                await self.bot.pool.fetchrow(
                    """
                UPDATE tokens
                SET token = $2
                WHERE user_id = $1
                """,
                    ctx.author.id,
                    token,
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

    @api.command("token", cls=Command, example="api token")
    @checks.api.has_applied()
    async def api_token(self, ctx: commands.Context):
        """
        Sends your OpenRobot API token to your DM.
        """

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", ctx.author.id
                )
                if not db:
                    return await ctx.send(f"You did not apply for the API.")
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        try:
            await ctx.author.send(f'Your API Token: `{db["token"]}`')
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("I cannot send your API token in your DM!")

        return await ctx.send("Check your DM for your API token!")

    @api.group("info", invoke_without_command=True, cls=Group, example="api info")
    @checks.api.has_applied()
    async def api_info(
        self,
        ctx: commands.Context,
        *,
        arguments: str = commands.Option(
            None,
            description='Flags: [--ignore-guild-warning] [--yes] [--order "Newest to Oldest"/"Oldest to Newest"]',
        ),
    ):
        """
        Gets info/logs on your token. Useful for tracking, etc.

        Flags:
        - `--ignore-guild-warning`: Ignores the Guild warning, making it runnable in a Guild.
        - `--yes`: Assumes a automatic Yes option on the confirmation.
        - `--order`: Orders the list, from `Newest to Oldest` or `Oldest to Newest`.
        """

        if ctx.invoked_subcommand is None:
            converter = LegacyFlagConverter(
                [
                    LegacyFlagItems(
                        "--ignore-guild-warning", action="store_true", default=False
                    ),
                    LegacyFlagItems("--yes", "-y", action="store_true", default=False),
                    LegacyFlagItems(
                        "--order",
                        "--order-by",
                        "-ob",
                        "--ob",
                        "-s",
                        "--s",
                        "--sort",
                        type=str,
                        default="Newest to Oldest",
                    ),
                ]
            )

            args = converter.convert(arguments)

            while True:
                try:
                    db = await self.bot.pool.fetchrow(
                        "SELECT * FROM tokens WHERE user_id = $1", ctx.author.id
                    )
                    if not db:
                        return await ctx.send(f"You did not apply for the API.")
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break

            while True:
                try:
                    db = await self.bot.pool.fetchrow(
                        "SELECT endpoints_accessed FROM tokens WHERE user_id = $1",
                        ctx.author.id,
                    )
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break

            if not db or not len(json.loads(db["endpoints_accessed"])):
                return await ctx.send(
                    "No results we're found or we do not have enough data to display results. You have not made any API requests using your token.\nNote that requests made before <t:1633777200:F> are not collected."
                )

            if ctx.guild and not args.ignore_guild_warning:
                return await ctx.send(
                    "This command requires to be ran in DM for security-purposes as this includes IP address and such. If you would like to make this runnable in a guild, use the `--ignore-guild-warning` flag."
                )
            elif args.ignore_guild_warning and not args.yes:
                value = await self.bot.confirm(
                    ctx,
                    "Are you sure? There will be IP Addresses in this message. To ignore this message, use the `--yes`/`-y` flag. Note that the message will not be sent as a ephemeral message.",
                )

                if value is True:
                    pass
                elif value is None:
                    return await ctx.send("Timed out...")
                else:
                    return await ctx.send("Canceling...")

            order_by = process.extractOne(
                args.order, ["newest to oldest", "oldest to newest"]
            )
            if not order_by:
                order_by = "newest to oldest"
            else:
                order_by = order_by[0]

            x = json.loads(db["endpoints_accessed"])

            if order_by == "oldest to newest":
                x = list(reversed(x))

            pages = MenuPages(source=APIInfoPaginator(x), delete_message_after=True)
            await pages.start(ctx)

    @api_info.command("reset", cls=Command, example="api info reset")
    @checks.api.has_applied()
    async def api_info_reset(
        self,
        ctx: commands.Context,
        *,
        arguments: str = commands.Option(None, description="Flags: [--yes]"),
    ):
        """
        Resets your OpenRobot API logs. Note that this action cannot be undone.

        Flags:
        - `--yes`: Assumes a automatic Yes option on the confirmation.
        """

        converter = LegacyFlagConverter(
            [LegacyFlagItems("--yes", "-y", action="store_true", default=False)]
        )

        args = converter.convert(arguments)

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", ctx.author.id
                )
                if not db:
                    return await ctx.send(f"You did not apply for the API.")
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        if not args.yes:
            value = await self.bot.confirm(
                ctx,
                "Are you sure you want to reset all your data? This action cannot be un-done.",
            )

            if value is True:
                pass
            elif value is None:
                return await ctx.send("Timed out...")
            else:
                return await ctx.send("Canceling...")

        while True:
            try:
                await self.bot.pool.execute(
                    """
                UPDATE tokens
                SET endpoints_accessed = $2
                WHERE user_id = $2
                """,
                    ctx.author.id,
                    "[]",
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        return await ctx.send("Reseted.")

    @api.group(name="ip", invoke_without_command=True, cls=Group, example="api ip")
    @checks.api.has_applied()
    async def api_ip(self, ctx: commands.Context):
        """
        IP management.

        You can ban IPs from using your API Token, or unban IPs, or look at the list of IP bans you banned.
        """

        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command)

    def is_valid_ip(self, ip: str):
        # if not IPv4 and not IPv6
        if not re.match(
            r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
            ip,
        ) and not re.match(
            r"(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))",
            ip,
        ):
            return False

        return ip not in ["127.0.0.1", "0.0.0.0"]

    @api_ip.command("list", aliases=["show"], cls=Command, example="api ip list")
    @checks.api.has_applied()
    async def api_ip_list(
        self,
        ctx,
        *,
        arguments: str = commands.Option(
            None,
            description='Flags: [--ignore-guild-warning] [--yes] [--order "Newest to Oldest"/"Oldest to Newest"]',
        ),
    ):
        """
        Gets a list of the Ban IPs you banned.

        Flags:
        - `--ignore-guild-warning`: Ignores the Guild warning, making it runnable in a Guild.
        - `--yes`: Assumes a automatic Yes option on the confirmation.
        - `--order`: Orders the list, from `Newest to Oldest` or `Oldest to Newest`.
        """

        converter = LegacyFlagConverter(
            [
                LegacyFlagItems(
                    "--ignore-guild-warning", action="store_true", default=False
                ),
                LegacyFlagItems("--yes", "-y", action="store_true", default=False),
                LegacyFlagItems(
                    "--order",
                    "--order-by",
                    "-ob",
                    "--ob",
                    "-s",
                    "--s",
                    "--sort",
                    type=str,
                    default="Newest to Oldest",
                ),
            ]
        )

        args = converter.convert(arguments)

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", ctx.author.id
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        if not db:
            return await ctx.send(f"You did not apply for the API.")

        ip_bans = json.loads(db["ip_bans"])

        if not ip_bans:
            return await ctx.send("You have not IP Banned anyone yet.")

        if ctx.guild and not args.ignore_guild_warning:
            return await ctx.send(
                "This command requires to be ran in DM for security-purposes as this includes IP address and such. If you would like to make this runnable in a guild, use the `--ignore-guild-warning` flag."
            )
        elif args.ignore_guild_warning and not args.yes:
            value = await self.bot.confirm(
                ctx,
                "Are you sure? There will be IP Addresses in this message. To ignore this message, use the `--yes`/`-y` flag. Note that the message will not be sent as a ephemeral message.",
            )

            if value is True:
                pass
            elif value is None:
                return await ctx.send("Timed out...")
            else:
                return await ctx.send("Canceling...")

        order_by = process.extractOne(
            args.order, ["newest to oldest", "oldest to newest"]
        )
        if not order_by:
            order_by = "newest to oldest"
        else:
            order_by = order_by[0]

        if order_by == "newest to oldest":
            ip_bans = sorted(ip_bans, key=lambda d: d["banned_at"])
        else:
            ip_bans = sorted(ip_bans, key=lambda d: d["banned_at"], reverse=True)

        pages = MenuPages(source=IPBanListPaginator(ip_bans), delete_message_after=True)
        await pages.start(ctx)

    @api_ip.command(
        "ban",
        aliases=["reject"],
        cls=Command,
        example="api ip ban Insert-IP Your-Reason",
    )
    @checks.api.has_applied()
    async def api_ip_ban(
        self,
        ctx,
        ip: str = commands.Option(description="The IP to ban."),
        *,
        reason: str = commands.Option(None, description="The reason for the ban."),
    ):
        """
        IP bans a IP from using your token. This can accept either IPv4 or IPv6.

        Flags:
        - `--ip`: The IPv4 or IPv6 to ban.
        - `--reason`: The reason of the ban. Defaults to None.
        """

        if not self.is_valid_ip(ip):
            return await ctx.send(f"IP {ip} is invalid.")

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", ctx.author.id
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        if not db:
            return await ctx.send(f"You did not apply for the API.")

        ip_bans = json.loads(db["ip_bans"])

        if ip in [d["ip"] for d in ip_bans]:
            return await ctx.send(
                f"IP {ip} is already IP Banned from using your API Token."
            )

        ip_bans.append(
            {
                "ip": ip,
                "banned_at": ctx.message.created_at.timestamp(),
                "reason": reason,
                "info": {
                    "message_id": ctx.message.id,
                    "channel_id": ctx.channel.id,
                    "guild_id": ctx.guild.id if ctx.guild else None,
                    "author_id": ctx.author.id,
                    "message_url": ctx.message.jump_url,
                },
            }
        )

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    """
                UPDATE tokens
                SET ip_bans = $2
                WHERE user_id = $1
                """,
                    ctx.author.id,
                    json.dumps(ip_bans),
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        await ctx.send(f"IP banned {ip}.")

    @api_ip.command(
        "unban",
        aliases=["accept", "un-ban", "un_ban"],
        cls=Command,
        example="api ip unban Insert-IP",
    )
    @checks.api.has_applied()
    async def api_ip_unban(
        self, ctx, *, ip: str = commands.Option(description="The IP Address to unban.")
    ):
        """
        IP unban a IP from using your token. This can accept either IPv4 or IPv6.
        """

        if not self.is_valid_ip(ip):
            return await ctx.send(f"IP {ip} is invalid.")

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    "SELECT * FROM tokens WHERE user_id = $1", ctx.author.id
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        if not db:
            return await ctx.send(f"You did not apply for the API.")

        ip_bans = json.loads(db["ip_bans"])

        if ip not in [d["ip"] for d in ip_bans]:
            return await ctx.send(
                f"IP {ip} is not IP Banned from using your API Token."
            )

        for data in ip_bans:
            if data["ip"] == ip:
                ip_bans.remove(data)
                break

        while True:
            try:
                db = await self.bot.pool.fetchrow(
                    """
                UPDATE tokens
                SET ip_bans = $2
                WHERE user_id = $1
                """,
                    ctx.author.id,
                    json.dumps(ip_bans),
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        await ctx.send(f"IP unbanned {ip}.")


def setup(bot):
    bot.add_cog(API(bot))

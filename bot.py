import discord
from discord.ext import commands

import config

import re
import os
import json
import time
import urllib
import typing
import random
import string
import base64
import asyncio
import asyncpg
import jishaku
import aiohttp
import inspect
import mystbin
import pathlib
import humanize
import aioredis
import datetime
import textwrap
import aiospotify
import async_timeout

from threading import Thread
from io import BytesIO, StringIO

from openrobot import discord_activities as discord_activity

from cogs.utils import (
    MenuPages,
    CodePaginator,
    executor,
    Bot as BaseBot,
    ChristmasEvent,
)

description = """
I am OpenRobot. I provide help and utilities for OpenRobot stuff such as our API (Hosted at <https://api.openrobot.xyz>).

GitHub: <https://github.com/OpenRobot>
Website: <https://openrobot.xyz/>
"""


class LineCount:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class Bot(BaseBot):
    CDN_BUCKET = "cdn.openrobot.xyz"

    def line_count(self, directory: str = "./") -> LineCount:
        p = pathlib.Path(directory)
        cm = cr = fn = cl = ls = fc = 0
        for f in p.rglob("*.py"):
            if str(f).startswith("venv"):
                continue
            fc += 1
            with f.open() as of:
                for l in of.readlines():
                    l = l.strip()
                    if l.startswith("class"):
                        cl += 1
                    if l.startswith("def"):
                        fn += 1
                    if l.startswith("async def"):
                        cr += 1
                    if "#" in l:
                        cm += 1
                    ls += 1

        return LineCount(
            files=fc, lines=ls, classes=cl, functions=fn, coroutines=cr, comments=cm
        )

    @executor()
    def screenshot(self, url: str, *, delay: int = None, proxy: bool = False):
        if delay is not None:
            if delay <= 0:
                delay = None

        with self.driver(use_proxy=proxy or False) as driver:
            driver.get(url)
            driver.set_window_size(1920, 1080)

            if delay:
                time.sleep(delay)

            buffer = BytesIO(driver.get_screenshot_as_png())

        return buffer

    async def publishCdn(
        self, fp: BytesIO, filename: str = "uwu.png", from_aiohttp=True, file_type=None
    ):
        fileType = file_type or f"{filename.split('.')[-1:]}"

        if from_aiohttp:
            original = fp.close
            fp.close = lambda: None

        data = aiohttp.FormData()
        data.add_field("file", fp)

        url = f"https://cdn.ayomerdeka.com/upload?Authorization={config.CDN_TOKEN}&File-Type={fileType}"

        try:
            async with self.session.post(url, data=data) as resps:
                if resps.status == 200:
                    d = await resps.json()
                    return d["url"]
                else:
                    return None
        finally:
            if from_aiohttp:
                fp.close = original

    @executor()  # CDN may be blocking, so lets just use an executor just in case
    def publish_cdn(
        self, fp: BytesIO | bytes, filename: str, *, raw: bool = False
    ) -> str | dict | typing.Any:
        hash = "".join(
            random.choices(
                string.ascii_letters + string.digits, k=random.randint(10, 32)
            )
        )

        file_type = filename.split(".")
        file_type = file_type[len(file_type) - 1]

        with open(f"./cdn-images/{hash}.{file_type}", "wb") as f:
            f.write(getattr(fp, "getvalue", lambda: fp)())

        response = self.cdn.upload_file(
            f"./cdn-images/{hash}.{file_type}", self.CDN_BUCKET, filename
        )

        try:
            os.remove(f"./cdn-images/{hash}.{file_type}")
        except:
            pass

        if not raw:
            return "https://" + self.CDN_BUCKET + "/" + filename
        else:
            return response

    async def close(self):
        if self.redis:
            await self.redis.close()

        if self.pool:
            await self.pool.close()

        if self.spotify_pool:
            await self.spotify_pool.close()

        if self.spotify_redis:
            await self.spotify_redis.close()

        if self.tb_pool:
            await self.tb_pool.close()

        await self.spotify.close()

        await self.session.close()

        return await super().close()


bot = Bot(
    command_prefix=commands.when_mentioned_or(*config.PREFIXES),
    help_command=commands.MinimalHelpCommand(
        no_category="Miscellaneous"
    ),  # For old help command purposes only. This is used whenever the help cog fails.
    intents=discord.Intents.all(),
    activity=discord.Activity(type=discord.ActivityType.listening, name="or.help"),
    case_insensitive=True,
    description=description,
    slash_commands=True,
)

api = bot.api


def override(func):  # Plainly just for `source` command.
    func.__is_overridden__ = True
    return func


@bot.event
@override
async def on_ready():
    print(f"{bot.user} is ready!")


@bot.event
@override
async def on_message(message: discord.Message):
    if re.match(rf"^<@!?{bot.user.id}>$", message.content):
        return await message.reply(
            "My prefix is `or.`! You can also mention me!", mention_author=False
        )

    await bot.process_commands(message)


@bot.command(aliases=["latency"])
async def ping(ctx: commands.Context):
    """
    Gets the latency of the bot, databases and more.
    """

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    def do_ping_string(ping: int) -> str:
        s = "```diff\n"

        if ping <= 250:
            s += f"+ {ping} ms"
        else:
            s += f"- {ping} ms"

        s += "```"

        return s

    msg = await ctx.send("Calculating Latency...")

    embed = (
        discord.Embed(color=bot.color, timestamp=ctx.message.created_at)
        .set_author(name="Latency/Ping Info:", icon_url=ctx.author.avatar.url)
        .set_footer(icon_url=ctx.author.avatar.url, text=f"Requested by: {ctx.author}")
    )

    web_ping = await bot.ping.discord_web_ping() * 1000
    typing_ping = await bot.ping.typing_latency() * 1000
    bot_latency = bot.ping.bot_latency() * 1000

    embed.add_field(
        name=f'{bot.ping.EMOJIS["bot"]} Bot Latency:',
        value=do_ping_string(round(bot_latency, 2)),
    )
    embed.add_field(
        name=f'{bot.ping.EMOJIS["typing"]} Typing Latency:',
        value=do_ping_string(round(typing_ping, 2)),
    )
    embed.add_field(
        name=f'{bot.ping.EMOJIS["discord"]} Discord Web Latency:',
        value=do_ping_string(round(web_ping, 2)),
    )

    if bot.pool is not None:
        postgresql_ping = await bot.ping.database.postgresql()
    else:
        postgresql_ping = None

    if bot.spotify_pool is not None:
        postgresql_spotify_ping = await bot.ping.database.postgresql(spotify=True)
    else:
        postgresql_spotify_ping = None

    if postgresql_ping is not None or postgresql_ping is not None:
        if postgresql_ping is not None and postgresql_spotify_ping is not None:
            psql_ping = list(sorted([postgresql_ping, postgresql_spotify_ping]))[0]
        elif postgresql_spotify_ping is None:
            psql_ping = postgresql_ping
        elif postgresql_ping is None:
            psql_ping = postgresql_spotify_ping

        embed.add_field(
            name=f'{bot.ping.EMOJIS["postgresql"]} PostgreSQL Latency:',
            value=do_ping_string(round(psql_ping * 1000, 2)),
        )

    if bot.redis:
        redis_ping = await bot.ping.database.redis()

        if redis_ping:
            embed.add_field(
                name=f'{bot.ping.EMOJIS["redis"]} Redis Latency:',
                value=do_ping_string(round(redis_ping * 1000, 2)),
            )

    embed.add_field(
        name=f'{bot.ping.EMOJIS["openrobot-api"]} OpenRobot API Latency:',
        value=do_ping_string(round(await bot.ping.api() * 1000, 2)),
    )

    embed.add_field(
        name="Average Discord Latency:",
        value=do_ping_string(round((web_ping + typing_ping + bot_latency) / 3, 2)),
    )

    # await msg.delete()
    await msg.edit(
        embed=embed, content=None, allowed_mentions=discord.AllowedMentions.none()
    )


@bot.command("system", aliases=["sys"])
async def system(ctx: commands.Context):
    """
    Gets systen information e.g CPU, Memory, Disk, etc.

    Most of the code is inspired by [Ami#7836](https://discord.com/users/801742991185936384).
    """

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    return await bot.get_command("jishaku system")(
        ctx
    )  # yes i am too lazy to move the code here, sorry!


@bot.command(aliases=["act"])
async def activity(
    ctx: commands.Context,
    channel: discord.VoiceChannel = commands.Option(
        description="The voice channel to start the activity. Defaults to the channel you are in."
    ),
    activity: typing.Literal[
        "Watch Together",
        "Poker Night",
        "Chess",
        "Doodle Crew",
        "Word Snacks",
        "Letter Tile",
        "Spellcast",
        "Checkers",
        "Fishington",
        "Betrayal",
    ] = commands.Option(description="The activity to start."),
):
    act = getattr(discord_activity.ActivityType, activity.replace(" ", "_").lower())

    try:
        started_activity = await bot.discord_activity.set_activity(channel.id, act)
    except Exception as e:
        if ctx.debug:
            raise e

        return await ctx.send(
            f"Something wen't wrong. Make sure I have `Create Invite` permissions in {channel.mention}!"
        )

    await ctx.send(
        embed=discord.Embed(
            color=bot.color,
            description=f"[Click here to start your `{activity}` activity]({started_activity.url})",
        )
    )


@activity.error
async def activity_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.BadLiteralArgument):
        await ctx.send("Invalid activity.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide a channel.")


@bot.command()
async def lyrics(
    ctx: commands.Context,
    *,
    query: str = commands.Option(description="The query to search for the lyrics."),
):
    """
    Get lyrics on a specific song/query.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    - `--file`: Sends/Exports the lyrics in a text file.
    - `--from-spotify`: Gets the lyrics from spotify. This gets the lyrics from your spotify activity and edits them automatically when a new song plays. If it does not sync, try pausing/playing, or do anything regarding to the playback of your Spotify song.
    """

    query = re.sub("\n+", " ", query)

    if (
        ("--raw" in query.split(" ") and "--from-spotify" in query.split(" "))
        or ("--raw" in query.split(" ") and "--file" in query.split(" "))
        or ("--file" in query.split(" ") and "--from-spotify" in query.split(" "))
    ):
        return await ctx.send("Invalid flags.")
    if query == "--from-spotify":
        from_spotify = True
    else:
        from_spotify = False

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    async def getLyrics(q):
        try:
            lyric = await api.lyrics(
                q.replace("--raw", "")
                .replace("--file", "")
                .replace("--from-spotify", "")
            )

            if "--raw" in query.split(" "):
                s = StringIO()
                s.write(json.dumps(lyric.raw, indent=4))
                s.seek(0)

                return await ctx.send(file=discord.File(s, "response.json"))

            title = lyric.title
            artist = lyric.artist
            lyrics = lyric.lyrics
            track_image = lyric.images.track
            artist_image = lyric.images.background

            if "--file" in query.split(" "):
                content = ""

                if title and not getattr(title, "lower", lambda: title)() == "none":
                    content += f"Title: {title}\n"
                else:
                    content += f"Search Result for: {q}\n"

                if artist and not getattr(artist, "lower", lambda: artist)() == "none":
                    content += f"Artist: {artist}\n"
                else:
                    content += f"Artist: Unknown\n"

                content += f"Track Image URL: {track_image or 'Unknown'}\n"

                content += f"Atist Image URL: {artist_image or 'Unknown'}\n"

                content += "\n"

                content += lyrics

                s = StringIO()
                s.write(content)
                s.seek(0)

                return await ctx.send(file=discord.File(s, "lyrics.txt"))

            if not lyrics:
                return None  # return await ctx.send(f"Song with query `{query}` not found.")

            embed = discord.Embed(color=bot.color)
            if title and not getattr(title, "lower", lambda: title)() == "none":
                embed.title = title
            else:
                embed.title = f"{q} Search Result:"

            if artist and not getattr(artist, "lower", lambda: artist)() == "none":
                embed.set_author(
                    name=f"Artist: {artist}",
                    icon_url=artist_image or discord.Embed.Empty,
                )
            else:
                pass

            embed.set_thumbnail(url=track_image or discord.Embed.Empty)

            pag = commands.Paginator(prefix="", suffix="", max_size=4000)

            for line in lyrics.split("\n"):
                pag.add_line(line)

            embed.description = discord.utils.escape_markdown(pag.pages[0])

            embed.set_footer(text=f"Invoked by: {ctx.author}")

            embeds = []

            if len(pag.pages) >= 2:
                for page in pag.pages[1:]:
                    e = discord.Embed(color=bot.color)
                    e.description = discord.utils.escape_markdown(page)
                    e.set_footer(text=f"Invoked by: {ctx.author}")

                    embeds.append(e)

            return [embed] + embeds  # await ctx.send(embed=embed)
        except Exception as e:
            if ctx.debug:
                raise e

            return (
                None  # return await ctx.send(f"Song with query `{query}` not found.")
            )

    def generateErrorEmbed(error):
        embed = discord.Embed(color=bot.color)

        embed.description = error

        embed.set_author(name=f"Invoked by: {ctx.author}")

        return embed

    if from_spotify:
        for act in ctx.author.activities:
            if isinstance(act, discord.Spotify):
                activity = act
                break

        activity = None

        for act in ctx.author.activities:
            if isinstance(act, discord.Spotify):
                activity = act
                break

        if not activity:
            return await ctx.send(
                embed=generateErrorEmbed("You are not playing any spotify music!")
            )

        stop_process = False

        msg = None

        while True:
            if stop_process:
                return

            await asyncio.sleep(3)

            for act in ctx.guild.get_member(ctx.author.id).activities:
                if isinstance(act, discord.Spotify):
                    activity = act
                    break

            if msg:
                await msg.delete()

            if not activity:
                msg = await ctx.send(
                    embed=generateErrorEmbed("You are not playing any spotify music!")
                )
            else:
                l = await getLyrics(activity.title + " " + activity.artists[0])

                if not l:
                    l = await getLyrics(activity.title)

                if not l:
                    for x in activity.artists:
                        l = await getLyrics(activity.title + " " + x)
                        if l:
                            break

                if not l:
                    l = await getLyrics(
                        activity.title + " " + " ".join(activity.artists)
                    )

                if not l:
                    msg = await ctx.send(
                        embed=generateErrorEmbed(
                            f"Song with query `{query}` cannot be found."
                        )
                    )
                else:
                    msg = await ctx.send(embeds=l)

            await msg.add_reaction("\U000023f9")

            async def do_stop():
                while True:
                    reaction, user = await bot.wait_for(
                        "reaction_add",
                        check=lambda r, u: str(r.emoji) == "\U000023f9"
                        and r.message == msg
                        and not u.bot,
                    )

                    if (
                        not await bot.is_owner(user)
                        and not user == ctx.author
                        and not user.guild_permissions.manage_messages
                    ):
                        continue

                    nonlocal stop_process
                    stop_process = True
                    await msg.delete()

            bot.loop.create_task(do_stop())

            if stop_process:
                return

            _, __ = await bot.wait_for(
                "presence_update",
                check=lambda b, a: b == ctx.author and a == ctx.author,
            )

            if stop_process:
                return
    else:
        l = await getLyrics(query)

        if isinstance(l, discord.Message):
            return

        if not l:
            return await ctx.send(
                embed=generateErrorEmbed(f"Song with query `{query}` cannot be found.")
            )

        for embed in l:
            await ctx.send(embed=embed)


@bot.command(aliases=["ss"])
async def screenshot(
    ctx: commands.Context,
    url: str = commands.Option(description="The website URL to screenshot."),
    delay: int = commands.Option(
        None, description="Waits for x seconds before taking the screenshot."
    ),
):
    """
    Screenshots a URL.
    """

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()
    else:
        await ctx.message.add_reaction("<a:openrobot_searching_gif:899928367799885834>")

    try:
        buffer: BytesIO = await bot.screenshot(url, delay=delay)
    except Exception as e:
        if ctx.debug:
            raise e

        return await ctx.send(f"Error: {e}")

    render_msg = await bot.get_channel(847804286933925919).send(
        file=discord.File(fp=BytesIO(buffer.getvalue()), filename="screenshot.png")
    )

    await ctx.message.remove_reaction(
        "<a:openrobot_searching_gif:899928367799885834>", bot.user
    )

    if not ctx.channel.is_nsfw():
        check = await bot.api.nsfw_check(render_msg.attachments[0].url)

        is_unsafe = check.score > 50 or bool(check.labels)

        if is_unsafe:
            return await ctx.send(
                "This website seems to be NSFW/Innapropriate. I am sorry, but I may not be able to send the screenshot result in this channel."
            )

    embed = discord.Embed(color=bot.color)

    embed.description = f"[`{url}`]({url})"

    embed.set_image(url="attachment://screenshot.png")

    embed.set_footer(text=f"Requested by: {ctx.author} | Delay: {delay}s.")

    class View(discord.ui.View):
        @discord.ui.button(
            label="Delete",
            emoji="<:trash:911955690644447273>",
            style=discord.ButtonStyle.red,
        )
        async def delete(
            self, button: discord.ui.Button, interaction: discord.Interaction
        ):
            await interaction.message.delete()
            self.stop()

    return await ctx.send(
        embed=embed,
        view=View(timeout=None),
        file=discord.File(buffer, filename="screenshot.png"),
    )


# @bot.group()
async def spotify(ctx: commands.Context):
    """
    OpenRobot Spotify (OpenRobot x Spotify)
    """

    if ctx.invoked_subcommand is None:
        return await ctx.send_help(ctx.command)


# @spotify.command('login')
async def spotify_login(
    ctx: commands.Context,
    *,
    flags: str = commands.Option(None, description="Flags: [--interactive]"),
):
    """
    Pair your spotify account to OpenRobot x Spotify.

    Flags:
    - `--interactive`: Interactively helps you step-by-step on how to pair your spotify account to OpenRobot Spotify.
    """

    flags = (flags or "").split(" ")

    if "--interactive" not in flags:
        return await ctx.send("https://spotify.openrobot.xyz/")

    DEMO_URLS = {
        "discord": "https://api.openrobot.xyz/static/openrobot_spotify_step_discord.gif",
        "spotify": "https://api.openrobot.xyz/static/openrobot_spotify_step_spotify.gif",
    }

    DESCRIPTION = {
        "discord": f"""
Go to https://spotify.openrobot.xyz and `Authorize` to this Discord account, {ctx.author}.
        """,
        "spotify": """
Now, sign in to the correct spotify account and click the `Agree` button.
        """,
    }

    def generate_embed(step: str = None):
        step = step or "discord"

        embed = discord.Embed(color=bot.color)

        embed.set_image(url=DEMO_URLS[step])

        embed.description = DESCRIPTION[step]

        return embed

    async def wait_for(step: str, *, timeout=60):
        c = 0

        async with async_timeout.timeout(timeout):
            while (
                not getattr(
                    await bot.spotify_redis.get(str(ctx.author.id)),
                    "decode",
                    lambda: None,
                )()
                == f"ON_STEP({step.upper()})"
            ):
                pass

    username = None
    url = None

    get_step = getattr(
        await bot.spotify_redis.get(str(ctx.author.id)), "decode", lambda: None
    )()

    if get_step:
        step: str = re.findall(r"\(.*\)", get_step)[0].strip("(").strip(")").lower()

        if step == "finish":
            return await ctx.send("You just authenticated, wait for some time!")

        confirm = await bot.confirm(
            ctx,
            embed=discord.Embed(
                description=f"Seems like you already tried to authenticate/pair your spotify account to OpenRobot. You we're at the `{step.capitalize()}` step.\nDo you want to continue from your step?",
                color=bot.color,
            ),
        )

        if confirm:
            if step not in ["spotify"]:
                return await ctx.send(
                    f"Unknown step. This is a problem in our back-end! Please try restarting your steps and report this to {bot.owner.mention} - `{bot.owner}`!"
                )

            await ctx.send("Check your DMs!")

            embed = generate_embed("spotify")

            await ctx.author.send(embed=embed)

            try:
                await wait_for("FINISH", timeout=90)
            except asyncio.TimeoutError as e:
                if ctx.debug:
                    raise e

                return await ctx.author.send("Took to long, try again later.")

            while True:
                try:
                    spotify_db_res = await bot.spotify_pool.fetchrow(
                        "SELECT * FROM spotify_auth WHERE user_id = $1", ctx.author.id
                    )
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break

            spotify = aiospotify.Client()

            async with bot.session.get(
                "https://api.spotify.com/v1/me",
                headers={"Authorization": f'Bearer {spotify_db_res["access_token"]}'},
            ) as resp:
                js = await resp.json()

                username = js["display_name"]
                url = js["uri"]
        else:
            await bot.spotify_redis.delete(str(ctx.author.id))

    if not username and not url:
        embed = generate_embed()

        await ctx.author.send(embed=embed)

        try:
            await wait_for("SPOTIFY", timeout=90)
        except asyncio.TimeoutError as e:
            if ctx.debug:
                raise e

            return await ctx.author.send("Took to long, try again later.")

        embed = generate_embed("spotify")

        await ctx.send("Check your DMs!")
        await ctx.author.send(embed=embed)

        try:
            await wait_for("FINISH", timeout=90)
        except asyncio.TimeoutError as e:
            if ctx.debug:
                raise e

            return await ctx.author.send("Took to long, try again later.")

        while True:
            try:
                spotify_db_res = await bot.spotify_pool.fetchrow(
                    "SELECT * FROM spotify_auth WHERE user_id = $1", ctx.author.id
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        async with bot.session.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f'Bearer {spotify_db_res["access_token"]}'},
        ) as resp:
            js = await resp.json()

            username = js["display_name"]
            url = js["uri"]

    embed = discord.Embed(color=bot.color)

    embed.description = f"Just for confirmation, Is [`{username}`]({url}) the spotify account you are trying to link to your discord account, `{ctx.author}`"

    value = await bot.confirm(ctx, channel=ctx.author, embed=embed)

    if value:
        await ctx.author.send("Ok! Authenticated and paired successfully!")
    else:
        await bot.spotify_redis.delete(str(ctx.author))

        while True:
            try:
                await bot.spotify_pool.fetchrow(
                    "DELETE FROM spotify_auth WHERE user_id = $1", ctx.author.id
                )
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        await ctx.author.send(
            "Removed your spotify pair from this account. Please redo the command again."
        )


# @spotify.command('logout')
async def spotify_logout(ctx: commands.Context):
    while True:
        try:
            x = await bot.spotify_pool.fetchrow(
                "SELECT * FROM spotify_auth WHERE user_id = $1", ctx.author.id
            )
        except asyncpg.exceptions._base.InterfaceError:
            pass
        else:
            break

    if not x:
        return await ctx.send("You have not logged in to OpenRobot Spotify.")

    await bot.spotify_redis.delete(str(ctx.author))

    while True:
        try:
            await bot.spotify_pool.fetchrow(
                "DELETE FROM spotify_auth WHERE user_id = $1", ctx.author.id
            )
        except asyncpg.exceptions._base.InterfaceError:
            pass
        else:
            break

    await ctx.send("Logged out successfully!")


@bot.command(aliases=["sp"])
async def spotify(
    ctx: commands.Context, member: typing.Optional[discord.Member] = None, *flags
):
    """
    Shows a member's currently listening track in spotify. Defaults to yourself.

    Flags:
    - `--sync`: Disables the Auto Spotify Sync feature (Automatically edits the message).
    """

    member = member or ctx.author

    flags = [x.lower() for x in flags]

    sync = "--sync" in flags

    class LyricButton(discord.ui.Button):
        def __init__(self, query: str):
            super().__init__(
                label="Lyrics", emoji="🎶", style=discord.ButtonStyle.blurple
            )
            self.embeds = []
            self.query = query
            self.response = None

            bot.loop.create_task(self.get_lyrics())

        async def get_lyrics(self):
            if self.embeds:
                return self.embeds

            lyric = await bot.api.lyrics(self.query)

            if not lyric or not lyric.lyrics:
                return

            self.response = lyric

            embed = discord.Embed(color=bot.color)

            title = lyric.title
            artist = lyric.artist
            lyrics = lyric.lyrics
            track_image = lyric.images.track
            artist_image = lyric.images.background

            if title and not getattr(title, "lower", lambda: title)() == "none":
                embed.title = title
            else:
                embed.title = f"{self.query} Search Result:"

            if artist and not getattr(artist, "lower", lambda: artist)() == "none":
                embed.set_author(
                    name=f"Artist: {artist}",
                    icon_url=artist_image or discord.Embed.Empty,
                )
            else:
                pass

            embed.set_thumbnail(url=track_image or discord.Embed.Empty)

            pag = commands.Paginator(prefix="", suffix="", max_size=4000)

            for line in lyrics.split("\n"):
                pag.add_line(line)

            embed.description = discord.utils.escape_markdown(pag.pages[0])

            embed.set_footer(text=f"Invoked by: {ctx.author}")

            embeds = []

            if len(pag.pages) >= 2:
                for page in pag.pages[1:]:
                    e = discord.Embed(color=bot.color)
                    e.description = discord.utils.escape_markdown(page)
                    e.set_footer(text=f"Invoked by: {ctx.author}")

                    embeds.append(e)

            self.embeds = [embed] + embeds  # await ctx.send(embed=embed)

            return self.embeds

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            embeds = await self.get_lyrics()

            if not embeds:
                return await interaction.followup.send(
                    "No lyrics found.", ephemeral=True
                )

            if len(embeds) == 1:
                return await interaction.followup.send(embed=embeds[0], ephemeral=True)

            for embed in embeds:
                await interaction.followup.send(embed=embed, ephemeral=True)

    if sync:
        latest_spotify = None

        msg = None

        async def msgIsNew(msg: discord.Message):
            if not msg:
                return True

            async for m in msg.channel.history(limit=10):
                if m == msg:
                    return True

            return False

        stopped = False

        class StopView(discord.ui.View):
            def __init__(self, query: str, *, timeout: float = None):
                super().__init__(timeout=timeout)
                self.message = None
                self.add_item(LyricButton(query))

            @discord.ui.button(
                label="Stop",
                style=discord.ButtonStyle.red,
                emoji="<:openrobot_stop_button:899878227969974322>",
            )
            async def stop(
                self, button: discord.ui.Button, interaction: discord.Interaction
            ):
                if interaction.user != ctx.author and not await bot.is_owner(
                    interaction.user
                ):
                    return await interaction.response.send_message(
                        f"This is not your interaction! This is {ctx.author}'s interaction!",
                        ephemeral=True,
                    )

                nonlocal stopped
                stopped = True

                await self.message.delete()

                self.stop()

        while not stopped:
            if msg:
                await asyncio.sleep(
                    random.randint(5, 10)
                )  # API Ratelimit and Cache update

            spotify = discord.utils.find(
                lambda a: isinstance(a, discord.Spotify), member.activities
            )
            if spotify is None:
                if msg:
                    continue
                else:
                    msg = await ctx.send(
                        f"**{member}** is not listening or connected to Spotify."
                    )
                    continue

            if msg and latest_spotify:
                is_new = await msgIsNew(msg)

                if spotify.track_id == latest_spotify.track_id:
                    if ctx.debug:
                        await ctx.send("1")

                    params = {
                        "title": spotify.title,
                        "cover_url": spotify.album_cover_url,
                        "duration_seconds": spotify.duration.seconds,
                        "start_timestamp": spotify.start.timestamp(),
                        "artists": spotify.artists[0],
                    }

                    async with bot.session.get(
                        "https://api.jeyy.xyz/discord/spotify", params=params
                    ) as response:
                        buf = BytesIO(await response.read())

                    url = await bot.publish_cdn(
                        buf,
                        f'spotify/{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 32)))}.png',
                    )  # discord rooBulli and blocked me from publishing spotify images to their CDN and just returns to a Access Denied XML page (GCP) :rooBulli:

                    embed = msg.embeds[0]

                    embed.set_image(url=url)

                    # if is_new:
                    try:
                        view.message = msg = await msg.edit(embed=embed, content=None)
                    except:
                        pass
                    # else:
                    # try:
                    # await msg.delete()
                    # except:
                    # pass

                    # view = StopView(f"{spotify.title} {spotify.artists[0]}")

                    # msg = view.message = await ctx.send(embed=embed, view=view)

                    latest_spotify = spotify
                else:
                    if ctx.debug:
                        await ctx.send("2")

                    params = {
                        "title": spotify.title,
                        "cover_url": spotify.album_cover_url,
                        "duration_seconds": spotify.duration.seconds,
                        "start_timestamp": spotify.start.timestamp(),
                        "artists": spotify.artists[0],
                    }

                    async with bot.session.get(
                        "https://api.jeyy.xyz/discord/spotify", params=params
                    ) as response:
                        buf = BytesIO(await response.read())

                    url = await bot.publish_cdn(
                        buf,
                        f'spotify/{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 32)))}.png',
                    )  # discord rooBulli and blocked me from publishing spotify images to their CDN and just returns to a Access Denied XML page (GCP) :rooBulli:

                    embed = discord.Embed(color=spotify.colour)

                    embed.set_image(url=url)

                    artists = []

                    do_spotify_api = True

                    if do_spotify_api:
                        try:
                            async with bot.session.post(
                                "https://accounts.spotify.com/api/token",
                                params={"grant_type": "client_credentials"},
                                headers={
                                    "Authorization": f'Basic {base64.urlsafe_b64encode(f"{bot.spotify._client_id}:{bot.spotify._client_secret}".encode()).decode()}',
                                    "Content-Type": "application/x-www-form-urlencoded",
                                },
                            ) as resp:
                                auth_js = await resp.json()
                        except Exception as e:
                            if ctx.debug:
                                raise e

                            artists = [f"`{x}`" for x in spotify.artists]
                            album = f"`{spotify.album}`"
                        else:
                            try:
                                async with bot.session.get(
                                    f"https://api.spotify.com/v1/tracks/{urllib.parse.quote(spotify.track_id)}",
                                    params={
                                        "market": "US",
                                    },
                                    headers={
                                        "Authorization": f'Bearer {auth_js["access_token"]}'
                                    },
                                ) as resp:
                                    js = await resp.json()

                                for artist in js["artists"]:
                                    artists.append(
                                        f'[`{artist["name"]}`]({artist["external_urls"]["spotify"]})'
                                    )

                                album = f'[`{js["album"]["name"]}`]({js["album"]["external_urls"]["spotify"]})'
                            except Exception as e:
                                if ctx.debug:
                                    raise e

                                artists = [f"`{x}`" for x in spotify.artists]
                                album = f"`{spotify.album}`"

                        artists = ", ".join(artists)
                    else:
                        artists = ", ".join([f"`{x}`" for x in spotify.artists])
                        album = "`" + spotify.album + "`"

                    embed.set_author(
                        name=f"{member}'s Spotify:", icon_url=member.avatar.url
                    )

                    embed.description = f"""
> **{member}** is listening to [`{spotify.title}`]({spotify.track_url}) by {artists}
> 
> **Album:** {album}
> **Duration:** `{str(spotify.duration).split('.')[0]}` | `{humanize.naturaldelta(spotify.duration, minimum_unit="milliseconds")}`
> **Artists:** {artists}
> **Lyrics:** moved to {f'`{ctx.prefix}lyrics --from-spotify`/' if member == ctx.author else ''}`{ctx.prefix}lyrics {spotify.title} {spotify.artists[0]}`
                    """

                    embed.set_thumbnail(url=spotify.album_cover_url)

                    if is_new:
                        try:
                            view = StopView(f"{spotify.title} {spotify.artists[0]}")

                            view.message = msg = await msg.edit(
                                embed=embed, content=None, view=view
                            )
                        except:
                            pass
                    else:
                        try:
                            await msg.delete()
                        except:
                            pass

                        view = StopView(f"{spotify.title} {spotify.artists[0]}")

                        msg = view.message = await ctx.send(embed=embed, view=view)

                latest_spotify = spotify
            else:
                if ctx.debug:
                    await ctx.send("3")

                params = {
                    "title": spotify.title,
                    "cover_url": spotify.album_cover_url,
                    "duration_seconds": spotify.duration.seconds,
                    "start_timestamp": spotify.start.timestamp(),
                    "artists": spotify.artists[0],
                }

                async with bot.session.get(
                    "https://api.jeyy.xyz/discord/spotify", params=params
                ) as response:
                    buf = BytesIO(await response.read())

                url = await bot.publish_cdn(
                    buf,
                    f'spotify/{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 32)))}.png',
                )  # discord rooBulli and blocked me from publishing spotify images to their CDN and just returns to a Access Denied XML page (GCP) :rooBulli:

                embed = discord.Embed(color=spotify.colour)

                embed.set_image(url=url)

                artists = []

                do_spotify_api = True

                if do_spotify_api:
                    try:
                        async with bot.session.post(
                            "https://accounts.spotify.com/api/token",
                            params={"grant_type": "client_credentials"},
                            headers={
                                "Authorization": f'Basic {base64.urlsafe_b64encode(f"{bot.spotify._client_id}:{bot.spotify._client_secret}".encode()).decode()}',
                                "Content-Type": "application/x-www-form-urlencoded",
                            },
                        ) as resp:
                            auth_js = await resp.json()
                    except Exception as e:
                        if ctx.debug:
                            raise e

                        artists = [f"`{x}`" for x in spotify.artists]
                        album = f"`{spotify.album}`"
                    else:
                        try:
                            async with bot.session.get(
                                f"https://api.spotify.com/v1/tracks/{urllib.parse.quote(spotify.track_id)}",
                                params={
                                    "market": "US",
                                },
                                headers={
                                    "Authorization": f'Bearer {auth_js["access_token"]}'
                                },
                            ) as resp:
                                js = await resp.json()

                            for artist in js["artists"]:
                                artists.append(
                                    f'[`{artist["name"]}`]({artist["external_urls"]["spotify"]})'
                                )

                            album = f'[`{js["album"]["name"]}`]({js["album"]["external_urls"]["spotify"]})'
                        except Exception as e:
                            if ctx.debug:
                                raise e

                            artists = [f"`{x}`" for x in spotify.artists]
                            album = f"`{spotify.album}`"

                    artists = ", ".join(artists)
                else:
                    artists = ", ".join([f"`{x}`" for x in spotify.artists])
                    album = "`" + spotify.album + "`"

                embed.set_author(
                    name=f"{member}'s Spotify:", icon_url=member.avatar.url
                )

                embed.description = f"""
> **{member}** is listening to [`{spotify.title}`]({spotify.track_url}) by {artists}
> 
> **Album:** {album}
> **Duration:** `{str(spotify.duration).split('.')[0]}` | `{humanize.naturaldelta(spotify.duration, minimum_unit="milliseconds")}`
> **Artists:** {artists}
> **Lyrics:** moved to {f'`{ctx.prefix}lyrics --from-spotify`/' if member == ctx.author else ''}`{ctx.prefix}lyrics {spotify.title} {spotify.artists[0]}`
                """

                embed.set_thumbnail(url=spotify.album_cover_url)

                view = StopView(f"{spotify.title} {spotify.artists[0]}")

                msg = view.message = await ctx.send(embed=embed, view=view)

                latest_spotify = spotify
    else:
        spotify = discord.utils.find(
            lambda a: isinstance(a, discord.Spotify), member.activities
        )
        if spotify is None:
            return await ctx.send(
                f"**{member}** is not listening or connected to Spotify."
            )

        params = {
            "title": spotify.title,
            "cover_url": spotify.album_cover_url,
            "duration_seconds": spotify.duration.seconds,
            "start_timestamp": spotify.start.timestamp(),
            "artists": spotify.artists[0],
        }

        async with bot.session.get(
            "https://api.jeyy.xyz/discord/spotify", params=params
        ) as response:
            buf = BytesIO(await response.read())

        url = await bot.publish_cdn(
            buf,
            f'spotify/{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 32)))}.png',
        )  # discord rooBulli and blocked me from publishing spotify images to their CDN and just returns to a Access Denied XML page (GCP) :rooBulli:

        embed = discord.Embed(color=spotify.colour)

        embed.set_image(url=url)

        artists = []

        do_spotify_api = True

        if do_spotify_api:
            try:
                async with bot.session.post(
                    "https://accounts.spotify.com/api/token",
                    params={"grant_type": "client_credentials"},
                    headers={
                        "Authorization": f'Basic {base64.urlsafe_b64encode(f"{bot.spotify._client_id}:{bot.spotify._client_secret}".encode()).decode()}',
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                ) as resp:
                    auth_js = await resp.json()
            except Exception as e:
                if ctx.debug:
                    raise e

                artists = [f"`{x}`" for x in spotify.artists]
                album = f"`{spotify.album}`"
            else:
                try:
                    async with bot.session.get(
                        f"https://api.spotify.com/v1/tracks/{urllib.parse.quote(spotify.track_id)}",
                        params={
                            "market": "US",
                        },
                        headers={"Authorization": f'Bearer {auth_js["access_token"]}'},
                    ) as resp:
                        js = await resp.json()

                    for artist in js["artists"]:
                        artists.append(
                            f'[`{artist["name"]}`]({artist["external_urls"]["spotify"]})'
                        )

                    album = f'[`{js["album"]["name"]}`]({js["album"]["external_urls"]["spotify"]})'
                except Exception as e:
                    if ctx.debug:
                        raise e

                    artists = [f"`{x}`" for x in spotify.artists]
                    album = f"`{spotify.album}`"

            artists = ", ".join(artists)
        else:
            artists = ", ".join([f"`{x}`" for x in spotify.artists])
            album = "`" + spotify.album + "`"

        embed.set_author(name=f"{member}'s Spotify:", icon_url=member.avatar.url)

        embed.description = f"""
> **{member}** is listening to [`{spotify.title}`]({spotify.track_url}) by {artists}
> 
> **Album:** {album}
> **Duration:** `{str(spotify.duration).split('.')[0]}` | `{humanize.naturaldelta(spotify.duration, minimum_unit="milliseconds")}`
> **Artists:** {artists}
        """  # > **Lyrics:** moved to {f'`{ctx.prefix}lyrics --from-spotify`/' if member == ctx.author else ''}`{ctx.prefix}lyrics {spotify.title} {spotify.artists[0]}`

        embed.set_thumbnail(url=spotify.album_cover_url)

        view = discord.ui.View(timeout=None)
        view.add_item(LyricButton(f"{spotify.title} {spotify.artists[0]}"))

        await ctx.send(embed=embed, view=view)


@bot.command(aliases=["docs"])
async def documentation(ctx: commands.Context):
    """
    Gives the OpenRobot documentation URL.
    """

    return await ctx.send("<https://api.openrobot.xyz/api/docs>")


def codeblock(code: str, *, language=""):
    return f"```{language}\n{code}```"


bot.codeblock = codeblock


@bot.command(aliases=["src"])
async def source(
    ctx: commands.Context,
    *,
    command: str = commands.Option(
        None, description="The command name/cog/event to get the source code"
    ),
):
    """
    The source code of OpenRobot. You can get a code from a specific
    command such as `api apply`, or get a source code from a
    cog/extension by typing `cog:<Insert Cog Name>` e.g `cog:API`.
    You can also get a event source code by typing `event:<Event Name>`
    e.g `event:on_message`.

    Flags:
    - `--code`: Sends the code instead of the GitHub URL.
    """

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    try:
        if "--code" in command.split(" "):
            code = True
            command = command.replace(" --code", "")
        else:
            code = False
    except:
        code = False

    source_url = "https://github.com/OpenRobot/OpenRobot-Bot"
    branch = "main"
    if command is None:
        return await ctx.send(source_url)

    if command.startswith("cog:"):  # Cog proccessing
        command = command[4:]

        cog = bot.get_cog(command)
        if not cog:
            return await ctx.send("Could not find cog.")

        src = cog.__class__

        module = inspect.getfile(src)
    elif command.startswith("event:"):  # Event processing
        command = command[6:]

        if not command.startswith("on_"):
            command = "on_" + command

        src = getattr(bot, command, None)

        if not src:
            return await ctx.send("Could not find event.")

        if not getattr(src, "__is_overridden__", False):
            return await ctx.send("Could not find event.")

        module = inspect.getfile(src)
    else:  # Command processing
        if command == "help":
            if isinstance(
                bot.help_command,
                (commands.DefaultHelpCommand, commands.MinimalHelpCommand),
            ):
                return await ctx.send(
                    "I cannot get the source code of the help command as of now. Sorry!"
                )

            src = type(bot.help_command)
            module = src.__module__
        else:
            obj = bot.get_command(command.replace(".", " "))
            if obj is None:
                return await ctx.send("Could not find command.")

            # since we found the command we're looking for, presumably anyway, let's
            # try to access the code itself
            src = obj.callback.__code__
            module = obj.callback.__module__

    if not code:
        lines, firstlineno = inspect.getsourcelines(src)
        # location = module.replace('.', '/') + '.py'
        location = module.replace(os.getcwd() + "/", "").replace(os.getcwd(), "")

        if location.endswith(".py"):
            location = location[:-3]

        location = location.replace(".", "/") + ".py"

        final_url = f"<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>"
        return await ctx.send(final_url)
    else:
        param = {
            "text": inspect.getsource(src),
            "width": 4000,
            "replace_whitespace": False,
        }
        list_codeblock = [codeblock(cb, language="py") for cb in textwrap.wrap(**param)]
        menu = MenuPages(CodePaginator(list_codeblock), delete_message_after=True)
        await menu.start(ctx)


async def _confirm(ctx, channel=None, *args, **kwargs):
    timeout = kwargs.pop("timeout", 60)

    options = kwargs.pop("options", [])

    channel = channel or ctx.channel

    class Yes(discord.ui.Button):
        def __init__(self):
            super().__init__(
                label="Yes",
                style=discord.ButtonStyle.green,
                emoji="<:yes:814691942821920810>",
            )

        async def callback(self, interaction: discord.Interaction):
            for child in self.view.children:
                child.disabled = True

            self.view.value = True

            await interaction.message.edit(view=self.view)

            self.view.stop()

    class No(discord.ui.Button):
        def __init__(self):
            super().__init__(
                label="No",
                style=discord.ButtonStyle.red,
                emoji="<:no:814692370430951476>",
            )

        async def callback(self, interaction: discord.Interaction):
            for child in self.view.children:
                child.disabled = True

            self.view.value = False

            await interaction.message.edit(view=self.view)

            self.view.stop()

    class View(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=timeout)
            self.msg = None
            self.value = None

            if options:
                for option in options:
                    self.add_item(option)
            else:
                self.add_item(Yes())
                self.add_item(No())

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    f"This is not your interaction! Only {ctx.author} can manage and click/respond to interactions!",
                    ephemeral=True,
                )
                return False

            return True

    kwargs["view"] = view = View()

    view.msg = await channel.send(*args, **kwargs)
    await view.wait()

    return view.value


@bot.command()
async def invite(
    ctx: commands.Context,
    option: typing.Literal["Slash Commands", "Bot Invite"] = commands.Option(
        description="Either Slash Commands or Message Commands (Normal)"
    ),
):
    if option == "Bot Invite":
        url_with_slash = discord.utils.oauth_url(
            bot.user.id,
            permissions=discord.Permissions(8),
            scopes=[
                "bot",
                "applications.commands",
            ],
        )
        url = discord.utils.oauth_url(
            bot.user.id,
            permissions=discord.Permissions(8),
            scopes=[
                "bot",
            ],
        )
        return await ctx.send(
            f"With slash commands: <{url_with_slash}>\nWithout slash commands: <{url}>"
        )
    elif option == "Slash Commands":
        url = discord.utils.oauth_url(
            bot.user.id,
            permissions=discord.Permissions(8),
            scopes=[
                "applications.commands",
            ],
        )
        return await ctx.send(f"<{url}>")
    else:
        return await ctx.send("Unknown Option")  # idk when this would happen, but ok.


bot.confirm = _confirm

bot.exts = [
    #'jishaku',
    "cogs.api",
    "cogs.error",
    "cogs.music",
    "cogs.help",
    "cogs.jsk",
    "cogs.fun",
    "cogs.speech",
    "cogs.ai",
]


def start(**kwargs):
    async def parse_flags(**kwargs):
        if kwargs.get("db") is False:
            bot.pool = None
            bot.redis = None
            bot.spotify_redis = None
        else:
            bot.pool = await asyncpg.create_pool(config.DATABASE)
            # bot.spotify_pool = await asyncpg.create_pool(config.SPOTIFY_DATABASE)
            bot.redis = aioredis.Redis(**config.REDIS_DATABASE_CRIDENTIALS)
            bot.spotify_redis = aioredis.Redis(
                **config.REDIS_DATABASE_CRIDENTIALS, db=1
            )
            # bot.tb_pool = await asyncpg.create_pool(config.TRACEBACK_DATABASE)

            # bot.cache = aioredis.Redis(**config.REDIS_DATABASE_CRIDENTIALS, db=2)

        if kwargs.get("cogs") is not None and "cogs" not in kwargs:
            l = list(
                filter(lambda i: i[0].startswith("without-") and i[1], kwargs.items())
            )

            for i in l:
                try:
                    bot.exts.remove(i)
                except KeyError:
                    try:
                        bot.exts.remove("cogs." + i)
                    except:
                        pass

            for ext in bot.exts:
                try:
                    bot.load_extension(ext)
                except:
                    pass
        elif kwargs.get("cogs") is True:
            for ext in bot.exts:
                try:
                    bot.load_extension(ext)
                except:
                    pass
        else:
            pass

        if kwargs.get("colour") and bot.color is None:
            try:
                bot.color = await commands.ColourConverter().convert(
                    None, kwargs.get("colour")
                )  # ctx argument isn't used, so we'll just pass in None.
            except:
                pass

        if kwargs.get("color") and bot.color is None:
            try:
                bot.color = await commands.ColourConverter().convert(
                    None, kwargs.get("color")
                )  # ctx argument isn't used, so we'll just pass in None.
            except:
                pass

        bot.color = bot.color or discord.Colour(0x38B6FF)

    async def do_on_ready():
        await bot.wait_until_ready()

        bot.owner = bot.get_user(699839134709317642)

        try:
            await bot.cogs["Music"].initiate_node()
        except KeyError:  # Cog isnt loaded
            pass

    async def do_restart_message():
        await bot.wait_until_ready()

        utcnow = discord.utils.utcnow()

        with open("restart.json", "r") as f:
            js: dict = json.load(f)

        with open("restart.json", "w") as f:
            json.dump({}, f, indent=4)

        if ("channel_id" in js) and ("message_id" in js) and ("restarted_at" in js):
            restarted_at = datetime.datetime.fromtimestamp(
                js["restarted_at"], tz=datetime.timezone.utc
            )
            restart_duration = utcnow - restarted_at

            chan = bot.get_channel(js["channel_id"])

            if chan:
                msg = chan.get_partial_message(js["message_id"])

                try:
                    await msg.edit(
                        embed=discord.Embed(
                            description=f"Back in `{restart_duration.seconds} seconds`.",
                            color=bot.color,
                        )
                    )
                except:
                    pass

    async def send_online_msg():
        await bot.wait_until_ready()

        utcnow = discord.utils.utcnow()

        webhook = discord.Webhook.from_url(config.UPTIME_WEBHOOK, session=bot.session)
        await webhook.send(
            embed=discord.Embed(
                description=f'<:status_online:596576749790429200> OpenRobot is going online and up!\n\nAt: {discord.utils.format_dt(utcnow, "F")}',
                color=bot.color,
                timestamp=utcnow,
            )
        )

    def start_tasks():
        bot.loop.create_task(parse_flags(**kwargs))
        bot.loop.create_task(do_on_ready())
        bot.loop.create_task(do_restart_message())
        bot.loop.create_task(send_online_msg())

        try:
            bot.loop.create_task(bot.cogs["Music"].renew())
        except KeyError:  # Cog isnt loaded
            pass

        try:
            bot.loop.create_task(bot.cogs["Error"].initiate_tb_pool())
        except KeyError:  # Cog isnt loaded
            pass

        ChristmasEvent(bot).start()

    start_tasks()

    try:
        bot.run(config.TOKEN)
    finally:
        utcnow = discord.utils.utcnow()

        webhook = discord.SyncWebhook.from_url(config.UPTIME_WEBHOOK)
        webhook.send(
            embed=discord.Embed(
                description=f'<:status_offline:596576752013279242> OpenRobot is going offline and shutting down!\n\nAt: {discord.utils.format_dt(utcnow, "F")}',
                color=bot.color,
                timestamp=utcnow,
            )
        )

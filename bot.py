import re
import os
import json
import time
import copy
import urllib
import typing
import random
import string
import base64
import shutil
import asyncio
import logging
import inspect
import pathlib
import platform
import datetime
import textwrap

from io import BytesIO, StringIO
from collections import namedtuple

import psutil
import discord
import asyncpg
import jishaku
import aiohttp
import mystbin
import cpuinfo
import humanize
import aioredis
import tabulate
import speedtest
import aiospotify
import async_timeout

from discord.ext import commands
from humanize import naturalsize as get_size
from openrobot import discord_activities as discord_activity

import config

from cogs.utils import (
    MenuPages,
    CodePaginator,
    executor,
    Bot as BaseBot,
    ChristmasEvent,
    Command,
    ApplyPrefix,
    case_insensitive_prefix,
    no_prefix_for_owner,
    checks,
    rdanny,
    naturalnumber,
)

from cogs.utils.spotify import spotify as spotify_img

description = """
I am OpenRobot. I provide help and utilities for OpenRobot stuff such as our API (Hosted at <https://api.openrobot.xyz>).

GitHub: <https://github.com/OpenRobot>
Website: <https://openrobot.xyz/>
"""

LineCount = namedtuple("LineCount", ["files", "lines", "classes", "functions", "coroutines", "comments"],
                       defaults=(0,) * 6)


class Bot(BaseBot):
    CDN_BUCKET = "cdn.openrobot.xyz"
    ICDN_URL = "icdn.openrobot.xyz"

    @staticmethod
    def line_count(directory: str = "./") -> LineCount:
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
    def screenshot(self, url: str, *, delay: int = None, ad_block: bool = False, use_proxy: bool = False):
        if delay is not None:
            if delay <= 0:
                delay = None

        with self.driver(ad_block=ad_block or False, use_proxy=use_proxy or False) as driver:
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
    def publish_s3_cdn(
            self, fp: BytesIO | bytes, filename: str, *, raw: bool = False
    ) -> str | dict | typing.Any:
        hash = "".join(
            random.choices(
                string.ascii_letters + string.digits, k=random.randint(10, 32)
            )
        )

        file_type = filename.split(".")
        file_type = file_type[-1]

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

    async def publish_icdn(
            self, fp: BytesIO | bytes, content_type: str = None, *, raw: bool = False
    ) -> str | dict | typing.Any:
        data = aiohttp.FormData()
        data.add_field("file", BytesIO(fp), content_type=content_type)

        async with self.session.post(f"https://{self.ICDN_URL}/upload", headers={'Authorization': config.ICDN_TOKEN},
                                     data=data) as resp:
            js = await resp.json()

            if raw:
                return js
            else:
                return f"https://{self.ICDN_URL}/{js['file_id']}"

    async def publish_cdn(self, *args, imoog: bool = False, try_both=False, **kwargs):
        if try_both:
            if imoog:
                try:
                    return await self.publish_icdn(*args, **kwargs)
                except:
                    return await self.publish_s3_cdn(*args, **kwargs)
            else:
                try:
                    return await self.publish_s3_cdn(*args, **kwargs)
                except:
                    return await self.publish_icdn(*args, **kwargs)

        if imoog:
            return await self.publish_icdn(*args, **kwargs)
        else:
            return await self.publish_s3_cdn(*args, **kwargs)

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

        # await self.spotify.close() Broken: AttributeError: 'HTTPClient' object has no attribute 'close'

        await self.session.close()

        return await super().close()


bot = Bot(
    command_prefix=ApplyPrefix(
        config.PREFIXES,

        case_insensitive_prefix(),
        commands.when_mentioned,
        # no_prefix_for_owner(),
    ),
    owner_ids=config.OWNER_IDS,
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


logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


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


@bot.event
@override
async def on_message_edit(before: discord.Message, after: discord.Message):
    if after.content == before.content:
        return  # Do not process commands if the msg content is the same, e.g. URL Embed, etc.

    await bot.process_commands(after)


@bot.command(name="beta", cls=Command, example="beta spotify", hidden=True)
async def execute_beta(ctx: commands.Context, *command):
    if not command:
        return await ctx.send("A command name is a required argument to provide!")

    msg = copy.copy(ctx.message)
    msg.content = f"{ctx.prefix}" + " ".join(command)

    ctx = await bot.get_context(msg)

    ctx.beta = True

    return await bot.invoke(ctx)


@bot.command(aliases=["latency"], cls=Command, example="ping")
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
            .set_author(name="Latency/Ping Info:", icon_url=ctx.author.display_avatar.url)
            .set_footer(icon_url=ctx.author.display_avatar.url, text=f"Requested by: {ctx.author}")
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

    embed.add_field(
        name="Average Discord Latency:",
        value=do_ping_string(round((web_ping + typing_ping + bot_latency) / 3, 2)),
        inline=False,
    )

    if bot.pool is not None:
        postgresql_ping = await bot.ping.database.postgresql()
    else:
        postgresql_ping = None

    if bot.spotify_pool is not None:
        postgresql_spotify_ping = await bot.ping.database.postgresql(spotify=True)
    else:
        postgresql_spotify_ping = None

    psql_ping = None
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

    if redis_ping and psql_ping:
        embed.add_field(
            name=f'Average Database Latency:',
            value=do_ping_string(round((redis_ping + psql_ping) / 2, 2)),
        )

    embed.add_field(
        name=f'{bot.ping.EMOJIS["openrobot-api"]} OpenRobot API Latency:',
        value=do_ping_string(round(await bot.ping.api.openrobot() * 1000, 2)),
        # inline=False,
    )

    embed.add_field(
        name=f'{bot.ping.EMOJIS["jeyy-api"]} Jeyy API Latency:',
        value=do_ping_string(round(await bot.ping.api.jeyy() * 1000, 2)),
    )

    # embed.add_field(
    #     name=f'{bot.ping.EMOJIS["dagpi"]} Dagpi API Latency:',
    #     value=do_ping_string(round(await bot.ping.api.dagpi() * 1000, 2)),
    # )

    # embed.add_field(
    #     name=f'{bot.ping.EMOJIS["waifu-im"]} Waifu.im API Latency:',
    #     value=do_ping_string(round(await bot.ping.api.waifu_im() * 1000, 2)),
    # )

    embed.add_field(
        name=f'{bot.ping.EMOJIS["repi"]} OpenRobot REPI API Latency:',
        value=do_ping_string(round(await bot.ping.api.repi() * 1000, 2)),
    )

    # await msg.delete()
    await msg.edit(
        embed=embed, content=None, allowed_mentions=discord.AllowedMentions.none()
    )


@bot.command("uptime", aliases=["up"])
async def uptime(ctx: commands.Context):
    """
    Gets the Uptime info of the bot.
    """

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    embed = (
        discord.Embed(color=bot.color, timestamp=ctx.message.created_at)
            .set_author(name="Uptime Info:", icon_url=ctx.author.display_avatar.url)
            .set_footer(icon_url=ctx.author.display_avatar.url, text=f"Requested by: {ctx.author}")
    )

    time_elapsed = discord.utils.utcnow() - bot.start_time

    embed.description = f"""
**Uptime:** `{humanize.naturaldelta(time_elapsed)}`
**Launch/Start Time:** {discord.utils.format_dt(bot.start_time, 'F')} | {discord.utils.format_dt(bot.start_time, 'R')}
**Messages sent since last restart:** `{bot.sent_messages}`
**Messages edited since last restart:** `{bot.edited_messages}`
**Messages deleted since last restart:** `{bot.deleted_messages}`

**Commands invoked since last restart:** `{bot.commands_invoked}`
    """

    await ctx.send(embed=embed)


@bot.command("system", aliases=["sys", "info"], cls=Command, example="system")
async def system(ctx: commands.Context):
    """
    Gets system information e.g CPU, Memory, Disk, etc.
    """

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    async with ctx.typing():
        embed = discord.Embed(color=bot.color)

        msg = await ctx.send(
            "Retrieving Basic Information...",
            allowed_mentions=discord.AllowedMentions.none(),
        )

        start = time.perf_counter()

        embed.description = f"""```yml
Python Version: Python {platform.python_version()}
Discord.py Version: {discord.__version__}
Guilds: {len(bot.guilds)}
Members: {len(list(bot.get_all_members()))}```
        """

        await msg.edit(
            content="Retrieving System Information...",
            allowed_mentions=discord.AllowedMentions.none(),
        )

        uname = platform.uname()
        system_name = uname.system
        node_name = uname.node
        machine = uname.machine
        processor = uname.processor

        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time(), datetime.timezone.utc)

        embed.add_field(
            name="System:",
            value=f"""Boot Time: {discord.utils.format_dt(boot_time, 'F')} | {discord.utils.format_dt(boot_time, 'R')}
```yml
OS: {system_name}
Name: {node_name}
Machine: {machine}
Processor: {processor}```
        """,
            inline=False,
        )

        await msg.edit(
            content="Retrieving CPU Information...",
            allowed_mentions=discord.AllowedMentions.none(),
        )

        physical_cores = psutil.cpu_count(logical=False)
        total_cores = psutil.cpu_count(logical=True)

        cpufreq = psutil.cpu_freq()
        current_cpu_freq = f"{cpufreq.current:.2f}Mhz"

        cpu_usage = []

        total_cpu_usage = psutil.cpu_percent()

        for i, usage in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
            cpu_usage.append(f"Core {i}: {usage}%")

        cpu_usage = '\n'.join(cpu_usage)

        embed.add_field(
            name="CPU:",
            value=f"""```yml
Name: {cpuinfo.get_cpu_info()['brand_raw']}
Physical cores: {physical_cores}
Total cores: {total_cores}
Frequency: {current_cpu_freq}
```
        """,
        )

        embed.add_field(
            name="CPU Usage:",
            value=f"""```yml
Total CPU Usage: {total_cpu_usage}%

{cpu_usage}
```
            """,
        )

        await msg.edit(
            content="Retrieving Code Information...",
            allowed_mentions=discord.AllowedMentions.none(),
        )

        line_count = bot.line_count()

        embed.add_field(
            name="Code Stats:",
            value=f"""```yml
Files: {line_count.files}
Lines: {line_count.lines}
Classes: {line_count.classes}
Functions: {line_count.functions}
Coroutines: {line_count.coroutines}
Comments: {line_count.comments}```
        """,
            inline=False,
        )

        await msg.edit(
            content="Retrieving Memory Information...",
            allowed_mentions=discord.AllowedMentions.none(),
        )

        svmem = psutil.virtual_memory()
        total_mem = f"{get_size(svmem.total)}"
        available_mem = f"{get_size(svmem.available)}"
        free_mem = f"{get_size(svmem.free)}"
        used_mem = f"{get_size(svmem.used)}"
        mem_perc = f"{svmem.percent}%"

        embed.add_field(
            name="Memory:",
            value=f"""```yml
Total: {total_mem}
Available: {available_mem}
Free: {free_mem}
Used: {used_mem}
Percentage: {mem_perc}```
        """,
        )

        await msg.edit(
            content="Retrieving Disk Information...",
            allowed_mentions=discord.AllowedMentions.none(),
        )

        disk_io = psutil.disk_io_counters()
        disk_io_bytes_read = f"{get_size(disk_io.read_bytes)}"
        disk_io_bytes_send = f"{get_size(disk_io.write_bytes)}"

        total, used, free = shutil.disk_usage("/")

        total_gib = total // (2 ** 30)
        used_gib = used // (2 ** 30)
        free_gib = free // (2 ** 30)
        percentage_used = used_gib / total_gib * 100
        percentage_free = free_gib / total_gib * 100

        embed.add_field(
            name="Disk:",
            value=f"""```yml
Total: {total_gib} GiB
Used: {used_gib} GiB
Free: {free_gib} GiB
Percentage Used: {round(percentage_used, 1)}%

Read: {disk_io_bytes_read}
Send: {disk_io_bytes_send}```
        """,
        )

        await msg.edit(
            content="Retrieving Network and Speedtest Information...",
            allowed_mentions=discord.AllowedMentions.none(),
        )

        net_io = psutil.net_io_counters()
        net_io_bytes_sent = f"{get_size(net_io.bytes_sent)}"
        net_io_bytes_recv = f"{get_size(net_io.bytes_recv)}"
        packets_sent = f"{naturalnumber(net_io.packets_sent)} ({net_io.packets_sent:,})"
        packets_recv = f"{naturalnumber(net_io.packets_recv)} ({net_io.packets_recv:,})"

        embed.add_field(
            name="Network:",
            value=f"""```yml
Bytes Sent: {net_io_bytes_sent}
Bytes Received: {net_io_bytes_recv}
Packets Sent: {packets_sent}
Packets Received: {packets_recv}```
        """,
            inline=False,
        )

        proc = await asyncio.create_subprocess_shell(
            "speedtest -f json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if ctx.debug:
            await ctx.send("Stdout: " + (stdout.decode() or "Empty."))
            await ctx.send("Stderr: " + (stderr.decode() or "Empty."))
            await ctx.send("Return Code: " + str(proc.returncode))

        if not stdout or proc.returncode != 0 or stderr:
            s = speedtest.Speedtest()
            s.get_best_server()
            s.download()
            s.upload(pre_allocate=False)

            data = s.results.dict()

            try:
                s.get_servers([23373, 37568])

                s.download()
                s.upload(pre_allocate=False)

                data2 = s.results.dict()

                if (
                        data["download"] < data2["download"]
                        and data["upload"] < data2["upload"]
                ):
                    data = data2
            except Exception as e:
                if ctx.debug:
                    raise e

                pass

            embed.add_field(
                name="Speedtest:",
                value=f"""`{data['client']['isp']}, {data['client']['country']}` --> `{data['server']['sponsor']} - {data['server']['name']}, {data['server']['cc']}`: 
```yml
Download: {round(data['download'] / 1000000, 2)} Mbps ({round(data['download'] / 1000000 / 1000, 2)} Gbps)
Upload: {round(data['upload'] / 1000000, 2)} Mbps ({round(data['upload'] / 1000000 / 1000, 2)} Gbps)
Ping: {round(data['ping'], 2)} ms

Bytes Sent: {round(data['bytes_sent'], 5)}
Bytes Received: {round(data['bytes_received'], 5)}
```Result URL: {'https://' + '.'.join(s.results.share().replace('http://', '').split('.')[:-1])}
            """,
                inline=False,
            )
        else:
            data = json.loads(stdout.decode())

            embed.add_field(
                name="Speedtest:",
                value=f"""`{data['isp']}` --> `{data['server']['name']} - {data['server']['location']}, {data['server']['country']}`:
```yml
Download: 
- Result: {round(data['download']['bandwidth'] / 125000, 2)} Mbps ({round(data['download']['bandwidth'] / 125000 / 1000, 2)} Gbps)
- Data Used: {get_size(data['download']['bytes'])}

Upload:
- Result: {round(data['upload']['bandwidth'] / 125000, 2)} Mbps ({round(data['upload']['bandwidth'] / 125000 / 1000, 2)} Gbps)
- Data Used: {get_size(data['upload']['bytes'])}

Ping:
- Jitter: {round(data['ping']['jitter'], 2)} ms
- Latency: {round(data['ping']['latency'], 2)} ms

Packet Loss: {str(round(data['packetLoss'], 2)) + '%' if 'packetLoss' in data else 'Not available.'}
```Result URL: {data['result']['url']}
            """,
                inline=False,
            )

        embed.set_footer(text=f"PID: {os.getpid()}")

        end = time.perf_counter()

        await msg.delete()

        await ctx.send(content=f'Time took: {round(end - start, 1)}s', embed=embed)


# @bot.command(
#     aliases=["act"], cls=Command, example="activity My-VC-Channel Watch Together"
# )
async def activity(
        ctx: commands.Context,
        channel: typing.Optional[discord.VoiceChannel] = commands.Option(
            None, description="The voice channel to start the activity. Defaults to the channel you are in."
        ),
        *,
        activity: typing.Literal[
            "Watch Together",
            "Poker Night",
            "Chess",
            "Sketch Heads",
            "Word Snacks",
            "Letter Leauge",
            "Spellcast",
            "Checkers",
            "Fishington",
            "Betrayal",
            "Ocho"
        ] = commands.Option(None, description="The activity to start."),
):
    channel = channel or (ctx.author.voice.channel if ctx.author.voice else None)

    if channel is None:
        return await ctx.send("A channel is required to start the activity!")

    if channel.permissions_for(ctx.me).create_instant_invite is False:
        return await ctx.send(
            f"I need the `Create Invite` permissions for {channel.mention} to start the activity!"
        )

    if activity is None:
        activities = discord_activity.ActivityType._member_names_

        class Select(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Select an activity",
                    options=[
                        discord.SelectOption(
                            label=x.replace("_", " ").title(),
                            description=f"Start a {x.replace('_', ' ').title()} activity.",
                        )
                        for x in activities
                    ],
                )

            async def callback(self, interaction: discord.Interaction):
                nonlocal activity
                activity = self.values[0]

                await interaction.message.delete()

                self.view.stop()

        class View(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)

                self.add_item(Select())

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user != ctx.author and not await bot.is_owner(
                        ctx.author
                ):
                    await interaction.response.send_message(
                        "This is not your interaction!", ephemeral=True
                    )

                    return False

                return True

        view = View()
        await ctx.send("Please select an activity to start.", view=view)

        await view.wait()

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


# @activity.error
async def activity_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.BadLiteralArgument):
        await ctx.send("Invalid activity.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide a channel.")

@bot.command(cls=Command, name='claimable-tags', aliases=['claimabletags', 'claimable_tags'])
@checks.rdanny_in_guild()
@commands.max_concurrency(1, commands.BucketType.guild)
@commands.cooldown(1, 60, commands.BucketType.guild)
async def claimable_tags(ctx: commands.Context):
    """
    Searches for claimable text in R. Danny for your server.

    This may not work as expected yet. It's a work in progress.
    """

    await ctx.send("Please invoke the `tag all --text` command from R.Danny for him to send the file.")

    try:
        cmd_invoke = await bot.wait_for('message', check=lambda m: m.content.strip().replace(' ', '').endswith(
            'tagall--text') and m.author.id == ctx.author.id, timeout=60)
    except asyncio.TimeoutError:
        return await ctx.send("I did not see a response from you. Please try again later.")

    try:
        m = await bot.wait_for('message', check=lambda m: m.attachments and m.author.id == 80528701850124288,
                               timeout=60)
    except asyncio.TimeoutError:
        return await ctx.send("I did not see a response from R.Danny. Please try again later.")

    if not m.attachments[0].content_type.startswith('text/plain'):
        return await ctx.send('Error: File sent is not a text file. Please try again later.')

    contents = await m.attachments[0].read()

    contents = contents.decode('utf-8')

    process = await ctx.message.reply(
        f'<a:openrobot_searching_gif:899928367799885834> Processing... This might take a while.',
        allowed_mentions=discord.AllowedMentions.none())

    try:
        tags = rdanny.Tags.parse(contents)

        if ctx.debug:
            await ctx.send(discord.File(json.dumps(tags.data, indent=4), filename='tags.json'))

        claimable_tags: set[rdanny.TagItem] = set()  # typehints are for linters cause seems like they don't recognize
        # them.

        for tag in tags:
            # Having tons of tags and using fetch_user will just
            # Make the bot API banned and making it to be an
            # API abuse. Because of this, I'll just be using
            # .get_member and .members to check.

            if not ctx.guild.get_member(tag.owner_id) or tag.owner_id not in [x.id for x in ctx.guild.members]:
                claimable_tags.add(tag)

        if not claimable_tags:
            return await ctx.send('No tags were found that are claimable.')

        headers = ['ID', 'Name', 'Owner ID', 'Uses', 'Is Alias']
        table = [[tag.id, tag.name, tag.user_id, tag.uses, tag.is_alias] for tag in claimable_tags]

        generated_table = tabulate.tabulate(table, headers, tablefmt='fancy_grid')

        file = discord.File(StringIO(generated_table), filename='claimable_tags.txt')

        try:
            await process.delete()
        except:
            pass

        await ctx.send(file=file)
    except Exception as e:
        ctx.command.reset_cooldown(ctx)

        if ctx.debug:
            raise e

        return await ctx.send('Something wen\'t wrong. Please try again later.')


@bot.command(cls=Command, example="lyrics See You Again")
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


@bot.command(aliases=["ss"], cls=Command, example="screenshot https://google.com/")
async def screenshot(
        ctx: commands.Context,
        url: str = commands.Option(description="The website URL to screenshot."),
        delay: typing.Optional[int] = commands.Option(
            None, description="Waits for x seconds before taking the screenshot."
        ),
        *,
        flags: str = commands.Option(
            None, description="Flags to pass to the screenshot utility."
        )
):
    """
    Screenshots a URL.

    Flags:
    `--proxy`: Uses a proxy to connect to the website.
    `--ad-block`: Activates ad-block.
    """

    flags = (flags or "").split(" ")

    use_proxy = "--proxy" in flags
    ad_block = "--ad-block" in flags

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()
    else:
        await ctx.message.add_reaction("<a:openrobot_searching_gif:899928367799885834>")

    url = url.strip('<>')  # Strips < and > from the URL e.g <https://google.com> to https://google.com.

    if not re.match(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            url,
    ):
        await ctx.message.remove_reaction(
            "<a:openrobot_searching_gif:899928367799885834>", bot.user
        )

        return await ctx.send("URL must be HTTP/HTTPS.")

    try:
        buffer: BytesIO = await bot.screenshot(url, delay=delay, use_proxy=use_proxy, ad_block=ad_block)
    except Exception as e:
        await ctx.message.remove_reaction(
            "<a:openrobot_searching_gif:899928367799885834>", bot.user
        )

        if ctx.debug:
            raise e

        return await ctx.send(f"Error: {e}")

    render_msg = await bot.get_channel(847804286933925919).send(
        file=discord.File(fp=BytesIO(buffer.getvalue()), filename="screenshot.png")
    )

    if not ctx.channel.is_nsfw():
        check = await bot.api.nsfw_check(render_msg.attachments[0].url)

        is_unsafe = check.score > 50 or bool(check.labels)

        if is_unsafe:
            await ctx.message.remove_reaction(
                "<a:openrobot_searching_gif:899928367799885834>", bot.user
            )

            return await ctx.send(
                "This website seems to be NSFW/Inappropriate. I am sorry, but I may not be able to send the "
                "screenshot result in this channel. "
            )

    await ctx.message.remove_reaction(
        "<a:openrobot_searching_gif:899928367799885834>", bot.user
    )

    embed = discord.Embed(color=bot.color)

    embed.description = f"[`{url}`]({url})"

    embed.set_image(url="attachment://screenshot.png")

    embed.set_footer(text=f"Requested by: {ctx.author} | Delay: {delay}s.")

    class View(discord.ui.View):
        @discord.ui.button(
            label="Delete",
            emoji="<:trash2:951507686711758848>",
            style=discord.ButtonStyle.red,
        )
        async def delete(
                self, button: discord.ui.Button, interaction: discord.Interaction
        ):
            await interaction.message.delete()
            self.stop()

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            has_perms = interaction.user == ctx.author or interaction.user.guild_permissions.manage_messages if \
                interaction.guild else False

            if not has_perms:
                await interaction.response.send_message('This is not your interaction!', ephemeral=True)

            return has_perms

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


@bot.command(aliases=["sp"], cls=Command, example="spotify @Member")
async def spotify(
        ctx: commands.Context, member: typing.Optional[discord.Member] = None, *flags
):
    """
    Shows a member's currently listening track in spotify. Defaults to yourself.

    Flags:
    - `--sync`: Enables the Auto Spotify Sync feature (Automatically edits the message).
    - `--quick`: This disables the `Possible Members Listening`. This is used for debug purposes only.
    - `--api`: Uses [Jeyy API](https://api.jeyy.xyz) instead of local PIL image manipulation. This is used for debug purposes only.
    """

    member = member or ctx.author

    flags = [x.lower() for x in flags]

    sync = "--sync" in flags
    quick = "--quick" in flags
    use_api = "--api" in flags

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

    def get_possible_members_in_same_session(member, spotify: discord.Spotify):
        if quick:
            return []

        l = []

        member_checked = set()

        for mem in bot.get_all_members():
            if (
                    mem.id == member.id or mem in member_checked
            ):
                continue

            spot = discord.utils.find(
                lambda a: isinstance(a, discord.Spotify), mem.activities
            )

            if spot:
                if spot._sync_id == spotify._sync_id:
                    l.append(mem)

            member_checked.add(mem)

        return l

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

                    if use_api:
                        params = {
                            "title": spotify.title,
                            "cover_url": spotify.album_cover_url,
                            "duration_seconds": spotify.duration.seconds,
                            "start_timestamp": spotify.start.timestamp(),
                            "artists": spotify.artists,
                        }

                        async with bot.session.get(
                                "https://api.jeyy.xyz/discord/spotify", params=params
                        ) as response:
                            buf = BytesIO(await response.read())
                    else:
                        async with bot.session.get(spotify.album_cover_url) as resp:
                            cover_buff = BytesIO(await resp.read())

                        buf = await spotify_img(title=spotify.title, artists=spotify.artists, cover_buff=cover_buff,
                                                duration=spotify.duration.seconds, start=spotify.start.timestamp(),
                                                beta=ctx.beta)

                    url = await bot.publish_cdn(
                        buf,
                        f'spotify/{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 32)))}.png',
                    )  # discord rooBulli and blocked me from publishing spotify images to their CDN and just returns
                    # to a Access Denied XML page (GCP) :rooBulli:

                    embed = msg.embeds[0]

                    embed.set_image(url=url)

                    embed.description = "\n".join(embed.description.split("\n")[:-1])

                    if not quick:
                        members_listening = get_possible_members_in_same_session(
                            member, spotify
                        )
                        embed.description += "\n> **Possible Members Listening:** "

                        if not members_listening:
                            embed.description += "None."
                        else:
                            for member in members_listening:
                                embed.description += f"\n> - {member.mention} - `{member}`"

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

                    if use_api:
                        params = {
                            "title": spotify.title,
                            "cover_url": spotify.album_cover_url,
                            "duration_seconds": spotify.duration.seconds,
                            "start_timestamp": spotify.start.timestamp(),
                            "artists": spotify.artists,
                        }

                        async with bot.session.get(
                                "https://api.jeyy.xyz/discord/spotify", params=params
                        ) as response:
                            buf = BytesIO(await response.read())
                    else:
                        async with bot.session.get(spotify.album_cover_url) as resp:
                            cover_buff = BytesIO(await resp.read())

                        buf = await spotify_img(title=spotify.title, artists=spotify.artists, cover_buff=cover_buff,
                                                duration=spotify.duration.seconds, start=spotify.start.timestamp(),
                                                beta=ctx.beta)

                    url = await bot.publish_cdn(
                        buf,
                        f'spotify/{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 32)))}.png',
                    )  # discord rooBulli and blocked me from publishing spotify images to their CDN and just returns
                    # to a Access Denied XML page (GCP) :rooBulli:

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
                        name=f"{member}'s Spotify:", icon_url=member.display_avatar.url
                    )

                    embed.description = f"""
> **{member}** is listening to [`{spotify.title}`]({spotify.track_url}) by {artists}
> 
> **Album:** {album}
> **Duration:** `{str(spotify.duration).split('.')[0]}` | `{humanize.naturaldelta(spotify.duration, minimum_unit="milliseconds")}`
> **Listening Since:** {discord.utils.format_dt(spotify.start, style="F")} [{discord.utils.format_dt(spotify.start, style="R")}]
> **Artists:** {artists}
                    """  # > **Lyrics:** moved to {f'`{ctx.prefix}lyrics --from-spotify`/' if member == ctx.author else ''}`{ctx.prefix}lyrics {spotify.title} {spotify.artists[0]}`

                    if not quick:
                        members_listening = get_possible_members_in_same_session(
                            member, spotify
                        )

                        embed.description += "> \n> **Possible Members Listening:** "

                        if not members_listening:
                            embed.description += "None."
                        else:
                            for member in members_listening:
                                embed.description += f"\n> - {member.mention} - `{member}`"

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

                if use_api:
                    params = {
                        "title": spotify.title,
                        "cover_url": spotify.album_cover_url,
                        "duration_seconds": spotify.duration.seconds,
                        "start_timestamp": spotify.start.timestamp(),
                        "artists": spotify.artists,
                    }

                    async with bot.session.get(
                            "https://api.jeyy.xyz/discord/spotify", params=params
                    ) as response:
                        buf = BytesIO(await response.read())
                else:
                    async with bot.session.get(spotify.album_cover_url) as resp:
                        cover_buff = BytesIO(await resp.read())

                    buf = await spotify_img(title=spotify.title, artists=spotify.artists, cover_buff=cover_buff,
                                            duration=spotify.duration.seconds, start=spotify.start.timestamp(),
                                            beta=ctx.beta)

                url = await bot.publish_cdn(
                    buf,
                    f'spotify/{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 32)))}.png',
                )  # discord rooBulli and blocked me from publishing spotify images to their CDN and just returns to
                # a Access Denied XML page (GCP) :rooBulli:

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
                    name=f"{member}'s Spotify:", icon_url=member.display_avatar.url
                )

                embed.description = f"""
> **{member}** is listening to [`{spotify.title}`]({spotify.track_url}) by {artists}
> 
> **Album:** {album}
> **Duration:** `{str(spotify.duration).split('.')[0]}` | `{humanize.naturaldelta(spotify.duration, minimum_unit="milliseconds")}`
> **Listening Since:** {discord.utils.format_dt(spotify.start, style="F")} [{discord.utils.format_dt(spotify.start, style="R")}]
> **Artists:** {artists}
                """  # > **Lyrics:** moved to {f'`{ctx.prefix}lyrics --from-spotify`/' if member == ctx.author else ''}`{ctx.prefix}lyrics {spotify.title} {spotify.artists[0]}`

                if not quick:
                    members_listening = get_possible_members_in_same_session(
                        member, spotify
                    )

                    embed.description += "> \n> **Possible Members Listening:** "

                    if not members_listening:
                        embed.description += "None."
                    else:
                        for member in members_listening:
                            embed.description += f"\n> - {member.mention} - `{member}`"

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

        if use_api:
            params = {
                "title": spotify.title,
                "cover_url": spotify.album_cover_url,
                "duration_seconds": spotify.duration.seconds,
                "start_timestamp": spotify.start.timestamp(),
                "artists": spotify.artists,
            }

            async with bot.session.get(
                    "https://api.jeyy.xyz/discord/spotify", params=params
            ) as response:
                buf = BytesIO(await response.read())
        else:
            async with bot.session.get(spotify.album_cover_url) as resp:
                cover_buff = BytesIO(await resp.read())

            buf = await spotify_img(title=spotify.title, artists=spotify.artists, cover_buff=cover_buff,
                                    duration=spotify.duration.seconds, start=spotify.start.timestamp(), beta=ctx.beta)

        url = await bot.publish_cdn(
            buf,
            f'spotify/{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 32)))}.png',
        )  # discord rooBulli and blocked me from publishing spotify images to their CDN and just returns to a Access
        # Denied XML page (GCP) :rooBulli:

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

        embed.set_author(name=f"{member}'s Spotify:", icon_url=member.display_avatar.url)

        embed.description = f"""
> **{member}** is listening to [`{spotify.title}`]({spotify.track_url}) by {artists}
> 
> **Album:** {album}
> **Duration:** `{str(spotify.duration).split('.')[0]}` | `{humanize.naturaldelta(spotify.duration, minimum_unit="milliseconds")}`
> **Listening Since:** {discord.utils.format_dt(spotify.start, style="F")} [{discord.utils.format_dt(spotify.start, style="R")}]
> **Artists:** {artists}
        """  # > **Lyrics:** moved to {f'`{ctx.prefix}lyrics --from-spotify`/' if member == ctx.author else ''}`{ctx.prefix}lyrics {spotify.title} {spotify.artists[0]}`

        if not quick:
            members_listening = get_possible_members_in_same_session(member, spotify)

            embed.description += "> \n> **Possible Members Listening:** "

            if not members_listening:
                embed.description += "None."
            else:
                for member in members_listening:
                    embed.description += f"\n> - {member.mention} - `{member}`"

        embed.set_thumbnail(url=spotify.album_cover_url)

        view = discord.ui.View(timeout=None)
        view.add_item(LyricButton(f"{spotify.title} {spotify.artists[0]}"))

        await ctx.send(embed=embed, view=view)


@bot.command(aliases=["docs"], cls=Command, example="documentation")
async def documentation(ctx: commands.Context):
    """
    Gives the OpenRobot documentation URL.
    """

    return await ctx.send("<https://api.openrobot.xyz/api/docs>")


def codeblock(code: str, *, language=""):
    return f"```{language}\n{code}```"


bot.codeblock = codeblock


@bot.command(aliases=["src"], cls=Command, example="source spotify")
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

    new = kwargs.pop('new', False)

    if edit_msg := kwargs.pop('edit', None):
        view.msg = await edit_msg.edit(*args, **kwargs)
    elif kwargs.pop('reply', False):
        view.msg = await ctx.reply(*args, **kwargs)
    else:
        view.msg = await channel.send(*args, **kwargs)
    wait = await view.wait()

    if new:
        return view, view.value, wait
    else:
        return view.value


@bot.command(cls=Command, example="invite")
async def invite(
        ctx: commands.Context,
        *,
        option: typing.Literal["Slash Commands", "Bot Invite"] = commands.Option(
            "Bot Invite", description="Either Slash Commands or Message Commands (Normal)"
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
        return await ctx.send("Unknown Option")  # IDK when this would happen, but ok.


bot.confirm = _confirm

bot.exts = [
    # 'jishaku',
    "cogs.api",
    "cogs.error",
    # "cogs.music",
    "cogs.help",
    "cogs.jsk",
    "cogs.fun",
    "cogs.speech",
    "cogs.ai",
    "cogs.repi",
    "cogs.ipc",
    "cogs.events",
    "cogs.maps"
]


def start(**kwargs):
    async def parse_flags(**kwargs):
        if kwargs.get("db") is False:
            bot.pool = None
            bot.redis = None
            bot.spotify_redis = None
            bot.rethinkdb = None
        else:
            bot.pool = await asyncpg.create_pool(config.DATABASE)
            # bot.spotify_pool = await asyncpg.create_pool(config.SPOTIFY_DATABASE)
            bot.redis = aioredis.Redis(**config.REDIS_DATABASE_CRIDENTIALS)
            bot.spotify_redis = aioredis.Redis(
                **config.REDIS_DATABASE_CRIDENTIALS, db=1
            )
            # bot.tb_pool = await asyncpg.create_pool(config.TRACEBACK_DATABASE)

            # bot.cache = aioredis.Redis(**config.REDIS_DATABASE_CRIDENTIALS, db=2)

            try:
                bot.rethinkdb.connect(**config.RETHINKDB_CRIDENTIALS).repl()
            except:
                pass

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

        bot.christmas = ChristmasEvent(bot)
        bot.christmas.start()

        bot.ipc.start()

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

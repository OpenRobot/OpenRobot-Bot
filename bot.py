import asyncio
import datetime
import discord
import config
import re
import asyncpg
import jishaku
import aiohttp
import json
import inspect
import os
import textwrap
import mystbin
import typing
from discord.ext import commands
from cogs.utils import ImageConverter, CelebrityPaginator, MenuPages, LegacyFlagItems, LegacyFlagConverter, TranslateLanguagesPagniator, CodePaginator, Context, Ping
from io import BytesIO, StringIO
from PIL import Image
from openrobot.api_wrapper import AsyncClient, error
import aioredis
import aiospotify
import async_timeout

description = """
I am OpenRobot. I provide help and utilities for OpenRobot stuff such as our API (Hosted at <https://api.openrobot.xyz>).

GitHub: <https://github.com/OpenRobot>
Website: <https://openrobot.xyz/>
"""

class Bot(commands.Bot):
    def __init__(self, *args, **options):
        super().__init__(*args, **options)

        self.running_commands = {}

        # Some other attrs that can be used
        self.spotify: aiospotify.Client = aiospotify.Client(**config.AIOSPOTIFY_CRIDENTIALS)
        self.color: discord.Colour = None
        self.config = config
        self.mystbin: mystbin.Client = mystbin.Client()
        self.api: AsyncClient = AsyncClient(config.API_TOKEN, ignore_warning=True)
        self.ping: Ping = Ping(self)

        # Databases
        self.pool: asyncpg.Pool = None
        self.redis: aioredis.Redis = None
        self.spotify_pool: asyncpg.Pool = None
        self.spotify_redis: aioredis.Redis = None

    #async def get_context(self, message: discord.Message, *, cls: Context = Context) -> Context:
        #return await super().get_context(message, cls=cls)

    async def __invoke(self, ctx, **kwargs) -> None:
        if ctx.command is not None:
            self.dispatch('command', ctx)
            run_in_task = kwargs.pop('task', True)
            try:
                if await self.can_run(ctx, call_once=True):
                    if run_in_task:
                        task = await self.loop.create_task(ctx.command.invoke(ctx))
                        self.running_commands[ctx.message] = {'ctx': ctx, 'task': task}
                    else:
                        await ctx.command.invoke(ctx)
                else:
                    raise commands.CheckFailure('The global check once functions failed.')
            except commands.CommandError as exc:
                await ctx.command.dispatch_error(ctx, exc)
            else:
                self.dispatch('command_completion', ctx)
        elif ctx.invoked_with:
            exc = commands.CommandNotFound('Command "{}" is not found'.format(ctx.invoked_with))
            self.dispatch('command_error', ctx, exc)

bot = Bot(
    command_prefix=commands.when_mentioned_or(*config.PREFIXES),
    help_command=commands.MinimalHelpCommand(no_category="Miscellaneous"), # For old help command purposes only. This is used whenever the help cog fails.
    intents=discord.Intents.all(),
    activity=discord.Activity(type=discord.ActivityType.listening, name="or.help"),
    case_insensitive=True,
    description=description,
    slash_commands=True
)

api = bot.api

def override(func): # Plainly just for `source` command.
    func.__is_overridden__ = True
    return func

@bot.event
@override
async def on_ready():
    print(f'{bot.user} is ready!')

@bot.event
@override
async def on_message(message: discord.Message):
    if re.match(rf'^<@!?{bot.user.id}>$', message.content):
        return await message.reply("My prefix is `or.`! You can also mention me!", mention_author=False)

    await bot.process_commands(message)

@bot.command(aliases=['latency'])
async def ping(ctx: commands.Context):
    """
    Gets the latency of the bot, databases and more.
    """

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    def do_ping_string(ping: int) -> str:
        s = '```diff\n'

        if ping <= 250:
            s += f'+ {ping} ms'
        else:
            s += f'- {ping} ms'

        s += '```'
        
        return s

    msg = await ctx.send('Calculating Latency...')

    embed = discord.Embed(color=bot.color, timestamp=ctx.message.created_at).set_author(name='Latency/Ping Info:', icon_url=ctx.author.avatar.url).set_footer(icon_url=ctx.author.avatar.url, text=f'Requested by: {ctx.author}')

    embed.add_field(name=f'{bot.ping.EMOJIS["bot"]} Bot Latency:', value=do_ping_string(round(bot.ping.bot_latency() * 1000, 2)))
    embed.add_field(name=f'{bot.ping.EMOJIS["typing"]} Typing Latency:', value=do_ping_string(round(await bot.ping.typing() * 1000, 2)))
    embed.add_field(name=f'{bot.ping.EMOJIS["discord"]} Discord Web Latency:', value=do_ping_string(round(await bot.ping.discord_web_ping() * 1000, 2)))

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

        embed.add_field(name=f'{bot.ping.EMOJIS["postgresql"]} PostgreSQL Latency:', value=do_ping_string(round(psql_ping * 1000, 2)))

    if bot.redis:
        redis_ping = await bot.ping.database.redis()

        if redis_ping:
            embed.add_field(name=f'{bot.ping.EMOJIS["redis"]} Redis Latency:', value=do_ping_string(round(redis_ping * 1000, 2)))

    await msg.delete()
    await ctx.send(embed=embed)

@bot.command()
async def lyrics(ctx: commands.Context, *, query: str = commands.Option(description='The query to search for the lyrics.')):
    """
    Get lyrics on a specific song/query.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    - `--from-spotify`: Gets the lyrics from spotify. This gets the lyrics from your spotify activity and edits them automatically when a new song plays. If it does not sync, try pausing/playing, or do anything regarding to the playback of your Spotify song.
    """

    if '--raw' in query.split(' ') and '--from-spotify' in query.split(' '):
        return await ctx.send("You cannot define both `--raw` and `--from-spotify` flags.")
    if query == '--from-spotify':
        from_spotify = True
    else:
        from_spotify = False

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    async def getLyrics(q):
        try:
            lyric = await api.lyrics(q)

            if '--raw' in query.split(' '):
                s = StringIO()
                s.write(json.dumps(lyric.raw, indent=4))
                s.seek(0)

                return await ctx.send(file=discord.File(s, 'response.json'))

            title = lyric.title
            artist = lyric.artist
            lyrics = lyric.lyrics

            if not lyrics:
                return None # return await ctx.send(f"Song with query `{query}` not found.")

            embed = discord.Embed(color=bot.color)
            if title and not getattr(title, 'lower', lambda: title)() == 'none':
                embed.title = title
            else:
                embed.title = f'{q} Search Result:'

            if artist and not getattr(artist, 'lower', lambda: artist)() == 'none':
                embed.set_author(name=f'Artist: {artist}')
            else:
                pass

            embed.description = lyrics

            embed.set_footer(text=f'Invoked by: {ctx.author}')

            return embed # await ctx.send(embed=embed)
        except:
            return None # return await ctx.send(f"Song with query `{query}` not found.") 

    def generateErrorEmbed(error):
        embed = discord.Embed(color=bot.color)
        
        embed.description = error

        embed.set_author(name=f'Invoked by: {ctx.author}')

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
            return await ctx.send(embed=generateErrorEmbed("You are not playing any spotify music!"))

        async def msgIsNew(msg):
            async for message in msg.channel.history(limit=5):
                if msg == message:
                    return True

            return False

        msg = None

        stop_process = False

        while True:
            if stop_process:
                return

            await asyncio.sleep(3)

            for act in ctx.guild.get_member(ctx.author.id).activities:
                if isinstance(act, discord.Spotify):
                    activity = act
                    break

            if msg is None:
                if not activity:
                    msg = await ctx.send(embed=generateErrorEmbed("You are not playing any spotify music!"))
                else:
                    l = await getLyrics(activity.title + ' ' + activity.artists[0])

                    if not l:
                        l = await getLyrics(activity.title)

                    if not l:
                        for x in activity.artists:
                            l = await getLyrics(activity.title + ' ' + x)
                            if l:
                                break

                    if not l:
                        l = await getLyrics(activity.title + ' ' + ' '.join(activity.artists))

                    if not l:
                        msg = await ctx.send(embed=generateErrorEmbed(f"Song with query `{query}` cannot be found."))

                    msg = await ctx.send(embed=l)

                await msg.add_reaction('\U000023f9')
            elif await msgIsNew(msg):
                if not activity:
                    msg = await msg.edit(embed=generateErrorEmbed("You are not playing any spotify music!"))
                else:
                    l = await getLyrics(activity.title + ' ' + activity.artists[0])

                    if not l:
                        l = await getLyrics(activity.title)

                    if not l:
                        for x in activity.artists:
                            l = await getLyrics(activity.title + ' ' + x)
                            if l:
                                break

                    if not l:
                        l = await getLyrics(activity.title + ' ' + ' '.join(activity.artists))

                    if not l:
                        msg = await msg.edit(embed=generateErrorEmbed(f"Song with query `{query}` cannot be found."))

                    msg = await msg.edit(embed=l)
            else:
                await msg.delete()
                if not activity:
                    msg = await ctx.send(embed=generateErrorEmbed("You are not playing any spotify music!"))
                else:
                    l = await getLyrics(activity.title + ' ' + activity.artists[0])

                    if not l:
                        l = await getLyrics(activity.title)

                    if not l:
                        for x in activity.artists:
                            l = await getLyrics(activity.title + ' ' + x)
                            if l:
                                break

                    if not l:
                        l = await getLyrics(activity.title + ' ' + ' '.join(activity.artists))

                    if not l:
                        msg = await ctx.send(embed=generateErrorEmbed(f"Song with query `{query}` cannot be found."))

                    msg = await ctx.send(embed=l)

                    await msg.add_reaction('\U000023f9')

            async def do_stop():
                while True:
                    reaction, user = await bot.wait_for('reaction_add', check=lambda r, u: str(r.emoji) == '\U000023f9' and r.message == msg and not u.bot)

                    if not await bot.is_owner(user) and not user == ctx.author and not user.guild_permissions.manage_messages:
                        continue

                    nonlocal stop_process
                    stop_process = True
                    await msg.delete()

            bot.loop.create_task(do_stop())

            if stop_process:
                return

            _, __ = await bot.wait_for('presence_update', check=lambda b, a: b == ctx.author and a == ctx.author)

            if stop_process:
                return
    else:
        l = await getLyrics(query)

        if isinstance(l, discord.Message):
            return

        if not l:
            msg = await ctx.send(embed=generateErrorEmbed(f"Song with query `{query}` cannot be found."))

        msg = await ctx.send(embed=l)

async def publishCdn(fp : BytesIO, filename : str = "uwu.png", from_aiohttp=True, file_type = None):
    fileType = file_type or f"{filename.split('.')[-1:]}"

    if from_aiohttp:
        original = fp.close
        fp.close = lambda: None

    data = aiohttp.FormData()
    data.add_field('file', fp)

    url = f"https://cdn.ayomerdeka.com/upload?Authorization={config.CDN_TOKEN}&File-Type={fileType}"

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, data=data) as resps:
                if resps.status == 200:
                    d = await resps.json()
                    return d['url']
                else:
                    return None
    finally:
        if from_aiohttp:
            fp.close = original

bot.publishCdn = publishCdn

@bot.command(slash_command=False)
async def celebrity(ctx: commands.Context, *, image = commands.Option(None, description='The image. This can be a URL or a image attached.')):
    """
    Finds a celebrity in a image. Note that this is not 100% accurate and is still on beta.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    """

    url = await ImageConverter().convert(ctx, image)

    if not url:
        return await ctx.send('No image provided.')
    
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url) as resp:
            img_bytes = BytesIO(await resp.read())

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get('https://api.openrobot.xyz/api/celebrity', params={'url': url}, headers={'Authorization': config.API_TOKEN}) as resp:
                js = await resp.json()

        try:
            if '--raw' in image.split(' '):
                s = StringIO()
                s.write(json.dumps(js, indent=4))
                s.seek(0)

                return await ctx.send(file=discord.File(s, 'response.json'))
        except:
            pass

        if not js['detectedFaces']:
            try:
                return await ctx.send("Celebrity cannot be found in the image provided.", file=discord.File(img_bytes, 'image_celebrity.png'))
            except:
                return await ctx.send("Celebrity cannot be found in the image provided.")

        class CelebrityProperties:
            def __init__(self, **kwargs): # .url, .cropped_url, .name, .raw
                for k, v in kwargs.items():
                    setattr(self, k, v)

        def crop_image(detected_face):
            box = detected_face['Face']['BoundingBox']
            left = box['Left']
            top = box['Top']
            right = left + box['Width']
            bottom = top + box['Height']

            output_buffer = BytesIO()

            with Image.open(img_bytes) as img:
                img.crop((left, top, right, bottom)).save(output_buffer, "png")
                output_buffer.seek(0)

            return output_buffer

        #await ctx.send(await bot.mystbin.post(json.dumps(js, indent=4)))

        l = [CelebrityProperties(url=url, cropped_url=None, name=i['Name'], raw=js, item=i) for i in js['detectedFaces']]

        #for i in js['detectedFaces']:
            #l.append(CelebrityProperties(
                #url=url, cropped_url=None, name=i['Name'], raw=js, item=i
            #)) # await publishCdn(await bot.loop.run_in_executor(None, crop_image, i), file_type='png')
    except Exception as e:
        raise e
        try:
            return await ctx.send("Celebrity cannot be found in the image provided.", file=discord.File(img_bytes, 'image_celebrity.png'))
        except:
            return await ctx.send("Celebrity cannot be found in the image provided.")

    menu = MenuPages(CelebrityPaginator(l), delete_message_after=True)
    await menu.start(ctx)

@bot.command()
async def ocr(ctx: commands.Context, *, image = commands.Option(None, description='The image. This can be a URL or a image attached.')):
    """
    Optical Character Recognition. Reads text from images.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    """

    url = await ImageConverter().convert(ctx, image)

    if not url:
        return await ctx.send('No image provided.')

    if ctx.interaction is not None:
        await ctx.interaction.response.defer()

    try:
        ocr = await api.ocr(url=url)

        try:
            if '--raw' in image.split(' '):
                s = StringIO()
                s.write(json.dumps(ocr.raw, indent=4))
                s.seek(0)

                return await ctx.send(file=discord.File(s, 'response.json'))
        except:
            pass
        
        text = ocr.text

        if len(discord.utils.escape_markdown(text)) > 4000:
            url = await bot.mystbin.post(text, syntax="text")
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(style=discord.ButtonStyle.url, url=str(url)))

            return await ctx.send('Content too long to send. Click the button to view the result.', view=view)
        else:
            embed = discord.Embed(color=bot.color)
            embed.set_author(name='Result:')
            embed.timestamp = discord.utils.utcnow()

            embed.description = discord.utils.escape_markdown(text)

            return await ctx.send(embed=embed)
    except:
        return await ctx.send("No text found in image.")

@bot.group(invoke_without_command=True, aliases=['tr'], usage='<text> <flags>', slash_command=False)
async def translate(ctx: commands.Context, *, flags: str):
    """
    Translates a text to another language.

    Flags:
    - `--to`: The language that needs to be translated to.
    - `--from`: The original text language. This is optional and detects the language by default.
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    """

    if ctx.invoked_subcommand is None:
        converter = LegacyFlagConverter([
            LegacyFlagItems(
                'text',
                nargs='+'
            ),
            LegacyFlagItems(
                '--to', '--t', '-t', '-to', '--to-lang', '-to-lang', '-tl', '--tl',
                type=str
            ),
            LegacyFlagItems(
                '--from', '--f', '-f', '-from', '--from-lang', '-from-lang', '-fl', '--fl',
                type=str,
                default=None
            ),
            LegacyFlagItems(
                '--raw',
                action='store_true',
                default=False
            )
        ])

        args = converter.convert(flags)

        text = ' '.join(args.text)
        to_lang = args.to
        from_lang = getattr(args, 'from') # We can't do args.from cause that will raise a SyntaxError.

        raw = args.raw

        if from_lang is None:
            from_lang = "auto"

        try:
            try:
                translate = await api.translate(text, to_lang, from_lang)
            except error.BadRequest as e:
                if e.message == 'Invalid language in paramater to_lang.':
                    return await ctx.send(f'{to_lang} is not a valid language (`--to` flag)')
                elif e.message == 'Invalid language in paramater from_lang.':
                    return await ctx.send(f'{from_lang} is not a valid language (`--from` flag)')

            if raw:
                s = StringIO()
                s.write(json.dumps(translate.raw, indent=4))
                s.seek(0)

                return await ctx.send(file=discord.File(s, 'response.json'))

            embed = discord.Embed(color=bot.color)

            embed.description = f"""
**Translation Result:** {discord.utils.escape_markdown(translate.text)}
**To Language:** {translate.to}
**From Language:** {translate.source}
            """

            embed.set_author(name=f'Translation Result ({translate.source} -> {translate.to})')

            embed.timestamp = discord.utils.utcnow()

            return await ctx.send(embed=embed)
        except:
            return await ctx.send("Something wen't wrong while aquiring the translation from our API.")

@bot.group()
async def spotify(ctx: commands.Context):
    """
    OpenRobot Spotify (OpenRobot x Spotify)
    """
    
    if ctx.invoked_subcommand is None:
        return await ctx.send_help(ctx.command)

@spotify.command('login')
async def spotify_login(ctx: commands.Context, *, flags: str = commands.Option(None, description='Flags: [--interactive]')):
    """
    Pair your spotify account to OpenRobot x Spotify.

    Flags:
    - `--interactive`: Interactively helps you step-by-step on how to pair your spotify account to OpenRobot Spotify.
    """

    flags = (flags or '').split(' ')

    if '--interactive' not in flags:
        return await ctx.send('https://spotify.openrobot.xyz/')

    DEMO_URLS = {
        'discord': 'https://api.openrobot.xyz/static/openrobot_spotify_step_discord.gif',
        'spotify': 'https://api.openrobot.xyz/static/openrobot_spotify_step_spotify.gif'
    }

    DESCRIPTION = {
        'discord': f"""
Go to https://spotify.openrobot.xyz and `Authorize` to this Discord account, {ctx.author}.
        """,
        'spotify': """
Now, sign in to the correct spotify account and click the `Agree` button.
        """
    }

    def generate_embed(step: str = None):
        step = step or 'discord'

        embed = discord.Embed(color=bot.color)

        embed.set_image(url=DEMO_URLS[step])

        embed.description = DESCRIPTION[step]

        return embed

    async def wait_for(step: str, *, timeout = 60):
        c = 0

        async with async_timeout.timeout(timeout):
            while not getattr(await bot.spotify_redis.get(str(ctx.author.id)), 'decode', lambda: None)() == f'ON_STEP({step.upper()})':
                pass

    username = None
    url = None

    get_step = getattr(await bot.spotify_redis.get(str(ctx.author.id)), 'decode', lambda: None)()

    if get_step:
        step: str = re.findall(r'\(.*\)', get_step)[0].strip('(').strip(')').lower()

        if step == 'finish':
            return await ctx.send('You just authenticated, wait for some time!')

        confirm = await bot.confirm(ctx, embed=discord.Embed(description=f'Seems like you already tried to authenticate/pair your spotify account to OpenRobot. You we\'re at the `{step.capitalize()}` step.\nDo you want to continue from your step?', color=bot.color))

        if confirm:
            if step not in ['spotify']:
                return await ctx.send(f'Unknown step. This is a problem in our back-end! Please try restarting your steps and report this to {bot.owner.mention} - `{bot.owner}`!') 

            await ctx.send('Check your DMs!')

            embed = generate_embed('spotify')

            await ctx.author.send(embed=embed)

            try:
                await wait_for('FINISH', timeout=90)
            except asyncio.TimeoutError:
                return await ctx.author.send('Took to long, try again later.')

            while True:
                try:
                    spotify_db_res = await bot.spotify_pool.fetchrow("SELECT * FROM spotify_auth WHERE user_id = $1", ctx.author.id)
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break

            spotify = aiospotify.Client()

            async with aiohttp.ClientSession() as sess:
                async with sess.get('https://api.spotify.com/v1/me', headers={'Authorization': f'Bearer {spotify_db_res["access_token"]}'}) as resp:
                    js = await resp.json()

                    username = js['display_name']
                    url = js['uri']
        else:
            await bot.spotify_redis.delete(str(ctx.author.id))
    
    if not username and not url:
        embed = generate_embed()

        await ctx.author.send(embed=embed)

        try:
            await wait_for('SPOTIFY', timeout=90)
        except asyncio.TimeoutError:
            return await ctx.author.send('Took to long, try again later.')

        embed = generate_embed('spotify')

        await ctx.send('Check your DMs!')
        await ctx.author.send(embed=embed)

        try:
            await wait_for('FINISH', timeout=90)
        except asyncio.TimeoutError:
            return await ctx.author.send('Took to long, try again later.')

        while True:
            try:
                spotify_db_res = await bot.spotify_pool.fetchrow("SELECT * FROM spotify_auth WHERE user_id = $1", ctx.author.id)
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        async with aiohttp.ClientSession() as sess:
            async with sess.get('https://api.spotify.com/v1/me', headers={'Authorization': f'Bearer {spotify_db_res["access_token"]}'}) as resp:
                js = await resp.json()

                username = js['display_name']
                url = js['uri']

    embed = discord.Embed(color=bot.color)

    embed.description = f'Just for confirmation, Is [`{username}`]({url}) the spotify account you are trying to link to your discord account, `{ctx.author}`'

    value = await bot.confirm(ctx, channel=ctx.author, embed=embed)

    if value:
        await ctx.author.send('Ok! Authenticated and paired successfully!')
    else:
        await bot.spotify_redis.delete(str(ctx.author))

        while True:
            try:
                await bot.spotify_pool.fetchrow("DELETE FROM spotify_auth WHERE user_id = $1", ctx.author.id)
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        await ctx.author.send('Removed your spotify pair from this account. Please redo the command again.')

@spotify.command('logout')
async def spotify_logout(ctx: commands.Context):
    while True:
        try:
            x = await bot.spotify_pool.fetchrow("SELECT * FROM spotify_auth WHERE user_id = $1", ctx.author.id)
        except asyncpg.exceptions._base.InterfaceError:
            pass
        else:
            break

    if not x:
        return await ctx.send('You have not logged in to OpenRobot Spotify.')

    await bot.spotify_redis.delete(str(ctx.author))

    while True:
        try:
            await bot.spotify_pool.fetchrow("DELETE FROM spotify_auth WHERE user_id = $1", ctx.author.id)
        except asyncpg.exceptions._base.InterfaceError:
            pass
        else:
            break
    
    await ctx.send('Logged out successfully!')

#@bot.command(name='do-translate', message_command=False)
async def slash_translate(ctx: commands.Context, text: str = commands.Option(description='The text to be translated.'), to_lang: typing.Literal['Afrikaans', 'Albanian', 'Amharic', 'Arabic', 'Armenian', 'Azerbaijani', 'Bengali', 'Bosnian', 'Bulgarian', 'Catalan', 'Chinese (Simplified)', 'Chinese (Traditional)', 'Croatian', 'Czech', 'Danish', 'Dari', 'Dutch', 'English', 'Estonian', 'Farsi (Persian)', 'Filipino, Tagalog', 'Finnish', 'French', 'French (Canada)', 'Georgian', 'German', 'Greek', 'Gujarati', 'Haitian Creole', 'Hausa', 'Hebrew', 'Hindi', 'Hungarian', 'Icelandic', 'Indonesian', 'Italian', 'Japanese', 'Kannada', 'Kazakh', 'Korean', 'Latvian', 'Lithuanian', 'Macedonian', 'Malay', 'Malayalam', 'Maltese', 'Mongolian', 'Norwegian', 'Pashto', 'Polish', 'Portuguese', 'Romanian', 'Russian', 'Serbian', 'Sinhala', 'Slovak', 'Slovenian', 'Somali', 'Spanish', 'Spanish (Mexico)', 'Swahili', 'Swedish', 'Tamil', 'Telugu', 'Thai', 'Turkish', 'Ukrainian', 'Urdu', 'Uzbek', 'Vietnamese', 'Welsh'] = commands.Option(description='The language for the text to be translated to.', name='to'), from_lang: typing.Literal['Afrikaans', 'Albanian', 'Amharic', 'Arabic', 'Armenian', 'Azerbaijani', 'Bengali', 'Bosnian', 'Bulgarian', 'Catalan', 'Chinese (Simplified)', 'Chinese (Traditional)', 'Croatian', 'Czech', 'Danish', 'Dari', 'Dutch', 'English', 'Estonian', 'Farsi (Persian)', 'Filipino, Tagalog', 'Finnish', 'French', 'French (Canada)', 'Georgian', 'German', 'Greek', 'Gujarati', 'Haitian Creole', 'Hausa', 'Hebrew', 'Hindi', 'Hungarian', 'Icelandic', 'Indonesian', 'Italian', 'Japanese', 'Kannada', 'Kazakh', 'Korean', 'Latvian', 'Lithuanian', 'Macedonian', 'Malay', 'Malayalam', 'Maltese', 'Mongolian', 'Norwegian', 'Pashto', 'Polish', 'Portuguese', 'Romanian', 'Russian', 'Serbian', 'Sinhala', 'Slovak', 'Slovenian', 'Somali', 'Spanish', 'Spanish (Mexico)', 'Swahili', 'Swedish', 'Tamil', 'Telugu', 'Thai', 'Turkish', 'Ukrainian', 'Urdu', 'Uzbek', 'Vietnamese', 'Welsh', 'auto'] = commands.Option('auto', description='The text\'s original language. Defaults to "auto".', name='from'), flags: str = commands.Option('', description='Add --raw to this to get the raw response.')):
    if '--raw' in flags.split(' '):
        raw = True
    else:
        raw = False

    await ctx.interaction.response.defer()

    try:
        try:
            translate = await api.translate(text, to_lang, from_lang)
        except error.BadRequest as e:
            if e.message == 'Invalid language in paramater to_lang.':
                return await ctx.send(f'{to_lang} is not a valid language (`--to` flag)')
            elif e.message == 'Invalid language in paramater from_lang.':
                return await ctx.send(f'{from_lang} is not a valid language (`--from` flag)')

        if raw:
            s = StringIO()
            s.write(json.dumps(translate.raw, indent=4))
            s.seek(0)

            return await ctx.send(file=discord.File(s, 'response.json'))

        embed = discord.Embed(color=bot.color)

        embed.description = f"""
**Translation Result:** {discord.utils.escape_markdown(translate.text)}
**To Language:** {translate.to}
**From Language:** {translate.source}
        """

        embed.set_author(name=f'Translation Result ({translate.source} -> {translate.to})')

        embed.timestamp = discord.utils.utcnow()

        return await ctx.send(embed=embed)
    except:
        return await ctx.send("Something wen't wrong while aquiring the translation from our API.")

#@bot.command(name='translate-languages', message_command=False)
async def slash_languages(ctx: commands.Context, *, flags: str = commands.Option('', description='Add --raw to this to get the raw response.')):
    """
    Gets a list of languages supported by the translator.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    """

    await ctx.interaction.response.defer()

    try:
        js = await api.translate.languages()

        if '--raw' in flags.split(' '):
            s = StringIO()
            s.write(json.dumps(js, indent=4))
            s.seek(0)

            return await ctx.send(file=discord.File(s, 'response.json'))

        menu = MenuPages(TranslateLanguagesPagniator(list(js.items())), delete_message_after=True)
        await menu.start(ctx)
    except:
        return await ctx.send("Something wen't wrong while aquiring the supported languages for translation from our API.")

@translate.command(aliases=['langs', 'language', 'lang'])
async def languages(ctx: commands.Context, *, flags: str = commands.Option('', description='Add --raw to this to get the raw response.')):
    """
    Gets a list of languages supported by the translator.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    """

    try:
        js = await api.translate.languages()

        if '--raw' in flags.split(' '):
            s = StringIO()
            s.write(json.dumps(js, indent=4))
            s.seek(0)

            return await ctx.send(file=discord.File(s, 'response.json'))

        menu = MenuPages(TranslateLanguagesPagniator(list(js.items())), delete_message_after=True)
        await menu.start(ctx)
    except:
        return await ctx.send("Something wen't wrong while aquiring the supported languages for translation from our API.")

@bot.command(aliases=['docs'])
async def documentation(ctx: commands.Context):
    """
    Gives the OpenRobot documentation URL.
    """

    return await ctx.send('<https://api.openrobot.xyz/api/docs>')

def codeblock(code: str, *, language = ''):
    return f"```{language}\n{code}```"

bot.codeblock = codeblock

@bot.command(aliases=['src'])
async def source(ctx: commands.Context, *, command: str = commands.Option(None, description='The command name/cog/event to get the source code')):
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

    if '--code' in command.split(' '):
        code = True
        command = command.replace(' --code', '')
    else:
        code = False

    source_url = 'https://github.com/OpenRobot/OpenRobot-Bot'
    branch = 'main'
    if command is None:
        return await ctx.send(source_url)

    if command.startswith('cog:'): # Cog proccessing
        command = command[4:]

        cog = bot.get_cog(command)
        if not cog:
            return await ctx.send('Could not find cog.')

        src = cog.__class__

        module = inspect.getfile(src)
    elif command.startswith('event:'): # Event processing
        command = command[6:]

        if not command.startswith('on_'):
            command = 'on_' + command

        src = getattr(bot, command, None)

        if not src:
            return await ctx.send('Could not find event.')

        if not getattr(src, '__is_overridden__', False):
            return await ctx.send('Could not find event.')

        module = inspect.getfile(src)
    else: # Command processing
        if command == 'help':
            return await ctx.send('Could not find command.')

        obj = bot.get_command(command.replace('.', ' '))
        if obj is None:
            return await ctx.send('Could not find command.')

        # since we found the command we're looking for, presumably anyway, let's
        # try to access the code itself
        src = obj.callback.__code__
        module = obj.callback.__module__

    if not code:
        lines, firstlineno = inspect.getsourcelines(src)
        #location = module.replace('.', '/') + '.py'
        location = module.replace(os.getcwd() + '/', '').replace(os.getcwd(), '')

        if location.endswith('.py'):
            location = location[:-3]

        location = location.replace('.', '/') + '.py'

        final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        return await ctx.send(final_url)
    else:
        param = {
            "text": inspect.getsource(src), 
            "width": 4000, 
            "replace_whitespace": False
        }
        list_codeblock = [codeblock(cb, language='py') for cb in textwrap.wrap(**param)]
        menu = MenuPages(CodePaginator(list_codeblock), delete_message_after=True)
        await menu.start(ctx)

async def _confirm(ctx, channel = None, *args, **kwargs):
    timeout = kwargs.pop('timeout', 60)

    options = kwargs.pop('options', [])

    channel = channel or ctx.channel

    class Yes(discord.ui.Button):
        def __init__(self):
            super().__init__(
                label='Yes',
                style=discord.ButtonStyle.green,
                emoji="<:yes:814691942821920810>"
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
                label='No',
                style=discord.ButtonStyle.red,
                emoji="<:no:814692370430951476>"
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
                await interaction.response.send_message(f'This is not your interaction! Only {ctx.author} can manage and click/respond to interactions!', ephemeral=True)
                return False

            return True

    kwargs['view'] = view = View()

    view.msg = await channel.send(*args, **kwargs)
    await view.wait()
    
    return view.value

@bot.command()
async def invite(ctx: commands.Context, option: typing.Literal['Slash Commands', 'Bot Invite'] = commands.Option(description='Either Slash Commands or Message Commands (Normal)')):
    if option == 'Bot Invite':
        url_with_slash = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions(8), scopes=['bot', 'applications.commands',])
        url = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions(8), scopes=['bot',])
        return await ctx.send(f'With slash commands: <{url_with_slash}>\nWithout slash commands: <{url}>')
    elif option == 'Slash Commands':
        url = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions(8), scopes=['applications.commands',])
        return await ctx.send(f'<{url}>')
    else:
        return await ctx.send('Unknown Option') # idk when this would happen, but ok.

bot.confirm = _confirm

bot.exts = [
    #'jishaku',
    'cogs.api',
    'cogs.error',
    'cogs.music',
    'cogs.help',
    'cogs.jsk',
    'cogs.fun',
]

def start(**kwargs):
    async def parse_flags(**kwargs):
        if kwargs.get('db') is False:
            bot.pool = None
            bot.redis = None
        else:
            bot.pool = await asyncpg.create_pool(config.DATABASE)
            bot.spotify_pool = await asyncpg.create_pool(config.SPOTIFY_DATABASE)
            bot.redis = aioredis.Redis(**config.REDIS_DATABASE_CRIDENTIALS)
            bot.spotify_redis = aioredis.Redis(**config.REDIS_DATABASE_CRIDENTIALS, db=1)

        if kwargs.get('cogs') is not None and 'cogs' not in kwargs:
            l = list(filter(lambda i: i[0].startswith('without-') and i[1], kwargs.items()))

            for i in l:
                try:
                    bot.exts.remove(i)
                except KeyError:
                    try:
                        bot.exts.remove('cogs.' + i)
                    except:
                        pass

            for ext in bot.exts:
                try:
                    bot.load_extension(ext)
                except:
                    pass
        elif kwargs.get('cogs') is True:
            for ext in bot.exts:
                try:
                    bot.load_extension(ext)
                except:
                    pass
        else:
            pass

        if kwargs.get('colour') and bot.color is None:
            try:
                bot.color = await commands.ColourConverter().convert(None, kwargs.get('colour')) # ctx argument isn't used, so we'll just pass in None.
            except:
                pass

        if kwargs.get('color') and bot.color is None:
            try:
                bot.color = await commands.ColourConverter().convert(None, kwargs.get('color')) # ctx argument isn't used, so we'll just pass in None.
            except:
                pass

        bot.color = bot.color or discord.Colour(0x38B6FF)

    async def do_on_ready():
        await bot.wait_until_ready()

        bot.owner = bot.get_user(699839134709317642)

        return await bot.cogs['Music'].initiate_node()

    async def do_restart_message():
        await bot.wait_until_ready()

        with open('restart.json', 'r') as f:
            js: dict = json.load(f)

        restarted_at = datetime.datetime.fromtimestamp(js['restarted_at'], tz=datetime.timezone.utc)
        utcnow = datetime.datetime.utcnow()

        restart_duration = utcnow - restarted_at

        if js.get('channel_id') and js.get('message_id'):
            chan = bot.get_channel(js['channel_id'])

            if chan:
                msg = await chan.get_partial_message(js['message_id'])

                try:
                    await msg.edit(content=f'Back in `{restart_duration.seconds} seconds`.')
                except:
                    pass

            with open('restart.json', 'w') as f:
                json.dump({}, f, indent=4)

    def start_tasks():
        bot.loop.create_task(parse_flags(**kwargs))
        bot.loop.create_task(do_on_ready())
        bot.loop.create_task(do_restart_message())

        try:
            bot.loop.create_task(bot.cogs['Music'].renew())
        except KeyError: # Cog isnt loaded
            pass

    start_tasks()

    bot.run(config.TOKEN)
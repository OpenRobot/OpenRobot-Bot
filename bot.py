import discord
import config
import re
import asyncpg
import time
import jishaku
import aiohttp
import json
import inspect
import os
import textwrap
import mystbin
from discord.ext import commands
from urllib.parse import quote_plus
from cogs.utils import ImageConverter, CelebrityPaginator, MenuPages, LegacyFlagItems, LegacyFlagConverter, TranslateLanguagesPagniator, CodePaginator
from io import BytesIO, StringIO
from PIL import Image, ImageDraw
from openrobot.api_wrapper import AsyncClient, error

description = """
I am OpenRobot. I provide help and utilities for OpenRobot stuff such as our API (Hosted at <https://api.openrobot.xyz>).

GitHub: <https://github.com/OpenRobot>
Website: <https://openrobot.xyz/>
"""

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(*config.PREFIXES),
    help_command=commands.MinimalHelpCommand(no_category="Miscellanous"),
    intents=discord.Intents.all(),
    activity=discord.Activity(type=discord.ActivityType.listening, name="or.help"),
    case_insensitive=True,
    description=description,
)

bot.color = None
bot.config = config
bot.mystbin = mystbin.Client()
api = AsyncClient(config.API_TOKEN, ignore_warning=True)
bot.api = api

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

@bot.command()
async def ping(ctx):
    """Gets the latency of the bot and the database."""

    content = f"Pong! My ping is `{round(bot.latency * 1000, 2)}ms`!"

    if bot.pool is not None:
        start = time.perf_counter()

        while True:
            try:
                await bot.pool.execute("SELECT 1")
            except asyncpg.exceptions._base.InterfaceError:
                pass
            else:
                break

        result = time.perf_counter() - start

        content += f"\nDB Latency: `{round(result * 1000, 2)}ms`"

    return await ctx.reply(content, mention_author=False)

@bot.command()
async def lyrics(ctx, *, query: str):
    """
    Get lyrics on a specific song/query.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    - `--from-spotify`: Gets the lyrics from spotify. This gets the lyrics from your spotify activity and edits them automatically when a new song plays.
    """

    if '--raw' in query.split(' ') and '--from-spotify' in query.split(' '):
        return await ctx.send("You cannot define both `--raw` and `--from-spotify` flags.")
    if query == '--from-spotify':
        from_spotify = True
    else:
        from_spotify = False

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

            if msg is None:
                if not activity:
                    msg = await ctx.send(embed=generateErrorEmbed("You are not playing any spotify music!"))
                else:
                    l = await getLyrics(activity.title + ' ' + ' '.join(activity.artists))
                    if not l:
                        l = await getLyrics(activity.title)

                    if not l:
                        msg = await ctx.send(embed=generateErrorEmbed(f"Song with query `{query}` cannot be found."))

                    msg = await ctx.send(embed=l)

                await msg.add_reaction('\U000023f9')
            elif msgIsNew(msg):
                if not activity:
                    msg = await msg.edit(embed=generateErrorEmbed("You are not playing any spotify music!"))
                else:
                    l = await getLyrics(activity.title + ' ' + ' '.join(activity.artists))

                    if not l:
                        for x in activity.artists:
                            l = await getLyrics(activity.title + ' ' + x)
                            if l:
                                break

                    if not l:
                        l = await getLyrics(activity.title)

                    if not l:
                        msg = await msg.edit(embed=generateErrorEmbed(f"Song with query `{query}` cannot be found."))

                    msg = await msg.edit(embed=l)
            else:
                if not activity:
                    msg = await ctx.send(embed=generateErrorEmbed("You are not playing any spotify music!"))
                else:
                    l = await getLyrics(activity.title + ' ' + ' '.join(activity.artists))
                    if not l:
                        l = await getLyrics(activity.title)

                    if not l:
                        msg = await ctx.send(embed=generateErrorEmbed(f"Song with query `{query}` cannot be found."))

                    msg = await ctx.send(embed=l)

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

            _, __ = await bot.wait_for('presence_update', check=lambda b, a: b == ctx.author and a == ctx.author and any([isinstance(new_act, discord.Spotify) for new_act in ctx.author.activities]))

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

@bot.command()
async def celebrity(ctx, *, image = None):
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

        if '--raw' in image.split(' '):
            s = StringIO()
            s.write(json.dumps(js, indent=4))
            s.seek(0)

            return await ctx.send(file=discord.File(s, 'response.json'))

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
                img.crop((left, top, right, bottom))
                #draw = ImageDraw.Draw(img)
                #draw.rectangle(((left, top), (right, bottom)), outline='red')

                img.save(output_buffer, "png")
                output_buffer.seek(0)

            return output_buffer

        l = []

        for i in js['detectedFaces']:
            l.append(CelebrityProperties(
                url=url, cropped_url=await publishCdn(
                    await bot.loop.run_in_executor(None, crop_image, i)
                ), name=i['Name'], raw=js
            ))
    except:
        try:
            return await ctx.send("Celebrity cannot be found in the image provided.", file=discord.File(img_bytes, 'image_celebrity.png'))
        except:
            return await ctx.send("Celebrity cannot be found in the image provided.")

    menu = MenuPages(CelebrityPaginator(l), delete_message_after=True)
    await menu.start(ctx)

@bot.command()
async def ocr(ctx, *, image = None):
    """
    Optical Character Recognition. Reads text from images.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    """

    url = await ImageConverter().convert(ctx, image)

    if not url:
        return await ctx.send('No image provided.')

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

@bot.group(invoke_without_command=True, aliases=['tr'], usage='<text> <flags>')
async def translate(ctx, *, flags: str):
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

@translate.command(aliases=['langs', 'language', 'lang'])
async def languages(ctx, *flags):
    """
    Gets a list of languages supported by the translator.

    Flags:
    - `--raw`: Returns the raw response sent by our (OpenRobot) API.
    """

    try:
        js = await api.translate.languages()

        if '--raw' in flags:
            s = StringIO()
            s.write(json.dumps(js, indent=4))
            s.seek(0)

            return await ctx.send(file=discord.File(s, 'response.json'))

        menu = MenuPages(TranslateLanguagesPagniator(list(js.items())), delete_message_after=True)
        await menu.start(ctx)
    except:
        return await ctx.send("Something wen't wrong while aquiring the supported languages for translation from our API.")

@bot.command(aliases=['docs'])
async def documentation(ctx):
    """
    Gives the OpenRobot documentation URL.
    """

    return await ctx.send('<https://api.openrobot.xyz/api/docs>')

def codeblock(code: str, *, language = ''):
    return f"```{language}\n{code}```"

bot.codeblock = codeblock

@bot.command(aliases=['src'])
async def source(ctx, *, command: str = None):
    """
    The source code of OpenRobot. You can get a code from a specific 
    command such as `api apply`, or get a source code from a 
    cog/extension by typing `cog:<Insert Cog Name>` e.g `cog:API`. 
    You can also get a event source code by typing `event:<Event Name>`
    e.g `event:on_message`.

    Flags:
    - `--code`: Sends the code instead of the GitHub URL.
    """

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
            location[:-3]

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

async def _confirm(ctx, *args, **kwargs):
    timeout = kwargs.pop('timeout', 60)

    class View(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=timeout)
            self.msg = None
            self.value = None

        @discord.ui.button(label='Yes', style=discord.ButtonStyle.green, emoji="<:yes:814691942821920810>")
        async def yes(self, button: discord.ui.Button, interaction: discord.Interaction):
            for child in view.children:
                child.disabled = True

            self.value = True
            
            await interaction.message.edit(view=self)

            self.stop()

        @discord.ui.button(label='No', style=discord.ButtonStyle.red, emoji="<:no:814692370430951476>")
        async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
            for child in view.children:
                child.disabled = True

            self.value = False

            await interaction.message.edit(view=self)

            self.stop()

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user != ctx.author:
                await interaction.response.send_message(f'This is not your interaction! Only {ctx.author} can manage and click/respond to interactions!', ephemeral=True)
                return False

            return True

    kwargs['view'] = view = View()

    view.msg = await ctx.send(*args, **kwargs)
    await view.wait()
    
    return view.value

bot.confirm = _confirm

bot.exts = [
    'jishaku',
    'cogs.api',
    'cogs.error',
]

def start(**kwargs):
    async def parse_flags(**kwargs):
        if kwargs.get('db') is False:
            bot.pool = None
        else:
            bot.pool = await asyncpg.create_pool(config.DATABASE)

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
                bot.load_extension(ext)
        elif kwargs.get('cogs') is True:
            for ext in bot.exts:
                bot.load_extension(ext)
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

    bot.loop.create_task(parse_flags(**kwargs))

    bot.run(config.TOKEN)
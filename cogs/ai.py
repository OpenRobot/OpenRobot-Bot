import discord
import openai
import json
import aiohttp
from io import StringIO, BytesIO
from config import OPENAI_KEY
from discord.ext import commands
from cogs.utils import Cog, ImageConverter, MenuPages, CelebrityPaginator, LegacyFlagConverter, LegacyFlagItems, TranslateLanguagesPagniator
from openrobot.api_wrapper import error

openai.api_key = OPENAI_KEY

class AI(Cog, emoji="🤖"):
    def get_ai_text(self):
        ai_text = """The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.

Human: Hello
AI: Hello! How are you doing today?
Human: Who are you?
AI: I am a Robot made by OpenRobot. How can I help you?
Human: What is your name?
AI: My name is OpenRobot.
Human: What is your GitHub organization?
AI: My GitHub organization can be found at <https://github.com/OpenRobot/>.
Human: What is 1+1?
AI: 1+1 is 2
Human: What is 5 times 6?
AI: 5 times 6 is 30"""

        with open('cogs/utils/math_train.jsonl', 'r') as f:
            l = [list(json.loads(x).values()) for x in f.read().splitlines()]

        for question, answer in l:
            ai_text += f"\nHuman: {question}\nAI: {answer}"

        return ai_text

    @commands.command('chat', aliases=['assistant'])
    async def chat(self, ctx: commands.Context):
        """
        Makes a OpenRobot Chat Session with you and OpenRobot.

        Powered by [OpenAI](https://openai.com/).

        You can say `stop`, `goodbye` or `end` to end the chat.
        """

        ai_text = self.get_ai_text()

        await ctx.send('OpenRobot Chat Session has started. Note that chats *can* be collected. Say `stop`, `goodbye` or `end` to end the chat.')

        while True:
            msg: discord.Message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel)

            if msg.content.lower() in ['goodbye', 'stop', 'end']:
                return await ctx.send('OpenRobot Chat Session has ended.')

            ai_text += f'{msg}\nAI: '
            
            response = openai.Completion.create(
                engine="davinci",
                prompt=ai_text,
                temperature=0.9,
                max_tokens=150,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0.6,
                stop=["\n", " Human:", " AI:"]
            )

            if ctx.debug:
                await ctx.send(file=discord.File(StringIO(json.dumps(response, indent=4)), filename='response.json'))

            ai_response = response['choices'][0]['text']

            if not ai_response:
                ai_text = ai_text.replace(f'{msg}\nAI: ', '')
                await ctx.send('Sorry, I did not understand.')
                continue

            ai_text += f'{ai_response}\nHuman: '

            await msg.reply(ai_response, mention_author=False)

    @commands.command('nsfw-check', aliases=['nsfwcheck', 'nsfw_check', 'check'])
    async def nsfw_check(self, ctx: commands.Context, *, image = commands.Option(None, description='The image. This can be a URL or a image attached.')):
        """
        NSFW Checks an Image. 
        
        Heavily inspired by [Ami#7836](https://discord.com/users/801742991185936384)'s check command

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        if image:
            if '--raw' in image.split(' '):
                raw = True
            else:
                raw = False
        else:
            raw = False

        url = await ImageConverter(strip_remove=['--raw']).convert(ctx, image) or ctx.author.avatar.url

        check = await self.bot.api.nsfw_check(url)

        if raw:
            s = StringIO()
            s.write(json.dumps(check.raw, indent=4))
            s.seek(0)

            return await ctx.send(file=discord.File(s, 'response.json'))

        label_str = ''

        parent_name_added = []

        for label in reversed(check.labels): # Childrens are always returned last in the label, so.....
            if label.name in parent_name_added:
                continue

            label_str += f'- `{label.name}` - `{round(label.confidence, 2)}%`\n'

            if label.parent_name:
                parent_name_added.append(label.parent_name)

        label_str = label_str[:-1] # remove last newline.

        safe_score = round(100 - check.score * 100, 2)
        safe_score = int(safe_score) if safe_score % 1 == 0 else safe_score
        unsafe_score = round(check.score * 100, 2)
        unsafe_score = int(unsafe_score) if unsafe_score % 1 == 0 else unsafe_score

        is_safe = not bool(check.labels) or safe_score > unsafe_score

        newline = '\n' # Python won't let backstrings in f-strings, so yeah.

        embed = discord.Embed(color=self.bot.color)
        embed.set_image(url=url)
        embed.add_field(name='<:status_dnd:596576774364856321> Unsafe Score:', value=f'`{unsafe_score}%`')
        embed.add_field(name='<:status_online:596576749790429200> Safe Score:', value=f'`{safe_score}%`')
        embed.description = f"""
**Is Safe:** {is_safe}
**Labels:**{newline + label_str if label_str else ' None.'}
        """
        embed.set_footer(text='Powered by OpenRobot API (https://api.openrobot.xyz/)\nInspired by Ami#7836')

        await ctx.send(embed=embed)

    @commands.command(slash_command=False)
    async def celebrity(self, ctx: commands.Context, *, image = commands.Option(None, description='The image. This can be a URL or a image attached.')):
        """
        Finds a celebrity in a image. Note that this is not 100% accurate and is still on beta.

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        url = await ImageConverter(strip_remove=['--raw']).convert(ctx, image)

        if not url:
            return await ctx.send('No image provided.')
        
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url) as resp:
                img_bytes = BytesIO(await resp.read())

        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get('https://api.openrobot.xyz/api/celebrity', params={'url': url}, headers={'Authorization': self.bot.api.token}) as resp:
                    js = await resp.json()

            try:
                if '--raw' in image.split(' '):
                    s = StringIO()
                    s.write(json.dumps(js, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, 'response.json'))
            except Exception as e:
                if ctx.debug:
                    raise e
                    
                pass

            if not js['detectedFaces']:
                try:
                    return await ctx.send("Celebrity cannot be found in the image provided.", file=discord.File(img_bytes, 'image_celebrity.png'))
                except Exception as e:
                    if ctx.debug:
                        raise e

                    return await ctx.send("Celebrity cannot be found in the image provided.")

            class CelebrityProperties:
                def __init__(self, **kwargs): # .url, .cropped_url, .name, .raw
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            #await ctx.send(await bot.mystbin.post(json.dumps(js, indent=4)))

            l = [CelebrityProperties(url=url, cropped_url=None, name=i['Name'], raw=js, item=i) for i in js['detectedFaces']]

            #for i in js['detectedFaces']:
                #l.append(CelebrityProperties(
                    #url=url, cropped_url=None, name=i['Name'], raw=js, item=i
                #)) # await publishCdn(await bot.loop.run_in_executor(None, crop_image, i), file_type='png')
        except Exception as e:
            if ctx.debug:
                raise e
                
            try:
                return await ctx.send("Celebrity cannot be found in the image provided.", file=discord.File(img_bytes, 'image_celebrity.png'))
            except:
                return await ctx.send("Celebrity cannot be found in the image provided.")

        menu = MenuPages(CelebrityPaginator(l), delete_message_after=True)
        await menu.start(ctx)

    @commands.command()
    async def ocr(self, ctx: commands.Context, *, image = commands.Option(None, description='The image. This can be a URL or a image attached.')):
        """
        Optical Character Recognition. Reads text from images.

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        url = await ImageConverter(strip_remove=['--raw']).convert(ctx, image)

        if not url:
            return await ctx.send('No image provided.')

        if ctx.interaction is not None:
            await ctx.interaction.response.defer()

        try:
            ocr_result = await self.bot.api.ocr(source=url)

            try:
                if '--raw' in image.split(' '):
                    s = StringIO()
                    s.write(json.dumps(ocr_result.raw, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, 'response.json'))
            except Exception as e:
                pass
            
            text = ocr_result.text

            if len(discord.utils.escape_markdown(text)) > 4000:
                url = await self.bot.mystbin.post(text, syntax="text")
                view = discord.ui.View(timeout=None)
                view.add_item(discord.ui.Button(style=discord.ButtonStyle.url, url=str(url), label='OCR Result (View in Mystbin)'))

                return await ctx.send('Content too long to send. Click the button to view the result.', view=view)
            else:
                embed = discord.Embed(color=self.bot.color)
                embed.set_author(name='Result:')
                embed.timestamp = discord.utils.utcnow()

                embed.description = await commands.clean_content(use_nicknames=False, escape_markdown=True).convert(ctx, text)

                return await ctx.send(embed=embed)
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("No text found in image.")

    @commands.group(invoke_without_command=True, aliases=['tr'], usage='<text> <flags>', slash_command=False)
    async def translate(self, ctx: commands.Context, *, flags: str):
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
                    translate = await self.bot.api.translate(text, to_lang, from_lang)
                except error.BadRequest as e:
                    if ctx.debug:
                        raise e

                    if e.message == 'Invalid language in paramater to_lang.':
                        return await ctx.send(f'{to_lang} is not a valid language (`--to` flag)')
                    elif e.message == 'Invalid language in paramater from_lang.':
                        return await ctx.send(f'{from_lang} is not a valid language (`--from` flag)')

                if raw:
                    s = StringIO()
                    s.write(json.dumps(translate.raw, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, 'response.json'))

                embed = discord.Embed(color=self.bot.color)

                embed.description = f"""
**Translation Result:** {discord.utils.escape_markdown(translate.text)}
**To Language:** {translate.to}
**From Language:** {translate.source}
                """

                embed.set_author(name=f'Translation Result ({translate.source} -> {translate.to})')

                embed.timestamp = discord.utils.utcnow()

                return await ctx.send(embed=embed)
            except Exception as e:
                if ctx.debug:
                    raise e

                return await ctx.send("Something wen't wrong while aquiring the translation from our API.")

    @translate.command(aliases=['langs', 'language', 'lang'])
    async def languages(self, ctx: commands.Context, *, flags: str = commands.Option('', description='Add --raw to this to get the raw response.')):
        """
        Gets a list of languages supported by the translator.

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        try:
            js = await self.bot.api.translate.languages()

            if '--raw' in flags.split(' '):
                s = StringIO()
                s.write(json.dumps(js, indent=4))
                s.seek(0)

                return await ctx.send(file=discord.File(s, 'response.json'))

            menu = MenuPages(TranslateLanguagesPagniator(list(js.items())), delete_message_after=True)
            await menu.start(ctx)
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("Something wen't wrong while aquiring the supported languages for translation from our API.")

def setup(bot):
    bot.add_cog(AI(bot))
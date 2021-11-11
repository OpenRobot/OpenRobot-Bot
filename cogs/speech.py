import aiohttp
import discord
import io
from discord.ext import commands
from cogs.utils import Cog, LegacyFlagConverter, LegacyFlagItems, ViewMenuPages, TextToSpeechDetailsPaginator, AudioConverter

class Speech(Cog):
    @commands.group(name='text-to-speech', invoke_without_command=True, aliases=['speak', 'tts', 'text_to_speech', 'texttospeech', 'talk'], usage='<text> <flags>', slash_command=False)
    async def text_to_speech(self, ctx: commands.Context, *, flags: str):
        """
        Performs a text to speech.

        Flags:
        - `--voice`: The voice ID. This can be found by invoking the `text-to-speech details` command.
        - `--language-code`: The language code. This can be found by invoking the `text-to-speech details` command.
        """
        
        if ctx.invoked_subcommand is None:
            converter = LegacyFlagConverter([
                LegacyFlagItems('text', nargs='+'),
                LegacyFlagItems('--voice', '-v', '--v'),
                LegacyFlagItems('--language-code', '-l', '--l', '-lc', '-l-c', '--lc', '--l-c', '--language_code', '--languagecode', default='en-US'),
            ])

            flag = converter.convert(flags)

            lang_code = ''.join(flag.language_code)

            try:
                langs = (await self.bot.api.speech.text_to_speech_support(None))['languages']

                if lang_code not in langs:
                    return await ctx.send(f'`{langs}` is not a valid Language Code.')
            except:
                pass

            text = ' '.join(flag.text)

            if not flag.voice:
                return await ctx.send(f'You must specify a voice ID with the `--voice` flag. To view a list of them, invoke the `{ctx.prefix}text-to-speech details` command.')

            voice_id = ''.join(flag.voice)

            tts = await self.bot.api.speech.text_to_speech(text, 'en-US', voice_id)

            async with aiohttp.ClientSession() as session:
                async with session.get(tts.url) as resp:
                    await ctx.send(f'Requested by {ctx.author.mention} - `{ctx.author}`', file=discord.File(io.BytesIO(await resp.read()), filename='tts.mp3'), allowed_mentions=discord.AllowedMentions(users=False))

    @text_to_speech.command(name='details', aliases=['info', 'support'])
    async def text_to_speech_details(self, ctx: commands.Context, language_code: str = None):
        """
        Shows the details of the available voices.
        """

        if language_code is None:
            languages = await self.bot.api._request('GET', '/api/speech/text-to-speech/supports', params={'engine': 'standard'})

            embed = discord.Embed(title='Text to Speech Supported Languages:', color=self.bot.color)
            embed.description = 'The following languages are supported:\n'

            embed.description += '\n'.join([f'`{lang.code}`' for lang in languages['languages']])

            return await ctx.send(embed=embed)

        voices = await self.bot.api.speech.text_to_speech_support(language_code)

        menu = ViewMenuPages(TextToSpeechDetailsPaginator(voices.voices, per_page=3))

        await menu.start(ctx)

    @commands.group('speech-to-text', aliases=['detect-text-from-speech', 'detect-text-from-audio', 'dtfa', 'dtfs', 'stt', 'speechtotext', 'speech_to_text'], usage='<text> <flags>')
    async def speech_to_text(self, ctx, *, flags = None):
        """
        Performs speech to text.

        Source can be either a URL, a audio attachment, a message replied to a audio attachment or a messsage replied to a URL.

        Flags:
        - `--language-code`: Whether or not to return the raw response returned by the API.
        """

        if ctx.invoked_subcommand is None:
            lang_code = None

            if flags:
                converter = LegacyFlagConverter([
                    LegacyFlagItems('--language-code', '-l', '--l', '-lc', '-l-c', '--lc', '--l-c', '--language_code', '--languagecode', default='en-US'),
                ])

                flag = converter.convert(flags)

                lang_code = flag.language_code

                if lang_code:
                    lang_code = ''.join(lang_code)

                    try:
                        langs = (await self.bot.api.speech.speech_to_text_support())['languages']

                        if lang_code not in langs:
                            return await ctx.send(f'`{langs}` is not a valid Language Code.')
                    except:
                        pass

            lang_code = lang_code or 'en-US'

            source = await AudioConverter().convert(ctx, flags)

            if source is None:
                return await ctx.send('No source provided.')

            stt = await self.bot.api.speech.speech_to_text(source, lang_code)

            if not stt.text:
                return await ctx.send('No text detected.')

            if len(stt.text) > 4000:
                url = await self.bot.mystbin.post(stt.text, syntax="text")
                view = discord.ui.View(timeout=None)
                view.add_item(discord.ui.Button(style=discord.ButtonStyle.url, url=str(url), label='Speech To Text Result (View in Mystbin)'))

                return await ctx.send('Content too long to send. Click the button to view the result.', view=view)

            embed = discord.Embed(title='Result:', color=self.bot.color).set_footer(text=f'Requested by {ctx.author}', icon_url=ctx.author.avatar.url)

            embed.description = stt.text

            return await ctx.send(embed=embed)

    @speech_to_text.command(name='details', aliases=['info', 'support'])
    async def speech_to_text_details(self, ctx: commands.Context):
        """
        Shows the details of the available languages.
        """

        languages = await self.bot.api.speech.speech_to_text_support()

        embed = discord.Embed(title='Speech To Text Supported Languages:', color=self.bot.color)
        embed.description = 'The following languages are supported:\n'

        embed.description += '\n'.join([f'`{code}`' for code in languages['languages']])

        return await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Speech(bot))
import aiohttp
import discord
import io
from discord.ext import commands
from cogs.utils import Cog, LegacyFlagConverter, LegacyFlagItems, ViewMenuPages, TextToSpeechDetailsPaginator, AudioConverter

class Speech(Cog):
    @commands.group(name='text-to-speech', invoke_without_command=True, aliases=['speak', 'tts', 'text_to_speech', 'texttospeech', 'talk'], usage='<text> <flags>', slash_command=False)
    async def text_to_speech(self, ctx, *, flags: str):
        """
        Performs a text to speech.

        Flags:
        - `--voice`: The voice ID. This can be found by invoking the `text-to-speech details` command.
        - `--raw`: Whether or not to return the raw response returned by the API.
        """
        
        if ctx.invoked_subcommand is None:
            converter = LegacyFlagConverter([
                LegacyFlagItems('text', nargs='+'),
                LegacyFlagItems('--voice', '-v', '--v'),
            ])

            flag = converter.convert(flags)

            text = ' '.join(flag.text)
            voice_id = ''.join(flag.voice)

            tts = await self.bot.api.speech.text_to_speech(text, 'en-US', voice_id)

            async with aiohttp.ClientSession() as session:
                async with session.get(tts.url) as resp:
                    await ctx.send(f'Requested by {ctx.author.mention} - `{ctx.author}`', file=discord.File(io.BytesIO(await resp.read()), filename='tts.mp3'), allowed_mentions=discord.AllowedMentions(users=False))

    @text_to_speech.command(name='details', aliases=['info', 'support'])
    async def text_to_speech_details(self, ctx):
        """
        Shows the details of the available voices.
        """

        voices = await self.bot.api.speech.text_to_speech_support('en-US')

        menu = ViewMenuPages(TextToSpeechDetailsPaginator(voices.voices, per_page=3))

        await menu.start(ctx)

    @commands.command('speech-to-text', aliases=['detect-text-from-speech', 'detect-text-from-audio', 'dtfa', 'dtfs', 'stt', 'speechtotext', 'speech_to_text'])
    async def speech_to_text(self, ctx, *, source = None):
        """
        Performs speech to text.

        Source can be either a URL, a audio attachment, a message replied to a audio attachment or a messsage replied to a URL.
        """

        source = await AudioConverter().convert(ctx, source)

        if source is None:
            return await ctx.send('No source provided.')

        stt = await self.bot.api.speech.speech_to_text(source, 'en-US')

        if not stt.text:
            return await ctx.send('No text detected.')

        embed = discord.Embed(title='Result:', color=self.bot.color).set_footer(text=f'Requested by {ctx.author}', icon_url=ctx.author.avatar_url)

        embed.description = stt.text

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Speech(bot))
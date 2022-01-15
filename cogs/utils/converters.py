import re
import aiohttp
import discord
import datetime
from discord.ext import commands
from discord.ext.commands import Converter, Context
from jishaku.codeblocks import codeblock_converter, Codeblock


class ImageConverter(Converter):
    def __init__(self, **kwargs):
        self.options = kwargs

    async def convert(self, ctx: Context, argument: str):
        if isinstance(argument, str):
            for strip_remove in self.options.get("strip_remove", []):
                argument = argument.replace(strip_remove, "")
                argument = argument.replace(" " + strip_remove, "")
                argument = argument.replace(strip_remove + " ", "")

        if argument:
            x = re.findall(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                argument,
            )
            if x:
                return x[0]
        elif ctx.message.reference:
            x = re.findall(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                ctx.message.reference.resolved.content,
            )
            if x:
                return x[0]

        try:
            return (await commands.MemberConverter().convert(ctx, argument)).avatar.url
        except:
            try:
                return (
                    await commands.UserConverter().convert(ctx, argument)
                ).avatar.url
            except:
                pass

        if ctx.message.attachments:
            return ctx.message.attachments[0].url
        if ctx.message.reference:
            if ctx.message.reference.resolved.attachments:
                return ctx.message.reference.resolved.attachments[0].url

            elif ctx.message.reference.resolved.embeds:
                for embed in ctx.message.reference.resolved.embeds:
                    if embed.image is not discord.Embed.Empty:
                        return embed.image.url
                    elif embed.thumbnail is not discord.Embed.Empty:
                        return embed.thumbnail.url

        if ctx.message.content:
            if emoji := re.findall(
                r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>",
                ctx.message.content,
            ):
                emoji_id = emoji[0][2]
                return f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
        elif ctx.message.reference:
            if ctx.message.reference.resolved.content:
                if emoji := re.findall(
                    r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>",
                    ctx.message.reference.resolved.content,
                ):
                    emoji_id = emoji[0][2]
                    return f"https://cdn.discordapp.com/emojis/{emoji_id}.png"

            return ctx.message.reference.resolved.author.avatar.url

        return None


class AudioConverter(Converter):
    async def convert(self, ctx: Context, argument: str):
        if argument:
            x = re.findall(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                argument,
            )

            for i in x:
                async with ctx.bot.session.get(i) as resp:
                    if resp.content_type.startswith("audio/"):
                        return i
        elif ctx.message.reference:
            x = re.findall(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                ctx.message.reference.resolved.content,
            )

            for i in x:
                async with ctx.bot.session.get(i) as resp:
                    if resp.content_type.startswith("audio/"):
                        return i

        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                if attachment.content_type.startswith("audio/"):
                    return attachment.url
        if ctx.message.reference:
            if ctx.message.reference.resolved.attachments:
                for attachment in ctx.message.reference.resolved.attachments:
                    if attachment.content_type.startswith("audio/"):
                        return attachment.url

        return None


class CodeblockConverter(Converter):
    async def convert(self, ctx: Context, argument: str) -> Codeblock | str:
        x = re.findall(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            argument,
        )
        if x:
            return x[0]

        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                if attachment.content_type.startswith(
                    "text/x-python"
                ):  # For some reason its text/x-...
                    async with ctx.bot.session.get(attachment.url) as resp:
                        text = await resp.text()

                    return Codeblock("python", text)
                elif attachment.content_type.startswith("text/x-java"):
                    async with ctx.bot.session.get(attachment.url) as resp:
                        text = await resp.text()

                    return Codeblock("java", text)

        return codeblock_converter(argument)


# https://github.com/Axelware/Life-bot/blob/949937a37d349b816abfe99c50bd878878f6a94a/bot/utilities/objects/time.py#L5-L12
# https://github.com/Axelware/Life-bot/blob/main/bot/utilities/converters/time.py#L15-L61


class Time:
    def __init__(self, *, seconds: int) -> None:
        self._seconds = seconds
        self._timedelta = datetime.timedelta(seconds=self._seconds)

    @property
    def seconds(self) -> int:
        return self._seconds

    @property
    def timedelta(self):
        return self._timedelta

    @property
    def minutes(self) -> int:
        return self._seconds // 60

    @property
    def hours(self) -> int:
        return self._seconds // 3600

    @property
    def days(self) -> int:
        return self._seconds // 86400

    @property
    def weeks(self) -> int:
        return self._seconds // 604800

    @property
    def months(self) -> int:
        return self._seconds // 2592000

    @property
    def years(self) -> int:
        return self._seconds // 31536000


COLON_FORMAT_REGEX = re.compile(
    r"""
^
    (?:
        (?:
            (?P<hours>[0-1]?[0-9]|2[0-3]):
        )?
        (?P<minutes>[0-5]?[0-9]):
    )?
    (?P<seconds>[0-5]?[0-9])
$
""",
    flags=re.VERBOSE,
)

HUMAN_FORMAT_REGEX = re.compile(
    r"""
^
    (?: (?P<hours>[0-1]?[0-9]|2[0-3]) \s? (?:h|hour|hours)              (?:\s?|\s?and\s?) )?
    (?: (?P<minutes>[0-5]?[0-9])      \s? (?:m|min|mins|minute|minutes) (?:\s?|\s?and\s?) )?
    (?: (?P<seconds>[0-5]?[0-9])      \s? (?:s|sec|secs|second|seconds)                   )?
$
""",
    flags=re.VERBOSE,
)


class TimeConverter(Converter[Time]):
    @staticmethod
    async def convert(ctx: Context, argument: str) -> Time:

        if (match := COLON_FORMAT_REGEX.match(argument)) or (
            match := HUMAN_FORMAT_REGEX.match(argument)
        ):

            total = 0

            if hours := match.group("hours"):
                total += int(hours) * 60 * 60
            if minutes := match.group("minutes"):
                total += int(minutes) * 60
            if seconds := match.group("seconds"):
                total += int(seconds)

        else:

            try:
                total = int(argument)
            except ValueError:
                return None

        return Time(seconds=total)

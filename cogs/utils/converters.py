import re
import discord
from discord.ext.commands import Converter, Context

class ImageConverter(Converter):
    async def convert(self, ctx: Context, argument: str):
        if argument:
            x = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', argument)
            if x:
                return x[0]
        elif ctx.message.reference:
            x = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', ctx.message.reference.resolved.content)
            if x:
                return x[0]

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

        return None
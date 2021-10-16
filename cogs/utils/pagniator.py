import discord
import asyncio
import datetime
import json
from discord import ui
from discord.ext import menus
from discord.ext.menus import ListPageSource

class ViewMenuPages(ui.View, menus.MenuPages):
    def __init__(self, source, *, timeout=180, delete_message_after=False, clear_buttons_after=False, force_paginate=False):
        super().__init__(timeout=timeout)
        self._source = source
        self.current_page = 0
        self.ctx = None
        self.message = None
        self.delete_message_after = delete_message_after
        self.clear_buttons_after = clear_buttons_after
        self.force_paginate = force_paginate

    async def start(self, ctx, *, channel=None, wait=False):
        # We wont be using wait, you can implement them yourself. This is to match the MenuPages signature.
        await self._source._prepare_once()

        channel = channel or ctx.channel
        self.ctx = ctx
        self.message = await self.send_initial_message(ctx, channel)

    async def _get_kwargs_from_page(self, page):
        """This method calls ListPageSource.format_page class"""
        value = await super()._get_kwargs_from_page(page)
        if 'view' not in value:
            if not self.force_paginate:
                if self._source.get_max_pages() <= 1:
                    return value

            value.update({'view': self})
        return value

    async def send_initial_message(self, ctx, channel):
        self.message = await super().send_initial_message(ctx, channel)
        await self.update_buttons()
        return self.message

    async def update_buttons(self):
        if not self.force_paginate:
            if self._source.get_max_pages() <= 1:
                return await self.message.edit(view=None)

        self.page_button.label = f'{self.current_page + 1}/{self._source.get_max_pages()}'
        if self.current_page == 0:
            self.first_page.disabled = True
            self.before_page.disabled = True
            self.last_page.disabled = False
            self.next_page.disabled = False
        elif self.current_page == (self._source.get_max_pages() - 1):
            self.last_page.disabled = True
            self.next_page.disabled = True
            self.first_page.disabled = False
            self.before_page.disabled = False
        else:
            self.last_page.disabled = False
            self.next_page.disabled = False
            self.first_page.disabled = False
            self.before_page.disabled = False

        await self.message.edit(view=self)

    def try_int(self, string):
        try:
            return int(string)
        except:
            return None

    async def on_timeout(self) -> None:
        if self.delete_message_after is True:
            await self.message.delete(delay=0)
        elif self.clear_buttons_after is True:
            await self.message.edit(view=None)
        else:
            for child in self.children:
                child.disabled = True

            await self.message.edit(view=self)

    async def interaction_check(self, interaction):
        """Only allow the author that invoke the command to be able to use the interaction"""
        if not interaction.user == self.ctx.author or await self.ctx.bot.is_owner(interaction.user):
            await interaction.response.send_message(f'This is not your interaction! Only {self.ctx.author.mention} can respond to this interaction!', ephemeral=True)
            return False
        else:
            return True

    @ui.button(emoji='<:fast_forward_left:802368686547271741>', style=discord.ButtonStyle.gray, row=1)
    async def first_page(self, button, interaction):
        await self.show_page(0)
        await self.update_buttons()

    @ui.button(emoji='<a:facing_left_arrow:799579706688667669>', label='Previous', style=discord.ButtonStyle.gray, row=1)
    async def before_page(self, button, interaction):
        await self.show_checked_page(self.current_page - 1)
        await self.update_buttons()

    @ui.button(label='\u200b', style=discord.ButtonStyle.gray, row=1)
    async def page_button(self, button, interaction):
        await interaction.response.defer()
        
        m = await self.ctx.send(f"Enter page number you would like to see (1/{self._source.get_max_pages()})")

        def check(msg):
            page_num = self.try_int(msg.content)
            if page_num is None:
                return False
            else:
                return 1 <= page_num <= self._source.get_max_pages()

        try:
            msg = await self.ctx.bot.wait_for('message', check = check, timeout=30)
        except asyncio.TimeoutError:
            await m.delete()
            return await self.ctx.send('Took to long...', delete_after=10)
        else:
            page_num = int(msg.content) - 1

            await self.show_checked_page(page_num)

        try:
            await m.delete()
        except:
            pass

        try:
            await msg.delete()
        except:
            pass

        await self.update_buttons()

    @ui.button(emoji='<a:facing_right_arrow:799579865296535583>', label='Next', style=discord.ButtonStyle.gray, row=1)
    async def next_page(self, button, interaction):
        await self.show_checked_page(self.current_page + 1)
        await self.update_buttons()

    @ui.button(emoji='<:fast_forward_right:802368548482580510>', style=discord.ButtonStyle.gray, row=1)
    async def last_page(self, button, interaction):
        await self.show_page(self._source.get_max_pages() - 1)
        await self.update_buttons()

    @ui.button(emoji='\U000023f9', label='Quit', style=discord.ButtonStyle.red, row=2)
    async def stop_page(self, button, interaction):
        self.stop()
        if self.delete_message_after:
            await self.message.delete(delay=0)
        elif self.clear_buttons_after is True:
            await self.message.edit(view=None)
        else:
            for child in self.children:
                child.disabled = True

            await self.message.edit(view=self)

MenuPages = ViewMenuPages

class APIInfoPaginator(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=5)

    async def format_page(self, menu, entries):
        embed = discord.Embed()
        embed.color = menu.ctx.bot.color
        embed.description = ""

        c = 1

        for page in entries:
            embed.description += f"""
__**{c})**__
 \u200b \u200b \u200b- **IP:** `{page['ip']}`
 \u200b \u200b \u200b- **Endpoint/Path:** `{page['endpoint']}`
 \u200b \u200b \u200b- **Requested At:** {discord.utils.format_dt(datetime.datetime.fromtimestamp(page['timestamp'], datetime.timezone.utc))}
            """
            c += 1

        embed.set_footer(text=f'Page {menu.current_page + 1}/{self.get_max_pages()}')
        embed.timestamp = menu.ctx.message.created_at

        return embed

class CelebrityPaginator(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=1)

    async def format_page(self, menu, page):
        embed = discord.Embed()
        embed.color = menu.ctx.bot.color

        embed.set_image(url=page.url)
        embed.set_thumbnail(url=page.cropped_url)

        emotion = sorted(page.item['Face']['Emotions'], key=lambda i: i['Confidence'])

        embed.description = f"""
Seems like this is `{page.name}`. I am `{round(page.item['Confidence'], 1)}%` sure.

- **Name:** {page.name}
- **Emotion:** {emotion}
- **Pose:**
 \u200b \u200b \u200b- **Roll:** {page.item['Face']['Pose']['Roll']}
 \u200b \u200b \u200b- **Yaw:** {page.item['Face']['Pose']['Yaw']}
 \u200b \u200b \u200b- **Pitch:** {page.item['Face']['Pose']['Pitch']}
        """

        embed.set_footer(text=f'Page {menu.current_page + 1}/{self.get_max_pages()}')
        embed.timestamp = menu.ctx.message.created_at

        return embed

class TranslateLanguagesPagniator(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        embed = discord.Embed(color=menu.ctx.bot.color)

        embed.timestamp = discord.utils.utcnow()

        embed.set_author(name = "Languages:", icon_url=menu.ctx.author.avatar.url)

        embed.description = "```yml\n"

        entries = list(entries)

        embed.description += "\n".join([f"{k.rjust(len(max(dict(entries).keys(), key=len)))}: {v}" for k, v in entries])

        embed.description += "```"

        embed.set_footer(text = f"Requested by {menu.ctx.author} | Page {menu.current_page + 1}/{self.get_max_pages()}", icon_url=menu.ctx.author.avatar.url)

        return embed

class CodePaginator(menus.ListPageSource):
    def __init__(self, code):
        super().__init__(code, per_page=1)

    async def format_page(self, menu, entries):
        embed = discord.Embed(color=menu.ctx.bot.color)

        embed.timestamp = discord.utils.utcnow()

        embed.description = entries

        return embed

class IPBanListPaginator(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=5)

    async def format_page(self, menu, entries):
        embed = discord.Embed()
        embed.color = menu.ctx.bot.color
        embed.description = ""

        c = 1

        for page in entries:
            embed.description += f"""
__**{c})**__
 \u200b \u200b \u200b- **IP:** `{page['ip']}`
 \u200b \u200b \u200b- **Banned At:** {discord.utils.format_dt(datetime.datetime.fromtimestamp(page['banned_at'], datetime.timezone.utc))}
            """
            c += 1

        embed.set_footer(text=f'Page {menu.current_page + 1}/{self.get_max_pages()}')
        embed.timestamp = menu.ctx.message.created_at

        return embed
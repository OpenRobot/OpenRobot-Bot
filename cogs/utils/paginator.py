import discord
import asyncio
import datetime
import json
import re
from discord import ui
from discord.ext import menus
from discord.ext.menus import ListPageSource
import humanize


class BaseViewMenuPages(ui.View, menus.MenuPages):
    def __init__(
        self,
        source,
        *,
        timeout=180,
        delete_message_after=False,
        clear_buttons_after=False,
        force_paginate=False,
        try_send_in_dm=False,
        reply=None,
    ):
        super().__init__(timeout=timeout)
        self._source = source
        self.current_page = 0
        self.ctx = None
        self.message = None
        self.delete_message_after = delete_message_after
        self.clear_buttons_after = clear_buttons_after
        self.force_paginate = force_paginate
        self.try_send_in_dm = try_send_in_dm
        self.reply = reply

    async def prepare(self):
        pass

    async def start(self, ctx, *, channel=None, wait=False):
        # We wont be using wait, you can implement them yourself. This is to match the MenuPages signature.
        await self._source._prepare_once()
        await self.prepare()

        channel = channel or ctx.channel
        self.ctx = ctx

        self.message = await self.send_initial_message(ctx, channel)

    async def _get_kwargs_from_page(self, page):
        """This method calls ListPageSource.format_page class"""
        value = await super()._get_kwargs_from_page(page)
        if "view" not in value:
            if not self.force_paginate:
                if self._source.get_max_pages() <= 1:
                    return value

            value.update({"view": self})
        return value

    async def send_initial_message(self, ctx, channel):
        if self.reply == "channel":
            if self.try_send_in_dm:
                try:
                    page = await self._source.get_page(0)
                    kwargs = await self._get_kwargs_from_page(page)
                    self.message = await ctx.author.send(**kwargs)
                except:
                    page = await self._source.get_page(0)
                    kwargs = await self._get_kwargs_from_page(page)
                    self.message = await ctx.reply(**kwargs)
            else:
                page = await self._source.get_page(0)
                kwargs = await self._get_kwargs_from_page(page)
                self.message = await ctx.reply(**kwargs)
        else:
            if self.try_send_in_dm:
                try:
                    page = await self._source.get_page(0)
                    kwargs = await self._get_kwargs_from_page(page)
                    self.message = await ctx.author.send(**kwargs)
                except:
                    self.message = await super().send_initial_message(ctx, channel)
            else:
                self.message = await super().send_initial_message(ctx, channel)

        await self.update_buttons()
        return self.message

    async def update_buttons(self):
        if not self.force_paginate:
            if self._source.get_max_pages() <= 1:
                return await self.message.edit(view=None)

        self.page_button.label = (
            f"{self.current_page + 1}/{self._source.get_max_pages()}"
        )

        if self._source.get_max_pages() <= 1:
            self.first_page.disabled = True
            self.before_page.disabled = True
            self.page_button.disabled = True
            self.last_page.disabled = True
            self.next_page.disabled = True
        else:
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

    @staticmethod
    def try_int(string):
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
        if not (
            interaction.user == self.ctx.author
            or await self.ctx.bot.is_owner(interaction.user)
        ):
            await interaction.response.send_message(
                f"This is not your interaction! Only {self.ctx.author.mention} can respond to this interaction!",
                ephemeral=True,
            )
            return False
        else:
            return True


BaseMenuPages = BaseViewMenuPages


class ViewMenuPages(BaseViewMenuPages):
    @ui.button(
        emoji="<:openrobot_rewind_button:899931475720413187>",
        style=discord.ButtonStyle.gray,
        row=1,
    )
    async def first_page(self, button, interaction):
        await self.show_page(0)
        await self.update_buttons()

    @ui.button(
        emoji="<:openrobot_previous_button:899937597877542922>",
        label="Previous",
        style=discord.ButtonStyle.gray,
        row=1,
    )
    async def before_page(self, button, interaction):
        await self.show_checked_page(self.current_page - 1)
        await self.update_buttons()

    @ui.button(label="\u200b", style=discord.ButtonStyle.gray, row=1)
    async def page_button(self, button, interaction):
        await interaction.response.defer()

        m = await self.ctx.send(
            f"Enter page number you would like to see (1/{self._source.get_max_pages()})"
        )

        def check(msg):
            page_num = self.try_int(msg.content)
            if page_num is None:
                return False
            else:
                return 1 <= page_num <= self._source.get_max_pages()

        try:
            msg = await self.ctx.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            await m.delete()
            return await self.ctx.send("Took to long...", delete_after=10)
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

    @ui.button(
        emoji="<:openrobot_next_button:899878229437984799>",
        label="Next",
        style=discord.ButtonStyle.gray,
        row=1,
    )
    async def next_page(self, button, interaction):
        await self.show_checked_page(self.current_page + 1)
        await self.update_buttons()

    @ui.button(
        emoji="<:openrobot_fast_forward_button:899878227777060894>",
        style=discord.ButtonStyle.gray,
        row=1,
    )
    async def last_page(self, button, interaction):
        await self.show_page(self._source.get_max_pages() - 1)
        await self.update_buttons()

    @ui.button(
        emoji="<:openrobot_stop_button:899878227969974322>",
        label="Quit",
        style=discord.ButtonStyle.red,
        row=2,
    )
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


class CodeReviewPages(BaseViewMenuPages):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.thumbsup = False
        self.thumbsdown = False

    @ui.button(emoji="\U0001f44d", style=discord.ButtonStyle.blurple, row=1)
    async def good_recommendation(self, button, interaction):
        bot = self.ctx.bot

        AI = bot.get_cog("AI")

        codeguru = AI.codeguru

        entries = self._source.entries

        entry = entries[self.current_page]

        CodeReviewArn = entry["CodeReviewArn"]

        RecommendationId = entry["RecommendationId"]

        if self.thumbsup:
            codeguru.put_recommendation_feedback(
                CodeReviewArn=CodeReviewArn,
                RecommendationId=RecommendationId,
                Reactions=[],
            )

            button.style = discord.ButtonStyle.blurple

            self.thumbsup = False
        else:
            codeguru.put_recommendation_feedback(
                CodeReviewArn=CodeReviewArn,
                RecommendationId=RecommendationId,
                Reactions=["ThumbsUp"],
            )

            button.style = discord.ButtonStyle.green
            self.bad_recommendation.style = discord.ButtonStyle.blurple

            self.thumbsup = True

        # button.disabled = True
        # self.bad_recommendation.disabled = False

        await interaction.message.edit(view=self)

    @ui.button(emoji="\U0001f44e", style=discord.ButtonStyle.blurple, row=1)
    async def bad_recommendation(self, button, interaction):
        bot = self.ctx.bot

        AI = bot.get_cog("AI")

        codeguru = AI.codeguru

        entries = self._source.entries

        entry = entries[self.current_page]

        CodeReviewArn = entry["CodeReviewArn"]

        RecommendationId = entry["RecommendationId"]

        if self.thumbsdown:
            codeguru.put_recommendation_feedback(
                CodeReviewArn=CodeReviewArn,
                RecommendationId=RecommendationId,
                Reactions=[],
            )

            button.style = discord.ButtonStyle.blurple

            self.thumbsdown = False
        else:
            codeguru.put_recommendation_feedback(
                CodeReviewArn=CodeReviewArn,
                RecommendationId=RecommendationId,
                Reactions=["ThumbsDown"],
            )

            button.style = discord.ButtonStyle.red
            self.good_recommendation.style = discord.ButtonStyle.blurple

            self.thumbsdown = True

        # button.disabled = True
        # self.good_recommendation.disabled = False

        await interaction.message.edit(view=self)

    @ui.button(
        emoji="<:openrobot_rewind_button:899931475720413187>",
        style=discord.ButtonStyle.gray,
        row=2,
    )
    async def first_page(self, button, interaction):
        await self.show_page(0)
        await self.update_buttons()

    @ui.button(
        emoji="<:openrobot_previous_button:899937597877542922>",
        label="Previous",
        style=discord.ButtonStyle.gray,
        row=2,
    )
    async def before_page(self, button, interaction):
        await self.show_checked_page(self.current_page - 1)
        await self.update_buttons()

    @ui.button(label="\u200b", style=discord.ButtonStyle.gray, row=2)
    async def page_button(self, button, interaction):
        await interaction.response.defer()

        m = await self.ctx.send(
            f"Enter page number you would like to see (1/{self._source.get_max_pages()})"
        )

        def check(msg):
            page_num = self.try_int(msg.content)
            if page_num is None:
                return False
            else:
                return 1 <= page_num <= self._source.get_max_pages()

        try:
            msg = await self.ctx.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            await m.delete()
            return await self.ctx.send("Took to long...", delete_after=10)
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

    @ui.button(
        emoji="<:openrobot_next_button:899878229437984799>",
        label="Next",
        style=discord.ButtonStyle.gray,
        row=2,
    )
    async def next_page(self, button, interaction):
        await self.show_checked_page(self.current_page + 1)
        await self.update_buttons()

    @ui.button(
        emoji="<:openrobot_fast_forward_button:899878227777060894>",
        style=discord.ButtonStyle.gray,
        row=2,
    )
    async def last_page(self, button, interaction):
        await self.show_page(self._source.get_max_pages() - 1)
        await self.update_buttons()

    @ui.button(
        emoji="<:openrobot_stop_button:899878227969974322>",
        label="Quit",
        style=discord.ButtonStyle.red,
        row=3,
    )
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


class ClassicPaginator(ListPageSource):
    async def format_page(self, menu, page):
        return page


class APIInfoPaginator(ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=5)

    async def format_page(self, menu, entries):
        embed = discord.Embed()
        embed.color = menu.ctx.bot.color
        embed.description = ""

        for page in entries:
            embed.description += f"""
__**{self.entries.index(page)+1})**__
 \u200b \u200b \u200b- **IP:** `{page['ip']}`
 \u200b \u200b \u200b- **Endpoint/Path:** `{page['endpoint']}`
 \u200b \u200b \u200b- **Requested At:** {discord.utils.format_dt(datetime.datetime.fromtimestamp(page['timestamp'], datetime.timezone.utc))}
            """

        embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")
        embed.timestamp = menu.ctx.message.created_at

        return embed


class CelebrityPaginator(ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=1)

    async def format_page(self, menu, page):
        embed = discord.Embed()
        embed.color = menu.ctx.bot.color

        if page.url:
            embed.set_image(url=page.url)

        if page.cropped_url:
            embed.set_thumbnail(url=page.cropped_url)

        emotion = sorted(
            page.item["Face"]["Emotions"], key=lambda i: i["Confidence"], reverse=True
        )

        urls = ""

        for url in page.item["URLs"]:
            if not url.startswith(("https://", "http://")):
                url = "https://" + url

            urls += f" \u200b \u200b \u200b- {url}\n"

        urls = urls[:-1]

        newline = "\n"

        embed.description = f"""
Seems like this is `{page.name}`. I am `{round(page.item['Confidence'], 1)}%` sure.

- **Name:** `{page.name}`
- **Gender:** `{page.item['Gender']}`
- **Is Smiling:** `{page.item['Face']['Smile']['Value']}`
- **Emotion:** `{emotion[0]['Type'].lower().capitalize()}` - `Confidence: {round(emotion[0]['Confidence'], 1)}%`
- **Pose:**
 \u200b \u200b \u200b- **Roll:** `{page.item['Face']['Pose']['Roll']}`
 \u200b \u200b \u200b- **Yaw:** `{page.item['Face']['Pose']['Yaw']}`
 \u200b \u200b \u200b- **Pitch:** `{page.item['Face']['Pose']['Pitch']}`{f'{newline}- **URLs Related to {page.name}:** {newline}{urls}' if urls else ''}
- **Picture Quality:**
 \u200b \u200b \u200b- **Brightness:** `{round(page.item['Face']['Quality']['Brightness'], 1)}%`
 \u200b \u200b \u200b- **Sharpness:** `{round(page.item['Face']['Quality']['Sharpness'], 1)}%`
        """

        embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")
        embed.timestamp = menu.ctx.message.created_at

        return embed


class TranslateLanguagesPagniator(ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        embed = discord.Embed(color=menu.ctx.bot.color)

        embed.timestamp = discord.utils.utcnow()

        embed.set_author(name="Languages:", icon_url=menu.ctx.author.avatar.url)

        embed.description = "```yml\n"

        entries = list(entries)

        embed.description += "\n".join(
            [
                f"{k.rjust(len(max(dict(entries).keys(), key=len)))}: {v}"
                for k, v in entries
            ]
        )

        embed.description += "```"

        embed.set_footer(
            text=f"Requested by {menu.ctx.author} | Page {menu.current_page + 1}/{self.get_max_pages()}",
            icon_url=menu.ctx.author.avatar.url,
        )

        return embed


class CodePaginator(menus.ListPageSource):
    def __init__(self, code):
        super().__init__(code, per_page=1)

    async def format_page(self, menu, entries):
        embed = discord.Embed(color=menu.ctx.bot.color)

        embed.timestamp = discord.utils.utcnow()

        embed.description = entries

        return embed


class IPBanListPaginator(ListPageSource):
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

        embed.set_footer(text=f"Page {menu.current_page + 1}/{self.get_max_pages()}")
        embed.timestamp = menu.ctx.message.created_at

        return embed


class QueueNowPlayingPaginator(ListPageSource):
    def __init__(self, queue, entries, *, per_page):
        super().__init__(entries, per_page=per_page)
        self.queue = queue

        self.num = 0

    async def format_page(self, menu, entries):
        embed = discord.Embed()
        embed.color = menu.ctx.bot.color

        embed.description = f"""
**Tracks:** {len(self.queue)}
**Time:** {humanize.naturaldelta(datetime.timedelta(seconds=sum(track.length for track in self.queue) // 1000))}
**Loop mode:** {self.queue.loop_mode.name.title()}\n
        """

        for index, track in enumerate(entries):
            self.num += 1

            try:
                embed.description += f"**{self.num}.** [{str(track.title)}]({track.uri}) | {humanize.naturaldelta(datetime.timedelta(seconds=track.length // 1000))} | {track.requester.mention}\n"
            except:
                embed.description += f"**{self.num}.** [{str(track.title)}]({track.uri}) | LIVE | {track.requester.mention}\n"

        return embed


class QueueHistoryPaginator(ListPageSource):
    async def format_page(self, menu, entries):
        embed = discord.Embed(color=menu.ctx.bot.color)

        embed.title = "Queue history:"

        embed.set_footer(text=f"1 = most recent | {len(entries)} = least recent")

        embed.description = f"**Tracks:** {len(entries)}\n**Time:** {humanize.naturaldelta(datetime.timedelta(seconds=sum(track.length for track in entries) // 1000))}\n\n"

        for index, track in entries:
            embed.description = "\n".join(
                [
                    f"**{index + 1}.** [{str(track.title)}]({track.uri}) | {humanize.naturaldelta(datetime.timedelta(track.length // 1000))} | {track.requester.mention}"
                ]
            )

        return embed


class TextToSpeechDetailsPaginator(ListPageSource):
    async def format_page(self, menu, entries):
        embed = discord.Embed(
            color=menu.ctx.bot.color,
            title=f"Text to speech details for language `{entries[0].language.name}`:",
        )
        embed.description = ""

        for page in entries:
            embed.description += f"""
__**{self.entries.index(page) + 1})**__
**Gender:** `{page.gender}`
**Voice ID:** `{page.id}`
**Name:** `{page.name}`
            """

        return embed


class CodeReviewPaginator(ListPageSource):
    async def format_page(self, menu, entries):
        embed = discord.Embed(
            color=menu.ctx.bot.color,
        )

        embed.description = (
            f"**File:** {entries['FilePath']}\n" if entries["FromGitHub"] else ""
        )

        embed.set_author(
            name="Your Code Review Results:", url=menu.ctx.message.jump_url
        )

        RecommendationCategory = entries["RecommendationCategory"]

        regex = re.findall(r"[A-Z]+", RecommendationCategory)
        regex = regex[1:]

        for i in regex:
            RecommendationCategory = RecommendationCategory.replace(i, " " + i)

        RecommendationCategory = RecommendationCategory.strip()

        code = entries["Code"].split("\n")

        code = "\n".join(code[entries["StartLine"] - 1 : entries["EndLine"]])

        RecommendationCategory = RecommendationCategory.replace("A W S", "AWS")

        embed.description += f"""
**Recomendation:** {entries['Description']}

**Recomendation for code:** `Line {entries['StartLine']}`{f" to `Line {entries['EndLine']}`" if entries['StartLine'] != entries['EndLine'] else ""} ```py
{code}```

**Category:** `{RecommendationCategory}`
        """

        if entries.get("Severity"):
            embed.description += f"**Severity:** `{entries['Severity']}`"

        return embed

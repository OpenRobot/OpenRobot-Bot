# Thanks to https://github.com/Axelware/Life-bot/blob/main/bot/utilities/custom/player.py

from __future__ import annotations
import typing

import discord
import asyncio
import yarl
import humanize
import datetime
import slate
import async_timeout
import slate.obsidian
from discord.components import SelectOption
from discord.ext import commands
from .enums import Filters

class Queue(slate.Queue[slate.obsidian.Track]):

    def __init__(
        self,
        player: Player,
        /
    ) -> None:

        super().__init__()
        self.player: Player = player

    def put(
        self,
        items: list[slate.obsidian.Track[commands.Context]] | slate.obsidian.Track[commands.Context],
        /,
        *,
        position: int | None = None
    ) -> None:

        super().put(items, position=position)

        self.player._queue_add_event.set()
        self.player._queue_add_event.clear()

class Player(slate.obsidian.Player["commands.Bot", commands.Context, "Player"]):

    def __init__(self, client: commands.Bot, channel: discord.VoiceChannel) -> None:
        super().__init__(client, channel)

        self.bot = client

        self._queue_add_event: asyncio.Event = asyncio.Event()
        self._track_end_event: asyncio.Event = asyncio.Event()

        self._task: asyncio.Task | None = None

        self._text_channel: discord.TextChannel | None = None
        self.message: discord.Message | None = None

        self.skip_request_ids: set[int] = set()
        self.enabled_filters: set[Filters] = set()

        self.queue: Queue = Queue(self)

        self._volume = 1

    @property
    def text_channel(self) -> discord.TextChannel | None:
        return self._text_channel

    @property
    def voice_channel(self) -> discord.VoiceChannel:
        return self.channel

    async def invoke_controller(
        self,
        channel: discord.TextChannel | None = None
    ) -> discord.Message | None:

        if (channel is None and self.text_channel is None) or self.current is None:
            return

        text_channel = channel or self.text_channel
        if text_channel is None:
            return

        embed = discord.Embed(
            title="Now playing:",
            description=f"**[{self.current.title}]({self.current.uri})**\nBy **{self.current.author}**",
            thumbnail=self.current.thumbnail
        )

        embed.add_field(
            name="__Player info:__",
            value=f"**Paused:** {self.paused}\n"
                  f"**Loop mode:** {self.queue.loop_mode.name.title()}\n"
                  f"**Queue length:** {len(self.queue)}\n"
                  f"**Queue time:** {humanize.naturaldelta(datetime.timedelta(seconds=sum(track.length for track in self.queue) // 1000), friendly=True)}\n",
        )

        embed.add_field(
            name="__Track info:__",
            value=f"**Time:** {humanize.naturaldelta(datetime.timedelta(seconds=self.position // 1000))} / {humanize.naturaldelta(datetime.timedelta(seconds=self.current.length // 1000))}\n"
                  f"**Is Stream:** {self.current.is_stream()}\n"
                  f"**Source:** {self.current.source.value.title()}\n"
                  f"**Requester:** {self.current.requester.mention if self.current.requester else 'N/A'}\n"
        )

        if not self.queue.is_empty():
            entries = [f"**{index + 1}.** [{entry.title}]({entry.uri})" for index, entry in enumerate(list(self.queue)[:3])]

            if len(self.queue) > 3:
                entries.append(f"**...**\n**{len(self.queue)}.** [{self.queue[-1].title}]({self.queue[-1].uri})")

            embed.add_field(
                name="__Up next:__",
                value="\n".join(entries),
                inline=False
            )

        return await text_channel.send(embed=embed)

    async def set_volume(self, volume: typing.Union[int, float]):
        await self.set_filter(
            slate.obsidian.Filter(self.filter, volume=volume)
        )

        old_volume = self._volume
        self._volume = volume

        return (old_volume, volume)

    @property
    def volume(self):
        return self._volume

    async def set_filter(self, filter: slate.obsidian.Filter, /, *, seek: bool = False):
        return await super().set_filter(filter, seek=seek)

    async def send(
        self,
        *args, **kwargs
    ) -> None:

        if not self.text_channel:
            return

        await self.text_channel.send(*args, **kwargs)

    async def search(
        self,
        query: str,
        /,
        *,
        source: slate.Source,
        ctx: commands.Context,
    ) -> slate.obsidian.SearchResult[commands.Context]:

        if (url := yarl.URL(query)) and url.host and url.scheme:
            source = slate.Source.NONE

        try:
            search = await self._node.search(query, ctx=ctx, source=source)

        except slate.NoMatchesFound as error:

            if error.source:
                message = f"No {error.source.value.lower().replace('_', ' ')} {error.search_type.value}s were found for your search."
            else:
                message = f"No results were found for your search.",

            raise error

        except (slate.SearchError, slate.HTTPError) as exc:
            raise exc

        return search

    async def queue_search(
        self,
        query: str,
        /,
        *,
        source: slate.Source,
        ctx: commands.Context,
        now: bool = False,
        next: bool = False,
        choose: bool = False,
        message: discord.Message = None
    ) -> None:

        search = await self.search(query, source=source, ctx=ctx)

        if message:
            await message.delete()

        if choose:
            entries = []

            for index, track in enumerate(search.tracks):
                entries.append((f'{index + 1:}', track.title, track.uri, track))

            embed = discord.Embed(color=self.bot.color, title='Select the number of the track you want to play.')
            embed.description = ''

            for index, title, url, _ in entries:
                embed.description += f'`{index}`. [`{title}`]({url})\n'

            class Select(discord.ui.Select):
                def __init__(self):
                    super().__init__(placeholder='Select an option.', options=[SelectOption(label=index + ' - ' + title, description=url) for index, title, url, _ in entries])

                async def callback(self, interaction: discord.Interaction):
                    x = discord.utils.find(lambda option: self.values[0] == option.label, self.options)

                    for child in self.view.children:
                        child.disabled = True

                    await interaction.response.defer()
                    
                    await self.view.msg.edit(view=self.view, content=f'You selected {x.label} - <{x.description}>.')

                    self.view.stop()
                    
                    self.view.value = (x, entries[int(x.label.split(' - ')[0])])

                    return self.view.value

            class View(discord.ui.View):
                def __init__(self, ctx):
                    super().__init__(timeout=60)
                    self.ctx = ctx
                    self.msg = None

                    self.value = None

                    self.add_item(Select())

                async def on_timeout(self) -> None:
                    for child in self.children:
                        child.disabled = True

                    await self.msg.edit(view=self, content='Timed Out.')

            view = View(ctx)

            view.msg = msg = await ctx.send(embed=embed, view=view)

            await view.wait()

            if not view.value:
                return

            track = view.value[1][3]
        else:
            tracks = search.tracks[0] if search.type is slate.SearchType.TRACK else search.tracks

        self.queue.put(tracks, position=0 if (now or next) else None)
        if now:
            await self.stop()

        if search.type is slate.SearchType.TRACK or isinstance(search.result, list):
            description = f"Added the {search.source.value.lower()} track [{search.tracks[0].title}]({search.tracks[0].uri}) to the queue."
        else:
            description = f"Added the {search.source.value.lower()} {search.type.name.lower()} [{search.result.name}]({search.result.uri}) to the queue."

        await ctx.reply(embed=discord.Embed(color=self.bot.color, description=description))

    async def loop(self) -> None:

        while True:

            self._queue_add_event.clear()
            self._track_end_event.clear()

            if self.queue.is_empty():

                try:
                    with async_timeout.timeout(timeout=3600):
                        await self._queue_add_event.wait()
                except asyncio.TimeoutError:
                    await self.disconnect()
                    break

            track = self.queue.get()

            if track.source is slate.Source.SPOTIFY:

                try:
                    search = await self.search(f"{track.author} - {track.title}", source=slate.Source.YOUTUBE, ctx=track.ctx)
                except Exception as error:
                    await self.send(embed=error.embed)
                    continue

                track = search.tracks[0]

            await self.play(track)

            await self._track_end_event.wait()

    async def connect(self, *, timeout: float | None = None, reconnect: bool | None = None, self_deaf: bool = True) -> None:

        await super().connect(timeout=timeout, reconnect=reconnect, self_deaf=self_deaf)
        self._task = asyncio.create_task(self.loop())

    async def disconnect(self, *, force: bool = False) -> None:

        await super().disconnect(force=force)

        if self._task is not None and self._task.done() is False:
            self._task.cancel()

    async def handle_track_start(self) -> None:
        self.message = await self.invoke_controller()

    async def handle_track_over(self) -> None:

        self.skip_request_ids = set()
        self._current = None

        self._track_end_event.set()
        self._track_end_event.clear()

        if not self.message:
            return

        try:
            old = self.queue._queue_history[0]
        except IndexError:
            return

        #await self.message.edit(embed=utils.embed(description=f"Finished playing **[{old.title}]({old.uri})** by **{old.author}**."))

    async def handle_track_error(self) -> None:

        await self.send(
            embed=discord.Embed(
                colour=self.bot.color,
                description=f"Something went wrong while playing a track.",
            )
        )

        await self.handle_track_over()
# Thanks to https://github.com/Axelware/Life-bot/blob/main/bot/extensions/voice.py

import datetime
import inspect
import io
import aiohttp
import discord
import typing
from discord import voice_client
import humanize
import slate
import math
import base64
import asyncpg
import asyncio
from discord.ext import commands
from cogs.utils import Cog, Player, FlagConverter, TimeConverter, is_guild_owner, QueueNowPlayingPaginator, ViewMenuPages, ClassicPaginator, QueueHistoryPaginator, Filters
from slate import obsidian

class Options(FlagConverter):
    music: bool = False
    soundcloud: bool = False
    local: bool = False
    http: bool = False
    next: bool = False
    now: bool = False

def get_source(flags) -> slate.Source:
    if flags.music:
        return slate.Source.YOUTUBE_MUSIC
    elif flags.soundcloud:
        return slate.Source.SOUNDCLOUD

    return slate.Source.YOUTUBE

music = commands

class Music(Cog):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

        self.bot.slate = obsidian.NodePool()
        self.slate = self.bot.slate

    async def initiate_node(self):
        await self.slate.create_node(bot=self.bot, identifier='OpenRobot Obsidian - 1', **self.bot.config.OBSIDIAN_SLATE_CRIDENTIALS)

        print('Obsidian Ready!')

    async def get_user_near_expire(self) -> typing.Tuple[int, dict]:
        while True:
            try:
                res = await self.bot.spotify_pool.fetchrow('SELECT * FROM spotify_auth ORDER BY expires_at ASC')
            except:
                pass
            else:
                if res is None:
                    return None

                return int(res['user_id']), dict(res)

    async def renew(self): # Renews spotify token
        await self.bot.wait_until_ready()

        while True:
            user_near_expire = await self.get_user_near_expire()

            if user_near_expire is not None:
                user_id, res = user_near_expire

                while res['expires_at'] > datetime.datetime.utcnow():
                    pass

                try:
                    async with aiohttp.ClientSession() as sess:
                        async with sess.post('https://accounts.spotify.com/api/token', headers={'Authorization': 'Basic ' + base64.urlsafe_b64encode(f'{self.spotify_auth.application_id}:{self.spotify_auth.application_secret}')}, params = {'grant_type': 'refresh_token', 'refresh_token': res['refresh_token']}) as resp:
                            js = await resp.json()

                            if 'expires_in' not in js and 'access_token' not in js:
                                await self.bot.spotify_pool.execute("""
                                DELETE FROM spotify_auth
                                WHERE user_id = $1
                                """, user_id)
                                continue

                            while True:
                                try:
                                    await self.bot.spotify_pool.execute("""
                                    UPDATE spotify_auth
                                    SET access_token = $2,
                                        expires_st = $3,
                                        expires_in = $4
                                    WHERE user_id = $1
                                    """, user_id, js['access_token'], (datetime.datetime.utcnow() + datetime.timedelta(seconds=js['expires_in'])), js['expires_in'])
                                except asyncpg.exceptions._base.InterfaceError:
                                    pass
                                else:
                                    pass
                except Exception as e:
                    raise e

            await asyncio.sleep(10)
            continue

    @commands.Cog.listener()
    async def on_obsidian_track_start(self, player: Player, _: obsidian.TrackStart) -> None:
        await player.handle_track_start()

    @commands.Cog.listener()
    async def on_obsidian_track_end(self, player: Player, _: obsidian.TrackEnd) -> None:
        await player.handle_track_over()

    @commands.Cog.listener()
    async def on_obsidian_track_exception(self, player: Player, _: obsidian.TrackException) -> None:
        await player.handle_track_error()

    @commands.Cog.listener()
    async def on_obsidian_track_stuck(self, player: Player, _: obsidian.TrackStuck) -> None:
        await player.handle_track_error()

    #@commands.group('music')
    async def __music(self, ctx: commands.Context): # useless
        """
        Useful Music commands.
        """

        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command)

    @music.command('connect', aliases=['join', 'summon'])
    async def connect(self, ctx: commands.Context, *, channel: typing.Union[discord.VoiceChannel, discord.StageChannel] = commands.Option(None, description='The channel to join to.')):
        """
        Connects to a channel.
        """

        if ctx.voice_client and ctx.voice_client.is_connected():
            return await ctx.send(embed=discord.Embed(
                colour=self.bot.color,
                description=f"I am already connected to {ctx.voice_client.voice_channel.mention}.",
            ))

        if not channel:
            channel = getattr(ctx.author.voice, 'channel', None)
            if not channel:
                return await ctx.send(embed=discord.Embed(color=self.bot.color, description='You must be in a voice channel to use this command!'))

        await channel.connect(cls=Player)
        ctx.voice_client._text_channel = ctx.channel

        return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'Joined {ctx.voice_client.voice_channel.mention}'))

    @music.command('disconnect', aliases=['leave', 'dc', 'destroy'])
    async def disconnect(self, ctx: commands.Context):
        """
        Disconnects the bot from the voice channel.

        You must be in the bot's voice channel to disconnect the bot.
        """

        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='I am not in any Voice Channels!'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        chan = ctx.voice_client.voice_channel

        await ctx.voice_client.disconnect()

        return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'Left {chan.mention}'))

    @music.command('play', aliases=['p'])
    async def play(self, ctx: commands.Context, *, query: str = None):
        """
        Queues tracks with the given name or url.

        Arguments:
        - query: The query to search for.

        Flags:
        - `--from-spotify-liked-songs`: Plays music from your liked songs. Note that you are required to sign in to OpenRobot Spotify. `or.spotify login`
        - `--music`: Searches [YouTube music](https://music.youtube.com/) for results.
        - `--soundcloud`: Searches [soundcloud](https://soundcloud.com/) for results.
        - `--next`: Puts the track that is found at the start of the queue.
        - `--now`: Skips the current track and plays the track that is found.
        """

        if query is None and ctx.voice_client and ctx.voice_client.paused is True:
            return await self.resume(ctx)
        elif query is None:
            raise commands.MissingRequiredArgument(inspect.Parameter('query', inspect.Parameter.KEYWORD_ONLY, annotation=str))

        flags = discord.Object(0)

        if query == '--from-spotify-liked-songs':
            from_liked_songs = True
        else:
            from_liked_songs = False

        if '--music' in query.split(' '):
            flags.music = True
            query = query.split(' --music', '')
        else:
            flags.music = False
        
        if '--soundcloud' in query.split(' '):
            flags.soundcloud = True
            query = query.replace(' --soundcloud', '')
        else:
            flags.soundcloud = False

        if '--next' in query.split(' '):
            flags.next = True
            query = query.replace(' --next', '')
        else:
            flags.next = False

        if '--now' in query.split(' '):
            flags.now = True
            query = query.replace(' --now', '')
        else:
            flags.now = False

        if ctx.voice_client is None or ctx.voice_client.is_connected() is False:
            if (command := ctx.bot.get_command("connect")) is None or await command.can_run(ctx) is True:
                await ctx.invoke(command, channel=None)

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        offset = 0

        urls = []

        tracks = []

        async with ctx.channel.typing():
            m = await ctx.send(embed=discord.Embed(color=self.bot.color, description='<a:openrobot_searching_gif:899928367799885834> Searching...'))

            if from_liked_songs:
                try:
                    while True:
                        try:
                            x = await self.bot.spotify_pool.fetchrow("SELECT * FROM spotify_auth WHERE user_id = $1", ctx.author.id)
                        except asyncpg.exceptions._base.InterfaceError:
                            pass
                        else:
                            if x:
                                access_token = x['access_token']
                            else:
                                access_token = None

                            break

                    if not access_token:
                        return await ctx.send('Please Sign-In to OpenRobot Spotify using `or.spotify login`.')

                    while True:
                        async with aiohttp.ClientSession() as sess:
                            async with sess.get('https://api.spotify.com/v1/me/tracks', params={'limit': 50, 'offset': offset, 'market': 'US'}, headers={'Authorization': f'Bearer {access_token}'}) as resp:
                                js = await resp.json()

                                import json

                                await ctx.send(file=discord.File(io.StringIO(json.dumps(js, indent=4)), filename='result.json'))

                                if not js['items']:
                                    break

                                for item in js['items']:
                                    urls.append(item['track']['external_urls']['spotify'])

                                offset += 50

                    if not urls:
                        return await ctx.send('If you don\'t have any Spotify Liked Songs, how can I load them?')

                    for url in urls:
                        tracks.append((await ctx.voice_client.search(url, source=slate.Source.YOUTUBE, ctx=ctx)).tracks[0])
                except Exception as e:
                    raise e
                    return await ctx.send('Something wen\'t wrong in our back-end, and we aren\'t able to query your Spotify Liked Songs.')

                ctx.voice_client.queue.put(tracks, position=0 if (flags.now or flags.next) else None)
                if flags.now:
                    await self.stop()

                await m.delete()

                await ctx.reply(embed=discord.Embed(color=self.bot.color, description=f'Added {len(tracks)} tracks to the queue from your Spotify Liked Songs.'))
            else:
                await ctx.voice_client.queue_search(query, ctx=ctx, now=flags.now, next=flags.next, source=get_source(flags), message=m, delete_message=True)

    @music.command('search')
    async def search(self, ctx: commands.Context, *, query: str = None):
        """
        Choose which track to play based on a search.

        Arguments:
        - query: The query to search for.

        Flags:
        - --music: Searches [YouTube music](https://music.youtube.com/) for results.
        - --soundcloud: Searches [soundcloud](https://soundcloud.com/) for results.
        - --next: Puts the track that is found at the start of the queue.
        - --now: Skips the current track and plays the track that is found.
        """

        if query is None and ctx.voice_client and ctx.voice_client.paused is True:
            return await ctx.voice_client.set_pause(False)
        elif query is None:
            raise commands.MissingRequiredArgument(inspect.Parameter('query', inspect.Parameter.KEYWORD_ONLY, annotation=str))

        flags = discord.Object(0)

        if '--music' in query.split(' '):
            flags.music = True
            query = query.split(' --music', '')
        else:
            flags.music = False
        
        if '--soundcloud' in query.split(' '):
            flags.soundcloud = True
            query = query.replace(' --soundcloud', '')
        else:
            flags.soundcloud = False

        if '--next' in query.split(' '):
            flags.next = True
            query = query.replace(' --next', '')
        else:
            flags.next = False

        if '--now' in query.split(' '):
            flags.now = True
            query = query.replace(' --now', '')
        else:
            flags.now = False

        if ctx.voice_client is None or ctx.voice_client.is_connected() is False:
            if (command := ctx.bot.get_command("connect")) is None or await command.can_run(ctx) is True:
                await ctx.invoke(command, channel=None)

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        async with ctx.channel.typing():
            m = await ctx.send(embed=discord.Embed(color=self.bot.color, description='<a:openrobot_searching_gif:899928367799885834> Searching...'))
            await ctx.voice_client.queue_search(query, ctx=ctx, now=flags.now, next=flags.next, source=get_source(flags), choose=True, message=m)

    @music.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """
        Pauses the current track.
        """

        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.paused is True:
            return await ctx.send(embed=discord.Embed(
                color=self.bot.color,
                description="The track is already paused."
            ))

        await ctx.voice_client.set_pause(True)
        await ctx.send(embed=discord.Embed(color=self.bot.color, description="The player is now paused."))

    @music.command('stop')
    async def stop(self, ctx: commands.Context):
        """
        Stops the current track.
        """

        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.paused is True:
            return await ctx.send(embed=discord.Embed(
                color=self.bot.color,
                description="This track is already paused."
            ))

        await ctx.voice_client.set_pause(True)
        await ctx.send(embed=discord.Embed(color=self.bot.color, description="The player is now stopped."))

    @music.command('resume')
    async def resume(self, ctx: commands.Context):
        """
        Resumes the current track.
        """

        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.paused is False:
            return await ctx.send(embed=discord.Embed(
                color=self.bot.color,
                description="The track is already resumed."
            ))

        await ctx.voice_client.set_pause(False)
        await ctx.send(embed=discord.Embed(color=self.bot.color, description="The player is now resumed."))

    @music.command('volume', aliases=['vol'])
    async def volume(self, ctx: commands.Context, volume: int = commands.Option(description='The volume to be set to.')):
        """
        Sets the volume of the player.

        This can be a number from 1 - 100.
        """
        
        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if 0 >= volume > 100:
            return await ctx.send("Invalid volume. Only accepts numbers from 1-100.")
        else:
            volume /= 100

        old_volume, new_volume = await ctx.voice_client.set_volume(volume)

        await ctx.send(embed=discord.Embed(color=self.bot.color, description=f"Volume has been changed from **{old_volume*100}%** to **{new_volume*100}%**."))

    @music.command('seek', aliases=['skip-to', 'skipto', 'skip_to'])
    async def seek(self, ctx: commands.Context, *, time: TimeConverter = commands.Option(description='Seeks to the time provided.')):
        """
        Seeks to a position in the current track.

        Valid time formats include:

        - 01:10:20 (hh:mm:ss)
        - 01:20 (mm:ss)
        - 20 (ss)
        - (h:m:s)
        - (hh:m:s)
        - (h:mm:s)
        - ...

        - 1 hour 20 minutes 30 seconds
        - 1 hour 20 minutes
        - 1 hour 30 seconds
        - 20 minutes 30 seconds
        - 20 minutes
        - 30 seconds
        - 1 hour 20 minutes and 30 seconds
        - 1h20m30s
        - 20m and 30s
        - 20s
        - ...
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if not ctx.voice_client.current or not ctx.voice_client.current.is_seekable():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The current track is not seekable.'))

        if time is None:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='That time format was not recognized.'))

        milliseconds = time.seconds * 1000

        if 0 < milliseconds > ctx.voice_client.current.length:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'That is not a valid amount of time, please choose a time between `0s` and `{ctx.voice_client.current.length // 1000}s`.'))

        await ctx.voice_client.set_position(milliseconds)

        await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'The player position is now at `{ctx.voice_client.position // 1000}s` (`{humanize.naturaldelta(datetime.timedelta(seconds=ctx.voice_client.position // 1000))}`)'))

    @music.command('fast-forward', aliases=['fast_forward', 'fastforward', 'ff', 'forward', 'fwd'])
    async def fast_forward(self, ctx: commands.Context, *, time: TimeConverter = commands.Option(description='Fast-forwards to the time provided')):
        """
        Seeks the player forward.

        Valid time formats include:

        - 01:10:20 (hh:mm:ss)
        - 01:20 (mm:ss)
        - 20 (ss)
        - (h:m:s)
        - (hh:m:s)
        - (h:mm:s)
        - ...

        - 1 hour 20 minutes 30 seconds
        - 1 hour 20 minutes
        - 1 hour 30 seconds
        - 20 minutes 30 seconds
        - 20 minutes
        - 30 seconds
        - 1 hour 20 minutes and 30 seconds
        - 1h20m30s
        - 20m and 30s
        - 20s
        - ...
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if not ctx.voice_client.current or not ctx.voice_client.current.is_seekable():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The current track is not seekable.'))

        if time is None:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='That time format was not recognized.'))

        milliseconds = time.seconds * 1000
        position = ctx.voice_client.position
        remaining = ctx.voice_client.current.length - position

        if milliseconds >= remaining:
            await ctx.send(embed=discord.Embed(
                color=self.bot.color,
                description=f"That was too much time to seek forward, try seeking forward an amount less than "
                            f"**{humanize.naturaldelta(datetime.timedelta(seconds=remaining // 1000))}**.",
            ))

        await ctx.voice_client.set_position(position + milliseconds)

        embed = discord.Embed(
            color=self.bot.color,
            description=f"Seeking forward **{humanize.naturaldelta(datetime.timedelta(seconds=time.seconds))}**, the players position is now "
                        f"**{humanize.naturaldelta(datetime.timedelta(seconds=ctx.voice_client.position // 1000))}**."
        )
        await ctx.send(embed=embed)

    @music.command('rewind', aliases=['rwd', 'backward', 'bwd'])
    async def rewind(self, ctx: commands.Context, *, time: TimeConverter = commands.Option(description='Rewinds to the time provided.')):
        """
        Seeks the player backward.

        Valid time formats include:

        - 01:10:20 (hh:mm:ss)
        - 01:20 (mm:ss)
        - 20 (ss)
        - (h:m:s)
        - (hh:m:s)
        - (h:mm:s)
        - ...

        - 1 hour 20 minutes 30 seconds
        - 1 hour 20 minutes
        - 1 hour 30 seconds
        - 20 minutes 30 seconds
        - 20 minutes
        - 30 seconds
        - 1 hour 20 minutes and 30 seconds
        - 1h20m30s
        - 20m and 30s
        - 20s
        - ...
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if not ctx.voice_client.current or not ctx.voice_client.current.is_seekable():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The current track is not seekable.'))

        if time is None:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='That time format was not recognized.'))

        milliseconds = time.seconds * 1000
        position = ctx.voice_client.position

        if milliseconds >= position:
            await ctx.send(embed=discord.Embed(
                color=self.bot.color,
                description=f"That was too much time to seek backward, try seeking backward an amount less than "
                            f"**{humanize.naturaldelta(datetime.timedelta(seconds=position // 1000))}**.",
            ))

        await ctx.voice_client.set_position(position - milliseconds)

        embed = discord.Embed(
            color=self.bot.color,
            description=f"Seeking backward **{humanize.naturaldelta(datetime.timedelta(seconds=time.seconds))}**, the players position is now "
                        f"**{humanize.naturaldelta(datetime.timedelta(seconds=ctx.voice_client.position // 1000))}**."
        )
        await ctx.send(embed=embed)

    @music.command('replay', aliases=['restart'])
    async def replay(self, ctx: commands.Context):
        """
        Replays the current track.
        """
        
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if not ctx.voice_client.current or not ctx.voice_client.current.is_seekable():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The current track is not seekable.'))

        await ctx.voice_client.set_position(0)

        embed = discord.Embed(
            color=self.bot.color,
            description=f"Replaying [{ctx.voice_client.current.title}]({ctx.voice_client.current.uri}) by **{ctx.voice_client.current.author}**."
        )
        await ctx.send(embed=embed)

    @music.command('loop')
    async def loop(self, ctx: commands.Context, *, loop_type: typing.Literal['Current', 'Queue', 'None'] = commands.Option(description='The new loop type to be set.')):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if loop_type == 'None':
            ctx.voice_client.queue.set_loop_mode(slate.QueueLoopMode.OFF)
        elif loop_type == 'Current':
            ctx.voice_client.queue.set_loop_mode(slate.QueueLoopMode.CURRENT)
        elif loop_type == 'Queue':
            ctx.voice_client.queue.set_loop_mode(slate.QueueLoopMode.QUEUE)
        else:
            return await ctx.send('Loop type not recognized.')

        embed = discord.Embed(
            color=self.bot.color,
            description=f"The queue looping mode is now **{ctx.voice_client.queue.loop_mode.name.title()}**.",
        )
        await ctx.send(embed=embed)

    @music.command('skip', aliases=['fs'])
    async def skip(self, ctx: commands.Context, *, amount: int = commands.Option(1, description='Number of tracks to skip. Defaults to 1.')):
        """
        Skips the current track.

        **amount**: The amount of tracks to skip, only works if you are the bot owner, guild owner, or have the manage guild, manage message, manage channels, kick members, or ban members permissions.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        try:
            await commands.check_any(  # type: ignore
                commands.is_owner(),
                is_guild_owner(),
                commands.has_permissions(manage_guild=True, manage_messages=True, manage_channels=True, kick_members=True, ban_members=True),
            ).predicate(ctx=ctx)

            if 0 <= amount > len(ctx.voice_client.queue) + 1:
                return await ctx.send(embed=discord.Embed(
                    color=self.bot.color,
                    description=f"There are not enough tracks in the queue to skip that many, try again with an amount between "
                                f"**1** and **{len(ctx.voice_client.queue) + 1}**.",
                ))

            for _ in enumerate(ctx.voice_client.queue[:amount - 1]):
                ctx.voice_client.queue.get(put_history=False)

            await ctx.voice_client.stop()
            await ctx.send(embed=discord.Embed(color=self.bot.color, description=f"Skipped **{amount}** track{'s' if amount != 1 else ''}."))
            return

        except commands.CheckAnyFailure:

            if ctx.author.id == ctx.voice_client.current.requester.id:
                await ctx.voice_client.stop()
                return await ctx.send(embed=discord.Embed(color=self.bot.color, description="Skipped the current track."))

            if ctx.author not in ctx.voice_client.listeners:
                return await ctx.send(embed=discord.Embed(
                    color=self.bot.color,
                    description="You can not vote to skip as you are currently deafened.",
                ))

            skips_needed = math.floor(75 * len(ctx.voice_client.listeners) / 100)

            if ctx.author.id not in ctx.voice_client.skip_request_ids:

                ctx.voice_client.skip_request_ids.add(ctx.author.id)

                if len(ctx.voice_client.skip_request_ids) < skips_needed:
                    embed = discord.Embed(
                        color=self.bot.color,
                        description=f"Added your vote to skip, currently on **{len(ctx.voice_client.skip_request_ids)}** out of **{skips_needed}** votes "
                                    f"needed to skip."
                    )
                    await ctx.send(embed=embed)
                    return

                await ctx.voice_client.stop()
                await ctx.send(embed=discord.Embed(color=self.bot.color, description="Skipped the current track."))
                return

            ctx.voice_client.skip_request_ids.remove(ctx.author.id)
            await ctx.send(embed=discord.Embed(color=self.bot.color, description="Removed your vote to skip."))

    @music.command('now-playing', aliases=['nowplaying', 'now_playing', 'np'])
    async def now_playing(self, ctx: commands.Context):
        """
        Shows info about the current track.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        await ctx.voice_client.invoke_controller(ctx.channel)

    @music.command('save', aliases=['grab', 'keep'])
    async def save(self, ctx: commands.Context):
        """
        Saves the current track to your DM's.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        try:
            embed = discord.Embed(
                title=f"{ctx.voice_client.current.title}",
                url=f"{ctx.voice_client.current.uri}",
                description=f"**Author:** {ctx.voice_client.current.author}\n"
                            f"**Source:** {ctx.voice_client.current.source.name.title()}\n"
                            f"**Length:** {humanize.naturaldelta(datetime.timedelta(seconds=ctx.voice_client.current.length // 1000))}\n" if not ctx.voice_client.is_stream() else "**Length:** LIVE"
                            f"**Is stream:** {ctx.voice_client.current.is_stream()}\n"
                            f"**Is seekable:** {ctx.voice_client.current.is_seekable()}\n"
                            f"**Requester:** {ctx.voice_client.current.requester} `{ctx.voice_client.current.requester.id}`",
                color=self.bot.color
            ).set_thumbnail(url=ctx.voice_client.current.thumbnail)
            await ctx.author.send(embed=embed)
            await ctx.send(embed=discord.Embed(color=self.bot.color, description="Saved the current track to our DM's."))
        except discord.Forbidden:
            return await ctx.send(embed=discord.Embed(
                color=self.bot.color,
                description="I am unable to DM you."
            ))

    @music.command('queue', aliases=['q'])
    async def queue(self, ctx: commands.Context, action: typing.Literal['Detailed', 'Show'] = commands.Option(description='Views detailed or shows normally.')):
        """
        Queue music commands.
        """

        if action == 'Show':
            return await self.queue_show(ctx)
        elif action == 'Detailed':
            return await self.queue_detailed(ctx)
        else:
            return await ctx.send('Unknown action.')

    #@queue.command('show', aliases=['list'])
    async def queue_show(self, ctx: commands.Context):
        """
        Displays tracks in the queue.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.voice_client.queue.is_empty():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue is empty.'))

        queue = ctx.voice_client.queue

        await ViewMenuPages(QueueNowPlayingPaginator(queue, queue, per_page=10)).start(ctx)

    #@queue.command('detailed', aliases=['detail', 'd'])
    async def queue_detailed(self, ctx: commands.Context):
        """
        Displays detailed information about the tracks in the queue.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.voice_client.queue.is_empty():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue is empty.'))

        entries = []

        for track in ctx.voice_client.queue:
            embed = discord.Embed(
                title=track.title,
                url=track.uri,
                description=f"**Author:** {track.author}\n"
                            f"**Length:** {humanize.naturaldelta(datetime.timedelta(seconds=round(track.length) // 1000))}\n" if not track.is_stream() else "**Length:** LIVE"
                            f"**Source:** {track.source.name.title()}\n"
                            f"**Requester:** {track.requester.mention} `{track.requester.id}`\n"
                            f"**Is stream:** {track.is_stream()}\n"
                            f"**Is seekable:** {track.is_seekable()}\n",
                color=self.bot.color
            ).set_image(url=track.thumbnail)

            entries.append(embed)

        await ViewMenuPages(ClassicPaginator(entries, per_page=1)).start(ctx)

    @music.group('queue-history', aliases=['h'])
    async def queue_history(self, ctx: commands.Context, action: typing.Literal['Detailed', 'Show'] = commands.Option(description='Views detailed or shows normally.')):
        """
        Displays tracks in the queue history.
        """

        if action == 'Show':
            return await self.queue_history_show(ctx)
        elif action == 'Detailed':
            return await self.queue_history_detailed(ctx)
        else:
            return await ctx.send('Unknown action.')

    #@queue_history.command('show', aliases=['list'])
    async def queue_history_show(self, ctx: commands.Context):
        """
        Displays tracks in the queue history.
        """

        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        history = ctx.voice_client.queue._queue_history

        if not history:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue history is empty.'))

        l = []

        for index, track in enumerate(history):
            l.append((index, track))

        await ViewMenuPages(QueueHistoryPaginator(l, per_page=10)).start(ctx)

    #@queue_history.command('detailed', aliases=['detail', 'd'])
    async def queue_history_detailed(self, ctx: commands.Context):
        """
        Displays detailed information about the tracks in the queue history.
        """

        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        history = ctx.voice_client.queue._queue_history

        if not history:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue history is empty.'))

        entries = []

        for track in ctx.voice_client.queue:
            embed = discord.Embed(
                title=track.title,
                url=track.uri,
                description=f"**Author:** {track.author}\n"
                            f"**Length:** {humanize.naturaldelta(datetime.timedelta(seconds=round(track.length) // 1000))}\n" if not track.is_stream() else "**Length:** LIVE"
                            f"**Source:** {track.source.name.title()}\n"
                            f"**Requester:** {track.requester.mention} `{track.requester.id}`\n"
                            f"**Is stream:** {track.is_stream()}\n"
                            f"**Is seekable:** {track.is_seekable()}\n",
                color=self.bot.color
            ).set_thumbnail(url=track.thumbnail)

            entries.append(embed)

        await ViewMenuPages(ClassicPaginator(entries, per_page=1)).start(ctx)

    @music.command('clear', aliases=['cls', 'clr'])
    async def clear(self, ctx: commands.Context):
        """
        Clears the queue.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.queue.is_empty():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue is empty.'))

        ctx.voice_client.queue.clear()
        await ctx.send(embed=discord.Embed(colour=self.bot.color, description="The queue has been cleared."))

    @music.command('shuffle', aliases=['shfl'])
    async def shuffle(self, ctx: commands.Context):
        """
        Shuffles the queue.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.queue.is_empty():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue is empty.'))

        ctx.voice_client.queue.shuffle()
        await ctx.send(embed=discord.Embed(colour=self.bot.color, description="The queue has been shuffled."))

    @music.command('reverse')
    async def reverse(self, ctx: commands.Context):
        """
        Reverses the queue.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.queue.is_empty():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue is empty.'))

        ctx.voice_client.queue.reverse()
        await ctx.send(embed=discord.Embed(colour=self.bot.color, description="The queue has been reversed."))

    @music.command('sort')
    async def sort(self, ctx: commands.Context, method: typing.Literal["Title", "Length", "Author"] = commands.Option(description='Sorts by Title/Length/Author.'), reverse: bool = commands.Option(False, description='Whether to reverse the sort.')):
        """
        Sorts the queue.

        **method**: The method to sort the queue with. Can be **title**, **length** or **author**.
        **reverse**: Whether to reverse the sort, as in **5, 3, 2, 4, 1** -> **5, 4, 3, 2, 1** instead of **5, 3, 2, 4, 1** -> **1, 2, 3, 4, 5**. Defaults to False.

        **Usage:**
        `l-sort title True`
        `l-sort author`
        `l-sort length True`
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.queue.is_empty():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue is empty.'))

        if method == "Title":
            ctx.voice_client.queue._queue.sort(key=lambda track: track.title, reverse=reverse)
        elif method == "Author":
            ctx.voice_client.queue._queue.sort(key=lambda track: track.author, reverse=reverse)
        elif method == "Length":
            ctx.voice_client.queue._queue.sort(key=lambda track: track.length, reverse=reverse)

        await ctx.send(embed=discord.Embed(colour=self.bot.color, description=f"The queue has been sorted by {method}."))

    @music.command('remove', aliases=['rm'])
    async def remove(self, ctx: commands.Context, entry: int = commands.Option(description='The entry/index of the track to be removed.')):
        """
        Removes a track from the queue.

        **entry**: The position of the track you want to remove.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.queue.is_empty():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue is empty.'))

        if entry <= 0 or entry > len(ctx.voice_client.queue):
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f"That was not a valid track entry, try again with a number between **1** and **{len(ctx.voice_client.queue)}**."))

        item = ctx.voice_client.queue.get(entry - 1, put_history=False)
        await ctx.send(embed=discord.Embed(color=self.bot.color, description=f"Removed **[{item.title}]({item.uri})** which was requested by **{item.author}** from the queue."))

    @music.command('move', aliases=['mv'])
    async def move(self, ctx: commands.Context, entry_1: int = commands.Option(description='The original track\'s entry/index.'), entry_2: int = commands.Option(description='The new entry/index for the track to be moved to.')):
        """
        Move a track in the queue to a different position.
        
        **entry_1**: The position of the track you want to move from.
        **entry_2**: The position of the track you want to move too.
        """

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if ctx.voice_client.queue.is_empty():
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='The queue is empty.'))

        if (entry_1 <= 0 or entry_1 > len(ctx.voice_client.queue)) or (entry_2 <= 0 or entry_2 > len(ctx.voice_client.queue)):
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f"That was not a valid track entry to move from, try again with a number between **1** and **{len(ctx.voice_client.queue)}**."))

        track = ctx.voice_client.queue.get(entry_1 - 1, put_history=False)
        ctx.voice_client.queue.put(track, position=entry_2 - 1)

        await ctx.send(embed=discord.Embed(color=self.bot.color, description=f"Moved **[{track.title}]({track.uri})** from position **{entry_1}** to position **{entry_2}**."))

    @music.command('filter', aliases=['filt', 'set-filter', 'set_filter', 'setfilter'])
    async def _filter(self, ctx: commands.Context, filter: typing.Literal['8D', 'Nightcore'] = commands.Option(description='The filter to enable/disable.')):
        """
        Filter commands.
        """

        if filter == '8D':
            return await self._8D(ctx)
        elif filter == 'Nightcore':
            return await self.nightcore(ctx)
        else:
            return await ctx.send('Unknown filter.')

    #@_filter.command('8D', aliases=['8dimentional', '8-dimentional', '8_dimentional'])
    async def _8D(self, ctx: commands.Context):
        """
        Sets an 8D audio filter on the player.
        """

        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if Filters.ROTATION in ctx.voice_client.enabled_filters:
            await ctx.voice_client.set_filter(
                obsidian.Filter(ctx.voice_client.filter, rotation=obsidian.Rotation())
            )
            ctx.voice_client.enabled_filters.remove(Filters.ROTATION)

            embed = discord.Embed(
                color=self.bot.color,
                description="**8D** audio effect is now **inactive**."
            )
        else:
            await ctx.voice_client.set_filter(
                obsidian.Filter(ctx.voice_client.filter, rotation=obsidian.Rotation(rotation_hertz=0.5))
            )
            ctx.voice_client.enabled_filters.add(Filters.ROTATION)
            embed = discord.Embed(
                color=self.bot.color,
                description="**8D** audio effect is now **active**."
            )

        await ctx.send(embed=embed)

    #@_filter.command('nightcore', aliases=["night_core", "night-core", "nc"])
    async def nightcore(self, ctx: commands.Context):
        """
        Sets a nightcore audio filter on the player.
        """

        if not ctx.voice_client:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description='There are no tracks playing.'))

        if ctx.author not in ctx.voice_client.channel.members:
            return await ctx.send(embed=discord.Embed(color=self.bot.color, description=f'You are not in {ctx.voice_client.channel.mention}!'))

        if Filters.NIGHTCORE in ctx.voice_client.enabled_filters:
            await ctx.voice_client.set_filter(obsidian.Filter(ctx.voice_client.filter, timescale=obsidian.Timescale()))
            ctx.voice_client.enabled_filters.remove(Filters.NIGHTCORE)

            embed = discord.Embed(
                color=self.bot.color,
                description="**Nightcore** audio effect is now **inactive**."
            )
        else:
            await ctx.voice_client.set_filter(obsidian.Filter(ctx.voice_client.filter, timescale=obsidian.Timescale(speed=1.12, pitch=1.12)))
            ctx.voice_client.enabled_filters.add(Filters.NIGHTCORE)

            embed = discord.Embed(
                color=self.bot.color,
                description="**Nightcore** audio effect is now **active**."
            )
        
        await ctx.send(embed=embed)

    @music.command(name="node-stats", aliases=["node_stats", "nodestats", "ns"])
    async def node_stats(self, ctx: commands.Context):
        """
        Displays information about the bots connected nodes.
        """

        embeds = []

        for node in self.bot.slate.nodes.values():

            embed = discord.Embed(
                color=self.bot.color,
                title=f"Stats: {node._identifier}",
                description=f"**Players:** {len(node.players.values())}\n"
                            f"**Active players:** {len([player for player in node.players.values() if player.is_playing()])}\n\n"
            )

            if node._stats:
                embed.description += f"**Threads (running):** {node._stats.threads_running}\n" \
                                     f"**Threads (daemon):** {node._stats.threads_daemon}\n" \
                                     f"**Threads (peak):** {node._stats.threads_peak}\n\n" \
                                     f"**Memory (init):** {humanize.naturalsize(node._stats.heap_used_init + node._stats.non_heap_used_init)}\n" \
                                     f"**Memory (max):** {humanize.naturalsize(node._stats.heap_used_max + node._stats.non_heap_used_max)}\n" \
                                     f"**Memory (committed):** " \
                                     f"{humanize.naturalsize(node._stats.heap_used_committed + node._stats.non_heap_used_committed)}\n" \
                                     f"**Memory (used):** {humanize.naturalsize(node._stats.heap_used_used + node._stats.non_heap_used_used)}\n\n" \
                                     f"**CPU (cores):** {node._stats.cpu_cores}\n"

            embeds.append(embed)

        await ViewMenuPages(ClassicPaginator(embeds, per_page=1)).start(ctx)

    @music.command(name="voice-clients", aliases=["voice_clients", "voiceclients", "vcs"])
    async def voiceclients(self, ctx: commands.Context):
        """
        Displays information about voice clients that the bot has.
        """

        entries = []

        for node in self.bot.slate.nodes.values():
            for player in node.players.values():

                current = f"[{player.current.title}]({player.current.uri}) by **{player.current.author}**" if player.current else "None"
                position = \
                    f"{humanize.naturaldelta(datetime.timedelta(seconds=player.position // 1000))} / {humanize.naturaldelta(datetime.timedelta(seconds=player.current.length // 1000)) if not player.current.is_stream() else 'LIVE'}" \
                    if player.current \
                    else "N/A"

                entries.append(
                    f"**{player.channel.guild}:** `{player.channel.guild.id}`\n"
                    f"**Voice channel:** {player.voice_channel} `{getattr(player.voice_channel, 'id', None)}`\n"
                    f"**Text channel:** {player.text_channel} `{getattr(player.text_channel, 'id', None)}`\n"
                    f"**Track:** {current}\n"
                    f"**Position:** {position}\n"
                    f"**Queue length:** {len(player.queue)}\n"
                    f"**Is playing:** {player.is_playing()}\n"
                    f"**Is paused:** {player.is_paused()}\n"
                )

        if not entries:
            return await ctx.send(embed = discord.Embed(
                color=self.bot.color,
                description="There are no active voice clients."
            ))

        await ViewMenuPages(ClassicPaginator(entries, per_page=1)).start(ctx)

    @music.command(name="voice-client", aliases=["voice_client", "voiceclient", "vc"])
    async def voiceclient(self, ctx: commands.Context, *, server: discord.Guild = commands.Option(None, description='The server to show voice client detais.')):
        """
        Displays information about a specific voice client.
        """

        guild = server or ctx.guild

        if not (player := self.bot.slate.players.get(guild.id)):
            return await ctx.send(embed = discord.Embed(
                color=self.bot.color,
                description=f"**{guild}** does not have a voice client."
            ))

        embed = discord.Embed(color=self.bot.color).set_thumbnail(url=guild.icon.url)

        embed.add_field(
            name="__Player info:__",
            value=f"**Voice channel:** {player.voice_channel} `{getattr(player.voice_channel, 'id', None)}`\n"
                  f"**Text channel:** {player.text_channel} `{getattr(player.text_channel, 'id', None)}`\n"
                  f"**Is playing:** {player.is_playing()}\n"
                  f"**Is paused:** {player.is_paused()}\n",
            inline=False
        )

        if player.current:
            embed.add_field(
                name="__Track info:__",
                value=f"**Track:** [{player.current.title}]({player.current.uri})\n"
                      f"**Author:** {player.current.author}\n"
                      f"**Position:** {humanize.naturaldelta(datetime.timedelta(seconds=player.position // 1000))} / {humanize.naturaldelta(datetime.timedelta(seconds=player.current.length // 1000)) if not player.current.is_stream() else 'LIVE'}\n"
                      f"**Source:** {player.current.source.value.title()}\n"
                      f"**Requester:** {player.current.requester} `{player.current.requester.id}`\n"
                      f"**Is stream:** {player.current.is_stream()}\n"
                      f"**Is seekable:** {player.current.is_seekable()}\n",
                inline=False
            )
            embed.set_image(
                url=player.current.thumbnail
            )
        else:
            embed.add_field(
                name="__Track info:__",
                value=f"**Track:** None\n",
                inline=False
            )

        embed.add_field(
            name=f"__Queue info:__",
            value=f"**Length:** {len(player.queue)}\n"
                  f"**Total time:** {humanize.naturaldelta(datetime.timedelta(seconds=sum(track.length for track in player.queue) // 1000))}\n" if not any([track.is_stream() for track in player.queue]) else "**Total time:** Unable to determine."
                  f"**Loop mode:** {player.queue.loop_mode.name.title()}\n",
            inline=False
        )

        if not player.queue.is_empty():

            embed.add_field(
                name="__Up next:__",
                value="\n".join(
                    [f"**{index + 1}.** [{entry.title}]({entry.uri}) by **{entry.author}**" for index, entry in enumerate(list(player.queue)[:5])]
                ) + (f"\n ... **5** of **{len(player.queue)}** total." if len(player.queue) > 3 else ""),
                inline=False
            )

        embed.add_field(
            name="__Listeners:__",
            value="\n".join(
                f"- {member} `{member.id}`" for member in player.listeners[:5]
            ) + (f"\n ... **5** of **{len(player.listeners)}** total." if len(player.listeners) > 5 else ""),
            inline=False
        )

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Music(bot))
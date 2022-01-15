import time
import asyncpg
import aiohttp
from discord.ext import commands

class DatabasePing:
    def __init__(self, ping: "Ping"):
        self._ping = ping

    async def postgresql(
        self, format: str = "seconds", spotify: bool = False
    ) -> int | float | None:
        try:
            start = time.perf_counter()

            for _ in range(5):
                try:
                    if spotify:
                        await self._ping.bot.spotify_pool.execute("SELECT 1")
                    else:
                        await self._ping.bot.pool.execute("SELECT 1")
                except asyncpg.exceptions._base.InterfaceError:
                    pass
                else:
                    break

            result = time.perf_counter() - start

            match format.lower():
                case "ms" | "milliseconds" | "millisecond":
                    return result * 1000
                case _:
                    return result
        except:
            return None

    async def redis(
        self, format: str = "seconds", spotify: bool = False
    ) -> int | float | None:
        try:
            start = time.perf_counter()

            if spotify:
                await self._ping.bot.spotify_redis.ping()
            else:
                await self._ping.bot.redis.ping()

            result = time.perf_counter() - start

            match format.lower():
                case "ms" | "milliseconds" | "millisecond":
                    return result * 1000
                case _:
                    return result
        except:
            return None


class APIPing:
    def __init__(self, ping: "Ping"):
        self._ping = ping

    async def openrobot(self, format: str = "seconds") -> int | float:
        # API ping test, fastest endpoint to test as it just returns a static JSON.
        url = "https://api.openrobot.xyz/_internal/available"

        start = time.perf_counter()
        async with self._ping.bot.session.get(url) as resp:
            end = time.perf_counter()

            match format.lower():
                case "ms" | "milliseconds" | "millisecond":
                    return (end - start) * 1000
                case _:
                    return end - start

    async def jeyy(self, format: str = "seconds") -> int | float:
        # API ping test, fastest endpoint to test as it just returns a static JSON AFAIK.
        url = "https://api.jeyy.xyz/isometric/codes"

        start = time.perf_counter()
        async with self._ping.bot.session.get(url) as resp:
            end = time.perf_counter()

            match format.lower():
                case "ms" | "milliseconds" | "millisecond":
                    return (end - start) * 1000
                case _:
                    return end - start

    async def repi(self, format: str = "seconds") -> int | float:
        # API ping test, fastest endpoint to test as it just returns a static HTML AFAIK.
        url = "https://repi.openrobot.xyz/"

        start = time.perf_counter()
        async with self._ping.bot.session.get(url) as resp:
            end = time.perf_counter()

            match format.lower():
                case "ms" | "milliseconds" | "millisecond":
                    return (end - start) * 1000
                case _:
                    return end - start

    async def dagpi(self, format: str = "seconds") -> int | float:
        url = "https://dagpi.xyz/"

        start = time.perf_counter()
        async with self._ping.bot.session.get(url) as resp:
            end = time.perf_counter()

            match format.lower():
                case "ms" | "milliseconds" | "millisecond":
                    return (end - start) * 1000
                case _:
                    return end - start

    async def waifu_im(self, format: str = "seconds") -> int | float:
        url = "https://waifu.im"

        start = time.perf_counter()
        async with self._ping.bot.session.get(url) as resp:
            end = time.perf_counter()

            match format.lower():
                case "ms" | "milliseconds" | "millisecond":
                    return (end - start) * 1000
                case _:
                    return end - start

class Ping:
    EMOJIS = {
        "postgresql": "<:postgresql:903286241066385458>",
        "redis": "<:redis:903286716058710117>",
        "bot": "\U0001f916",
        "discord": "<:BlueDiscord:842701102381269022>",
        "typing": "<a:typing:597589448607399949>",
        "openrobot-api": "<:OpenRobotLogo:901132699241168937>",
        "jeyy-api": "<:jeyyapi:922499477376475216>",
        "waifu-im": "<:waifuim:922500126969319476>",
        "dagpi": "<:dagpi:922499421772599346>"
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def database(self) -> DatabasePing:
        return DatabasePing(self)

    @property
    def db(self) -> DatabasePing:
        return self.database

    @property
    def api(self):
        return APIPing(self)

    def bot_latency(self, format: str = "seconds") -> int | float:
        latency = self.bot.latency

        match format.lower():
            case "ms" | "milliseconds" | "millisecond":
                return latency * 1000
            case _:
                return latency

    async def discord_web_ping(self, format: str = "seconds") -> int | float:
        url = "https://discordapp.com/"

        start = time.perf_counter()
        async with self.bot.session.get(url) as resp:
            end = time.perf_counter()

            match format.lower():
                case "ms" | "milliseconds" | "millisecond":
                    return (end - start) * 1000
                case _:
                    return end - start

    async def typing_latency(self, format: str = "seconds") -> int | float:
        chan = self.bot.get_channel(903282453735678035)  # Typing Channel ping test

        start = time.perf_counter()
        await chan.trigger_typing()
        end = time.perf_counter()

        match format.lower():
            case "ms" | "milliseconds" | "millisecond":
                return (end - start) * 1000
            case _:
                return end - start

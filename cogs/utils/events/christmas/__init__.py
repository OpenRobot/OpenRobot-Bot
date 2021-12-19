import random
import discord
import datetime
from io import BytesIO
from discord.ext import tasks
from cogs.utils.base import Bot


class ChristmasEvent:
    def __init__(self, bot):
        self.bot: Bot = bot

        self._old_activity = self.bot.activity
        self.activity = discord.Activity(
            name="Merry Christmas!! Ho Ho Ho!", type=discord.ActivityType.playing
        )
        self._old_description = self.bot.description
        self.description = f"\U0001f385 Merry Christmas from the OpenRobot Team!! Ho Ho Ho!\n\n{self._old_description}"

        self.start_time = datetime.datetime(
            year=2021,
            month=12,
            day=1,
            hour=0,
            minute=0,
            second=0,
            tzinfo=datetime.timezone.utc,
        )
        self.end_time = datetime.datetime(
            year=2021,
            month=12,
            day=31,
            hour=23,
            minute=59,
            second=59,
            tzinfo=datetime.timezone.utc,
        )

        self.bot.banner = self.get_banner(christmas=False, url=True)

        self._start_triggered = False

        self._color = self.bot._color

        self.colors = [
            # Hex Colors:
            discord.Colour(0x165B33),
            discord.Colour(0x146B3A),
            discord.Colour(0xF8B229),
            discord.Colour(0xEA4630),
            discord.Colour(0xBB2528),
            discord.Colour(0xD8D8D8),
            discord.Colour(0x5D9142),
            discord.Colour(0xFFD700),
            discord.Colour(0x0CA90C),
            discord.Colour(0xCE0D0D),
            discord.Colour(0x3225DE),
            discord.Colour(0x730710),
            discord.Colour(0x440506),
            discord.Colour(0xE03C48),
            discord.Colour(0x250404),
            discord.Colour(0xA91526),
            discord.Colour(0x6B060C),
            discord.Colour(0x470406),
            discord.Colour(0xEAB497),
            discord.Colour(0xA41321),
            discord.Colour(0xE2333F),
            discord.Colour(0xD6A55B),
            discord.Colour(0x882B22),
            discord.Colour(0xDDD7CE),
            discord.Colour(0x322419),
            discord.Colour(0x25372A),
            discord.Colour(0x710007),
            discord.Colour(0xDB010F),
            discord.Colour(0xFFE2AC),
            discord.Colour(0x8E742C),
            discord.Colour(0x90361B),
            discord.Colour(0x942C36),
            discord.Colour(0xBB7671),
            discord.Colour(0xF0EFF1),
            discord.Colour(0xBB9898),
            discord.Colour(0x3B1D1F),
            discord.Colour(0xA18D51),
            discord.Colour(0x1C3027),
            discord.Colour(0xBCBFB0),
            discord.Colour(0x797967),
            discord.Colour(0x3B5D3D),
            discord.Colour(0x944C07),
            discord.Colour(0xC79544),
            discord.Colour(0x121C0E),
            discord.Colour(0x685F41),
            discord.Colour(0x42613B),
            discord.Colour(0x071942),
            discord.Colour(0x3D79D2),
            discord.Colour(0xBDC5B2),
            discord.Colour(0x244372),
            discord.Colour(0x121F24),
            discord.Colour(0x9C530D),
            discord.Colour(0x0C1B3C),
            discord.Colour(0x2D527D),
            discord.Colour(0xD2B494),
            discord.Colour(0x2E211D),
            discord.Colour(0x3E0F1B),
            discord.Colour(0x913C48),
            discord.Colour(0xD9CECE),
            discord.Colour(0xAF7D7E),
            discord.Colour(0xC19E9F),
            discord.Colour(0x864839),
            discord.Colour(0x946A4A),
            discord.Colour(0x3D4B28),
            discord.Colour(0xD7C1BD),
            discord.Colour(0xA4776D),
            discord.Colour(0x523711),
            discord.Colour(0xBFA477),
            discord.Colour(0x705A3D),
            discord.Colour(0xCACEBC),
            discord.Colour(0x352F29),
            discord.Colour(0xA0724B),
            discord.Colour(0x75513C),
            discord.Colour(0xE5E0D6),
            discord.Colour(0xA78E70),
            discord.Colour(0x4B3A2F),
            discord.Colour(0xD3BE8C),
            discord.Colour(0xB79754),
            discord.Colour(0xE4E4E2),
            discord.Colour(0x403427),
            discord.Colour(0x806137),
            discord.Colour(0xB48262),
            discord.Colour(0xF0E9E2),
            discord.Colour(0x5A5047),
            discord.Colour(0x9D9189),
            discord.Colour(0x72736E),
            discord.Colour(0x5E5142),
            discord.Colour(0xD9DBE4),
            discord.Colour(0xB8B9BC),
            discord.Colour(0x323231),
            discord.Colour(0x75787D),
            discord.Colour(0x3A383F),
            discord.Colour(0x645B60),
            discord.Colour(0xD2D2D6),
            discord.Colour(0x7D7C84),
            discord.Colour(0x9D9EA5),
            # Built-in Colors:
            discord.Colour.yellow(),
            discord.Colour.gold(),
            discord.Colour.dark_gold(),
            discord.Colour.blue(),
            discord.Colour.dark_blue(),
            discord.Colour.red(),
            discord.Colour.dark_red(),
            discord.Colour.green(),
            discord.Colour.red(),
        ]

    def get_avatar(self, *, christmas=True, url=False) -> str | bytes:
        if url:
            if christmas:
                return "https://cdn.openrobot.xyz/Logos/Christmas.png"
            else:
                return "https://cdn.openrobot.xyz/Logos/Logo.png"
        else:
            if christmas:
                with open("./Logos/Christmas.png", "rb") as f:
                    return f.read()
            else:
                with open("./Logos/Logo.png", "rb") as f:
                    return f.read()

    def get_banner(self, *, christmas=True, url=False) -> str | bytes:
        if url:
            if christmas:
                return "https://cdn.openrobot.xyz/Logos/Christmas-Banner.png"
            else:
                return "https://cdn.openrobot.xyz/Logos/Banner.png"
        else:
            if christmas:
                with open("./Logos/Christmas-Banner.png", "rb") as f:
                    return f.read()
            else:
                with open("./Logos/Banner.png", "rb") as f:
                    return f.read()

    def start(self):
        self._start_task.start()
        self._end_task.start()

    @tasks.loop(seconds=1)
    async def _start_task(self):
        utcnow = discord.utils.utcnow()

        if self.start_time <= utcnow <= self.end_time:
            self._start_triggered = True
            await self._start_event()
            self._end_task.cancel()

    @_start_task.before_loop
    async def _start_task_before_loop(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=1)
    async def _end_task(self):
        utcnow = discord.utils.utcnow()

        if utcnow > self.end_time and self._start_triggered:
            await self._end_event()
            self._end_task.cancel()

    @_start_task.before_loop
    async def _start_task_before_loop(self):
        await self.bot.wait_until_ready()

    def color(self):
        return random.choice(self.colors)

    async def _start_event(self):
        await self.bot.change_presence(activity=self.activity)
        await self.bot.user.edit(avatar=self.get_avatar())
        self.bot.banner = self.get_banner(christmas=True, url=True)
        self.bot.description = self.description

        self.bot._color = self.color

    async def _end_event(self):
        await self.bot.change_presence(activity=self._old_activity)
        await self.bot.user.edit(avatar=self.get_avatar(christmas=False))
        self.bot.banner = self.get_banner(christmas=False, url=True)
        self.bot.description = self._old_description

        self.bot._color = self._color

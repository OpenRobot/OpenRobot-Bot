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
        self.description = f"Merry Christmas from the OpenRobot Team!! Ho Ho Ho!\n\n{self._old_description}"

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

        self._start_triggered = False

    def get_avatar(self, *, christmas=True, url=False) -> bytes:
        if url:
            if christmas:
                return "https://cdn.openrobot.xyz/Logos/Christmas.png"
            else:
                return "https://cdn.openrobot.xyz/Logos/Logo.png"
        else:
            if christmas:
                with open("./Logos/Christmas.png") as f:
                    return f.read()
            else:
                with open("./Logos/Logo.png") as f:
                    return f.read()

    def get_banner(self, *, christmas=True, url=False) -> bytes:
        if url:
            if christmas:
                return "https://cdn.openrobot.xyz/Logos/Christmas-Banner.png"
            else:
                return "https://cdn.openrobot.xyz/Logos/Banner.png"
        else:
            if christmas:
                with open("./Logos/Christmas-Banner.png") as f:
                    return f.read()
            else:
                with open("./Logos/Banner.png") as f:
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

    async def _start_event(self):
        await self.bot.change_presence(activity=self.activity)
        await self.bot.user.edit(avatar=self.get_avatar())
        self.bot.help_command.banner = self.get_banner(christmas=True, url=True)
        self.bot.description = self.description

    async def _end_event(self):
        await self.bot.change_presence(activity=self._old_activity)
        await self.bot.user.edit(avatar=self.get_avatar(christmas=False))
        self.bot.help_command.banner = self.get_banner(christmas=False, url=True)
        self.bot.description = self._old_description

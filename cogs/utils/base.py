import discord
import config
import asyncpg
import mystbin
import boto3
import aioredis
import aiospotify
import aiohttp
import psutil

from .ping import Ping
from .error import Error
from .driver import Driver
from .context import Context
from .rethinkdb import RethinkDB

from discord.ext import commands, ipc
from openrobot.api_wrapper import AsyncClient
from openrobot import discord_activities as discord_activity


class Bot(commands.Bot):
    def __init__(self, *args, **options):
        super().__init__(*args, **options)

        self.running_commands = {}

        # Some other attrs that can be used
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.banner: str = "https://cdn.openrobot.xyz/Logos/Banner.png"
        self.spotify: aiospotify.Client = aiospotify.Client(
            **config.AIOSPOTIFY_CRIDENTIALS, session=self.session
        )
        self.__color = discord.Colour(0x38B6FF)
        self.config = config
        self.mystbin: mystbin.Client = mystbin.Client(session=self.session)
        self.api: AsyncClient = AsyncClient(
            config.API_TOKEN, ignore_warning=True, session=self.session
        )
        self.ping: Ping = Ping(self)
        self.error: Error = Error(self)
        self.discord_activity: discord_activity.DiscordActivity = (
            discord_activity.DiscordActivity(config.TOKEN)
        )
        self.driver = Driver
        self.cdn = boto3.client("s3", **config.AWS_CRIDENTIALS)

        self.process = psutil.Process()

        self.ipc = ipc.Server(
            self, secret_key=config.IPC_SECRET_KEY, port=8766, multicast_port=22000
        )

        # Uptime and stuff:
        self.start_time = discord.utils.utcnow()
        self.sent_messages = 0
        self.edited_messages = 0
        self.deleted_messages = 0
        self.commands_invoked = 0

        # Databases
        self.pool: asyncpg.Pool = None
        self.redis: aioredis.Redis = None
        self.spotify_pool: asyncpg.Pool = None
        self.spotify_redis: aioredis.Redis = None
        self.tb_pool: asyncpg.Pool = None
        self.rethinkdb: RethinkDB = RethinkDB()

    async def get_context(
        self, message: discord.Message, *, cls: Context = Context
    ) -> Context:
        return await super().get_context(message, cls=cls)

    async def __invoke(self, ctx, **kwargs) -> None:
        if ctx.command is not None:
            self.dispatch("command", ctx)
            run_in_task = kwargs.pop("task", True)
            try:
                if await self.can_run(ctx, call_once=True):
                    if run_in_task:
                        task = await self.loop.create_task(ctx.command.invoke(ctx))
                        self.running_commands[ctx.message] = {"ctx": ctx, "task": task}
                    else:
                        await ctx.command.invoke(ctx)
                else:
                    raise commands.CheckFailure(
                        "The global check once functions failed."
                    )
            except commands.CommandError as exc:
                await ctx.command.dispatch_error(ctx, exc)
            else:
                self.dispatch("command_completion", ctx)
        elif ctx.invoked_with:
            exc = commands.CommandNotFound(
                'Command "{}" is not found'.format(ctx.invoked_with)
            )
            self.dispatch("command_error", ctx, exc)

    async def on_ipc_ready(self):
        """Called upon the IPC Server being ready"""
        print("IPC is ready.")

    async def on_ipc_error(self, endpoint, error):
        """Called upon an error being raised within an IPC route"""
        print(endpoint, "raised", error)

    def _color(self):
        return self.__color

    @property
    def color(self):
        return self._color()

    @color.setter
    def color(self, color: discord.Colour):
        self.__color = color

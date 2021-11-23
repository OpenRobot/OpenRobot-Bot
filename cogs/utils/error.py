import os
from traceback import format_exception
import prettify_exceptions

class OpenRobotFormatter(prettify_exceptions.DefaultFormatter):
    def __init__(self, **kwargs):
        kwargs['theme'] = {'_ansi_enabled': True if (not os.environ.get('OPENROBOT-FORMATTER_NO_COLOR', 'True').lower() == 'true') or (not kwargs.pop('no_color', True)) else False}

        super().__init__(**kwargs)

    def format_exception(self, exc, *args, **kwargs):
        etype = type(exc)
        trace = exc.__traceback__

        return super().format_exception(etype, exc, trace, *args, **kwargs)

class ErrorResult:
    def __init__(self, **kwargs):
        self.user_id: int = kwargs.get('user_id')
        self.error_id: str = kwargs.get('error_id')
        self.guild_id: int = kwargs.get('guild_id')
        self.channel_id: int = kwargs.get('channel_id')
        self.message_id: int = kwargs.get('message_id')
        self.message_jump_url: str = kwargs.get('message_jump_url')
        self.traceback_pretty: str = kwargs.get('traceback_pretty')
        self.traceback_original: str = kwargs.get('traceback_original')

class Error:
    def __init__(self, bot):
        self.bot = bot

    async def initiate(self):
        await self.bot.tb_pool.execute("""
        CREATE TABLE IF NOT EXISTS tracebacks(
            user_id BIGINT,
            error_id TEXT,
            guild_id BIGINT DEFAULT NULL,
            channel_id BIGINT,
            message_id BIGINT,
            message_jump_url TEXT,
            traceback_pretty TEXT,
            traceback_original TEXT
        );
        """)

    async def create(self, **kwargs) -> ErrorResult:
        user_id = kwargs.pop('user_id')

        error_id = kwargs.pop('error_id')

        guild_id = kwargs.pop('guild_id', None)

        channel_id = kwargs.pop('channel_id')
        channel_id = channel_id if channel_id != user_id else None

        message_id = kwargs.pop('message_id')

        message_jump_url = kwargs.pop('message_jump_url')

        pretty_tb = kwargs.pop('pretty_traceback')

        original_tb = kwargs.pop('original_traceback')

        return ErrorResult(**dict(await self.bot.tb_pool.fetchrow(
            "INSERT INTO tracebacks VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *", 

            user_id,
            error_id,
            guild_id,
            channel_id,
            message_id,
            message_jump_url,
            pretty_tb,
            original_tb,
        )))

    async def get(self, **kwargs) -> list[ErrorResult] | ErrorResult:
        if not kwargs:
            return [ErrorResult(dict(x)) for x in await self.bot.tb_pool.fetch('SELECT * FROM tracebacks')]

        s = 'AND'
        c = 1

        for key in kwargs.keys():
            s += f'{key}=${c} AND '
            c += 1

        s = s[:-5]

        db = await self.bot.tb_pool.fetch(f'SELECT * FROM traceback WHERE {s}', *[val for val in kwargs.values()])

        if len(db) == 0:
            return []
        elif len(db) == 1:
            return ErrorResult(**dict(db[0]))
        else:
            return [ErrorResult(**dict(x)) for x in db]
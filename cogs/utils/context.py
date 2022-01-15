from discord.ext import commands


class DataBase:
    def __init__(self, psql=None, redis=None):
        self.psql = psql
        self.redis = redis


class Context(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.db = DataBase(self.bot.pool, self.bot.redis)
        self.color = self.bot.color

        self.running = None

        self.debug = kwargs.get("debug", False)
        self.beta = kwargs.get("beta", False)

    async def send(self, content: str = None, **kwargs):
        if not self.interaction:
            if "mention_author" not in kwargs:
                kwargs["mention_author"] = False

            kwargs["reference"] = self.message

        return await super().send(content, **kwargs)

from discord.ext import commands

class DataBase:
    def __init__(self, psql = None, redis = None):
        self.psql = psql
        self.redis = redis

class Context(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.db = DataBase(self.bot.pool, self.bot.redis)
        self.color = self.bot.color

        self.running = None

    async def send(self, content: str = None, **kwargs):
        if not 'mention_author' in kwargs:
            kwargs['mention_author'] = False

        return await super().reply(content, **kwargs)
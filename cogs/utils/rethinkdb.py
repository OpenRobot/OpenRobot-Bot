from rethinkdb import RethinkDB as BaseRethinkDB


class RethinkDB(BaseRethinkDB):
    def __init__(self):
        super().__init__()

        self.set_loop_type("asyncio")


r = RethinkDB()

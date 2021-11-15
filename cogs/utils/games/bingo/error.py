class BingoError(Exception):
    """
    Base exception for bingo.
    """

    def __init__(self, cls, *args, **kwargs):
        self.bingo_cls = cls

        self.args = args
        self.kwargs = kwargs

        super().__init__(*args, **kwargs)
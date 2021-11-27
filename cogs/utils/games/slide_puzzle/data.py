class Location:
    def __init__(self, x: int = 0, y: int = 0):
        self.x: int = int(x)
        self.y: int = int(y)


class SwitchAttempts:
    def __init__(self, total: int, left: int = None):
        self.total = int(total)
        self.left = int(left or total)

class Timer:
    def __init__(self):
        self._start = None
        self._end = None

    def start(self):
        self._start = time.perf_counter()

    def stop(self):
        self._end = time.perf_counter()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __int__(self):
        return round(self.time)

    def __float__(self):
        return self.time

    def __str__(self):
        return str(self.time)

    def __repr__(self):
        return f"<Timer time={self.time}>"

    @property
    def time(self):
        if self._end is None:
            raise ValueError("Timer has not been ended.")
        return self._end - self._start


class AsyncTimer(Timer):  # eh, why not lmao
    def __aenter__(self):
        return self.__enter__()

    def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)

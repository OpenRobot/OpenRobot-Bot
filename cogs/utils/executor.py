import functools
import asyncio


def executor(loop: asyncio.AbstractEventLoop = None, executor=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal loop, executor

            partial = functools.partial(func, *args, **kwargs)
            loop = loop or asyncio.get_event_loop()
            return loop.run_in_executor(executor, partial)

        return wrapper

    return decorator

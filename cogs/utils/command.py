import typing
from discord.ext import commands


class _Command(commands.Command):
    def __init__(self, *args, **kwargs):
        self.kwargs: dict[str, typing.Any] = kwargs

        super().__init__(*args, **kwargs)

        self.example: str = kwargs.get("example", self._get_original_example())

    def _get_original_example(self):
        s = self.qualified_name

        if usage := self.usage:
            s += f" {usage}"

        return s


class _Group(commands.Group, _Command):
    pass


class Command(commands.HybridCommand, _Command):
    pass


class Group(commands.HybridGroup, _Group):
    pass


def command(*args, **kwargs):
    cls = kwargs.pop("cls", Command)
    return commands.command(*args, **kwargs, cls=cls)


def group(*args, **kwargs):
    cls = kwargs.pop("cls", Group)
    return commands.group(*args, **kwargs, cls=cls)

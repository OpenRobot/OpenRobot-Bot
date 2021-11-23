import argparse
import shlex
from discord.ext import commands

class FlagConverter(commands.FlagConverter, prefix='--', delimiter=' ', case_insensitive=True):
    pass

class _Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)

class LegacyFlagItems:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

class LegacyFlagConverter:
    def __init__(self, l: list[LegacyFlagItems]):
        self.data = l
        self.parser = _Arguments(add_help=False, allow_abbrev=False)

        for i in l:
            self.parser.add_argument(*i.args, **i.kwargs)

    def convert(self, argument: str):
        if argument:
            return self.parser.parse_args(shlex.split(argument))
        else:
            return self.parser.parse_args([])
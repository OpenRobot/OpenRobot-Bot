from discord.ext import commands


class CheckFailure(commands.CheckFailure):
    """Base Check Failure Exception"""


class APIHasApplied(CheckFailure):
    """Raised when an a user has apply for the API"""


class APIHasNotApplied(CheckFailure):
    """Raised when an a user has not apply for the API"""

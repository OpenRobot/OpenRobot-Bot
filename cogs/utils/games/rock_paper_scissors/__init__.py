import discord

from .enums import *
from .error import *

class RockPaperScissors:
    def __init__(self, player_one: discord.Member, player_two: discord.Member):
        self.player_one = player_one
        self.player_two = player_two
        
        self.player_one_option = None
        self.player_two_option = None

    def get_winner(self):
        if not self.player_one_option or not self.player_two_option:
            raise CannotGetWinner('Player options are not complete.')

        if self.player_one_option == self.player_two_option:
            return Winner.TIE
        elif self.player_one_option == Option.PAPER and \
            self.player_two_option == Option.ROCK:
            return Winner.PlayerOne
        elif self.player_one_option == Option.SCISSORS and \
            self.player_two_option == Option.PAPER:
            return Winner.PlayerOne
        elif self.player_one_option == Option.ROCK and \
            self.player_two_option == Option.SCISSORS:
            return Winner.PlayerOne
        else: # Nothing matches, so automatically Player Two wins.
            return Winner.PlayerTwo
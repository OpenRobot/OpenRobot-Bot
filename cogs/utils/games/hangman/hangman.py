import random

from cogs.utils.games.hangman import words, error

from .error import *
from .words import *


class Hangman:
    def __init__(self, ctx, category: str = None):
        self.ctx = ctx
        self.tries = 6

        self.word: tuple[str | None, str | None] = self.generate_word(category)

        self.guessed_words = []
        self.word_guess = ""

        for letter in self.word[0]:
            if letter == " ":
                self.word_guess += "  "
            else:
                self.word_guess += "_ "

        self.word_guess = self.word_guess.strip()

    def generate_word(self, category: str = None, *, set_as_word: bool = True):
        if category == None:
            l = (
                FRUITS
                + FOOD
                + DRINKS
                + COLORS
                + ANIMALS
                + COUNTRIES
                + VEHICLES
                + LANGUAGES
                + BUILDINGS
            )
        else:
            try:
                l = getattr(words, category.upper())
            except Exception as e:
                raise InvaildCategory(category) from e

        choice = random.choice(l)

        category = (
            category.upper() or "FRUITS"
            if choice in FRUITS
            else "FOOD"
            if choice in FOOD
            else "DRINKS"
            if choice in DRINKS
            else "COLORS"
            if choice in COLORS
            else "ANIMALS"
            if choice in ANIMALS
            else "COUNTRY"
            if choice in COUNTRIES
            else "VEHICLES"
            if choice in VEHICLES
            else "LANGUAGES"
            if choice in LANGUAGES
            else "BUILDINGS"
            if choice in BUILDINGS
            else None
        )

        if set_as_word:
            self.word = choice, category

        return choice, category

    def guess(self, letter: str):
        if len(letter) != 1:
            raise InvalidLetter("You must guess a single letter.")

        if not letter.replace(" ", "").strip():
            raise InvalidLetter("You cannot guess a space.")

        if letter in self.guessed_words:
            raise AlreadyGuessed(letter)

        self.guessed_words.append(letter)

        if letter in self.word[0]:
            # The letter might be in multiple places on the word
            # Such as beer, has 2 e's.
            # .index wont cover this, so we neeed to make our own implementation using enumerate.

            indexes = [
                index for index, value in enumerate(self.word[0]) if value == letter
            ]

            if indexes:
                for index in indexes:
                    self.word_guess = (
                        self.word_guess[:index*2] + letter + self.word_guess[index*2 + 1 :] # *2 cause the word_guess involves spaces in each "_".
                    )

                return True
            else:
                self.tries -= 1

                return False
        else:
            self.tries -= 1

            return False

    @property
    def win(self):
        return ' '.join([x.replace(' ', '') for x in self.word_guess.split(' ')]) == self.word[0] and self.tries > 0

    @property
    def lose(self):
        return self.tries <= 0

    def draw(self):  # thanks copilot
        match self.tries:
            case 0:
                return """
  _________
  |       |
  |       o
  |      /|\\
  |       |
  |      / \\
  |
  |
  |
  |   
__|__"""
            case 1:
                return """
  _________
  |       |
  |       o
  |      /|\\
  |       |
  |      /
  |
  |
  |
  |   
__|__"""

            case 2:
                return """
  _________
  |       |
  |       o
  |      /|\\
  |       |
  |
  |
  |
  |
  |   
__|__"""

            case 3:
                return """
  _________
  |       |
  |       o
  |      /|
  |       |
  |
  |
  |
  |
  |   
__|__"""

            case 4:
                return """
  _________
  |       |
  |       o
  |       |
  |       |
  |
  |
  |
  |
  |   
__|__"""

            case 5:
                return """
  _________
  |       |
  |       o
  |
  |
  |
  |
  |
  |
  |   
__|__"""

            case 6:
                return """
  _________
  |       |
  |
  |
  |
  |
  |
  |
  |
  |   
__|__"""

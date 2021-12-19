class HangmanExcpetion(Exception):
    pass


class InvaildCategory(HangmanExcpetion):
    def __init__(self, category):
        self.category = category
        super().__init__("Category %s does not exist" % category)


class AlreadyGuessed(HangmanExcpetion):
    def __init__(self, letter):
        self.letter = letter
        super().__init__("Letter %s has already been guessed" % letter)


class InvalidLetter(HangmanExcpetion):
    pass

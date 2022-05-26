import io

import discord
from discord import file

class CustomFile(file.File):
    def __init__(self, fp, *args, **kwargs):
        if isinstance(fp, discord.File):
            fp = fp.fp
        elif isinstance(fp, bytes):
            fp = io.BytesIO(fp)

        super().__init__(fp, *args, **kwargs)

file.File = CustomFile
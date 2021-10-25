import discord
from discord.ext import commands
from cogs.utils import Cog, games

class Fun(Cog, emoji=""): # TODO: Put fun emoji
    @commands.command('slide-puzzle', aliases=['slidepuzzle', 'slide_puzzle'])
    async def slide_puzzle(self, ctx: commands.Context, *, size: str = None):
        """
        Slide puzzle. You need to order the numbers to make it from the smallest to the greatest.

        Size can be from `2x2` to `5x5`.
        """

        size = size or '4x4'

        try:
            size_x, size_y = size.split('x')
        except:
            return await ctx.send('Invalid size')

        size_x = int(size_x.strip(' '))
        size_y = int(size_y.strip(' '))

        if (not 1 < size_x < 6) or (not 1 < size_y < 6):
            return await ctx.send('Invalid size')
        
        slide_puzzle = games.SlidePuzzle(x=size_x, y=size_y)

        class HelpButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.green, label='How to play?', emoji='<:rooThink:596576798351949847>', row=4)

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message(slide_puzzle.help, ephemeral=True)

        class StopButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.danger, label='Stop', emoji='<:openrobot_stop_button:899878227969974322>', row=4)

            async def callback(self, interaction: discord.Interaction):
                slide_puzzle.end()

                for child in self.view.children:
                    child.disabled = True

                await interaction.message.edit(view=self.view, content=f'You gave up and ended the game. You played for `{round(slide_puzzle.duration, 2)} seconds` and wasted `{slide_puzzle.tries} tries`.')
                self.view.stop()

        class Button(discord.ui.Button):
            def __init__(self, number, **kwargs):
                if number is None:
                    super().__init__(style=discord.ButtonStyle.grey, disabled=True, label='\u200b', **kwargs)
                else:
                    super().__init__(style=discord.ButtonStyle.blurple, label=number, **kwargs)

                self.number = number

            async def callback(self, interaction: discord.Interaction):
                try:
                    slide_puzzle.move(self.number)
                except games.slide_puzzle.CannotBeMoved:
                    await interaction.response.send_message(f'You can\'t move number {self.number}.')

                self.view.clear_items()

                row = 0

                c = 0

                for y in slide_puzzle.position:
                    for x in y:
                        print(c)
                        c += 1

                for y in slide_puzzle.position:
                    for x in y:
                        self.view.add_item(self.__class__(x, row=row))

                    row += 1

                self.view.add_item(StopButton())
                self.view.add_item(HelpButton())

                if slide_puzzle.win():
                    for child in self.view.children:
                        child.disabled = True

                    await interaction.message.edit(view=self.view, content=f'You won the game! You played for `{round(slide_puzzle.duration, 2)} seconds` and wasted `{slide_puzzle.tries} tries`.')

                await interaction.message.edit(view=self.view)

        class View(discord.ui.View):
            def __init__(self, ctx, *, timeout=180):
                super().__init__(timeout=timeout)

                self.ctx = ctx
                self.message = None

                row = 0

                for y in slide_puzzle.position:
                    for x in y:
                        self.add_item(Button(x, row=row))

                    row += 1

                self.add_item(StopButton())
                self.add_item(HelpButton())
            
            async def on_timeout(self) -> None:
                for child in self.children:
                    child.disabled = True

                await self.message.edit(view=self, content='Game ended cause you didn\'t respond.')

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user != ctx.author:
                    await interaction.response.send_message(f'Only {ctx.author.mention} can play this Slide Puzzle. To play your own game of Slide Puzzle, invoke the `slide-puzzle` command.', ephemeral=True)
                    return False
                else:
                    return True

        view = View(ctx)

        view.message = await ctx.send(view=view, content='\u200b')

        slide_puzzle.start()

def setup(bot):
    bot.add_cog(Fun(bot))
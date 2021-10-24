import discord
from discord.ext import commands
from cogs.utils import Cog, games

class Fun(Cog, emoji=""): # TODO: Put fun emoji
    @commands.command('slide-puzzle', aliases=['slidepuzzle', 'slide_puzzle'])
    async def slide_puzzle(self, ctx: commands.Context):
        slide_puzzle = games.SlidePuzzle()

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

                await interaction.message.edit(view=self.view, content=f'You gave up and ended the game. You played for `{round(slide_puzzle.duration*1000, 2)} seconds` and wasted `{slide_puzzle.tries} tries`.')
                self.view.stop()

        class Button(discord.ui.Button):
            def __init__(self, number, **kwargs):
                if number is None:
                    super().__init__(style=discord.ButtonStyle.grey, disabled=True, label='\u200b', **kwargs)
                else:
                    super().__init__(style=discord.ButtonStyle.blurple, label=number, **kwargs)

                self.number = number

            async def callback(self, interaction: discord.Interaction):
                slide_puzzle.move(self.number)

                for child in self.view.children:
                    self.view.remove_item(child)

                row = 0
                c = 0

                for y in slide_puzzle.position:
                    for x in y:
                        print(c)
                        c += 1
                        self.view.add_item(self.__class__(x))

                    row += 1

                self.view.add_item(StopButton())
                self.view.add_item(HelpButton())

                if slide_puzzle.win():
                    for child in self.view.children:
                        child.disabled = True

                    await interaction.message.edit(view=self.view, content=f'You won the game! You played for `{round(slide_puzzle.duration*1000, 2)} seconds` and wasted `{slide_puzzle.tries} tries`.')

        class View(discord.ui.View):
            def __init__(self, ctx, *, timeout=90):
                super().__init__(timeout=timeout)

                self.ctx = ctx
                self.message = None

                for y in slide_puzzle.position:
                    for x in y:
                        self.add_item(Button(x))

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

def setup(bot):
    bot.add_cog(Fun(bot))
import discord
from discord.ext import commands
from cogs.utils import Cog, games

class Fun(Cog, emoji=""): # TODO: Put fun emoji
    @commands.command('slide-puzzle', aliases=['slidepuzzle', 'slide_puzzle'])
    async def slide_puzzle(self, ctx: commands.Context, *, size: str = None):
        """
        Slide puzzle. You need to order the numbers to make it from the smallest to the greatest.

        Size can be from `2x2` to `5x4`.
        """

        size = size or '3x3'

        try:
            size_x, size_y = size.split('x')

            size_x = int(size_x.strip(' '))
            size_y = int(size_y.strip(' '))

            if (not 1 < size_x < 6) or (not 1 < size_y < 5):
                return await ctx.send('Invalid size')
        except:
            return await ctx.send('Invalid size')
        
        slide_puzzle = games.SlidePuzzle(x=size_x, y=size_y)

        class HelpButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.green, label='How to play?', emoji='<:rooThink:596576798351949847>', row=4)

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message(slide_puzzle.help, ephemeral=True)

        class SwitchButton(discord.ui.Button):
            def __init__(self, **kwargs):
                if slide_puzzle.switch_attempts.left == 0 and 'disabled' not in kwargs:
                    kwargs['disabled'] = True

                super().__init__(style=discord.ButtonStyle.green, label=f'Need help? Switch Numbers', emoji='<:rooBulli:744346131324076072>', row=4, **kwargs)

            async def callback(self, interaction: discord.Interaction):
                def check(m):
                    try:
                        return m.author == interaction.user and m.channel == self.view.ctx.channel and m.content.split('-') and m.content.split('-')[0].isdigit() and m.content.split('-')[1].isdigit()
                    except:
                        return False

                await interaction.response.send_message(f'Please send what numbers you want to switch. Send a message with the format `num1-num2`\n\nNote that you only have {slide_puzzle.switch_attempts.left} tries left to switch, including this one.\nTo cancel, just type something random \U0001f642', ephemeral=True)

                try:
                    msg = await self.view.ctx.bot.wait_for('message', check=check, timeout=60)
                except:
                    return await interaction.followup.send('Took to long to respond where to switch.', ephemeral=True) # btw proguy can u co-author me for the commit u will do whenever after this cuz i helped :> ok
                
                try:
                    num1 = int(msg.content.split('-')[0])
                    num2 = int(msg.content.split('-')[1])
                except:
                    return await interaction.followup.send('Not a valid integer.', ephemeral=True)

                if (not 0 < num1 <= (slide_puzzle.x*slide_puzzle.y)-1) or (not 0 < num2 <= (slide_puzzle.x*slide_puzzle.y)-1):
                    return await interaction.followup.send('Not a valid integer in the puzzle.', ephemeral=True)
                
                slide_puzzle.switch(num1, num2)

                self.view.refresh_buttons()

                if slide_puzzle.switch_attempts.left == 0:
                    self.disabled = True

                await interaction.message.edit(view=self.view)

                await interaction.followup.send(f'Switched number {num1} with {num2}. You now have {slide_puzzle.switch_attempts.left} tries to switch.', ephemeral=True)

        class StopButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.danger, label='Stop', emoji='<:openrobot_stop_button:899878227969974322>', row=4)

            async def callback(self, interaction: discord.Interaction):
                slide_puzzle.end()

                for child in self.view.children:
                    child.disabled = True

                await interaction.message.edit(view=self.view, content=f'You gave up and ended the game. You played for `{round(slide_puzzle.duration, 2)} seconds` and tried `{slide_puzzle.tries} times`.')
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

                self.view.refresh_buttons()

                if slide_puzzle.win():
                    for child in self.view.children:
                        child.disabled = True

                    await interaction.message.edit(view=self.view, content=f'You won the game! You played for `{round(slide_puzzle.duration, 2)} seconds` and took `{slide_puzzle.tries} tries`.')
                    self.view.stop()
                    return

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
                self.add_item(SwitchButton())

            def refresh_buttons(self):
                self.clear_items()

                row = 0

                for y in slide_puzzle.position:
                    for x in y:
                        self.add_item(Button(x, row=row))

                    row += 1

                self.view.add_item(StopButton())
                self.view.add_item(HelpButton())
                self.add_item(SwitchButton())
            
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

            async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
                if isinstance(error, games.slide_puzzle.CannotBeMoved):
                    return await interaction.response.send_message(f'You can\'t move number {item.number}.', ephemeral=True)
                elif isinstance(error, games.slide_puzzle.SwitchAttemptExhausted):
                    item.disabed = True
                    await interaction.message.edit(view=self)

                    return await interaction.response.send_message('There are no available attempts for you to switch.')

                raise error

        view = View(ctx)

        view.message = await ctx.send(view=view, content='\u200b')

        slide_puzzle.start()

    #@commands.command('rock-paper-scissors', aliases=['rock-paper-scissor', 'rps', 'rock_paper_scissors', 'rock_paper_scissor'])
    async def rock_paper_scissors(self, ctx: commands.Context, opponent: discord.Member):
        rps = games.RockPaperScissors()

        class View(discord.ui.View):
            def __init__(self, *, timeout: float = 60):
                super().__init__(timeout=timeout)

                self.add_item(discord.ui.Button(emoji=(games.rock_paper_scissors.Emoji.ROCK), label='Rock', style=discord.ButtonStyle.primary))
                self.add_item(discord.ui.Button(emoji=(games.rock_paper_scissors.Emoji.PAPER), label='Paper', style=discord.ButtonStyle.primary))
                self.add_item(discord.ui.Button(emoji=(games.rock_paper_scissors.Emoji.SCISSORS), label='Scissors', style=discord.ButtonStyle.primary))

            def disable_all(self):
                for child in self.children:
                    child.disabled = True
    
def setup(bot):
    bot.add_cog(Fun(bot))
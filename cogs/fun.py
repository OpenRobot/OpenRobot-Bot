import discord
import asyncio
import random
from discord.ext import commands
from discord.message import DeletedReferencedMessage
from cogs.utils import Cog, games


class Fun(Cog, emoji=""):  # TODO: Put fun emoji
    bingo_instances: list[games.Bingo] = []

    @commands.command("slide-puzzle", aliases=["slidepuzzle", "slide_puzzle"])
    async def slide_puzzle(self, ctx: commands.Context, *, size: str = None):
        """
        Slide puzzle. You need to order the numbers to make it from the smallest to the greatest.

        Size can be from `2x2` to `5x4`.
        """

        size = size or "3x3"

        try:
            size_x, size_y = size.split("x")

            size_x = int(size_x.strip(" "))
            size_y = int(size_y.strip(" "))

            if (not 1 < size_x < 6) or (not 1 < size_y < 5):
                return await ctx.send("Invalid size")
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("Invalid size")

        slide_puzzle = games.SlidePuzzle(x=size_x, y=size_y)

        class HelpButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.green,
                    label="How to play?",
                    emoji="<:rooThink:596576798351949847>",
                    row=4,
                )

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    slide_puzzle.help, ephemeral=True
                )

        class SwitchButton(discord.ui.Button):
            def __init__(self, **kwargs):
                if slide_puzzle.switch_attempts.left == 0 and "disabled" not in kwargs:
                    kwargs["disabled"] = True

                super().__init__(
                    style=discord.ButtonStyle.green,
                    label=f"Need help? Switch Numbers",
                    emoji="<:rooBulli:744346131324076072>",
                    row=4,
                    **kwargs,
                )

            async def callback(self, interaction: discord.Interaction):
                def check(m):
                    try:
                        return (
                            m.author == interaction.user
                            and m.channel == self.view.ctx.channel
                            and m.content.split("-")
                            and (
                                m.content.split("-")[0].isdigit()
                                or m.content.split("-")[0].lower() == "none"
                            )
                            and (
                                m.content.split("-")[1].isdigit()
                                or m.content.split("-")[1].lower() == "none"
                            )
                        )
                    except Exception as e:
                        if ctx.debug:
                            raise e

                        return False

                await interaction.response.send_message(
                    f"Please send what numbers you want to switch. Send a message with the format `num1-num2` e.g `1-5`. To switch it with a empty number, use `none` e.g `1-none`\n\nNote that you only have {slide_puzzle.switch_attempts.left} tries left to switch, including this one.\nTo cancel, just type something random \U0001f642",
                    ephemeral=True,
                )

                try:
                    msg = await self.view.ctx.bot.wait_for(
                        "message", check=check, timeout=60
                    )
                except Exception as e:
                    if ctx.debug:
                        raise e

                    return await interaction.followup.send(
                        "Took to long to respond where to switch.", ephemeral=True
                    )  # btw proguy can u co-author me for the commit u will do whenever after this cuz i helped :> ok

                try:
                    num1 = (
                        int(msg.content.split("-")[0])
                        if msg.content.split("-")[0].lower() != "none"
                        else None
                    )
                    num2 = (
                        int(msg.content.split("-")[1])
                        if msg.content.split("-")[1].lower() != "none"
                        else None
                    )
                except Exception as e:
                    if ctx.debug:
                        raise e

                    return await interaction.followup.send(
                        "Not a valid integer.", ephemeral=True
                    )

                try:
                    if (not 0 < num1 <= (slide_puzzle.x * slide_puzzle.y) - 1) or (
                        not 0 < num2 <= (slide_puzzle.x * slide_puzzle.y) - 1
                    ):
                        return await interaction.followup.send(
                            "Not a valid integer in the puzzle.", ephemeral=True
                        )
                except TypeError as e:
                    if ctx.debug:
                        raise e

                if num1 == num2:
                    return await interaction.followup.send(
                        "You can't switch with the same number, that is just, wasting.",
                        ephemeral=True,
                    )

                slide_puzzle.switch(num1, num2)

                self.view.refresh_buttons()

                if slide_puzzle.switch_attempts.left == 0:
                    self.disabled = True

                await interaction.message.edit(view=self.view)

                await interaction.followup.send(
                    f"Switched number {str(num1).title()} with {str(num2).title()}. You now have {slide_puzzle.switch_attempts.left} tries to switch.",
                    ephemeral=True,
                )

                if slide_puzzle.win():
                    for child in self.view.children:
                        child.disabled = True

                    await interaction.message.edit(
                        view=self.view,
                        content=f"You won the game! You played for `{round(slide_puzzle.duration, 2)} seconds` and took `{slide_puzzle.tries} tries`.",
                    )
                    self.view.stop()
                    return

        class StopButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.danger,
                    label="Stop",
                    emoji="<:openrobot_stop_button:899878227969974322>",
                    row=4,
                )

            async def callback(self, interaction: discord.Interaction):
                slide_puzzle.end()

                for child in self.view.children:
                    child.disabled = True

                await interaction.message.edit(
                    view=self.view,
                    content=f"You gave up and ended the game. You played for `{round(slide_puzzle.duration, 2)} seconds` and tried `{slide_puzzle.tries} times`.",
                )
                self.view.stop()

        class Button(discord.ui.Button):
            def __init__(self, number, **kwargs):
                if number is None:
                    super().__init__(
                        style=discord.ButtonStyle.grey,
                        disabled=True,
                        label="\u200b",
                        **kwargs,
                    )
                else:
                    super().__init__(
                        style=discord.ButtonStyle.blurple, label=number, **kwargs
                    )

                self.number = number

            async def callback(self, interaction: discord.Interaction):
                slide_puzzle.move(self.number)

                self.view.refresh_buttons()

                if slide_puzzle.win():
                    for child in self.view.children:
                        child.disabled = True

                    await interaction.message.edit(
                        view=self.view,
                        content=f"You won the game! You played for `{round(slide_puzzle.duration, 2)} seconds` and took `{slide_puzzle.tries} tries`.",
                    )
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

                self.add_item(StopButton())
                self.add_item(HelpButton())
                self.add_item(SwitchButton())

            async def on_timeout(self) -> None:
                for child in self.children:
                    child.disabled = True

                await self.message.edit(
                    view=self, content="Game ended cause you didn't respond."
                )

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user != ctx.author:
                    await interaction.response.send_message(
                        f"Only {ctx.author.mention} can play this Slide Puzzle. To play your own game of Slide Puzzle, invoke the `slide-puzzle` command.",
                        ephemeral=True,
                    )
                    return False
                else:
                    return True

            async def on_error(
                self,
                error: Exception,
                item: discord.ui.Item,
                interaction: discord.Interaction,
            ) -> None:
                if isinstance(error, games.slide_puzzle.CannotBeMoved):
                    return await interaction.response.send_message(
                        f"You can't move number {item.number}.", ephemeral=True
                    )
                elif isinstance(error, games.slide_puzzle.SwitchAttemptExhausted):
                    item.disabed = True
                    await interaction.message.edit(view=self)

                    return await interaction.response.send_message(
                        "There are no available attempts for you to switch."
                    )

                raise error

        view = View(ctx)

        view.message = await ctx.send(view=view, content="\u200b")

        slide_puzzle.start()

    # @commands.command('rock-paper-scissors', aliases=['rock-paper-scissor', 'rps', 'rock_paper_scissors', 'rock_paper_scissor'])
    async def rock_paper_scissors(
        self, ctx: commands.Context, opponent: discord.Member
    ):
        rps = games.RockPaperScissors()

        class View(discord.ui.View):
            def __init__(self, *, timeout: float = 60):
                super().__init__(timeout=timeout)

                self.add_item(
                    discord.ui.Button(
                        emoji=(games.rock_paper_scissors.Emoji.ROCK),
                        label="Rock",
                        style=discord.ButtonStyle.primary,
                    )
                )
                self.add_item(
                    discord.ui.Button(
                        emoji=(games.rock_paper_scissors.Emoji.PAPER),
                        label="Paper",
                        style=discord.ButtonStyle.primary,
                    )
                )
                self.add_item(
                    discord.ui.Button(
                        emoji=(games.rock_paper_scissors.Emoji.SCISSORS),
                        label="Scissors",
                        style=discord.ButtonStyle.primary,
                    )
                )

            def disable_all(self):
                for child in self.children:
                    child.disabled = True

    @commands.command("hangman")
    @commands.max_concurrency(1, commands.BucketType.user)
    async def hangman_cmd(self, ctx: commands.Context):
        """
        Plays hangman.

        You need to guess the letter to win in 6 tries.
        Note that it is advised for you to know how to play hangman before playing using this command.
        """

        class View(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                self.category = None
                self.interaction = None

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user != ctx.author and not ctx.bot.is_owner(interaction.user):
                    await interaction.response.send_message(
                        f"Only {ctx.author.mention} can play this game. To play your own game of Hangman, invoke the `hangman` command.",
                        ephemeral=True,
                    )
                    return False

                return True

            @discord.ui.select(placeholder='Select a Category', options=[
                discord.SelectOption(label='Fruits', emoji='🍎', description='Play Hangman with Fruits category.'),
                discord.SelectOption(label='Food', emoji='🍝', description='Play Hangman with Food category.'),
                discord.SelectOption(label='Drinks', emoji='🍹', description='Play Hangman with Drinks category.'),
                discord.SelectOption(label='Colors', emoji='🔴', description='Play Hangman with Coffee category.'),
                discord.SelectOption(label='Animals', emoji='🐶', description='Play Hangman with Animals category.'),
                discord.SelectOption(label='Countries', emoji='\U0001f1fa\U0001f1f8', description='Play Hangman with Countries category.'),
                discord.SelectOption(label='Vehicles', emoji='🚗', description='Play Hangman with Vehicles category.'),
                discord.SelectOption(label='Languages', description='Play Hangman with Languages category.'),
                discord.SelectOption(label='Buildings', emoji='🏘️', description='Play Hangman with Buildings category.'),
                discord.SelectOption(label='Random', emoji='🎲', description='Randomly picks a category'),
            ])
            async def callback(self, select: discord.ui.Select, interaction: discord.Interaction):
                await interaction.response.defer()

                self.interaction = interaction

                self.category = select.values[0] if select.values[0] != 'Random' else None

                self.stop()

        view = View()

        msg = await ctx.send('Choose a category to play Hangman with.', view=view)

        await view.wait()

        await msg.delete()

        hangman = games.Hangman(ctx, view.category)

        category = hangman.word[1].lower().capitalize()

        await view.interaction.followup.send(f'You are playing Hangman with the **{category}** category.', ephemeral=True)

        stopped = False

        class StopButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.red, label="Stop", emoji='<:openrobot_stop_button:899878227969974322>')

            async def callback(self, interaction: discord.Interaction):
                nonlocal stopped
                stopped = True

                await interaction.message.delete()

                self.view.stop()

        msg = None

        while not hangman.lose and not hangman.win and not stopped:
            try:
                embed = discord.Embed(color=self.bot.color)

                embed.description = f"""
Guessed Words: {', '.join([f'`{x}`' for x in hangman.guessed_words])}
Word: {hangman.word_guess}
Tries Left: {hangman.tries_left}
```{hangman.draw()}```

Please reply to this message with a letter.
                """

                view = discord.ui.View(timeout=None)

                view.add_item(StopButton())

                msg = await ctx.send(embed=embed, view=view)

                m = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.reference and m.reference.resolved == msg and len(m.content) == 1 and not m.content.replace(' ', '').strip())

                correct = hangman.guess(m.content)

                if correct:
                    await m.reply("Good guess!", delete_after=10)
                else:
                    await m.reply("Incorrect guess.", delete_after=10)

                await msg.delete()
            except Exception as e:
                await ctx.send(f"```py\n{e}```")

                if msg:
                    try:
                        await msg.delete()
                    except:
                        pass

        if stopped:
            return

        if hangman.win:
            try:
                await msg.delete()
            except:
                pass

            return await ctx.send("Congrats! You won!", delete_after=10)
        elif hangman.lose:
            try:
                await msg.delete()
            except:
                pass

            return await ctx.send(f"OOF! You Lost! The word was `{hangman.word[0]}`.", delete_after=10)

    @commands.command("bingo")
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def bingo_cmd(self, ctx: commands.Context):
        """
        Play bingo with someone, like a friend.

        Note that it is advised for you to know how to play bingo before playing using this command.
        """

        players = [ctx.author]

        base_content = f"""
A bingo game has started in this channel.

**Host:** {ctx.author.mention}

**Note:** It is advised for you to know how to play bingo before playing this game.

**Players:**
""" + "\n".join(
            [f"- {player.mention}" for player in players]
        )

        class JoinButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.green, label="Join the Game", row=0
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user in players:
                    return await interaction.response.send_message(
                        f"You are already in the game.", ephemeral=True
                    )

                try:
                    await interaction.user.send(
                        f"You have joined the game bingo game in {ctx.channel.mention}. Please stay in this DM for your bingo cards when the game has started."
                    )
                except:
                    return await interaction.response.send_message(
                        "I cannot DM you. Make sure you have your DMs open and you did not block me.",
                        ephemeral=True,
                    )

                players.append(interaction.user)

                base_content = f"""
A bingo game has started in this channel.

**Host:** {ctx.author.mention}

**Note:** It is advised for you to know how to play bingo before playing this game.

**Players:**
""" + "\n".join(
                    [f"- {player.mention}" for player in players]
                )

                await interaction.message.edit(
                    content=base_content,
                    allowed_mentions=discord.AllowedMentions(users=False),
                )

                await interaction.response.send_message(
                    f"You have successfully joined the game.", ephemeral=True
                )

                return await interaction.followup.send(
                    f"{interaction.user.mention} has joined the game.",
                    allowed_mentions=discord.AllowedMentions(users=False),
                )

        class LeaveButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.red, label="Leave the Game", row=0
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user not in players:
                    return await interaction.response.send_message(
                        f"You are not in the game.", ephemeral=True
                    )

                if interaction.user == ctx.author:
                    return await interaction.response.send_message(
                        "You cannot leave the game if you are the host. Use the `Cancel The Game` button instead.",
                        ephemeral=True,
                    )

                players.remove(interaction.user)

                base_content = f"""
A bingo game has started in this channel.

**Host:** {ctx.author.mention}

**Note:** It is advised for you to know how to play bingo before playing this game.

**Players:**
""" + "\n".join(
                    [f"- {player.mention}" for player in players]
                )

                await interaction.message.edit(
                    content=base_content,
                    allowed_mentions=discord.AllowedMentions(users=False),
                )

                await interaction.response.send_message(
                    f"You have successfully left the game.", ephemeral=True
                )

                return await interaction.followup.send(
                    f"{interaction.user.mention} has left the game.",
                    allowed_mentions=discord.AllowedMentions(users=False),
                )

        class StartButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.primary, label="Start the Game", row=0
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message(
                        f"Only the host, {ctx.author.mention} can start the game.",
                        ephemeral=True,
                    )

                if len(players) < 2:
                    return await interaction.response.send_message(
                        f"You need at least 2 players to start the game.",
                        ephemeral=True,
                    )

                for child in self.view.children:
                    child.disabled = True

                await interaction.message.edit(
                    content=f"__**The game has started!**__\n\n{base_content}",
                    delete_after=10,
                    view=self.view,
                    allowed_mentions=discord.AllowedMentions(users=False),
                )

                self.view.started = True
                self.view.stop()

        class CancelButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.red, label="Cancel the Game", row=0
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message(
                        f"Only the host, {ctx.author.mention} can start the game.",
                        ephemeral=True,
                    )

                for child in self.view.children:
                    child.disabled = True

                await interaction.message.edit(
                    content=f"__**The game has been canceled by the host, {ctx.author.mention}!**__\n\n{base_content}",
                    allowed_mentions=discord.AllowedMentions(users=False),
                    view=self.view,
                )

                self.view.started = False
                self.view.stop()

        view = discord.ui.View()
        view.started = None
        view.add_item(JoinButton())
        view.add_item(LeaveButton())
        view.add_item(StartButton())
        view.add_item(CancelButton())

        m = await ctx.send(
            base_content,
            view=view,
            allowed_mentions=discord.AllowedMentions(users=False),
        )

        await view.wait()

        if view.started is None:
            for child in view.children:
                child.disabled = True

            await m.edit(view=view)

            return await ctx.send(
                "Game timed out, no one joined and the game didn't start in the last 3 minutes."
            )
        elif view.started is False:
            return

        bingo = games.Bingo(players)

        self.bingo_instances.append(bingo)

        for player in bingo.players:
            board = player.board

            class Button(discord.ui.Button):
                def __init__(self, number: int, **kwargs):
                    self.x = kwargs.pop("x", None)
                    self.y = kwargs.pop("y", None)

                    super().__init__(
                        label="Free" if number is None else str(number),
                        style=discord.ButtonStyle.green
                        if number is None
                        else discord.ButtonStyle.secondary,
                        **kwargs,
                    )

                async def callback(self, interaction: discord.Interaction):
                    if self.label == "Free":
                        return await interaction.response.send_message(
                            "This is a free space.", ephemeral=True
                        )

                    bingo.claim(player, int(self.label))

                    self.disabled = True
                    self.style = discord.ButtonStyle.green

                    await interaction.message.edit(view=self.view)

                    return await interaction.response.send_message(
                        f"Claimed number {self.label} on ({self.x}, {self.y})"
                    )

            class View(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=None)

                    for y in range(len(board)):
                        for x in range(len(board[y])):
                            self.add_item(
                                Button(
                                    getattr(board[y][x], "number", None),
                                    row=y,
                                    x=x,
                                    y=y,
                                )
                            )

                async def on_error(
                    self,
                    error: Exception,
                    item: discord.ui.Item,
                    interaction: discord.Interaction,
                ) -> None:
                    if isinstance(error, games.bingo.BingoError):
                        return await interaction.response.send_message(
                            f"{error}", ephemeral=True
                        )

                    raise error

            view = View()

            await player.member.send(
                f"""
You have been assigned a bingo card with a size of 5x5.

If the number rolled is in your card, you may click that specific button.

You have 20 seconds before the next roll number hits.

To view what number has been rolled, you can go to {ctx.channel.mention} and see the bot's roll history.

If you have hit a BINGO, you may go to the original message sent by the bot in {ctx.channel.mention} and click the "Bingo" button.
            """
            )

            await player.member.send(f"Here are your bingo cards:", view=view)

        await ctx.send(
            "Let's start this game: "
            + ", ".join([player.member.mention for player in bingo.players])
        )

        winner = None

        class Button(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.green, label="Bingo!", row=0)

            async def callback(self, interaction: discord.Interaction):
                nonlocal winner

                if interaction.user not in players:
                    return await interaction.response.send_message(
                        "You are not in this bingo game!", ephemeral=True
                    )

                if (player := bingo.winner(bingo.get_player(interaction.user))) not in [
                    None,
                    False,
                ]:
                    await interaction.response.send_message(
                        ", ".join([player.member.mention for player in bingo.players])
                        + f"\n\n{interaction.user}: BINGO!"
                    )

                    for player in bingo.players:
                        if player != interaction.user:
                            await player.member.send(
                                f"Bingo game has ended, {ctx.author.mention} has won the game."
                            )

                    winner = player

                    self.view.stop()
                else:
                    return await interaction.response.send_message(
                        f"Stop it, We all know that you didn't hit a Bingo.",
                        ephemeral=True,
                    )

        class StopButton(discord.ui.Button):
            def __init__(self):
                super().__init__(
                    style=discord.ButtonStyle.red, label="Stop the game", row=0
                )

            async def callback(self, interaction: discord.Interaction):
                if interaction.user not in players:
                    return await interaction.response.send_message(
                        "You are not in this bingo game!", ephemeral=True
                    )

                if interaction.user != ctx.author:
                    return await interaction.response.send_message(
                        "Only the host can stop this game.", ephemeral=True
                    )

                bingo.stopped = True

                await ctx.send(
                    f"The game has been stopped by the host, {ctx.author.mention}.",
                    allowed_mentions=discord.AllowedMentions(users=False),
                )

                self.view.stop()

        while winner is None and not bingo.stopped:
            view = discord.ui.View()
            view.add_item(Button())
            view.add_item(StopButton())

            m = await ctx.send("Rolling...", view=view)

            choice = bingo.roll()

            await asyncio.sleep(random.randint(1, 5))

            await m.edit(
                content=f"Rolled a `{choice}`!\nYou have 30 seconds to claim your Bingo card. If you hit a BINGO, click the `Bingo!` button below."
            )

            for player in bingo.players:
                await player.member.send(f"Rolled a `{choice}`!")

            await asyncio.sleep(20)

            await m.edit(content=f"Rolled a `{choice}`!", view=None)


def setup(bot):
    bot.add_cog(Fun(bot))

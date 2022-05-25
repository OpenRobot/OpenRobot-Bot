import io

import inspect
import typing
import discord
import openai
import json
import aiohttp
import random
import boto3
import re
import string
import asyncio
from io import StringIO, BytesIO
from config import OPENAI_KEY, AWS_CRIDENTIALS
from discord.ext import commands
from cogs.utils import (
    Cog,
    ImageConverter,
    MenuPages,
    Codeblock,
    CelebrityPaginator,
    LegacyFlagConverter,
    LegacyFlagItems,
    CodeblockConverter,
    TranslateLanguagesPagniator,
    CodeReviewPaginator,
    CodeReviewPages,
    command,
    group,
    Command,
    Group,
    GIST_REGEX,
    GITHUB_REGEX,
    HASTEBIN_REGEX,
)
from openrobot.api_wrapper import error

openai.api_key = OPENAI_KEY


class AI(Cog, emoji="🤖"):
    def __init__(self, bot):
        super().__init__(bot)

        self.codecommit = boto3.client("codecommit", **AWS_CRIDENTIALS)
        self.codeguru = boto3.client("codeguru-reviewer", **AWS_CRIDENTIALS)

    async def get_img_bytes(self, url: str):
        async with self.bot.session.get(url) as resp:
            return io.BytesIO(await resp.read())

    @staticmethod
    def get_ai_text():
        ai_text = """The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, intelligent and very friendly.

Human: Hello
AI: Hello! How are you doing today?
Human: Who are you?
AI: I am a Robot made by OpenRobot. How can I help you?
Human: What is your name?
AI: My name is OpenRobot.
Human: What is your GitHub organization?
AI: My GitHub organization can be found at <https://github.com/OpenRobot/>.
Human: What is 1+1?
AI: 1+1 is 2
Human: What is 5 times 6?
AI: 5 times 6 is 30"""

        # Human: What is "See you later!" in French?
        # AI: "See you later" in Englis is "À tout à l'heure!" in French.
        # Human: What is "Hello" in Spanish?
        # AI: "Hello" in English is "Hola" in Spanish.
        # Human: What is "Saya suka anda" in English?
        # AI: "Saya suka anda" in English is "I like you" in Indonesian language.

        # with open('cogs/utils/math_train.jsonl', 'r') as f:
        # l = [list(json.loads(x).values()) for x in f.read().splitlines()]

        # for question, answer in random.choices(l, k=random.randint(10, 30)):
        # ai_text += f"\nHuman: {question}\nAI: {answer}"

        ai_text += "\nHuman: "

        return ai_text

    # @commands.command('chat', aliases=['assistant'])
    async def chat(self, ctx: commands.Context):
        """
        Makes a OpenRobot Chat Session with you and OpenRobot.

        Powered by [OpenAI](https://openai.com/).

        You can say `stop`, `goodbye` or `end` to end the chat.
        """

        ai_text = self.get_ai_text()

        await ctx.send(
            "OpenRobot Chat Session has started. Note that chats *can* be collected. Say `stop`, `goodbye`, `end` or `exit` to end the chat."
        )

        while True:
            msg: discord.Message = await self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
            )

            if msg.content.lower() in ["goodbye", "stop", "end", "exit"]:
                return await ctx.send("OpenRobot Chat Session has ended.")

            ai_text += f"{msg}\nAI: "

            try:
                response = openai.Completion.create(
                    engine="davinci",
                    prompt=ai_text,
                    temperature=0.9,
                    max_tokens=150,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0.6,
                    stop=["\n", " Human:", " AI:"],
                )
            except Exception as e:
                if ctx.debug:
                    raise e

                ai_text = ai_text.replace(f"{msg}\nAI: ", "")
                await ctx.send("Sorry, I did not understand.")
                continue

            if ctx.debug:
                await ctx.send(
                    file=discord.File(
                        StringIO(json.dumps(response, indent=4)),
                        filename="response.json",
                    )
                )

            ai_response = response["choices"][0]["text"]

            if not ai_response:
                ai_text = ai_text.replace(f"{msg}\nAI: ", "")
                await ctx.send("Sorry, I did not understand.")
                continue

            ai_text += f"{ai_response}\nHuman: "

            await msg.reply(ai_response, mention_author=False)

    # @commands.command('create-study-notes', aliases=['study-notes', 'create-study-note', 'study-note', 'createstudynote', 'createstudynotes', 'studynotes', 'studynote'])
    async def create_study_notes(self, ctx: commands.Context, *, topic: str):
        """
        Creates study notes from the topic provided.

        Powered by [OpenAI](https://openai.com/).

        Examples of some topics can be:
        - `Ancient Rome`
        - `Python`
        - `Javascript`
        - `Math Algebra`
        ...
        """

        ai_str = f"""What are some key points I should know when studying {topic.title()}?

1."""

        try:
            response = openai.Completion.create(
                engine="davinci-instruct-beta",
                prompt=ai_str,
                temperature=1,
                max_tokens=100,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            )
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("Failed to get study notes.")

        if ctx.debug:
            await ctx.send(
                file=discord.File(
                    StringIO(json.dumps(response, indent=4)), filename="response.json"
                )
            )

        ai_response = response["choices"][0]["text"]

        if not ai_response:
            return await ctx.send("Could not find any study notes.")

        embed = discord.Embed(color=self.bot.color)

        embed.set_author(
            name=f"Study Notes for {topic.title()}:", icon_url=ctx.author.display_avatar.url
        )

        s = "1."

        for line in ai_response.split("\n"):
            if line.replace(". ", "").replace(".", "").isdigit():
                continue
            else:
                s += f"{line}\n"

        if s == "1.":
            return await ctx.send("Could not find any study notes.")

        embed.description = s

        await ctx.send(embed=embed)

    @command(
        name="review-code",
        aliases=[
            "review_code",
            "reviewcode",
            "code-review",
            "code-reviewer",
            "codereview",
            "codereviewer",
            "code_review",
            "code_reviewer",
        ],
        example="review-code My-URL-Or-Code",
    )
    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.cooldown(1, 250, commands.BucketType.user)  # 5 minute cooldown
    async def review_code(
        self,
        ctx: commands.Context,
        *,
        code: CodeblockConverter = commands.Option(
            None, description="The code/link to be reviewed."
        ),
    ):
        """
        Reviews a code and sends suggestions to improve it.

        This can either take a physical codeblock/code or a link.
        Note that this currently can only take Java and Python code.

        Currently supported Links:
        - [GitHub Gist](https://gist.github.com/)
        - [GitHub Repository](https://github.com/) (Public Repositories)
        - [Mystbin](https://mystb.in/)
        - [Hastebin](https://www.toptal.com/developers/hastebin/)

        Attachments are also supported.
        """

        async def task(
            ctx: commands.Context,
            code: Codeblock,
            *,
            repo_name: str = None,
            repo_code: dict[str, str] = None,
        ):
            if not repo_name:
                random_name = "".join(
                    random.choices(
                        string.ascii_letters + string.digits, k=random.randint(10, 50)
                    )
                )

                name = f"codeguru-reviewer-{ctx.author.id}-{random_name}"

                create_repository_response = self.codecommit.create_repository(
                    repositoryName=name,
                    repositoryDescription=f'<p>Code Reviewer Repository for {ctx.author.name} (<a href="{ctx.message.jump_url}">{ctx.message.jump_url}</a>)</p>',  # HTML
                )

                if ctx.debug:
                    await ctx.send(
                        file=discord.File(
                            StringIO(
                                json.dumps(
                                    {
                                        str(k): str(v)
                                        for k, v in create_repository_response.items()
                                    },
                                    indent=4,
                                )
                            ),
                            filename="create_repository_response.json",
                        )
                    )

                # branch_name = create_repository_response['repositoryMetadata']['defaultBranch']

                extension = "py" if code.language in ["py", "python"] else "java"

                branch_name = "main"

                put_file_reponse = self.codecommit.put_file(
                    repositoryName=name,
                    branchName=branch_name,
                    fileContent=code.content.encode(),
                    filePath=f"main.{extension}",
                    fileMode="NORMAL",
                )

                if ctx.debug:
                    await ctx.send(
                        file=discord.File(
                            StringIO(
                                json.dumps(
                                    {
                                        str(k): str(v)
                                        for k, v in put_file_reponse.items()
                                    },
                                    indent=4,
                                )
                            ),
                            filename="put_file_reponse.json",
                        )
                    )
            else:
                name = repo_name

                branch_name = "main"

            try:
                assosiate_repository_response = self.codeguru.associate_repository(
                    Repository={
                        "CodeCommit": {
                            "Name": name,
                        },
                    },
                )

                if ctx.debug:
                    await ctx.send(
                        file=discord.File(
                            StringIO(
                                json.dumps(
                                    {
                                        str(k): str(v)
                                        for k, v in assosiate_repository_response.items()
                                    },
                                    indent=4,
                                )
                            ),
                            filename="assosiate_repository_response.json",
                        )
                    )

                AssociationArn = assosiate_repository_response["RepositoryAssociation"][
                    "AssociationArn"
                ]

                response = self.codeguru.create_code_review(
                    Name=name,
                    RepositoryAssociationArn=AssociationArn,
                    Type={
                        "RepositoryAnalysis": {
                            "RepositoryHead": {
                                "BranchName": branch_name,
                            },
                        },
                    },
                )

                if ctx.debug:
                    await ctx.send(
                        file=discord.File(
                            StringIO(
                                json.dumps(
                                    {str(k): str(v) for k, v in response.items()},
                                    indent=4,
                                )
                            ),
                            filename="create_code_review.json",
                        )
                    )

                CodeReviewArn = response["CodeReview"]["CodeReviewArn"]

                while True:
                    response = self.codeguru.describe_code_review(
                        CodeReviewArn=CodeReviewArn,
                    )

                    if response["CodeReview"]["State"].lower() == "completed":
                        break

                    await asyncio.sleep(3)

                token = None

                recommendations = []

                while True:
                    try:
                        if token:
                            recommendation = self.codeguru.list_recommendations(
                                NextToken=token,
                                MaxResults=100,
                                CodeReviewArn=CodeReviewArn,
                            )
                        else:
                            recommendation = self.codeguru.list_recommendations(
                                MaxResults=100,
                                CodeReviewArn=CodeReviewArn,
                            )

                        if not recommendation["RecommendationSummaries"]:
                            break

                        recommendations.extend(
                            recommendation["RecommendationSummaries"]
                        )

                        token = recommendation["NextToken"]
                    except:
                        break

                if not recommendations:
                    try:
                        return await ctx.author.send(
                            f"No recommendations found for Code Review {ctx.message.jump_url}."
                        )
                    except:
                        return await ctx.reply("No recommendations found in the code.")

                if repo_name and repo_code:
                    for recommendation in recommendations:
                        recommendation["Code"] = repo_code[recommendation["FilePath"]]
                        recommendation["CodeReviewArn"] = CodeReviewArn
                        recommendation["FromGitHub"] = True
                else:
                    for recommendation in recommendations:
                        recommendation["Code"] = code.content
                        recommendation["CodeReviewArn"] = CodeReviewArn
                        recommendation["FromGitHub"] = False

                await CodeReviewPages(
                    CodeReviewPaginator(recommendations, per_page=1),
                    timeout=None,
                    force_paginate=True,
                    try_send_in_dm=True,
                    reply="channel",
                ).start(ctx)
            except Exception as e:
                ctx.command.reset_cooldown(ctx)

                if ctx.debug:
                    raise e

                try:
                    return await ctx.author.send(
                        f"Sorry. Something wen't wrong and I failed to create the code review for {ctx.message.jump_url}."
                    )
                except:
                    return await ctx.reply(
                        f"Sorry. Something wen't wrong and I failed to create the code review."
                    )
            finally:
                delete_repository_response = self.codecommit.delete_repository(
                    repositoryName=name,
                )

        if isinstance(code, str):
            if regex_result := GIST_REGEX.match(code):
                author = regex_result.group("author")
                gist_id = regex_result.group("gist_id")
                file_name = regex_result.group("file_name")

                if file_name:
                    file_name = file_name.replace("-", ".")

                l = [author, gist_id]

                if file_name:
                    l.append(file_name)

                async with self.bot.session.get(
                    "https://gist.githubusercontent.com/" + "/".join(l)
                ) as resp:
                    if 200 >= resp.status < 300:
                        code = await resp.text()
                    else:
                        ctx.command.reset_cooldown(ctx)
                        return await ctx.send("Invalid Gist URL.")
            elif regex_result := GITHUB_REGEX.fullmatch(code):
                author = regex_result.group("author")
                repo = regex_result.group("repo")

                l = []

                folders = []

                async with self.bot.session.get(
                    f"https://api.github.com/repos/{author}/{repo}/contents/", headers={
                            'Authorization': f'token {self.bot.config.CODE_REVIEW_GITHUB_TOKEN}'
                    }
                ) as resp:
                    js = await resp.json()

                if isinstance(js, dict) and resp.status != 200:
                    ctx.command.reset_cooldown(ctx)

                    if (msg := js.get("message")) and msg != "Not Found":
                        return await ctx.send(msg)
                    elif msg == "Not Found":
                        return await ctx.send("Invalid GitHub URL.")
                    else:
                        return await ctx.send("Unknown error.")

                for file in js:
                    if file["type"] == "dir":
                        folders.append(file)
                    elif file["type"] == "file":
                        if file["name"].endswith((".py", ".java")):
                            l.append(file)

                for folder in folders:
                    async with self.bot.session.get(
                        f'https://api.github.com/repos/{author}/{repo}/contents/{folder["path"]}', headers={
                            'Authorization': f'token {self.bot.config.CODE_REVIEW_GITHUB_TOKEN}'
                        }
                    ) as resp:
                        js = await resp.json()

                    if isinstance(js, dict) and resp.status != 200:
                        ctx.command.reset_cooldown(ctx)

                        if (msg := js.get("message")) and msg != "Not Found":
                            return await ctx.send(msg)
                        elif msg == "Not Found":
                            return await ctx.send("Invalid GitHub URL.")

                    for file in js:
                        if file["type"] == "dir":
                            folders.append(file)
                        elif file["type"] == "file":
                            if file["name"].endswith((".py", ".java")):
                                l.append(file)

                if not l:
                    ctx.command.reset_cooldown(ctx)
                    return await ctx.send(
                        "No Python and Java files found in that repository."
                    )

                await ctx.send(
                    "Code review has started. I will try to DM you with the code review results. If I cannot DM you, "
                    "I will post the results in this channel replying to your message.\nCode reviews can take up from "
                    "seconds to minutes depending on how large the code is. "
                )

                random_name = "".join(
                    random.choices(
                        string.ascii_letters + string.digits, k=random.randint(10, 50)
                    )
                )

                name = f"codeguru-reviewer-{ctx.author.id}-{random_name}"

                create_repository_response = self.codecommit.create_repository(
                    repositoryName=name,
                    repositoryDescription=f'<p>Code Reviewer Repository for {ctx.author.name} (<a href="{ctx.message.jump_url}">{ctx.message.jump_url}</a>)</p>',  # HTML
                )

                if ctx.debug:
                    await ctx.send(
                        file=discord.File(
                            StringIO(
                                json.dumps(
                                    {
                                        str(k): str(v)
                                        for k, v in create_repository_response.items()
                                    },
                                    indent=4,
                                )
                            ),
                            filename="create_repository_response.json",
                        )
                    )

                branch_name = "main"

                d = {}

                commit_id = None

                for file in l:
                    async with self.bot.session.get(file["download_url"]) as resp:
                        content = await resp.text()

                    d[file["path"]] = content

                    if not commit_id:
                        put_file_reponse = self.codecommit.put_file(
                            repositoryName=name,
                            branchName=branch_name,
                            fileContent=content.encode(),
                            filePath=file["path"],
                            fileMode="NORMAL",
                        )
                    else:
                        put_file_reponse = self.codecommit.put_file(
                            repositoryName=name,
                            branchName=branch_name,
                            fileContent=content.encode(),
                            filePath=file["path"],
                            fileMode="NORMAL",
                            parentCommitId=commit_id,
                        )

                    commit_id = put_file_reponse["commitId"]

                await task(ctx, None, repo_name=name, repo_code=d)

                return
            elif regex_result := HASTEBIN_REGEX.match(code):
                key = regex_result.group('key')
                async with self.bot.session.get(f'https://www.toptal.com/developers/hastebin/raw/{key}') as resp:
                    code = await resp.text()
            else:
                try:
                    mystbin = await self.bot.mystbin.get(code)
                except:
                    ctx.command.reset_cooldown(ctx)
                    return await ctx.send("Could not recognize the `code` argument.")
                else:
                    code = mystbin.paste_content

            class View(discord.ui.View):
                def __init__(self, *, timeout: int = None):
                    super().__init__(timeout=timeout)
                    self.language = None
                    self.message = None

                @discord.ui.button(
                    label="Python",
                    emoji="<:python:918350483096236043>",
                    style=discord.ButtonStyle.blurple,
                )
                async def python(
                    self, button: discord.ui.Button, interaction: discord.Interaction
                ):
                    self.language = "py"

                    await self.message.delete()
                    self.stop()

                @discord.ui.button(
                    label="Java",
                    emoji="<:java:918350372370796615>",
                    style=discord.ButtonStyle.blurple,
                )
                async def java(
                    self, button: discord.ui.Button, interaction: discord.Interaction
                ):
                    self.language = "java"

                    await self.message.delete()
                    self.stop()

            view = View()

            view.message = await ctx.send(
                "What language is this code written in? If you select the wrong language, things might break.",
                view=view,
            )
            await view.wait()

            code = Codeblock(view.language, code)
        elif isinstance(code, Codeblock):
            if code.language not in ["java", "python", "py"]:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(
                    "Currently only Java and Python code is supported."
                )
        else:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("Could not recognize the `code` argument.")

        await ctx.send(
            "Code review has started. I will try to DM you with the code review results. If I cannot DM you, "
            "I will post the results in this channel replying to your message.\nCode reviews can take up from seconds "
            "to minutes depending on how large the code is. "
        )

        await task(ctx, code)

    @command(
        "nsfw-check",
        aliases=["nsfwcheck", "nsfw_check", "check", "nc", "nsfw"],
        example="nsfw-check My-Image-URL-Or-Attachment",
    )
    async def nsfw_check(
        self,
        ctx: commands.Context,
        *,
        image=commands.Option(
            None, description="The image. This can be a URL or a image attached."
        ),
    ):
        """
        NSFW Checks an Image.

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        if image:
            if "--raw" in image.split(" "):
                raw = True
            else:
                raw = False
        else:
            raw = False

        url = (
            await ImageConverter(strip_remove=["--raw"]).convert(ctx, image)
            or ctx.author.display_avatar.url
        )

        img = await self.get_img_bytes(url)
        check = await self.bot.api.nsfw_check(img)

        if raw:
            s = StringIO()
            s.write(json.dumps(check.raw, indent=4))
            s.seek(0)

            return await ctx.send(file=discord.File(s, "response.json"))

#         label_str = ""
#
#         parent_name_added = []
#
#         for label in reversed(
#             check.labels
#         ):  # Childrens are always returned last in the label, so.....
#             if label.name in parent_name_added:
#                 continue
#
#             label_str += f"- `{label.name}` - `{round(label.confidence, 2)}%`\n"
#
#             if label.parent_name:
#                 parent_name_added.append(label.parent_name)
#
#         label_str = label_str[:-1]  # remove last newline.
#
#         safe_score = round(100 - check.score * 100, 2)
#         safe_score = int(safe_score) if safe_score % 1 == 0 else safe_score
#         unsafe_score = round(check.score * 100, 2)
#         unsafe_score = int(unsafe_score) if unsafe_score % 1 == 0 else unsafe_score
#
#         is_safe = not bool(check.labels) and safe_score > unsafe_score
#
#         newline = "\n"  # Python won't let back-strings in f-strings, so yeah.
#
#         embed = discord.Embed(color=self.bot.color)
#         embed.set_image(url=url)
#         embed.add_field(
#             name="<:status_dnd:596576774364856321> Unsafe Score:",
#             value=f"`{unsafe_score}%`",
#         )
#         embed.add_field(
#             name="<:status_online:596576749790429200> Safe Score:",
#             value=f"`{safe_score}%`",
#         )
#         embed.description = f"""
# **Is Safe:** {is_safe}
# **Labels:**{newline + label_str if label_str else ' None.'}
#         """
#         embed.set_footer(
#             text="Powered by OpenRobot API (https://api.openrobot.xyz/)\nInspired by Ami#7836"
#         )
#
#         await ctx.send(embed=embed)

        embed = discord.Embed(color=self.bot.color, title='NSFW Check')
        embed.set_image(url=url)
        embed.add_field(
            name="__**Adult:**__",
            value=f"""
**Is Adult Content:** `{check.adult.is_adult}`
**Adult Score:** `{round(check.adult.adult_score * 100, 1)}`
            """,
            inline=False
        )
        embed.add_field(
            name="Racy:",
            value=f"""
**Is Racy Content:** `{check.racy.is_racy}`
**Racy Score:** `{round(check.racy.racy_score * 100, 1)}`
            """,
            inline=False
        )
        embed.add_field(
            name="Gore:",
            value=f"""
**Is Gore Content:** `{check.gore.is_gore}`
**Gore Score:** `{round(check.gore.gore_score * 100, 1)}`
            """,
            inline=False
        )
        embed.set_footer(
            text="Powered by OpenRobot API (https://api.openrobot.xyz/)"
        )

        return await ctx.send(embed=embed)

    @command(example="celebrity My-Image-URL-Or-Attachment")
    async def celebrity(
        self,
        ctx: commands.Context,
        *,
        image=commands.Option(
            None, description="The image. This can be a URL or a image attached."
        ),
    ):
        """
        Finds a celebrity in a image. Note that this is not 100% accurate and is still on beta.

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        url = await ImageConverter(strip_remove=["--raw"]).convert(ctx, image)

        if not url:
            return await ctx.send("No image provided.")

        img = await self.get_img_bytes(url)

        data = aiohttp.FormData()
        data.add_field('file', io.BytesIO(img))

        try:
            async with self.bot.session.post(
                "https://api.openrobot.xyz/api/celebrity",
                data=data,
                headers={"Authorization": self.bot.api.token},
            ) as resp:
                js = await resp.json()

            try:
                if "--raw" in image.split(" "):
                    s = StringIO()
                    s.write(json.dumps(js, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, "response.json"))
            except Exception as e:
                if ctx.debug:
                    raise e

                pass

            if not js["celebrities"]:
                try:
                    return await ctx.send(
                        "Celebrity cannot be found in the image provided.",
                        file=discord.File(img, "image_celebrity.png"),
                    )
                except Exception as e:
                    if ctx.debug:
                        raise e

                    return await ctx.send(
                        "Celebrity cannot be found in the image provided."
                    )

            class CelebrityProperties:
                def __init__(self, **kwargs):  # .url, .cropped_url, .name, .raw
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            # await ctx.send(await bot.mystbin.post(json.dumps(js, indent=4)))

            l = [
                CelebrityProperties(
                    url=url, cropped_url=None, name=i["name"], raw=js, item=i
                )
                for i in js["celebrities"]
            ]

            # for i in js['detectedFaces']:
            # l.append(CelebrityProperties(
            # url=url, cropped_url=None, name=i['Name'], raw=js, item=i
            # )) # await publishCdn(await bot.loop.run_in_executor(None, crop_image, i), file_type='png')
        except Exception as e:
            if ctx.debug:
                raise e

            try:
                return await ctx.send(
                    "Celebrity cannot be found in the image provided.",
                    file=discord.File(img, "image_celebrity.png"),
                )
            except:
                return await ctx.send(
                    "Celebrity cannot be found in the image provided."
                )

        menu = MenuPages(CelebrityPaginator(l), delete_message_after=True)
        await menu.start(ctx)

    @command(name='text-generator', aliases=['text-generation', 'text_generator', 'text_generation', 'textgenerator', 'textgeneration'], example="text-generator Hello,")
    async def text_generator(self, ctx: commands.Context, num_return: typing.Optional[int] = 1, *, text: str = None):
        """
        Text Generator. Generates more text from the text provided.
        """

        if not text:
            raise commands.MissingRequiredArgument(inspect.Parameter('text', inspect.Parameter.KEYWORD_ONLY))

        if ctx.interaction is not None:
            await ctx.interaction.response.defer()
        
        try:
            text_generator_result = await self.bot.api.text_generation(text, num_return=num_return, max_length=int(4000 / num_return)) # a issue with the api for now, requiring max_length as an int.

            while text_generator_result.result is None and text_generator_result.status in ['PENDING', 'STARTED']: 
                await asyncio.sleep(2)
                text_generator_result = await self.bot.api.text_generation_get(text_generator_result.task_id)

            try:
                if "--raw" in text.split(" "):
                    s = StringIO()
                    s.write(json.dumps(text_generator_result.raw, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, "response.json"))
            except Exception as e:
                pass

            if text_generator_result.status != 'COMPLETED' or text_generator_result.result is None:
                return await ctx.send("Something went wrong. Please try again.")

            embed = discord.Embed(color=self.bot.color)
            embed.set_author(name="Text Generator Result:")
            embed.description = '- ' + '\n- '.join(text_generator_result.result)

            await ctx.send(embed=embed)
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("Something went wrong. Please try again.")

    @command(example="sentiment Hello,")
    async def sentiment(self, ctx: commands.Context, *, text: str):
        """
        Sentiment. Analyzes the sentiment of the text provided, either if it is Positive or Negative.
        """

        if ctx.interaction is not None:
            await ctx.interaction.response.defer()

        try:
            sentiment_result = await self.bot.api.sentiment(text)

            while sentiment_result.result is None and sentiment_result.status in ['PENDING', 'STARTED']: 
                await asyncio.sleep(2)
                sentiment_result = await self.bot.api.sentiment_get(sentiment_result.task_id)

            try:
                if "--raw" in text.split(" "):
                    s = StringIO()
                    s.write(json.dumps(sentiment_result.raw, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, "response.json"))
            except Exception as e:
                pass

            if sentiment_result.status != 'COMPLETED' or sentiment_result.result is None:
                return await ctx.send("Something went wrong. Please try again.")

            embed = discord.Embed(color=self.bot.color)
            embed.set_author(name="Sentiment Result:")
            embed.description = f'Text: {text}\n\nResult: `{sentiment_result.result[0].label}` - `Confidence: {sentiment_result.result[0].score}`'

            await ctx.send(embed=embed)
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("Something went wrong. Please try again.")

    @command(aliases=['summarize', 'summarise', 'summarisation'], example="summarization Hey, I love chatting with my friends. I love it. I love using Discord. Its my favorite chat app.")
    async def summarization(self, ctx: commands.Context, *, text: str):
        """
        Summarization. Summarizes a text into a pretty short length. Including all the details and excluding most of the quite un-useful information.
        """

        if ctx.interaction is not None:
            await ctx.interaction.response.defer()

        try:
            summarization_result = await self.bot.api.summarization(text, max_length=4000)

            while summarization_result.result is None and summarization_result.status in ['PENDING', 'STARTED']: 
                await asyncio.sleep(2)
                summarization_result = await self.bot.api.summarization_get(summarization_result.task_id)

            try:
                if "--raw" in text.split(" "):
                    s = StringIO()
                    s.write(json.dumps(summarization_result.raw, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, "response.json"))
            except Exception as e:
                pass

            if summarization_result.status != 'COMPLETED' or summarization_result.result is None:
                return await ctx.send("Something went wrong. Please try again.")

            embed = discord.Embed(color=self.bot.color)
            embed.set_author(name="Summarization Result:")
            embed.description = summarization_result.result

            await ctx.send(embed=embed)
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("Something went wrong. Please try again.")

    @command(example="caption My-Image-URL-Or-Attachment", aliases=['description', 'captions', 'tags', 'descriptions'])
    async def caption(
        self,
        ctx: commands.Context,
        *,
        image=commands.Option(
            None, description="The image. This can be a URL or a image attached."
        )
    ):
        """
        Generates a caption from the image.

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        url = await ImageConverter(strip_remove=["--raw"]).convert(ctx, image)

        if not url:
            return await ctx.send("No image provided.")

        if ctx.interaction is not None:
            await ctx.interaction.response.defer()

        try:
            img = await self.get_img_bytes(url)
            description = await self.bot.api.description(img)

            embed = discord.Embed(color=self.bot.color, title='Caption')
            embed.description = f"**Tags:** {', '.join(description.tags)}\n\n**Captions:**\n"
            embed.set_image(url=url)

            if not description.captions:
                embed.description += "No captions found."
            else:
                for caption in description.captions:
                    embed.description += f"- {caption.text} | `Confidence: {round(caption.confidence * 100, 2)}%`\n"

            return await ctx.send(embed=embed)
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("Failed to generate caption.")

    @command(example="ocr My-Image-URL-Or-Attachment")
    async def ocr(
        self,
        ctx: commands.Context,
        *,
        image=commands.Option(
            None, description="The image. This can be a URL or a image attached."
        ),
    ):
        """
        Optical Character Recognition. Reads text from images.

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        url = await ImageConverter(strip_remove=["--raw"]).convert(ctx, image)

        if not url:
            return await ctx.send("No image provided.")

        if ctx.interaction is not None:
            await ctx.interaction.response.defer()

        try:
            img = await self.get_img_bytes(url)
            ocr_result = await self.bot.api.ocr(img)

            try:
                if "--raw" in image.split(" "):
                    s = StringIO()
                    s.write(json.dumps(ocr_result.raw, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, "response.json"))
            except Exception as e:
                pass

            text = ocr_result.text

            if len(discord.utils.escape_markdown(text)) > 4000:
                url = await self.bot.mystbin.post(text, syntax="text")
                view = discord.ui.View(timeout=None)
                view.add_item(
                    discord.ui.Button(
                        style=discord.ButtonStyle.url,
                        url=str(url),
                        label="OCR Result (View in Mystbin)",
                    )
                )

                return await ctx.send(
                    "Content too long to send. Click the button to view the result.",
                    view=view,
                )
            else:
                embed = discord.Embed(color=self.bot.color)
                embed.set_author(name="Result:")
                embed.timestamp = discord.utils.utcnow()

                embed.description = await commands.clean_content(
                    use_nicknames=False, escape_markdown=True
                ).convert(ctx, text)

                return await ctx.send(embed=embed)
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send("No text found in image.")

    @group(
        invoke_without_command=True,
        aliases=["tr"],
        usage="<text> <flags>",
        slash_command=False,
        example="translate Hola --to en",
    )
    async def translate(self, ctx: commands.Context, *, flags: str):
        """
        Translates a text to another language.

        Flags:
        - `--to`: The language that needs to be translated to.
        - `--from`: The original text language. This is optional and detects the language by default.
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        if ctx.invoked_subcommand is None:
            converter = LegacyFlagConverter(
                [
                    LegacyFlagItems("text", nargs="+"),
                    LegacyFlagItems(
                        "--to",
                        "--t",
                        "-t",
                        "-to",
                        "--to-lang",
                        "-to-lang",
                        "-tl",
                        "--tl",
                        type=str,
                    ),
                    LegacyFlagItems(
                        "--from",
                        "--f",
                        "-f",
                        "-from",
                        "--from-lang",
                        "-from-lang",
                        "-fl",
                        "--fl",
                        type=str,
                        default=None,
                    ),
                    LegacyFlagItems("--raw", action="store_true", default=False),
                ]
            )

            args = converter.convert(flags)

            text = " ".join(args.text)
            to_lang = args.to
            from_lang = getattr(
                args, "from"
            )  # We can't do args.from cause that will raise a SyntaxError.

            raw = args.raw

            if from_lang is None:
                from_lang = "auto"

            try:
                try:
                    translate = await self.bot.api.translate(text, to_lang, from_lang)
                except error.BadRequest as e:
                    if ctx.debug:
                        raise e

                    if e.message == "Invalid language in paramater to_lang.":
                        return await ctx.send(
                            f"{to_lang} is not a valid language (`--to` flag)"
                        )
                    elif e.message == "Invalid language in paramater from_lang.":
                        return await ctx.send(
                            f"{from_lang} is not a valid language (`--from` flag)"
                        )

                if raw:
                    s = StringIO()
                    s.write(json.dumps(translate.raw, indent=4))
                    s.seek(0)

                    return await ctx.send(file=discord.File(s, "response.json"))

                embed = discord.Embed(color=self.bot.color)

                embed.description = f"""
**Translation Result:** {discord.utils.escape_markdown(translate.text)}
**To Language:** {translate.to}
**From Language:** {translate.source}
                """

                embed.set_author(
                    name=f"Translation Result ({translate.source} -> {translate.to})"
                )

                embed.timestamp = discord.utils.utcnow()

                return await ctx.send(embed=embed)
            except Exception as e:
                if ctx.debug:
                    raise e

                return await ctx.send(
                    "Something wen't wrong while aquiring the translation from our API."
                )

    @translate.command(
        aliases=["langs", "language", "lang"],
        cls=Command,
        example="translate languages",
    )
    async def languages(
        self,
        ctx: commands.Context,
        *,
        flags: str = commands.Option(
            "", description="Add --raw to this to get the raw response."
        ),
    ):
        """
        Gets a list of languages supported by the translator.

        Flags:
        - `--raw`: Returns the raw response sent by our (OpenRobot) API.
        """

        try:
            js = await self.bot.api.translate.languages()

            if "--raw" in flags.split(" "):
                s = StringIO()
                s.write(json.dumps(js, indent=4))
                s.seek(0)

                return await ctx.send(file=discord.File(s, "response.json"))

            menu = MenuPages(
                TranslateLanguagesPagniator(list(js.items())), delete_message_after=True
            )
            await menu.start(ctx)
        except Exception as e:
            if ctx.debug:
                raise e

            return await ctx.send(
                "Something wen't wrong while aquiring the supported languages for translation from our API."
            )


def setup(bot):
    bot.add_cog(AI(bot))

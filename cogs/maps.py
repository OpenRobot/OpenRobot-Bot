import os
import json
import glob
from io import StringIO, BytesIO

import discord
from discord import app_commands
from discord.ext import commands

from cogs.utils import Cog, command, group, Command, Group, OriginalCommand, OriginalGroup


class Maps(Cog, emoji='<:maps:970725022538805258>'):
    """
    Gets info on specific Maps/Location.
    """

    MAPS_CACHE = {}
    MAPS_SEARCH_CACHE = {}

    # We want it to be a hidden folder so people don't mess around with the cache and break stuff.
    MAPS_CACHE_FOLDER = ".maps-cache"

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

        # try:
        #     self.restore_cache()
        # except:
        #     pass

        self.cache_process_running = False

    # def cog_unload(self):
    #     self.save_cache()

    @staticmethod
    def _remove_dir_contents(path):
        for i in os.listdir(path):
            os.remove(f'{path}/{i}')

    def purge_cache(self, local: bool = True, folder: bool = None) -> tuple[tuple[dict, dict], tuple[dict, dict], list]:
        local_stats = ({}, {})

        if local:
            local_stats = (self.MAPS_CACHE, self.MAPS_SEARCH_CACHE)

            self.MAPS_CACHE.clear()
            self.MAPS_SEARCH_CACHE.clear()

        persistent_stats = ({}, {})
        images = []

        if folder or folder is None:
            if folder:
                if not os.path.exists(self.MAPS_CACHE_FOLDER):
                    raise FileNotFoundError(f"{self.MAPS_CACHE_FOLDER} does not exist.")

            try:
                with open(f"{self.MAPS_CACHE_FOLDER}/maps_cache.json", "r") as f:
                    js = json.load(f)

                persistent_stats = (js['maps_cache'], js['maps_search_cache'])
            except:
                pass

            images = glob.glob(f"{self.MAPS_CACHE_FOLDER}/*.png")

            if os.path.exists(self.MAPS_CACHE_FOLDER):
                self._remove_dir_contents(self.MAPS_CACHE_FOLDER)
                os.rmdir(self.MAPS_CACHE_FOLDER)

        return local_stats, persistent_stats, images

    def save_cache(self):
        if os.path.exists(self.MAPS_CACHE_FOLDER):
            self.purge_cache(local=False, folder=True)

        os.mkdir(self.MAPS_CACHE_FOLDER)

        maps_cache = {}
        maps_search_cache = self.MAPS_SEARCH_CACHE

        id_counter = 0

        for query, cache in self.MAPS_CACHE.items():
            image = cache['image']
            embed = cache['embed'].to_dict()
            data = cache['data']
            dark = cache['dark']

            with open(f"{self.MAPS_CACHE_FOLDER}/{id_counter}.png", "wb") as f:
                f.write(image)

            maps_cache[query] = {
                'image': f"{self.MAPS_CACHE_FOLDER}/{id_counter}.png",
                'embed': embed,
                'data': data,
                'dark': dark,
                'id': id_counter,
            }

            id_counter += 1

        data = {'maps_cache': maps_cache, 'maps_search_cache': maps_search_cache}

        with open(f"{self.MAPS_CACHE_FOLDER}/maps_cache.json", "w") as f:
            json.dump(data, f, indent=4)

    def persistent_present(self):
        return os.path.exists(f"{self.MAPS_CACHE_FOLDER}/maps_cache.json")

    def restore_cache(self):
        if not os.path.exists(self.MAPS_CACHE_FOLDER):
            raise FileNotFoundError(f"{self.MAPS_CACHE_FOLDER} does not exist.")

        with open(f"{self.MAPS_CACHE_FOLDER}/maps_cache.json", "r") as f:
            data = json.load(f)

        self.MAPS_SEARCH_CACHE = data['maps_search_cache']

        for query, cache in data['maps_cache'].items():
            maps_cache = {}

            with open(cache['image'], 'rb') as f:
                maps_cache['image'] = f.read()

            maps_cache['embed'] = discord.Embed.from_dict(cache['embed'])

            maps_cache['data'] = cache['data']
            maps_cache['dark'] = cache['dark']

            self.MAPS_CACHE[query] = maps_cache

        self.purge_cache(local=False, folder=True)

    async def search(self, query: str) -> dict:
        if query.lower() in self.MAPS_SEARCH_CACHE:
            return self.MAPS_SEARCH_CACHE[query.lower()]
        elif query.lower() in self.MAPS_CACHE:
            return self.MAPS_CACHE[query.lower()]['data']

        data = await self.bot.maps.search(query)

        self.MAPS_SEARCH_CACHE[query.lower()] = data

        return data

    async def render(self, query, data, *, dark: bool) -> tuple[discord.Embed, discord.File] | None:
        if query.lower() in self.MAPS_CACHE:
            cache = self.MAPS_CACHE[query.lower()]

            if cache['dark'] is dark:
                return cache['embed'], discord.File(BytesIO(cache['image']), filename='map.png')

        style = "dark" if dark else "main"
        footer_text = "Source: Microsoft Atlas (Azure Maps)"

        if data['type'] == 'POI':
            image = await self.bot.maps.render(data, zoom=12, style=style, layer="basic")

            embed = discord.Embed(color=self.bot.color, title='POI')

            embed.set_image(url='attachment://map.png')

            if data['poi'].get('url'):
                name_embed = f"[{data['poi']['name']}](https://{data['poi']['url']}/)"
            else:
                name_embed = f"{data['poi']['name']}"

            if data['poi'].get('categories'):
                categories = f' - {", ".join([x.lower().title() for x in data["poi"]["categories"]])}'
                embed.title += f' ({", ".join(["`" + x.lower().title() + "`" for x in data["poi"]["categories"]])})'
            else:
                categories = ''

            embed.description = f"__**{name_embed}**__{categories}"

            if data['poi'].get('phone'):
                embed.description += f'\n\n**Phone:** {data["poi"]["phone"]}'
            else:
                embed.description += '\n'

            embed.description += f'\n**Address:** {data["address"]["freeformAddress"]}'

            embed.description += f"""
**Latitude:** `{data["position"]["lat"]}`
**Longitude:** `{data["position"]["lon"]}`
**Coordinates:** `{data["position"]["lat"]}, {data["position"]["lon"]}`"""

            embed.set_footer(text=footer_text)
        elif data['type'] == 'Geography':
            if data['entityType'] == 'Country':
                image = await self.bot.maps.render(data, zoom=3, style=style, layer="basic")
            elif data['entityType'] == 'Municipality':
                image = await self.bot.maps.render(data, zoom=5, style=style, layer="basic")
            else:
                image = await self.bot.maps.render(data, zoom=10, style=style, layer="basic")

            type = data['entityType']
            if type == 'Municipality':
                type = "City"
            elif type == 'MunicipalitySubdivision':
                type = "Town"

            embed = discord.Embed(color=self.bot.color, title=type)

            embed.set_image(url='attachment://map.png')

            if data['entityType'] != 'Country':
                if data['address'].get('municipality'):
                    embed.set_author(name=f"{data['address']['municipality']}, {data['address']['country']}")
                else:
                    embed.set_author(name=data['address']['freeformAddress'])

            embed.description = f"__**{data['address']['freeformAddress']}**__"

            embed.description += f"""
**Latitude:** `{data["position"]["lat"]}`
**Longitude:** `{data["position"]["lon"]}`
**Coordinates:** `{data["position"]["lat"]}, {data["position"]["lon"]}`"""

            embed.set_footer(text=footer_text)
        elif data['type'] == 'Street':
            image = await self.bot.maps.render(data, zoom=14, style=style, layer="basic")

            embed = discord.Embed(color=self.bot.color, title='Street')

            embed.set_image(url='attachment://map.png')

            if data['address'].get('municipality'):
                embed.set_author(
                    name=f"{data['address']['streetName']}, {data['address']['municipality']}, {data['address']['country']}")

            embed.description = f"__**{data['address']['freeformAddress']}**__"

            embed.description += f"""
**Latitude:** `{data["position"]["lat"]}`
**Longitude:** `{data["position"]["lon"]}`
**Coordinates:** `{data["position"]["lat"]}, {data["position"]["lon"]}`"""

            embed.set_footer(text=footer_text)
        elif data['type'] == 'Cross Street':
            image = await self.bot.maps.render(data, zoom=None, style=style, layer="basic")

            embed = discord.Embed(color=self.bot.color)

            embed.set_image(url='attachment://map.png')

            embed.set_author(
                name=f"{data['address']['streetName']}, {data['address']['municipality']}, {data['address']['country']}")

            embed.description = f"__**{data['address']['freeformAddress']}**__"

            embed.description += f"""
**Latitude:** `{data["position"]["lat"]}`
**Longitude:** `{data["position"]["lon"]}`
**Coordinates:** `{data["position"]["lat"]}, {data["position"]["lon"]}`"""

            embed.set_footer(text=footer_text)
        elif data['type'] == 'Address Range':
            image = await self.bot.maps.render(data, zoom=12, style=style, layer="basic")

            embed = discord.Embed(color=self.bot.color)

            embed.set_image(url='attachment://map.png')

            embed.set_author(
                name=f"{data['address']['streetName']}, {data['address']['municipality']}, {data['address']['country']}")

            embed.description = f"__**{data['address']['freeformAddress']}**__"

            embed.description += f"""
**Latitude:** `{data["position"]["lat"]}`
**Longitude:** `{data["position"]["lon"]}`
**Coordinates:** `{data["position"]["lat"]}, {data["position"]["lon"]}`

**Address Ranges:**
    - Range Right: `{data['addressRanges']['rangeRight']}`
    - From: `{data['addressRanges']['from']['lat']}, {data['addressRanges']['from']['lon']}`
    - To: `{data['addressRanges']['to']['lat']}, {data['addressRanges']['to']['lon']}`"""

            embed.set_footer(text=footer_text)
        else:
            return None

        if isinstance(image, bytes):
            image = BytesIO(image)

        if not isinstance(image, BytesIO):
            raise Exception(image)

        self.MAPS_CACHE[query.lower()] = {'image': image.getvalue(), 'embed': embed, 'data': data, 'dark': dark}

        return embed, discord.File(image, filename='map.png')

    @commands.group(invoke_without_command=True, slash_command=False, aliases=['map'], cls=OriginalGroup)
    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def maps(self, ctx, *, query):
        """
        Searches for a location using the query provided, then renders it in a image.

        Flags:
        - `--dark`: Makes the image in Dark Mode.
        """

        if ctx.invoked_subcommand is None:
            if self.cache_process_running:
                return await ctx.send("Maintenance for Maps is currently running. Please try again later.")

            msg = await ctx.reply(f"Searching for location with query {query}...")

            dark = "--dark" in query.split(" ")

            if dark:
                query = query.replace(" --dark", "")

            query = query.strip()

            data = await self.search(query)

            await msg.delete()

            if not data or not data['results']:
                ctx.command.reset_cooldown(ctx)
                return await ctx.reply(f"Location with query `{query}` cannot be found.")

            data = data['results'][0]

            if ctx.debug:
                await ctx.reply(file=discord.File(StringIO(json.dumps(data, indent=4)), filename="maps.json"))

            render = await self.render(query, data, dark=dark)

            if render is None:
                print(
                    f"Maps: Unknown type:\n{json.dumps(data, indent=4)}")  # Raising the error will trigger on_command_error which I don't want.
                return await ctx.reply("Unknown type. This error has been reported.")

            embed, file = render

            await ctx.reply(embed=embed, file=file)
        else:
            await ctx.send_help(ctx.command)

    @maps.command('search', cls=OriginalCommand, slash_command=False)
    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def maps_search(self, ctx, *, query):
        """
        Searches for a location using the query provided, asks the user for which location the user wants to see,
        then renders it in an image.

        Flags:
        - `--dark`: Makes the image in Dark Mode.
        """

        if self.cache_process_running:
            return await ctx.send("Maintenance for Maps is currently running. Please try again later.")

        msg = await ctx.reply(f"Searching for location with query {query}...")

        dark = "--dark" in query.split(" ")

        if dark:
            query = query.replace("--dark", "")

        query = query.strip()

        data = await self.search(query)

        await msg.delete()

        if not data or not data['results']:
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply(f"Location with query `{query}` cannot be found.")

        if len(data['results']) > 1:
            results = list(filter(lambda i: i['type'] in ['POI', 'Geography', 'Street',
                                                     'Cross Street', 'Address Range'], data['results'][:25]))

            if not results:
                ctx.command.reset_cooldown(ctx)
                return await ctx.reply(f"Location with query `{query}` cannot be found.")

            data = None

            class Select(discord.ui.Select):
                def __init__(self):
                    super().__init__(
                        placeholder="Select a location"
                    )

                    for index, result in enumerate(results):
                        name = self.get_name(result)

                        address = result['address']['freeformAddress']

                        if result['type'] == 'POI':
                            category = result["poi"]["categories"]

                            if category:
                                address = f'{category[0].lower().title()} | {address}'

                        if len(address) > 100:
                            address = address[:100-4] + " ..."

                        self.add_option(label=name, description=address, value=str(index))

                async def callback(self, interaction: discord.Interaction):
                    nonlocal data

                    index = int(self.values[0])

                    result = results[index]

                    self.view.result = result

                    self.view.stop()

                @staticmethod
                def get_name(result):
                    try:
                        if result['type'] == 'POI':
                            return result['poi']['name']
                        elif result['type'] == 'Geography':
                            if result['entityType'] != 'Country':
                                if result['address'].get('municipality'):
                                    return f"{result['address']['municipality']}, {result['address']['country']}"
                                else:
                                    return result['address']['freeformAddress']
                            else:
                                return result['address']['country']
                        elif result['type'] == 'Street' or result['type'] == 'Cross Street' or result[
                            'type'] == 'Address Range':
                            return result['address']['streetName']
                    except:
                        pass

                    return result['address']['freeformAddress']

            class View(discord.ui.View):
                def __init__(self, *, timeout: int = 180):
                    super().__init__(timeout=timeout)

                    self.add_item(Select())

                    self.result = None

                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                    if interaction.user != ctx.author and not await ctx.bot.is_owner(interaction.user):
                        await interaction.response.send_message('This is not your interaction!', ephemeral=True)
                        return False

                    return True

            view = View()

            msg = await ctx.reply('Here are your search results:', view=view)

            timed_out = await view.wait()

            if timed_out:
                return await msg.edit(content="You didn't respond in time. Try again later.", view=None)
            else:
                await msg.delete()

            data = view.result
        else:
            data = data['results'][0]

        if ctx.debug:
            await ctx.reply(file=discord.File(StringIO(json.dumps(data, indent=4)), filename="maps.json"))

        render = await self.render(query, data, dark=dark)

        if render is None:
            print(
                f"Maps: Unknown type:\n{json.dumps(data, indent=4)}")  # Raising the error will trigger on_command_error which I don't want.
            return await ctx.reply("Unknown type. This error has been reported.")

        embed, file = render

        await ctx.reply(embed=embed, file=file)

    maps_concurrency = commands.MaxConcurrency(1, per=commands.BucketType.user, wait=False)
    maps_cooldown = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user)

    @app_commands.command(name='maps-render')
    @app_commands.describe(query='The location to render the image of the map.',
                           dark='Whether to render the image in Dark Mode.')
    async def slash_maps(self, ctx, query: str, dark: bool = False):
        """
        Searches for a location using the query provided, then renders it in a image.
        """

        await self.maps_concurrency.acquire(ctx.message)

        bucket = self.maps_cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()

        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after, self.maps_cooldown.type)

        try:
            if self.cache_process_running:
                return await ctx.send("Maintenance for Maps is currently running. Please try again later.")

            msg = await ctx.send(f"Searching for location with query {query}...")

            data = await self.search(query)

            await msg.delete()

            if not data or not data['results']:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(f"Location with query `{query}` cannot be found.")

            data = data['results'][0]

            if ctx.debug:
                await ctx.send(file=discord.File(StringIO(json.dumps(data, indent=4)), filename="maps.json"))

            render = await self.render(query, data, dark=dark)

            if render is None:
                print(
                    f"Maps: Unknown type:\n{json.dumps(data, indent=4)}")  # Raising the error will trigger on_command_error which I don't want.
                return await ctx.send("Unknown type. This error has been reported.")

            embed, file = render

            await ctx.send(embed=embed, file=file)
        finally:
            await self.maps_concurrency.release(ctx.message)

    maps_search_concurrency = commands.MaxConcurrency(1, per=commands.BucketType.user, wait=False)
    maps_search_cooldown = commands.CooldownMapping.from_cooldown(1, 10, commands.BucketType.user)

    @app_commands.command(name='maps-search')
    @app_commands.describe(query='The location to render the image of the map.',
                           dark='Whether to render the image in Dark Mode.')
    async def slash_maps_search(self, ctx, query: str, dark: bool = False):
        """
        Searches for a location using the query provided, then renders it in an image.
        """

        await self.maps_search_concurrency.acquire(ctx.message)

        bucket = self.maps_search_cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()

        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after, self.maps_search_cooldown.type)

        try:
            if self.cache_process_running:
                return await ctx.send("Maintenance for Maps is currently running. Please try again later.")

            msg = await ctx.send(f"Searching for location with query {query}...")

            data = await self.search(query)

            await msg.delete()

            if not data or not data['results']:
                ctx.command.reset_cooldown(ctx)
                return await ctx.send(f"Location with query `{query}` cannot be found.")

            if len(data['results']) > 1:
                results = list(filter(lambda i: i['type'] in ['POI', 'Geography', 'Street',
                                                              'Cross Street', 'Address Range'], data['results'][:25]))

                if not results:
                    ctx.command.reset_cooldown(ctx)
                    return await ctx.reply(f"Location with query `{query}` cannot be found.")

                data = None

                class Select(discord.ui.Select):
                    def __init__(self):
                        super().__init__(
                            placeholder="Select a location"
                        )

                        for index, result in enumerate(results):
                            name = self.get_name(result)

                            address = result['address']['freeformAddress']

                            if result['type'] == 'POI':
                                category = result["poi"]["categories"]

                                if category:
                                    address = f'{category[0].lower().title()} | {address}'

                            if len(address) > 100:
                                address = address[:100 - 4] + " ..."

                            self.add_option(label=name, description=address, value=str(index))

                    async def callback(self, interaction: discord.Interaction):
                        nonlocal data

                        index = int(self.values[0])

                        result = results[index]

                        self.view.result = result

                        self.view.stop()

                    @staticmethod
                    def get_name(result):
                        try:
                            if result['type'] == 'POI':
                                return result['poi']['name']
                            elif result['type'] == 'Geography':
                                if result['entityType'] != 'Country':
                                    if result['address'].get('municipality'):
                                        return f"{result['address']['municipality']}, {result['address']['country']}"
                                    else:
                                        return result['address']['freeformAddress']
                                else:
                                    return result['address']['country']
                            elif result['type'] == 'Street' or result['type'] == 'Cross Street' or result[
                                'type'] == 'Address Range':
                                return result['address']['streetName']
                        except:
                            pass

                        return result['address']['freeformAddress']

                class View(discord.ui.View):
                    def __init__(self, *, timeout: int = 180):
                        super().__init__(timeout=timeout)

                        self.add_item(Select())

                        self.result = None

                    async def interaction_check(self, interaction: discord.Interaction) -> bool:
                        if interaction.user != ctx.author and not await ctx.bot.is_owner(interaction.user):
                            await interaction.response.send_message('This is not your interaction!', ephemeral=True)
                            return False

                        return True

                view = View()

                msg = await ctx.send('Here are your search results:', view=view)

                timed_out = await view.wait()

                if timed_out:
                    return await msg.edit(content="You didn't respond in time. Try again later.", view=None)
                else:
                    await msg.delete()

                data = view.result
            else:
                data = data['results'][0]

            if ctx.debug:
                await ctx.send(file=discord.File(StringIO(json.dumps(data, indent=4)), filename="maps.json"))

            render = await self.render(query, data, dark=dark)

            if render is None:
                print(
                    f"Maps: Unknown type:\n{json.dumps(data, indent=4)}")  # Raising the error will trigger on_command_error which I don't want.
                return await ctx.send("Unknown type. This error has been reported.")

            embed, file = render

            return await ctx.send(embed=embed, file=file)
        finally:
            await self.maps_search_concurrency.release(ctx.message)

    # Maps Cache stuff:
    @maps.group('cache', cls=Group, invoke_without_command=True, hidden=True, slash_command=False)
    @commands.is_owner()
    async def maps_cache(self, ctx):
        """
        Manages the cache of maps. Owner only.
        """

        return await ctx.send_help(ctx.command)

    @maps_cache.command('file', cls=Command, aliases=['set-file', 'setfile', 'set_file'], hidden=True,
                        slash_command=False)
    @commands.is_owner()
    async def maps_cache_file(self, ctx, *, folder: str):
        """
        Sets the cache file (`Maps.MAPS_CACHE_FOLDER`) for temporary. This doesn't persist through reboots. Owner only.
        """

        if self.cache_process_running:
            return await ctx.send(
                "There is a cache process currently running. Please wait for it to finish to avoid errors.")

        try:
            self.cache_process_running = True

            original = self.MAPS_CACHE_FOLDER
            self.MAPS_CACHE_FOLDER = folder

            await ctx.send(f"Cache file set from `{folder}` to `{folder}`.")
        finally:
            self.cache_process_running = False

    @maps_cache.command('restore', cls=Command, aliases=['replace'], hidden=True, slash_command=False)
    @commands.is_owner()
    async def maps_cache_restore(self, ctx):
        """
        Restores (Replaces) the current cache with the disk (from the persistent cache). Owner only.
        """

        if self.cache_process_running:
            return await ctx.send(
                "There is a cache process currently running. Please wait for it to finish to avoid errors.")

        try:
            self.cache_process_running = True

            msg = await ctx.send(f"Restoring cache from disk...")

            if not self.persistent_present():
                return await msg.edit(content="Persistent cache not found. Nothing to restore.")

            embed = discord.Embed(title="\U000026a0 WARNING \U000026a0", color=discord.Colour.red())
            embed.description = (
                f"This will remove all of the current cache in favour of replacing it with the persistent cache.\n\n"
                f"Do you wish to continue?"
            )

            view, value, timeout = await self.bot.confirm(ctx, embed=embed, edit=msg, new=True)

            await view.msg.delete()

            if timeout:
                return await ctx.send("You didn't respond in time. Try again later.")

            if not value:
                return await ctx.send("Cancelled.")

            await ctx.send("Restoring cache...")

            original_cache = self.MAPS_CACHE
            original_search = self.MAPS_SEARCH_CACHE

            self.restore_cache()

            embed = discord.Embed(title="Statistics:", color=self.bot.color)
            embed.description = f"""
Original (Before):
    - Maps Cache (`Maps.MAPS_CACHE`): `{len(original_cache)}`
    - Maps Search Cache (`Maps.MAPS_SEARCH_CACHE`): `{len(original_search)}`
    
Restored (After):
    - Maps Cache (`Maps.MAPS_CACHE`): `{len(self.MAPS_CACHE)}`
    - Maps Search Cache (`Maps.MAPS_SEARCH_CACHE`): `{len(self.MAPS_SEARCH_CACHE)}`"""

            await ctx.send("Cache restored.", embed=embed)
        finally:
            self.cache_process_running = False

    @maps_cache.command('save', cls=Command, aliases=['keep', 'backup'], hidden=True, slash_command=False)
    @commands.is_owner()
    async def maps_cache_save(self, ctx):
        """
        Saves the cache to disk. Owner only.
        """

        if self.cache_process_running:
            return await ctx.send(
                "There is a cache process currently running. Please wait for it to finish to avoid errors.")

        try:
            self.cache_process_running = True

            await ctx.send("Saving cache to disk...")

            self.save_cache()
            map_cache = len(self.MAPS_CACHE)
            map_search = len(self.MAPS_SEARCH_CACHE)

            embed = discord.Embed(title="Statistics:", color=self.bot.color)
            embed.description = f"""
**Maps Cache (`Maps.MAPS_CACHE`):** {map_cache}
**Maps Search Cache (`Maps.MAPS_SEARCH_CACHE`):** {map_search}
            """

            await ctx.send(f"Cache saved to disk.", embed=embed)
        finally:
            self.cache_process_running = False

    @maps_cache.command('purge', cls=Command, aliases=['clear', 'delete', 'del', 'remove', 'rm'], hidden=True,
                        slash_command=False)
    @commands.is_owner()
    async def maps_cache_purge(self, ctx, mode='all'):
        """
        Purges the cache of maps. Owner only.

        Mode accepts either `all`, `local` or `persistent`.
        """

        if self.cache_process_running:
            return await ctx.send(
                "There is a cache process currently running. Please wait for it to finish to avoid errors.")

        try:
            self.cache_process_running = True

            if mode.lower() not in ['all', 'local', 'persistent']:
                return await ctx.send(f"Invalid mode `{mode}`.")

            if not self.MAPS_SEARCH_CACHE and not self.MAPS_CACHE:
                return await ctx.send("Cache is empty. Not purging.")

            embed = discord.Embed(title="\U000026a0 WARNING \U000026a0", color=discord.Colour.red())
            embed.description = (
                f"Are you sure you want to purge {'**ALL** cache' if mode == 'all' else f'{mode.title()} cache'} of Maps?\n"
                f"This will delete all the cached searches, images, and data.\n\n"
                f"**This action cannot be undone.**"
            )

            view, value, timeout = await self.bot.confirm(ctx, embed=embed, reply=True, new=True)

            await view.msg.delete()

            if timeout:
                return await ctx.send("You didn't respond in time. Try again later.")

            if not value:
                return await ctx.send("Cancelled.")

            await ctx.send("Okay then. Purging cache...")

            if mode == 'all':
                (local_cache, local_search), (persistent_cache, persistent_search), image = self.purge_cache()
            elif mode == 'local':
                (local_cache, local_search), (persistent_cache, persistent_search), image = self.purge_cache(local=True,
                                                                                                             folder=False)
            elif mode == 'persistent':
                try:
                    (local_cache, local_search), (persistent_cache, persistent_search), image = self.purge_cache(
                        local=False, folder=True)
                except FileNotFoundError:
                    return await ctx.send("Persistent cache not found (doesn't exist).")

            embed = discord.Embed(title="Statistics:", color=self.bot.color)
            embed.description = f"""
**Local:**
    - Local Cache (`Maps.MAPS_CACHE`): `{len(local_cache):,} objects purged`
    - Local Search Cache (`Maps.MAPS_SEARCH_CACHE`): `{len(local_search):,} objects purged`
    
**Persistent:**
    - Persistent Cache: `{len(persistent_cache):,} objects purged`
    - Persistent Search Cache: `{len(persistent_search):,} objects purged`
    
**Images:** `{len(image):,} images purged`"""

            await ctx.send("Cache purged.", embed=embed)
        finally:
            self.cache_process_running = False


async def setup(bot):
    await bot.add_cog(Maps(bot))

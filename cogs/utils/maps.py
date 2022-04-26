from io import BytesIO
from typing import Literal

import aiohttp
import discord
from discord.ext import commands

from ._missing import MISSING

# I don't want to use the pkg, and just prefer to do raw API calls myself
class Maps:
    def __init__(self, key: str, bot: commands.Bot, session: aiohttp.ClientSession, *,
                 base_url: str = 'atlas.microsoft.com', api_version: str = '1.0'):
        self.bot = bot
        self.session = session

        self.base_url = base_url

        self.key = key
        self.api_version = api_version

        self._zoom_levels = {
            0: {'max-lon': 360.0, 'max-lat': 170.0},
            1: {'max-lon': 360.0, 'max-lat': 170.0},
            2: {'max-lon': 360.0, 'max-lat': 170.0},
            3: {'max-lon': 360.0, 'max-lat': 170.0},
            4: {'max-lon': 360.0, 'max-lat': 170.0},
            5: {'max-lon': 180.0, 'max-lat': 85.0},
            6: {'max-lon': 90.0, 'max-lat': 42.5},
            7: {'max-lon': 45.0, 'max-lat': 21.25},
            8: {'max-lon': 22.5, 'max-lat': 10.625},
            9: {'max-lon': 11.25, 'max-lat': 5.3125},
            10: {'max-lon': 5.625, 'max-lat': 2.62625},
            11: {'max-lon': 2.8125, 'max-lat': 1.328125},
            12: {'max-lon': 1.40625, 'max-lat': 0.6640625},
            13: {'max-lon': 0.703125, 'max-lat': 0.33203125},
            14: {'max-lon': 0.3515625, 'max-lat': 0.166015625},
            15: {'max-lon': 0.17578125, 'max-lat': 0.0830078125},
            16: {'max-lon': 0.087890625, 'max-lat': 0.0415039063},
            17: {'max-lon': 0.0439453125, 'max-lat': 0.0207519531},
            18: {'max-lon': 0.0219726563, 'max-lat': 0.0103759766},
            19: {'max-lon': 0.0109863281, 'max-lat': 0.0051879883},
            20: {'max-lon': 0.0054931641, 'max-lat': 0.0025939941},
        }

    async def search(self, query: str) -> dict:
        async with self.session.get(f'https://{self.base_url}/search/fuzzy/json', params={
            'query': query,
            'language': 'en-US',
            'api-version': self.api_version,
            'subscription-key': self.key,
        }) as resp:
            if resp.status == 200:
                return await resp.json()

    async def render(self, data: dict, *,
                     name: str = None,
                     layer: Literal["basic", "hybrid", "labels"] = "basic",
                     style: Literal["dark", "main"] = "main",
                     zoom: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20] = MISSING,
                     pin: bool = True) -> BytesIO:
        lat, lon = data["position"]["lat"], data["position"]["lon"]
        name = name or data["poi"]["name"]

        if zoom is None:
            # Calculate logic zoom

            for zoom_lvl, max in self._zoom_levels:
                if max['max-lat'] >= lat > self._zoom_levels[zoom_lvl + 1]['max-lat'] and lon <= max['max-lon'] and lon > self._zoom_levels[zoom_lvl + 1]['max-lon']:
                    zoom = zoom_lvl
                    break

        params = {
            'layer': layer,
            'style': style,
            'api-version': self.api_version,
            'subscription-key': self.key,
        }

        if zoom is not MISSING:
            params['zoom'] = zoom

        if pin is True and name:
            params['pin'] = f'default|coCF2A24||\'{name}\'{lon} {lat}'

        async with self.session.get(f'https://{self.base_url}/map/static/png', params=params) as resp:
            if resp.status == 200:
                return BytesIO(await resp.read())

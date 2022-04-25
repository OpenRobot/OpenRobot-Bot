"""
MIT License

Copyright (c) 2022 JeyyGit

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import math
import numpy as np
import datetime as dt

from io import BytesIO

from colorthief import ColorThief
from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..executor import executor


# This was inspired by Jeyy API/Bot (https://github.com/JeyyGit/Jeyy-Bot/blob/main/utils/imaging.py). This code was copied but modified/added some new things.
def _spotify(title, artists, cover_buff, duration, start, *, beta = False):
    def add_corners(im, rad):
        circle = Image.new('L', (rad * 2, rad * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
        alpha = Image.new('L', im.size, "white")
        w, h = im.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        im.putalpha(alpha)
        return im

    def shorten(text, font, max_length):
        res = ''
        for c in text:
            res += c
            if font.getlength(res) > max_length:
                res = res[:-2] + '...'
                break

        return res

    sfont = ImageFont.truetype("./cogs/utils/spotify/GothamMedium.ttf", 50)
    sfont_title = ImageFont.truetype('./cogs/utils/spotify/SourceHanSans-Bold.ttc', 60)
    sfont_auth = ImageFont.truetype('./cogs/utils/spotify/SourceHanSans-Bold.ttc', 50)

    cover = Image.open(cover_buff).convert('RGBA')
    color = ColorThief(cover_buff).get_color(quality=1)
    # gray = np.mean((0.2989 * color[0], 0.5870 * color[1], 0.1140 * color[2])) 'white' if gray < 65 else 'black'
    is_dark = math.sqrt(
        0.299 * color[0] ** 2 +
        0.587 * color[1] ** 2 +
        0.114 * color[2] ** 2
    ) < 127.5
    fcolor = 'white' if is_dark else 'black'

    artists_text = ', '.join(artists)

    end_minutes, end_seconds = divmod(duration, 60)
    on_minutes, on_seconds = divmod((dt.datetime.now() - dt.datetime.fromtimestamp(start)).seconds, 60)

    if beta:
        # Title: (310, 104), (981, 163)
        # Artist: (310, 175), (981, 213)
        # Duration: (Size: 450, 20), (431, 285), (881, 300)
        # Duration Start: (339, 285), (404, 300)
        # Duration End: (903, 285), (967, 300)
        # Cover: (49, 49), (300, 300)
        # Size: 1000x350

        # Cover:

        size = (1400, 750)
        add_x, add_y = (size[0]-1000, size[1]-350)

        cover = cover.resize((251+add_x, 251+add_y))
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((0, 0, *size), 30, color)

        mask = Image.new('RGBA', cover.size, 'black')
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, *cover.size), 20, 'white')
        mask = mask.convert('L')

        img.paste(cover, (49, 49, 300+add_x, 300+add_y), mask)

        # Title:
        text_box = Image.new('RGBA', (1368-734, 315-151), color)
        text_box_draw = ImageDraw.Draw(text_box)
        tbwidth, tbheight = text_box.size
        text_box_draw.text((tbwidth // 2, tbheight // 2), title, fcolor, anchor='mm', font=sfont_title)

        img.paste(text_box, (734, 151, 1368, 315))

        # Artist:
        text_box = Image.new('RGBA', (1368-734, 448-346), color)
        text_box_draw = ImageDraw.Draw(text_box)
        tbwidth, tbheight = text_box.size
        text_box_draw.text((tbwidth // 2, tbheight // 2), artists_text, fcolor, anchor='mm', font=sfont_auth)

        img.paste(text_box, (734, 346, 1368, 448))

        # Duration Start:
        text_box = Image.new('RGBA', (837-734, 645-569), color)
        text_box_draw = ImageDraw.Draw(text_box)
        tbwidth, tbheight = text_box.size
        text_box_draw.text((tbwidth // 2, tbheight // 2), f"{on_minutes:02}:{on_seconds:02}", fcolor, anchor='mm',
                           font=sfont)

        img.paste(text_box, (734, 569, 837, 645))

        # Duration End:
        text_box = Image.new('RGBA', (1368-1262, 645-569), color)
        text_box_draw = ImageDraw.Draw(text_box)
        tbwidth, tbheight = text_box.size
        text_box_draw.text((tbwidth // 2, tbheight // 2), f"{end_minutes:02}:{end_seconds:02}", fcolor, anchor='mm',
                           font=sfont)

        img.paste(text_box, (1262, 569, 1368, 645))

        # Duration Bar:
        fbar = Image.new('RGBA', (423, 76), (255, 255, 255, 100))
        img.paste(fbar, (839, 569, 1262, 645), fbar)

        end_pos = int(((dt.datetime.now() - dt.datetime.fromtimestamp(start)).seconds / duration) * 450)

        print(end_pos)

        a, b = 838, 1262

        while b-a > end_pos:
            a += 1
            b -= 1

        print(a, b)

        if b-a != end_pos:
            if b-a > end_pos:
                a += 1
            else:
                b += 1

        print(a, b)

        bar = Image.new('RGBA', (end_pos, 20), fcolor)
        img.paste(bar, (a, 569, b, 645), bar)
        draw.ellipse((838 + end_pos - 20, 569 - 20, 1262 + end_pos + 20, 645 + 20),
                     fill=fcolor)

        buf = BytesIO()
        img.save(buf, 'PNG')
        buf.seek(0)
    else:
        cover = cover.resize((256, 256))
        img = Image.new('RGBA', (1392, 368), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((0, 0, 1392, 368), 50, color)
        #shadow = Image.new('RGBA', (256, 256), (25, 25, 25, 240))
        #img.paste(shadow, (60, 60), shadow)
        img.paste(cover, (56, 56), cover)

        # draw.text((368, 65), title if len(title) <= 23 else title[:23] + '...', fcolor, font=sfontbold)
        # draw.text((368, 140), artists_text if len(artists_text) <= 35 else artists_text[:35] + '...', fcolor, font=sfont)
        draw.text((368, 47), shorten(title, sfont_title, 945), fcolor, font=sfont_title)
        draw.text((368, 125), shorten(artists_text, sfont_auth, 945), fcolor, font=sfont_auth)

        draw.text((368, 256), f"{on_minutes:02}:{on_seconds:02}", fcolor, font=sfont)
        draw.text((1200, 256), f"{end_minutes:02}:{end_seconds:02}", fcolor, font=sfont)

        fbar = Image.new('RGBA', (640, 10), (255, 255, 255, 100))
        img.paste(fbar, (530, 270), fbar)
        end_pos = int(((dt.datetime.now() - dt.datetime.fromtimestamp(start)).seconds / duration) * 640)
        bar = Image.new('RGBA', (end_pos, 10), fcolor)
        img.paste(bar, (530, 270), bar)
        draw.ellipse((530 + end_pos - 15, 276 - 15, 530 + end_pos + 15, 276 + 15), fill=fcolor)

        buf = BytesIO()
        img.save(buf, 'PNG')
        buf.seek(0)

    return buf


@executor()
def spotify(title, artists, cover_buff, duration, start, *, beta = False):
    return _spotify(title, artists, cover_buff, duration, start, beta=beta)

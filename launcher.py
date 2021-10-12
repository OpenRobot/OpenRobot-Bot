import sys
import random
import os
from discord import Colour
from bot import start

args = sys.argv

kwargs = {}

if '--without-db' in args:
    kwargs['db'] = False
else:
    kwargs['db'] = True

if list(filter(lambda i: i.startswith('--without-'), args)):
    if '--without-cogs' in args:
        kwargs['cogs'] = False
    else:
        for arg in list(filter(lambda i: i.startswith('--without-'), args)):
            kwargs[arg[2:]] = True
else:
    kwargs['cogs'] = True

if '--random-color' in args or '--random-colour' in args:
    kwargs['colour'] = Colour.random()
elif list(filter(lambda i: i.startswith('--color-'), args)):
    kwargs['colour'] = list(filter(lambda i: i.startswith('--color-'), args))[0].replace('--colour-', '')
elif list(filter(lambda i: i.startswith('--colour-'), args)):
    kwargs['colour'] = list(filter(lambda i: i.startswith('--colour-'), args))[0].replace('--colour-', '')

if 'without-jishaku' not in kwargs:
    os.environ['JISHAKU_NO_UNDERSCORE'] = 'True'
    os.environ['JISHAKU_FORCE_PAGINATOR'] = 'True'
    os.environ['JISHAKU_NO_DM_TRACEBACK'] = 'True'

start(**kwargs)
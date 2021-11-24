import discord
import sys
import math
import json
import os
import time
import platform
import speedtest
import asyncio
import re
from discord.ext import commands
from humanize import naturalsize as get_size
from jishaku.features.baseclass import Feature
from cogs.utils.cog import Cog
from jishaku.cog import STANDARD_FEATURES, OPTIONAL_FEATURES
from jishaku.features.baseclass import Feature
from jishaku.flags import Flags
from jishaku.modules import package_version
from jishaku.paginators import PaginatorInterface
from jishaku.models import copy_context_with
from jishaku.exception_handling import ReplResponseReactor

try:
    import psutil
except ImportError:
    psutil = None


def natural_size(size_in_bytes: int):
    """
    Converts a number of bytes to an appropriately-scaled unit
    E.g.:
        1024 -> 1.00 KiB
        12345678 -> 11.77 MiB
    """
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')

    power = int(math.log(size_in_bytes, 1024))

    return f"{size_in_bytes / (1024 ** power):.2f} {units[power]}"

class Jishaku(*STANDARD_FEATURES, *OPTIONAL_FEATURES):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.emoji = '<:jishaku_logo:901355736850890813>'
        self.full_name =  (f'{self.emoji} ' if self.emoji else '') + 'Jishaku'

    def cog_load(self):
        try:
            self.bot.unload_extension('jishaku')
        except:
            pass

    def cog_unload(self):
        try:
            self.bot.load_extension('jishaku')
        except:
            pass

    @Feature.Command(name="jishaku", aliases=["jsk", "jishakum", "admin", "dev"], invoke_without_command=True, ignore_extra=False, slash_command=False)
    async def jsk(self, ctx: commands.Context):
        """
        The Jishaku debug and diagnostic commands.

        This command on its own gives a status brief.
        All other functionality is within its subcommands.
        """

        summary = [
            f"OpenRobot-Jishaku `v{package_version('jishaku')}`, discord.py `{package_version('discord.py')}`, "
            f"`Python {sys.version}` on `{sys.platform}`".replace("\n", ""),
            f"Module was loaded <t:{self.load_time.timestamp():.0f}:R>, "
            f"cog was loaded <t:{self.start_time.timestamp():.0f}:R>.",
            ""
        ]

        if psutil:
            try:
                proc = psutil.Process()

                with proc.oneshot():
                    try:
                        mem = proc.memory_full_info()
                        summary.append(f"Using {natural_size(mem.rss)} physical memory and "
                                       f"{natural_size(mem.vms)} virtual memory, "
                                       f"{natural_size(mem.uss)} of which unique to this process.")
                    except psutil.AccessDenied:
                        pass

                    try:
                        name = proc.name()
                        pid = proc.pid
                        thread_count = proc.num_threads()

                        summary.append(f"Running on PID {pid} (`{name}`) with {thread_count} thread(s).")
                    except psutil.AccessDenied:
                        pass

                    summary.append("")  # blank line
            except psutil.AccessDenied:
                summary.append(
                    "psutil is installed, but this process does not have high enough access rights "
                    "to query process information."
                )
                summary.append("")  # blank line

        cache_summary = f"{len(self.bot.guilds)} guild(s) and {len(self.bot.users)} user(s)"

        # Show shard settings to summary
        if isinstance(self.bot, discord.AutoShardedClient):
            if len(self.bot.shards) > 20:
                summary.append(
                    f"This bot is automatically sharded ({len(self.bot.shards)} shards of {self.bot.shard_count})"
                    f" and can see {cache_summary}."
                )
            else:
                shard_ids = ', '.join(str(i) for i in self.bot.shards.keys())
                summary.append(
                    f"This bot is automatically sharded (Shards {shard_ids} of {self.bot.shard_count})"
                    f" and can see {cache_summary}."
                )
        elif self.bot.shard_count:
            summary.append(
                f"This bot is manually sharded (Shard {self.bot.shard_id} of {self.bot.shard_count})"
                f" and can see {cache_summary}."
            )
        else:
            summary.append(f"This bot is not sharded and can see {cache_summary}.")

        # pylint: disable=protected-access
        if self.bot._connection.max_messages:
            message_cache = f"Message cache capped at {self.bot._connection.max_messages}"
        else:
            message_cache = "Message cache is disabled"

        if discord.version_info >= (1, 5, 0):
            presence_intent = f"presence intent is {'enabled' if self.bot.intents.presences else 'disabled'}"
            members_intent = f"members intent is {'enabled' if self.bot.intents.members else 'disabled'}"

            summary.append(f"{message_cache}, {presence_intent} and {members_intent}.")
        else:
            guild_subscriptions = f"guild subscriptions are {'enabled' if self.bot._connection.guild_subscriptions else 'disabled'}"

            summary.append(f"{message_cache} and {guild_subscriptions}.")

        # pylint: enable=protected-access

        # Show websocket latency in milliseconds
        summary.append(f"Average websocket latency: {round(self.bot.latency * 1000, 2)}ms")

        embed = discord.Embed(description="\n".join(summary), color=self.bot.color)
        #embed.set_thumbnail(url=ctx.me.avatar.url)
        embed.timestamp = discord.utils.utcnow()
        embed.set_author(name='Jishaku', icon_url=self.bot.get_emoji(901355736850890813).url)
        embed.set_footer(text=f'Requested By: {ctx.author}', icon_url=ctx.author.avatar.url)

        await ctx.send(embed=embed)

    @Feature.Command(parent="jsk", name="system", aliases=["sys"])
    async def system(self, ctx: commands.Context):
        """
        Gets systen information e.g CPU, Memory, Disk, etc.

        Most of the code is inspired by [Ami#7836](https://discord.com/users/801742991185936384).
        """
        
        async with ctx.typing():
            embed = discord.Embed(color=self.bot.color)

            uname = platform.uname()
            system_name = uname.system
            node_name = uname.node
            machine = uname.machine
            processor = uname.processor

            embed.add_field(name="System:", value=f"""```yml
OS: {system_name}
Name: {node_name}
Machine: {machine}
Processor: {processor}```
            """)

            physical_cores = psutil.cpu_count(logical=False)
            total_cores = psutil.cpu_count(logical=True)

            cpufreq = psutil.cpu_freq()
            current_cpu_freq = f"{cpufreq.current:.2f}Mhz"

            cpu_usage = f"{psutil.cpu_percent()}%" 

            embed.add_field(name="CPU:", value=f"""```yml
Physical cores: {physical_cores}
Total cores: {total_cores}
Frequency: {current_cpu_freq}
Usage: {cpu_usage}```
            """)

            svmem = psutil.virtual_memory()
            total_mem = f"{get_size(svmem.total)}"
            available_mem = f"{get_size(svmem.available)}"
            used_mem = f"{get_size(svmem.used)}"
            mem_perc = f"{svmem.percent}%"

            embed.add_field(name="Memory:", value=f"""```yml
Total: {total_mem}
Available: {available_mem}
Used: {used_mem}
Percentage: {mem_perc}```
            """)

            line_count = self.bot.line_count()

            embed.add_field(name="Code Stats:", value=f"""```yml
Files: {line_count.files}
Lines: {line_count.lines}
Classes: {line_count.classes}
Functions: {line_count.functions}
Coroutines: {line_count.coroutines}
Comments: {line_count.comments}```
            """)
            
            disk_io = psutil.disk_io_counters()
            disk_io_bytes_read = f"{get_size(disk_io.read_bytes)}"
            disk_io_bytes_send = f"{get_size(disk_io.write_bytes)}"

            embed.add_field(name="Disk:", value=f"""```yml
Read: {disk_io_bytes_read}
Send: {disk_io_bytes_send}```
            """)
            
            proc = await asyncio.create_subprocess_shell(
                'speedtest -f json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if ctx.debug:
                await ctx.send('Stdout: ' + (stdout.decode() or 'Empty.'))
                await ctx.send('Stderr: ' + (stderr.decode() or 'Empty.'))
                await ctx.send('Return Code: ' + str(proc.returncode))

            if not stdout or proc.returncode != 0 or stderr:
                s = speedtest.Speedtest()
                s.get_best_server()
                s.download()
                s.upload(pre_allocate=False)

                data = s.results.dict()

                try:
                    s.get_servers([23373, 37568])

                    s.download()
                    s.upload(pre_allocate=False)

                    data2 = s.results.dict()

                    if data['download'] < data2['download'] and data['upload'] < data2['upload']:
                        data = data2
                except Exception as e:
                    if ctx.debug:
                        raise e

                    pass

                embed.add_field(name="Speedtest:", value=f"""`{data['client']['isp']}, {data['client']['country']}` --> `{data['server']['sponsor']} - {data['server']['name']}, {data['server']['cc']}`: 
```yml
Download: {round(data['download'] / 1000000, 2)} Mbps
Upload: {round(data['upload'] / 1000000, 2)} Mbps
Ping: {round(data['ping'], 2)} ms

Bytes Sent: {round(data['bytes_sent'], 5)}
Bytes Recieved: {round(data['bytes_received'], 5)}
```Result URL: {'https://' + '.'.join(s.results.share().replace('http://', '').split('.')[:-1])}
                """, inline=False)
            else:
                data = json.loads(stdout.decode())

                embed.add_field(name="Speedtest:", value=f"""`{data['isp']}` --> `{data['server']['name']} - {data['server']['location']}, {data['server']['country']}`:
```yml
Download: 
- Result: {round(data['download']['bandwidth'] / 125000, 2)} Mbps
- Data Used: {get_size(data['download']['bytes'])}

Upload:
- Result: {round(data['upload']['bandwidth'] / 125000, 2)} Mbps
- Data Used: {get_size(data['upload']['bytes'])}

Ping:
- Jitter: {round(data['ping']['jitter'], 2)} ms
- Latency: {round(data['ping']['latency'], 2)} ms

Packet Loss: {str(round(data['packetLoss'], 2)) + '%' if 'packetLoss' in data else 'Not available.'}
```Result URL: {data['result']['url']}
                """, inline=False)

            embed.set_footer(text=f'PID: {os.getpid()}')

            await ctx.send(embed=embed)

    @Feature.Command(parent="jsk", name="restart", aliases=["rs", "rst", "reboot", "rbt", "rb"])
    async def jsk_restart(self, ctx: commands.Context):
        m = await ctx.send(embed=discord.Embed(description='<a:openrobot_searching_gif:899928367799885834> Restarting...', color=self.bot.color))

        with open('restart.json', 'w') as f:
            json.dump({'message_id': m.id, 'channel_id': m.channel.id, 'restarted_at': discord.utils.utcnow().timestamp()}, f, indent=4)

        await self.bot.close() # Let systemd handle the rest

    @Feature.Command(parent="jsk", name="debug", aliases=["dbg"])
    async def jsk_debug(self, ctx: commands.Context, *, command_string: str):
        """
        Run a command timing execution and catching exceptions.
        """

        alt_ctx = await copy_context_with(ctx, content=ctx.prefix + command_string)

        alt_ctx.debug = True # To trigger exceptions and stuff, a.k.a CDM (Command Debug Mode)

        if alt_ctx.command is None:
            return await ctx.send(f'Command "{alt_ctx.invoked_with}" is not found')

        start = time.perf_counter()

        async with ReplResponseReactor(ctx.message):
            with self.submit(ctx):
                returned = await alt_ctx.command.invoke(alt_ctx)

        end = time.perf_counter()
        return await ctx.send(f"Command `{alt_ctx.command.qualified_name}` finished in `{end - start:.3f}s`, returning `{returned}`")  

    @Feature.Command(parent="jsk", name="sync", aliases=["pull"])
    async def jsk_sync(self, ctx: commands.Context, *, extra: str = None):
        """
        Syncs the bot with GitHub.

        This will ask you if you want to:
        - `Restart the Bot`
        - `Reload pulled cogs (try to)`
        - `Do Nothing`
        """

        extra = f' {extra}' if extra else ''

        proc = await asyncio.create_subprocess_shell(
            f'git pull{extra}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        embed = discord.Embed(color=self.bot.color)

        embed.description = f"""```bash
{stdout.decode()}
{stderr.decode()}

Exited with code {proc.returncode}.```
        """

        embed.set_author(name='Sync', icon_url=ctx.author.avatar.url)

        await ctx.send(embed=embed)

        if proc.returncode == 0 and not stderr and stdout != 'Already up to date.':
            class View(discord.ui.View):
                def __init__(self, *, timeout: float | None = 180):
                    self.message = None
                    self.value = None

                    super().__init__(timeout=timeout)

                @discord.ui.button(label='Restart', style=discord.ButtonStyle.blurple)
                async def restart(self, button: discord.ui.Button, interaction: discord.Interaction):
                    self.value = 'restart'
                    
                    for child in self.children:
                        child.disabled = True

                    await interaction.message.edit(view=self)

                    self.stop()

                @discord.ui.button(label='Reload', style=discord.ButtonStyle.blurple)
                async def restart(self, button: discord.ui.Button, interaction: discord.Interaction):
                    self.value = 'reload'
                    
                    for child in self.children:
                        child.disabled = True

                    await interaction.message.edit(view=self)

                    self.stop()

                @discord.ui.button(label='Do Nothing', style=discord.ButtonStyle.blurple)
                async def restart(self, button: discord.ui.Button, interaction: discord.Interaction):
                    self.value = 'do_nothing'
                    
                    for child in self.children:
                        child.disabled = True

                    await interaction.message.edit(view=self)

                    self.stop()

                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                    if interaction.user != ctx.author:
                        await interaction.response.send_message('This is not your interaction!', ephemeral=True)
                        return False
                    
                    return True

                async def on_timeout(self):
                    for child in self.children:
                        child.disabled = True

                    await self.message.edit(view=self, content='Timed out.')

            view = View()

            view.message = await ctx.send('Please select an option.', view=view)

            val = await view.wait()

            if val or not view.value or view.value == 'do_nothing' or view.value not in ['do_nothing', 'restart', 'reload']:
                return

            if view.value == 'restart':
                return await self.jsk_restart(ctx)
            
            if view.value == 'reload':
                cogs_found = [
                    x.split(' | ')[0][:-3].replace('/', '.') 
                    for x in re.findall(r'cogs\/.*', stdout.decode()) 
                    if x.split(' | ')[0].endswith('.py') and \
                        len(r'\/', re.findall(x.split(' | ')[0])) == 1
                ]

                if not cogs_found:
                    return await ctx.send('No cogs found to reload.')

                warning_sign = '\U000026a0'
                inbox_tray = '\U0001f4e5'

                l = []

                for cog in cogs_found:
                    try:
                        self.bot.reload_extension(cog)
                    except Exception as e:
                        l.append(f'{warning_sign} {cog}: {e}')
                    else:
                        l.append(f'{inbox_tray} {cog}')

                return await ctx.send('\n'.join(l))
        else:
            return

def setup(bot):
    bot.add_cog(Jishaku(bot=bot))
import os
import re
import sys
import pathlib
import asyncio
import subprocess

class RunShell:
    def __init__(self,
                 command: list[str] | str,
                 *,
                 loop: asyncio.AbstractEventLoop = None
    ):
        if sys.platform == "win32":
            # Check for powershell
            if pathlib.Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe").exists():
                self.decoded_command = ['powershell', command]
            else:
                self.decoded_command = ['cmd', '/c', command]
        else:
            self.decoded_command = [os.getenv('SHELL') or '/bin/bash', '-c', command]

        self.command = command
        self.loop = loop or asyncio.get_event_loop()

        self.process = subprocess.Popen(self.decoded_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.stdout = None
        self.stderr = None
        self.close_code = None

    @staticmethod
    def clean_line(line) -> str | None:
        if not line:
            return line
        elif not isinstance(line, str):
            try:
                line = line.decode('utf-8')
            except:
                line = str(line)

        line = line.replace('\r', '').strip('\n')
        return re.sub(r'\x1b[^m]*m', '', line).replace("``", "`\u200b`").strip('\n')

    @property
    def result(self) -> tuple[str | None, str | None, int | None]:
        return self.clean_line(self.stdout), self.clean_line(self.stderr), int(self.clean_line(self.close_code))

    async def run(self):
        return await self.loop.run_in_executor(None, self._run)

    def _run(self):
        self.stdout, self.stderr = self.process.communicate()

    def _stop(self):
        self.process.kill()
        self.process.terminate()
        self.close_code = self.process.wait(timeout=0.5)

    async def stop(self):
        return await self.loop.run_in_executor(None, self._stop)

    async def __aenter__(self):
        await self.run()
        await self.stop()
        return self

    def __enter__(self):
        self._run()
        self._stop()
        return self

    def __aexit__(self, exc_type, exc_val, exc_tb):
        #await self.stop()
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        #self._stop()
        pass

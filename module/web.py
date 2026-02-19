# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/2/19 18:50
# File:web.py
import os
import subprocess

from module import log
from module.ttyd import TTYD
from module.stdio import PanelTable
from module.language import _t
from module.enums import (
    Account,
    ENVIRON
)
from module.util import (
    gen_random_credential,
    get_subprocess_args
)


class Web(TTYD):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credential: dict = gen_random_credential()
        self.username: str = self.credential.get(Account.USERNAME)
        self.password: str = self.credential.get(Account.PASSWORD)
        self.port: int = int(os.environ.get(ENVIRON.TRMD_WEB_PORT, '0'))
        PanelTable(
            title='Web登录认证',
            header=(_t(Account.USERNAME), _t(Account.PASSWORD)),
            data=[[self.username, self.password]],
            show_lines=True
        ).print_meta()

    def run(self):
        process = None
        try:
            env: dict = os.environ.copy()
            env[ENVIRON.TRMD_WEB_PID] = str(os.getpid())
            env[ENVIRON.TRMD_WEB_PORT] = str(self.port)
            log.info(f'通过浏览器运行,父进程pid:{env.get(ENVIRON.TRMD_WEB_PID)},未写入系统环境变量。')
            cmd: list = [
                            self.ttyd_path,
                            '--writable',
                            '--port', str(self.port),
                            '--ipv6',
                            '--credential', f'{self.username}:{self.password}',
                            '--once',
                            '--browser'
                        ] + get_subprocess_args(self.main_file)
            log.info(f'通过浏览器运行,命令:"{cmd}"。')
            process = subprocess.Popen(cmd, env=env)
            os.environ[ENVIRON.TRMD_WEB_PID] = str(process.pid)
            log.info(f'通过浏览器运行,子进程pid:{os.environ.get(ENVIRON.TRMD_WEB_PID)},已写入系统环境变量。')
            process.wait()
            # TODO 将ttyd的运行日志重定向到rich.console。
            # TODO 账号密码明文记录在ttyd日志中带来的安全问题。
        except KeyboardInterrupt:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

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
    USERNAME: str = ''
    PASSWORD: str = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credential: dict = gen_random_credential()
        self.username: str = self.credential.get(Account.USERNAME)
        self.password: str = self.credential.get(Account.PASSWORD)
        self.port: int = int(os.environ.get(ENVIRON.TRMD_WEB_MODE, '0'))
        Web.USERNAME = self.username
        Web.PASSWORD = self.password
        PanelTable(
            title='Web登录认证',
            header=(_t(Account.USERNAME), _t(Account.PASSWORD)),
            data=[[self.username, self.password]],
            show_lines=True
        ).print_meta()

    def run(self):
        process = None
        try:
            cmd: list = [
                            self.ttyd_path,
                            '--writable',
                            '--cwd', os.getcwd(),
                            '--port', str(self.port),
                            '--ipv6',
                            '--credential', f'{self.username}:{self.password}',
                            '--browser'
                        ] + get_subprocess_args(self.main_file)
            log.info(f'通过浏览器运行,命令:"{cmd}"。')
            process = subprocess.Popen(cmd)
            process.wait()
            # TODO --cwd参数为中文路径需要添加双引号，但经过实测添加双引号也会报错。
            # TODO 将ttyd的运行日志重定向到rich.console。
        except KeyboardInterrupt:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

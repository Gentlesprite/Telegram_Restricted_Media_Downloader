# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/2/19 18:50
# File:web.py
import os
import socket
import platform
import subprocess

from module import (
    log,
    file_handler
)
from module.ttyd import TTYD
from module.stdio import PanelTable
from module.language import _t
from module.enums import (
    WebMeta,
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
        self.protocol: str = 'http'
        self.ip: str = '127.0.0.1'
        self.port: int = self.get_free_port()
        self.username: str = self.credential.get(WebMeta.USERNAME)
        self.password: str = self.credential.get(WebMeta.PASSWORD)

    @staticmethod
    def get_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', int(os.environ.get(ENVIRON.TRMD_WEB_PORT, '0'))))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]

    def run(self):
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
        if platform.system() == 'Windows':
            cmd.remove('--writable')
        log.info(f'通过浏览器运行,命令:"{cmd}"。')
        process = subprocess.Popen(cmd, env=env, stdout=file_handler.stream, stderr=file_handler.stream)
        os.environ[ENVIRON.TRMD_WEB_PID] = str(process.pid)
        PanelTable(
            title='Web配置',
            header=('属性', '内容'),
            data=[
                [_t(WebMeta.IP), self.ip],
                [_t(WebMeta.PORT), self.port],
                [_t(WebMeta.USERNAME), self.username],
                [_t(WebMeta.PASSWORD), self.password],
                ['访问链接', f'{self.protocol}://{self.ip}:{self.port}']
            ],
            show_lines=True
        ).print_meta()
        log.info(f'通过浏览器运行,子进程pid:{os.environ.get(ENVIRON.TRMD_WEB_PID)},已写入系统环境变量。')

# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/2/22 15:25
# File:tmux.py
import platform

from typing import Union
from pathlib import Path

from module import log
from module.util import is_nuitka


class TMUX:
    # https://github.com/pythops/tmux-linux-binary
    # https://github.com/marlocarlo/psmux
    MACHINE: dict = {
        'x86_64': 'tmux.linux-amd64',
        'amd64': 'tmux.exe',
        'armv6l': 'tmux.linux-arm64',
        'armv7l': 'tmux.linux-arm64',
        'aarch64': 'tmux.linux-arm64'
    }

    def __init__(self, main_file: str):
        self.main_file = main_file
        self.tmux_executable = self.get_tmux_executable()
        self.tmux_path = self.get_tmux_path()

    def get_tmux_path(self) -> Union[str]:
        if is_nuitka():
            path = str(Path(self.main_file).parent / self.tmux_executable)
            log.info(f'在编译环境获取tmux路径:"{path}"。')
            return path

        path = str(Path(f'res/bin/{self.tmux_executable}').resolve())
        log.info(f'在生产环境获取tmux路径:"{path}"。')
        return path

    @staticmethod
    def get_tmux_executable() -> str:
        return TMUX.MACHINE.get(platform.machine().lower())

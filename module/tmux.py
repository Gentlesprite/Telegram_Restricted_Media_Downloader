# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/2/22 15:25
# File:tmux.py
import os
import sys
import platform

from typing import Union
from pathlib import Path

from module import log
from module.util import (
    add_executable_permission,
    is_nuitka
)


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
        if not os.path.isfile(self.tmux_path):
            log.error(f'在"{os.path.dirname(self.tmux_path)}"目录下未找到"{os.path.basename(self.tmux_path)}"。')
            sys.exit(0)
        add_executable_permission(self.tmux_path)

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

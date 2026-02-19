# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/2/19 18:54
# File:ttyd.py
import os
import sys
import platform

from typing import Union
from pathlib import Path

from module import log
from module.util import add_executable_permission


class TTYD:
    MACHINE = {
        'x86_64': 'ttyd.x86_64',
        'amd64': 'ttyd.win32.exe',
        'i686': 'ttyd.i686',
        'i386': 'ttyd.i686',
        'armv6l': 'ttyd.arm',
        'armv7l': 'ttyd.armhf',
        'aarch64': 'ttyd.aarch64',
        'mips': 'ttyd.mips',
        'mipsel': 'ttyd.mipsel',
        'mips64': 'ttyd.mips64',
        'mips64el': 'ttyd.mips64el',
        's390x': 'ttyd.s390x'
    }

    def __init__(self, main_file: str):
        self.main_file = main_file
        self.ttyd_executable = self.get_ttyd_executable()
        self.ttyd_path = self.get_ttyd_path()
        if not os.path.isfile(self.ttyd_path):
            log.error(f'在"{os.path.dirname(self.ttyd_path)}"目录下未找到"{os.path.basename(self.ttyd_path)}"。')
            sys.exit(0)
        add_executable_permission(self.ttyd_path)

    def get_ttyd_path(self) -> Union[str]:
        if '__compiled__' in globals():
            path = str(Path(self.main_file).parent / self.ttyd_executable)
            log.info(f'在编译环境获取ttyd路径:"{path}"。')
            return path

        path = str(Path(f'res/bin/{self.ttyd_executable}').resolve())
        log.info(f'在生产环境获取ttyd路径:"{path}"。')
        return path

    @staticmethod
    def get_ttyd_executable() -> Union[str, None]:
        """获取对应平台的ttyd可执行文件。"""

        return TTYD.MACHINE.get(platform.machine().lower())

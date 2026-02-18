# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
import os
import sys
import subprocess

from module import log
from module.util import get_ttyd_path
from module.parser import PARSE_ARGS, get_subprocess_args
from module.downloader import TelegramRestrictedMediaDownloader

if __name__ == '__main__':
    if PARSE_ARGS.web:
        try:
            ttyd_path = get_ttyd_path(__file__)
            if not os.path.isfile(ttyd_path):
                log.error(f'在"{os.path.dirname(ttyd_path)}"目录下未找到"{os.path.basename(ttyd_path)}"。')
                sys.exit(0)

            cmd = [ttyd_path,
                   '--writable',
                   '--cwd', os.getcwd(),
                   '--port', '0',
                   '--browser'
                   ] + get_subprocess_args(__file__)
            log.info(f'通过浏览器运行,命令:"{cmd}"。')
            subprocess.Popen(cmd)
            # TODO --cwd参数为中文路径需要添加双引号，但经过实测添加双引号也会报错。
            # TODO 在Linux下，需要考虑执行权限的问题。
            # TODO 将ttyd的运行日志重定向到rich.console。
        except KeyboardInterrupt:
            pass  # TODO keyboard interrupt时，需要按两次的问题。
    else:
        trmd = TelegramRestrictedMediaDownloader()
        trmd.run()

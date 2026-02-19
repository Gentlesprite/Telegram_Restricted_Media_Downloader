# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
import os
import sys
import subprocess

from module import log
from module.util import (
    get_ttyd_path,
    add_executable_permission
)
from module.parser import (
    PARSE_ARGS,
    get_subprocess_args
)
from module.downloader import TelegramRestrictedMediaDownloader

if __name__ == '__main__':
    if PARSE_ARGS.web:
        process = None
        try:
            ttyd_path = get_ttyd_path(__file__)
            if not os.path.isfile(ttyd_path):
                log.error(f'在"{os.path.dirname(ttyd_path)}"目录下未找到"{os.path.basename(ttyd_path)}"。')
                sys.exit(0)

            add_executable_permission(ttyd_path)
            credential = 'admin:123456'
            cmd = [ttyd_path,
                   '--writable',
                   '--cwd', os.getcwd(),
                   '--port', '0',
                   '--ipv6',
                   '--credential', credential,
                   '--browser'
                   ] + get_subprocess_args(__file__)
            log.info(f'通过浏览器运行,命令:"{cmd}"。')
            process = subprocess.Popen(cmd)
            process.wait()
            # TODO --cwd参数为中文路径需要添加双引号，但经过实测添加双引号也会报错。
            # TODO 将ttyd的运行日志重定向到rich.console。
            # TODO ttyd使用随机端口，可能该端口未开放的问题。
            # TODO --web参数后考虑指定端口。
        except KeyboardInterrupt:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
    else:
        trmd = TelegramRestrictedMediaDownloader()
        trmd.run()

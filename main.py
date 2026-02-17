# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
import os
import sys
import subprocess

from module.parser import PARSE_ARGS
from module.downloader import TelegramRestrictedMediaDownloader


def build_subprocess_args():
    """构建子进程参数列表。"""
    args = [sys.argv[0]] if '__compiled__' in globals() else [sys.executable, __file__]

    # 添加非web参数
    if PARSE_ARGS.quiet:
        args.append('--quiet')
    if PARSE_ARGS.config:
        args.extend(['--config', PARSE_ARGS.config])
    if PARSE_ARGS.session:
        args.extend(['--session', PARSE_ARGS.session])
    if PARSE_ARGS.temp:
        args.extend(['--temp', PARSE_ARGS.temp])

    return args


if __name__ == '__main__':
    if PARSE_ARGS.web:
        try:
            subprocess_args = build_subprocess_args()
            subprocess.Popen(
                ['ttyd', '--writable', '--cwd', os.getcwd(), '--port', '0', '--browser'] + subprocess_args
            )
            # TODO --cwd参数为中文路径需要添加双引号，否则报错。
            # TODO ttyd跨平台的问题。
        except KeyboardInterrupt:
            pass  # TODO keyboard interrupt时，需要按两次的问题。
    else:
        trmd = TelegramRestrictedMediaDownloader()
        trmd.run()

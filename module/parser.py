# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/1/23 17:47
# File:parser.py
import sys

from typing import Optional
from argparse import (
    ArgumentParser,
    SUPPRESS
)

from pyrogram import __version__ as pyrogram_version

from module import __version__
from module.enums import (
    Banner,
    GradientColor,
    console
)


class TelegramRestrictedMediaDownloaderArgumentParser(ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument(
            '-h', '--help',
            action='help',
            default=SUPPRESS,
            help='展示帮助'
        )
        self.add_argument(
            '-v', '--version',
            action='version',
            version=f'TRMD {__version__} (pyrogram {pyrogram_version})',
            default=SUPPRESS,
            help='展示版本信息'
        )
        self.add_argument(
            '-q', '--quiet',
            action='store_true',
            default=False,
            help='跳过重新配置文件的确认提示'
        )
        self.add_argument(
            '-c', '--config',
            type=str,
            required=False,
            default='',
            help='设置用户配置文件的路径'
        )
        self.add_argument(
            '-s', '--session',
            type=str,
            required=False,
            default='',
            help='设置会话文件的路径'
        )
        self.add_argument(
            '-t', '--temp',
            type=str,
            required=False,
            default='',
            help='设置运行缓存的路径'
        )
        self.add_argument(
            '-w', '--web',
            action='store_true',
            default=False,
            help='通过浏览器运行'
        )

    def print_help(self, file=None):
        console.print(
            GradientColor.gen_gradient_text(
                text=Banner.TRMD,
                gradient_color=GradientColor.generate_gradient(
                    start_color='#fa709a',
                    end_color='#fee140',
                    steps=10)),
            style='bold',
            highlight=False
        )
        super().print_help(file)


PARSE_ARGS = TelegramRestrictedMediaDownloaderArgumentParser(add_help=False).parse_args()


def get_subprocess_args(file: Optional[str]) -> list:
    """获取子进程参数列表。"""
    args = [sys.argv[0]] if '__compiled__' in globals() else [sys.executable, file or __file__]
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

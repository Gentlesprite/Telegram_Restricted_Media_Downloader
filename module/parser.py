# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/1/23 17:47
# File:parser.py
from argparse import (
    ArgumentParser,
    SUPPRESS
)

from module.stdio import MetaData
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
            help='帮助'
        )
        self.add_argument(
            '-cp', '--config_path',
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
        MetaData.print_about()
        super().print_help(file)

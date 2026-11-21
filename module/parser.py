# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026-01-23 17:47:00
# File:parser.py
from argparse import (
    SUPPRESS,
    ArgumentParser
)

from module.language import _
from module import (
    console,
    VERSION_SEMVER,
    SOFTWARE_SHORT_NAME,
    TestLevel
)
from module.enums import (
    Banner,
    WebMeta,
    GradientColor
)


class TelegramRestrictedMediaDownloaderArgumentParser(ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument(
            '-h', '--help',
            action='help',
            default=SUPPRESS,
            help=_('Show help')
        )
        self.add_argument(
            '-v', '--version',
            action='version',
            version=f'{SOFTWARE_SHORT_NAME} {VERSION_SEMVER}',
            default=SUPPRESS,
            help=_('Show version information')
        )
        self.add_argument(
            '-q', '--quiet',
            action='store_true',
            default=False,
            help=_('Skip the confirmation prompt for reconfiguring the file')
        )
        self.add_argument(
            '-c', '--config',
            type=str,
            required=False,
            default='',
            help=_('Set the path to the user configuration file')
        )
        self.add_argument(
            '-s', '--session',
            type=str,
            required=False,
            default='',
            help=_('Set the path to the session file')
        )
        self.add_argument(
            '-t', '--temp',
            type=str,
            required=False,
            default='',
            help=_('Set the path to the runtime cache')
        )
        self.add_argument(
            '-p', '--port',
            type=int,
            nargs='?',
            metavar='PORT',
            const=WebMeta.DEFAULT_PORT,
            default=WebMeta.DEFAULT_PORT,
            help=_('Set the web panel port')
        )
        self.add_argument(
            '--test',
            nargs='?',
            const=TestLevel.INFO,
            default=False,
            help=SUPPRESS
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

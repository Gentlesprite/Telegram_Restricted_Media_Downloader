# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024-09-05 19:08:00
# File:main.py
from module.parser import PARSE_ARGS  # noqa: F401.
from module.downloader import TelegramRestrictedMediaDownloader

if __name__ == '__main__':
    trmd = TelegramRestrictedMediaDownloader()
    trmd.run()

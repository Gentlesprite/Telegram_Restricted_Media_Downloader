# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
from module.parser import PARSE_ARGS
from module.web import Web
from module.downloader import TelegramRestrictedMediaDownloader

if __name__ == '__main__':
    if PARSE_ARGS.web:
        web = Web(__file__)
        web.run()
    else:
        trmd = TelegramRestrictedMediaDownloader()
        trmd.run()

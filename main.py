# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
import os

from module.enums import ENVIRON
from module.util import check_environ
from module.web import Web
from module.downloader import TelegramRestrictedMediaDownloader

if __name__ == '__main__':
    check_environ()
    if os.environ.get(ENVIRON.TRMD_WEB_PORT) and os.environ.get(ENVIRON.TRMD_WEB_PID) is None:
        web = Web(__file__)
        web.run_once()
    else:
        trmd = TelegramRestrictedMediaDownloader()
        trmd.run()

# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
from module.stdio import MetaData
from module.downloader import TelegramRestrictedMediaDownloader

if __name__ == '__main__':
    MetaData.print_helper()
    trmd = TelegramRestrictedMediaDownloader()
    trmd.run()

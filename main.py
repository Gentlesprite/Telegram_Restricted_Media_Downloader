# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/9/5 19:08
# File:main.py
from module.downloader import TelegramRestrictedMediaDownloader

if __name__ == '__main__':
    trmd = TelegramRestrictedMediaDownloader()
    trmd.run()

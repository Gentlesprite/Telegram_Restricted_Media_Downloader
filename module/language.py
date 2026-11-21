# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025-03-01 01:15:00
# File:language.py
import os
import gettext

LOCALE_DIRECTORY: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locale')
TRANSLATION = gettext.translation(domain='trmd', localedir=LOCALE_DIRECTORY, languages=['zh_CN'], fallback=True)
_ = TRANSLATION.gettext

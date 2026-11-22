# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025-03-01 01:15:00
# File:language.py
import os
import re
import sys
import ctypes
import locale
import gettext

from typing import (
    List,
    Dict,
    Optional
)


class Language:
    LOCALE_DIRECTORY: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locale')
    SUPPORTED: Dict[str, Dict[str, List[str]]] = {
        'zh_CN': {
            'aliases': [
                'zh',
                'zh_cn',
                'zh_hans',
                'zh_sg',
                'zh_tw',
                'zh_hk',
                'zh_mo',
                'zh_hant',
                'chinese'
            ]
        }
    }
    DEFAULT: str = 'en_US'

    def __init__(
            self,
            language: str = ''
    ):
        self.detected: str = language or self.detect()
        self.language: str = self.normalize(self.detected)
        self.translation = self.get_translation()

    def normalize(
            self,
            raw: str
    ) -> str:
        if not raw:
            return self.DEFAULT
        normalized: str = re.sub(r'[^a-z0-9_]', '_', raw.replace('-', '_').lower())
        normalized: str = re.sub(r'_+', '_', normalized).strip('_')
        for code, config in self.SUPPORTED.items():
            for alias in config['aliases']:
                if normalized == alias or normalized.startswith(alias + '_'):
                    return code
        return self.DEFAULT

    @staticmethod
    def detect() -> str:
        for env_key in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
            env_language: str = os.environ.get(env_key, '')
            if env_language and env_language != 'C':
                return env_language
        if sys.platform == 'win32':
            try:
                language_id: int = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # noqa.
                windows_locale: Optional[str] = locale.windows_locale.get(language_id, '')
                if windows_locale:
                    return windows_locale
            except Exception:  # noqa.
                pass
        try:
            return locale.getlocale(locale.LC_ALL)[0] or ''
        except Exception:  # noqa.
            return ''

    def get_translation(self):
        if self.language == self.DEFAULT or self.language not in self.SUPPORTED:
            return gettext.NullTranslations()
        return gettext.translation(
            domain='trmd',
            localedir=self.LOCALE_DIRECTORY,
            languages=[self.language],
            fallback=True
        )


lang = Language()
translation = lang.translation
_ = lang.translation.gettext

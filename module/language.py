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

import yaml

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
                'zh_hant',  # noqa.
                'chinese'
            ]
        },
        'en_US': {
            'aliases': [
                'en',
                'en_us',
                'english'
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

    @classmethod
    def parse_cli_language(cls) -> str:
        for index, arg in enumerate(sys.argv[1:], start=1):
            if arg in ('-l', '--language'):
                next_args = sys.argv[index + 1:]
                if next_args and not next_args[0].startswith('-'):
                    return next_args[0]
            if arg.startswith('--language='):
                return arg.split('=', 1)[1]
            if arg.startswith('-l') and len(arg) > 2:
                return arg[2:]
        return ''

    @staticmethod
    def read_config_language() -> str:
        """读取全局配置文件中保存的界面语言。"""
        appdata_path: str = os.path.join(
            os.environ.get('APPDATA') or os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
            'TRMD'
        )
        config_path: str = os.path.join(appdata_path, '.CONFIG.yaml')
        if not os.path.isfile(config_path):
            return ''
        try:
            with open(file=config_path, mode='r', encoding='UTF-8') as file:
                config: dict = yaml.safe_load(file) or {}
            return str(config.get('language') or '')
        except Exception:  # noqa.
            return ''

    @classmethod
    def is_supported(cls, raw: str) -> bool:
        if not raw:
            return False
        normalized: str = re.sub(r'[^a-z0-9_]', '_', raw.replace('-', '_').lower())
        normalized: str = re.sub(r'_+', '_', normalized).strip('_')
        for code, config in cls.SUPPORTED.items():
            aliases: List[str] = [code.lower()] + config['aliases']
            if any(normalized == alias or normalized.startswith(alias + '_') for alias in aliases):
                return True
        return False

    def normalize(
            self,
            raw: str
    ) -> str:
        if not raw:
            return self.DEFAULT
        normalized: str = re.sub(r'[^a-z0-9_]', '_', raw.replace('-', '_').lower())
        normalized: str = re.sub(r'_+', '_', normalized).strip('_')
        for code, config in self.SUPPORTED.items():
            aliases: List[str] = [code.lower()] + config['aliases']
            if any(normalized == alias or normalized.startswith(alias + '_') for alias in aliases):
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


cli_language: str = Language.parse_cli_language()
config_language: str = Language.read_config_language()
raw_language: str = cli_language if Language.is_supported(cli_language) else config_language
lang = Language(raw_language if Language.is_supported(raw_language) else '')
translation = lang.translation
_ = lang.translation.gettext

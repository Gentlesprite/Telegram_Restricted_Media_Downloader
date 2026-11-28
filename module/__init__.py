# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023-11-18 12:28:18
# File:__init__.py
import os
import sys
import atexit
import logging
import platform

from logging.handlers import RotatingFileHandler

import yaml

from module.language import _
from rich.console import Console
from rich.logging import RichHandler


def read_input_history(history_path: str, max_record_len: int, **kwargs) -> None:
    if kwargs.get('platform') == 'Windows':
        # 尝试读取历史记录文件。
        import readline
        readline.backend = 'readline'
        try:
            readline.read_history_file(history_path)
        except FileNotFoundError:
            pass
        # 设置历史记录的最大长度。
        readline.set_history_length(max_record_len)
        # 注册退出时保存历史记录。
        atexit.register(readline.write_history_file, history_path)


def via_log_level(log_level: str, param_name: str, default_level: int = logging.INFO) -> bool:
    if log_level not in ['CRITICAL', 'FATAL', 'ERROR', 'WARN', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']:
        with open(file=GLOBAL_CONFIG_PATH, mode='w', encoding='UTF-8') as file:
            global_config[param_name] = logging.getLevelName(default_level)
            yaml.dump(global_config, file)
        return False
    return True


def get_test_level() -> str:
    """从命令行参数解析--test的等级。"""
    for arg in sys.argv[1:]:
        if arg == '--test':
            return TestLevel.INFO
        if arg.startswith('--test='):
            value = arg.split('=', 1)[1].strip().lower()
            if value in TestLevel():
                return value
            return TestLevel.INFO
    return ''


class CustomDumper(yaml.Dumper):

    def represent_none(self, data):
        """自定义将yaml文件中None表示为~。"""
        return self.represent_scalar('tag:yaml.org,2002:null', '~')


class CallerFilter(logging.Filter):
    PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    """为日志记录补充上层调用者信息,格式为"模块名.函数名"。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rel_path: str = os.path.relpath(record.pathname, CallerFilter.PROJECT_PATH)
            module_path: str = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        except Exception:  # noqa.
            module_path: str = record.module
        # 先写入默认值,保证后续任何分支返回时格式化字段都完整。
        # 若缺失字段,格式化日志时会抛出"Formatting field not found in record"(如在函数外直接调用日志)。
        record.name_part = '' if record.name == 'rich' else f'{record.name}:'
        record.caller_name = ''  # 没有上层调用者时留空,连分隔符一起省略。
        record.file_func = f'{module_path}.{record.funcName}'
        frame = sys._getframe(1)
        # 回溯到实际调用日志的帧(record的pathname与lineno即为其位置)。
        while frame is not None:
            if frame.f_code.co_filename == record.pathname and frame.f_lineno == record.lineno:
                break
            frame = frame.f_back
        caller_frame = frame.f_back if frame is not None else None
        if caller_frame is None:  # 在模块顶层等没有上层调用者的位置记录日志。
            return True
        func_name: str = caller_frame.f_code.co_name
        # 项目内的调用者显示完整模块名,第三方与标准库仅显示函数名,避免名称过长导致换行。
        if caller_frame.f_code.co_filename.startswith(CallerFilter.PROJECT_PATH):
            record.caller_name = f'{caller_frame.f_globals.get("__name__", "")}.{func_name}:'
        else:
            record.caller_name = f'{func_name}:'
        return True


class TestLevel:
    INFO: str = 'info'
    DEBUG: str = 'debug'
    CONSOLE_INFO: str = 'console_info'
    CONSOLE_DEBUG: str = 'console_debug'
    FILE_INFO: str = 'file_info'
    FILE_DEBUG: str = 'file_debug'

    @classmethod
    def console_info_levels(cls):
        return cls.INFO, cls.CONSOLE_INFO

    @classmethod
    def console_debug_levels(cls):
        return cls.DEBUG, cls.CONSOLE_DEBUG

    @classmethod
    def file_info_levels(cls):
        return cls.INFO, cls.FILE_INFO

    @classmethod
    def file_debug_levels(cls):
        return cls.DEBUG, cls.FILE_DEBUG

    @classmethod
    def console_show_all_levels(cls):
        return cls.DEBUG, cls.CONSOLE_DEBUG, cls.CONSOLE_INFO

    @classmethod
    def file_show_all_levels(cls):
        return cls.DEBUG, cls.FILE_DEBUG, cls.FILE_INFO

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value


LOG_TIME_FORMAT = '[%Y-%m-%d %H:%M:%S]'
console = Console(log_path=False, log_time_format=LOG_TIME_FORMAT)
DOWNLOAD_TIMEOUT = 120
FORWARD_LIMIT = 33  # 每分钟允许的最大转发次数。
AUTHOR = 'Gentlesprite'
__version__ = '2.2.1'
__license__ = 'GPL-3.0-or-later'
__update_date__ = '2026-11-28 17:41:26'
__copyright__ = _('Copyright (C) {year} {author} <https://github.com/{author}>').format(year=__update_date__[:4], author=AUTHOR)
REQUIRE_KURIGRAM_VERSION = (2, 2, 28)
SOFTWARE_FULL_NAME = 'Telegram Restricted Media Downloader'
SOFTWARE_SHORT_NAME = 'TRMD'
APPDATA_PATH = os.path.join(
    os.environ.get('APPDATA') or os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
    SOFTWARE_SHORT_NAME)
GLOBAL_CONFIG_NAME = '.CONFIG.yaml'
GLOBAL_CONFIG_PATH = os.path.join(APPDATA_PATH, GLOBAL_CONFIG_NAME)
PLATFORM = platform.system()
os.makedirs(APPDATA_PATH, exist_ok=True)  # v1.2.6修复初次运行打开报错问题。
INPUT_HISTORY_PATH = os.path.join(APPDATA_PATH, f'.{SOFTWARE_SHORT_NAME}_HISTORY')
MAX_RECORD_LENGTH = 1000
read_input_history(history_path=INPUT_HISTORY_PATH, max_record_len=MAX_RECORD_LENGTH, platform=PLATFORM)
LOG_PATH = os.path.join(APPDATA_PATH, f'{SOFTWARE_SHORT_NAME}_LOG.log')
MAX_LOG_SIZE = 200 * 1024 * 1024  # 200MB
BACKUP_COUNT = 0  # 不保留日志文件。
LOG_FORMAT = '%(name_part)s%(caller_name)s%(file_func)s:%(lineno)d - %(message)s'
FILE_LOG_LEVEL: int = logging.INFO
CONSOLE_LOG_LEVEL: int = logging.WARNING
REFERRAL_RECORD_PATH: str = os.path.join(APPDATA_PATH, f'.{SOFTWARE_SHORT_NAME}_REFERRAL')
TRMD_WEB_SESSION: str = os.path.join(APPDATA_PATH, f'.{SOFTWARE_SHORT_NAME}_WEB_SESSION')
TEST_LEVEL: str = get_test_level()
# 配置日志文件处理器(文件记录)
file_handler = RotatingFileHandler(
    filename=LOG_PATH,
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding='UTF-8'
)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s' + ' ' + LOG_FORMAT, datefmt=LOG_TIME_FORMAT))

if os.path.exists(GLOBAL_CONFIG_PATH):
    try:
        with open(file=GLOBAL_CONFIG_PATH, mode='r', encoding='UTF-8') as f:
            global_config = yaml.safe_load(f)
        file_log_level: str = global_config.get('file_log_level')
        console_log_level: str = global_config.get('console_log_level')
        if via_log_level(log_level=file_log_level, param_name='file_log_level', default_level=logging.INFO):
            FILE_LOG_LEVEL: int = logging.getLevelName(file_log_level)
        if via_log_level(log_level=console_log_level, param_name='console_log_level', default_level=logging.WARNING):
            CONSOLE_LOG_LEVEL: int = logging.getLevelName(console_log_level)
    except Exception:  # noqa.
        pass

if TEST_LEVEL:
    if TEST_LEVEL in TestLevel.console_debug_levels():
        CONSOLE_LOG_LEVEL = min(CONSOLE_LOG_LEVEL, logging.DEBUG)
    elif TEST_LEVEL in TestLevel.console_info_levels():
        CONSOLE_LOG_LEVEL = min(CONSOLE_LOG_LEVEL, logging.INFO)
    if TEST_LEVEL in TestLevel.file_debug_levels():
        FILE_LOG_LEVEL = min(FILE_LOG_LEVEL, logging.DEBUG)
    elif TEST_LEVEL in TestLevel.file_info_levels():
        FILE_LOG_LEVEL = min(FILE_LOG_LEVEL, logging.INFO)

file_handler.setLevel(logging.getLevelName(FILE_LOG_LEVEL))
file_handler.addFilter(CallerFilter())
# 配置日志终端记录器(控制台输出)
console_handler = RichHandler(
    level=CONSOLE_LOG_LEVEL,  # 控制台只显示WARNING及以上级别。
    console=console,
    rich_tracebacks=True,
    show_path=False,
    omit_repeated_times=True,
    log_time_format=LOG_TIME_FORMAT
)
console_handler.addFilter(CallerFilter())
# 配置日志记录器(根记录器设置为最低级别 DEBUG)
logging.basicConfig(
    level=logging.DEBUG,  # 根记录器设置为DEBUG,允许所有日志通过。
    format=LOG_FORMAT,
    datefmt=LOG_TIME_FORMAT,
    handlers=[
        console_handler,  # 控制台:WARNING+
        file_handler  # 文件:INFO+
    ]
)


class PyrogramQuietFilter(logging.Filter):
    """按记录名与调用者命名空间屏蔽pyrogram的INFO/DEBUG日志。"""
    PYROGRAM_LOGGERS = (
        'pyrogram.client',
        'pyrogram.crypto',
        'pyrogram.session',
        'pyrogram.connection',
        'pyrogram.dispatcher',
        'pyrogram.methods.advanced.invoke',
        'module.client.invoke'
    )

    def filter(self, record: logging.LogRecord) -> bool:
        caller_name: str = getattr(record, 'caller_name', '')
        file_func: str = getattr(record, 'file_func', '')
        for name in PyrogramQuietFilter.PYROGRAM_LOGGERS:
            if (record.name == name
                    or record.name.startswith(name + '.')
                    or caller_name == name + ':'
                    or caller_name.startswith(name + '.')
                    or file_func == name
                    or file_func.startswith(name + '.')):
                if record.levelno < logging.WARNING:
                    return False
                break
        return True


# 定向到该输出端显示全部的等级(含console_info、file_info、debug、console_debug、file_debug)不附加静默过滤器,使pyrogram日志也能完整显示,其余默认等级(如info双端)仍按原逻辑过滤。
if CONSOLE_LOG_LEVEL > logging.DEBUG and TEST_LEVEL not in TestLevel.console_show_all_levels():
    console_handler.addFilter(PyrogramQuietFilter())
if FILE_LOG_LEVEL > logging.DEBUG and TEST_LEVEL not in TestLevel.file_show_all_levels():
    file_handler.addFilter(PyrogramQuietFilter())
log = logging.getLogger('rich')


def get_commit_hash():
    env_commit = os.environ.get('TRMD_COMMIT_HASH')
    if env_commit:
        log.debug(_('Commit hash from environment variable TRMD_COMMIT_HASH: {commit_hash}.').format(
            commit_hash=env_commit
        ))
        return env_commit
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.isdir(os.path.join(repo_root, '.git')):
        try:
            import subprocess
            completed = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            if completed.returncode == 0 and completed.stdout.strip():
                commit_hash: str = completed.stdout.strip()
                log.debug(_('Commit hash from git: {commit_hash}.').format(commit_hash=commit_hash))
                return commit_hash
        except Exception as e:
            log.debug(_('Failed to get commit hash due to "{error}"').format(error=e))
    return None


def get_build_time():
    env_build_time = os.environ.get('TRMD_BUILD_TIME')
    if env_build_time:
        log.debug(_('Build time from environment variable TRMD_BUILD_TIME: {build_time}.').format(
            build_time=env_build_time
        ))
        return env_build_time
    return None


COMMIT = get_commit_hash()
BUILD_TIME = get_build_time()
BUILD_META: str = '.'.join(part for part in (COMMIT, BUILD_TIME) if part)
VERSION_SEMVER = f'{__version__}+{BUILD_META}' if BUILD_META else __version__
VERSION_WITH_COMMIT = f'{__version__}+{COMMIT}' if COMMIT else __version__
CustomDumper.add_representer(type(None), CustomDumper.represent_none)  # noqa.
README = _(r'''
```yaml
api_hash: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # Requested api_hash.
api_id: 'xxxxxxxx' # Requested api_id.
# bot_token (optional). If left empty, the bot feature is unavailable. Get one at https://t.me/BotFather.
bot_token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
download_type: # Types to download. Supported: video,photo,document,audio,voice,animation.
- video # Video.
- photo # Photo.
- document # Document.
- audio # Audio.
- voice # Voice.
- animation # GIF.
- video_note # Video note.
- live_photo # Live photo (if not specified and photo is enabled, live_photo is treated as photo).
is_shutdown: true # Auto shutdown after download completes. Supported: true,false.
links: D:\path\where\your\link\files\save\content.txt # Link file format:
# Create a txt file with one link per line, fill in its path below without quotes, prepare it before running.
# D:\path\where\your\link\txt\save\content.txt One link per line.
max_retries:
  download: 5 # Max retry count for download tasks.
  upload: 3 # Max retry count for upload tasks.
max_tasks:
  download: 5 # Max concurrent download tasks.
  upload: 3 # Max concurrent upload tasks.
proxy: # Proxy settings. Set all to null if unused. Note: a space after each colon is required.
  enable_proxy: true # Enable proxy. Supported: true,false.
  hostname: 127.0.0.1 # Proxy IP address.
  scheme: socks5 # Proxy scheme. Supported: http,socks4,socks5.
  port: 10808 # Proxy port. Supported: 0~65535.
  username: null # Proxy username, null if none.
  password: null # Proxy password, null if none.
save_directory: F:\directory\media\where\you\save # Directory to save downloaded media (wildcards supported).
session_directory: F:\directory\session\where\you\save # Directory to save sessions (wildcards supported).
temp_directory: F:\directory\temp\where\you\save # Directory for temporary files (wildcards supported).
```
''')  # noqa.

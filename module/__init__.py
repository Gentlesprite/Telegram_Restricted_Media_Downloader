# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023/11/18 12:28:18
# File:__init__.py
import os
import atexit
import logging
import platform
from logging.handlers import RotatingFileHandler

import yaml
from pyrogram.session import Session
from pyrogram.types.messages_and_media import LinkPreviewOptions
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


class CustomDumper(yaml.Dumper):

    def represent_none(self, data):
        """自定义将yaml文件中None表示为~。"""
        return self.represent_scalar('tag:yaml.org,2002:null', '~')


LOG_TIME_FORMAT = '[%Y-%m-%d %H:%M:%S]'
console = Console(log_path=False, log_time_format=LOG_TIME_FORMAT)
MAX_FILE_REFERENCE_TIME = 600
Session.WAIT_TIMEOUT = 100
Session.START_TIMEOUT = 60
SLEEP_THRESHOLD = 60
AUTHOR = 'Gentlesprite'
__version__ = '1.8.0'
__license__ = 'MIT License'
__update_date__ = '2026/01/05 01:14:18'
__copyright__ = f'Copyright (C) 2024-{__update_date__[:4]} {AUTHOR} <https://github.com/Gentlesprite>'
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
# 配置日志输出到文件
LOG_PATH = os.path.join(APPDATA_PATH, f'{SOFTWARE_SHORT_NAME}_LOG.log')
MAX_LOG_SIZE = 200 * 1024 * 1024  # 200MB
BACKUP_COUNT = 0  # 不保留日志文件。
LINK_PREVIEW_OPTIONS = LinkPreviewOptions(is_disabled=True)
LOG_FORMAT = '%(name)s:%(funcName)s:%(lineno)d - %(message)s'
FILE_LOG_LEVEL: int = logging.INFO
CONSOLE_LOG_LEVEL: int = logging.WARNING
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
    except Exception:
        pass

file_handler.setLevel(logging.getLevelName(FILE_LOG_LEVEL))

# 配置日志终端记录器(控制台输出)
console_handler = RichHandler(
    level=CONSOLE_LOG_LEVEL,  # 控制台只显示WARNING及以上级别。
    console=console,
    rich_tracebacks=True,
    show_path=False,
    omit_repeated_times=False,
    log_time_format=LOG_TIME_FORMAT
)
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
log = logging.getLogger('rich')
log.info(f'{SOFTWARE_SHORT_NAME}:{__version__},更新日期:{__update_date__}。')
log.info(f'文件日志等级:"{logging.getLevelName(FILE_LOG_LEVEL)}"。')
log.info(f'终端日志等级:"{logging.getLevelName(CONSOLE_LOG_LEVEL)}"。')
CustomDumper.add_representer(type(None), CustomDumper.represent_none)
README = r'''
```yaml
# 这里只是介绍每个参数的含义,软件会详细地引导配置参数。
# 如果是按照软件的提示填,选看。如果是手动打开config.yaml修改配置,请仔细阅读下面内容。
# 手动填写时请注意冒号是英文冒号,冒号加一个空格。
api_hash: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # 申请的api_hash。
api_id: 'xxxxxxxx' # 申请的api_id。
# bot_token(选填)如果不填,就不能使用机器人功能。可前往https://t.me/BotFather免费申请。
bot_token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
download_type: # 需要下载的类型。支持的参数:video,photo,document,audio,voice,animation。
- video
- photo
- document
- audio
- voice
- animation
is_shutdown: true # 下载完成后是否自动关机。支持的参数:true,false。
links: D:\path\where\your\link\files\save\content.txt # 链接地址写法如下:
# 新建txt文本,一个链接为一行,将路径填入即可请不要加引号,在软件运行前就准备好。
# D:\path\where\your\link\txt\save\content.txt 一个链接一行。
max_retries:
  download: 5 # 最大的下载任务的重试次数。
  upload: 3 # 最大的上传任务的重试次数。
max_tasks:
  download: 5 # 最大同时下载的任务数。
  upload: 3 # 最大同时上传的任务数。
proxy: # 代理部分,如不使用请全部填null注意冒号后面有空格,否则不生效导致报错。
  enable_proxy: true # 是否开启代理。支持的参数:true,false。
  hostname: 127.0.0.1 # 代理的ip地址。
  scheme: socks5 # 代理的类型。支持的参数:http,socks4,socks5。
  port: 10808 # 代理ip的端口。支持的参数:0~65535。
  username: null # 代理的账号,没有就填null。
  password: null # 代理的密码,没有就填null。
save_directory: F:\directory\media\where\you\save # 下载的媒体保存的目录(支持通配符,不支持网络路径)。
```
'''

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
from pyrogram import utils
from pyrogram.session import Session
from rich.console import Console
from rich.logging import RichHandler


# v1.1.2 解决链接若附带/c字段即私密频道无法下载的问题,是由于pyrogram的问题:https://github.com/pyrogram/pyrogram/issues/1314
def get_peer_type_new(peer_id: int) -> str:
    peer_id_str = str(peer_id)
    if not peer_id_str.startswith('-'):
        return 'user'
    elif peer_id_str.startswith('-100'):
        return 'channel'
    else:
        return 'chat'


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


class CustomDumper(yaml.Dumper):

    def represent_none(self, data):
        """自定义将yaml文件中None表示为~。"""
        return self.represent_scalar('tag:yaml.org,2002:null', '~')


LOG_TIME_FORMAT = '[%Y-%m-%d %H:%M:%S]'
console = Console(log_path=False, log_time_format=LOG_TIME_FORMAT)
utils.get_peer_type = get_peer_type_new
MAX_FILE_REFERENCE_TIME = 600
Session.WAIT_TIMEOUT = 100
Session.START_TIMEOUT = 60
AUTHOR = 'Gentlesprite'
__version__ = '1.4.8'
__license__ = 'MIT License'
__update_date__ = '2025/03/07 18:35:38'
__copyright__ = f'Copyright (C) 2024-{__update_date__[:4]} {AUTHOR} <https://github.com/Gentlesprite>'
SOFTWARE_FULL_NAME = 'Telegram Restricted Media Downloader'
SOFTWARE_SHORT_NAME = 'TRMD'
APPDATA_PATH = os.path.join(
    os.environ.get('APPDATA') or os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
    SOFTWARE_SHORT_NAME)
PLATFORM = platform.system()
os.makedirs(APPDATA_PATH, exist_ok=True)  # v1.2.6修复初次运行打开报错问题。
INPUT_HISTORY_PATH = os.path.join(APPDATA_PATH, f'.{SOFTWARE_SHORT_NAME}_HISTORY')
MAX_RECORD_LENGTH = 1000
read_input_history(history_path=INPUT_HISTORY_PATH, max_record_len=MAX_RECORD_LENGTH, platform=PLATFORM)
# 配置日志输出到文件
LOG_PATH = os.path.join(APPDATA_PATH, f'{SOFTWARE_SHORT_NAME}_LOG.log')
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 0  # 不保留日志文件

# 配置日志文件处理器（支持日志轮换）
file_handler = RotatingFileHandler(
    filename=LOG_PATH,
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding='UTF-8'
)
file_handler.setFormatter(logging.Formatter("%(message)s"))
# 配置日志记录器
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s',
    datefmt=LOG_TIME_FORMAT,
    handlers=[
        RichHandler(rich_tracebacks=True,
                    console=console,  # v1.2.5传入控制台对象,修复报错时进度条打印错位
                    show_path=False,
                    omit_repeated_times=False,
                    log_time_format=LOG_TIME_FORMAT),
        file_handler  # 文件输出
    ]
)
log = logging.getLogger('rich')
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
download_type: # 需要下载的类型。支持的参数:video,photo。
- video 
- photo
is_shutdown: true # 下载完成后是否自动关机。支持的参数:true,false。
links: D:\path\where\your\link\files\save\content.txt # 链接地址写法如下:
# 新建txt文本,一个链接为一行,将路径填入即可请不要加引号,在软件运行前就准备好。
# D:\path\where\your\link\txt\save\content.txt 一个链接一行。
max_download_task: 3 # 最大的下载任务数,值过高可能会导致网络相关问题。支持的参数:所有>0的整数。
proxy: # 代理部分,如不使用请全部填null注意冒号后面有空格,否则不生效导致报错。
  enable_proxy: true # 是否开启代理。支持的参数:true,false。
  hostname: 127.0.0.1 # 代理的ip地址。
  scheme: socks5 # 代理的类型。支持的参数:http,socks4,socks5。
  port: 10808 # 代理ip的端口。支持的参数:0~65535。
  username: null # 代理的账号,没有就填null。
  password: null # 代理的密码,没有就填null。
save_path: F:\directory\media\where\you\save # 下载的媒体保存的目录。
```
'''

# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024-7-2 00:59:00
# File:enums.py
import os
import re
import sys
import time
import ipaddress
import platform

from functools import wraps
from dataclasses import dataclass
from typing import (
    Any,
    List,
    Union,
    Tuple,
    Optional,
    Callable
)

from module import (
    log,
    console
)
from module.language import _t


class LinkType:
    SINGLE: str = 'single'
    GROUP: str = 'group'
    COMMENT: str = 'comment'
    TOPIC: str = 'topic'


@dataclass
class Link:
    # https://github.com/tangyoha/telegram_media_downloader/blob/master/utils/format.py#L14
    group_id: Union[str, int, None] = None
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    topic_id: Optional[int] = None


class DownloadType:
    VIDEO: str = 'video'
    PHOTO: str = 'photo'
    DOCUMENT: str = 'document'
    AUDIO: str = 'audio'
    VOICE: str = 'voice'
    ANIMATION: str = 'animation'
    VIDEO_NOTE: str = 'video_note'
    LIVE_PHOTO: str = 'live_photo'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value


class DownloadStatus:
    PENDING = 'pending'
    DOWNLOADING = 'downloading'
    SUCCESS = 'success'
    FAILURE = 'failure'
    SKIP = 'skip'
    RETRY = 'retry'


class UploadStatus:
    PENDING = 'pending'
    UPLOADING = 'uploading'
    SUCCESS = 'success'
    FAILURE = 'failure'
    SENT = 'sent'


class NoticeType:
    DOWNLOAD: str = 'download'  # 下载。
    UPLOAD: str = 'upload'  # 上传。
    FORWARD: str = 'forward'  # 转发。

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value


class CalenderKeyboard:
    START_TIME_BUTTON: str = 'start time button'
    END_TIME_BUTTON: str = 'end time button'


class SaveDirectoryPrefix:
    CHAT_ID: str = '%CHAT_ID%'
    CHAT_NAME: str = '%CHAT_NAME%'
    MIME_TYPE: str = '%MIME_TYPE%'
    MESSAGE_ID: str = '%MESSAGE_ID%'
    MESSAGE_ID_WITH_ENTITIES: str = '%MESSAGE_ID_WITH_ENTITIES%'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value


class WebMeta:
    IP: str = 'IP'
    PORT: str = 'port'
    USERNAME: str = 'username'
    PASSWORD: str = 'password'
    COOKIE_NAME: str = 'TRMD_WEB_SESSION'
    DEFAULT_PORT: int = 2921


class KeyWord:
    LINK: str = 'link'
    LINK_TYPE: str = 'link type'
    SIZE: str = 'size'
    STATUS: str = 'status'
    FILE: str = 'file'
    ERROR_SIZE: str = 'error size'
    ACTUAL_SIZE: str = 'actual size'
    ALREADY_EXIST: str = 'already exist'
    CHANNEL: str = 'channel'
    MESSAGE_ID: str = 'message id'
    TYPE: str = 'type'
    RE_DOWNLOAD: str = 're-download'
    RE_UPLOAD: str = 're-upload'
    RETRY_TIMES: str = 'retry times'
    CURRENT_DOWNLOAD_TASK: str = 'current download task'
    CURRENT_UPLOAD_TASK: str = 'current upload task'
    REASON: str = 'reason'
    RESUME: str = 'resume'
    DOWNLOAD_TASK: str = 'download task'
    UPLOAD_TASK: str = 'upload task'
    DOWNLOAD_AND_UPLOAD_TASK: str = 'download and upload task'
    FORWARD_SUCCESS: str = 'forward success'
    FORWARD_FAILURE: str = 'forward failure'
    FORWARD_SKIP: str = 'skip forward'
    UPLOAD_FILE_PART: str = 'upload file part'
    CHINESE_PATH_WARNING: str = 'chinese path warning'
    INVALID_API_ID: str = 'invalid api id'
    API_ID_TOO_LONG: str = 'api id too long'
    API_ID_NEED_QUOTES: str = 'api id need quotes'
    DIRECTORY_NOT_EXIST: str = 'directory not exist'
    DIRECTORY_CREATED: str = 'directory created'
    INVALID_YES_NO: str = 'invalid yes no'
    UNSUPPORTED_DTYPE: str = 'unsupported dtype'
    SYSTEM_PROXY_FOUND: str = 'system proxy found'
    AUTO_PROXY_VALUE: str = 'auto proxy value'
    PROXY_NOT_CONFIG: str = 'proxy not config'
    PROXY_AUTH_EMPTY: str = 'proxy auth empty'
    UNKNOWN: str = 'unknown'
    ASK_SAVE_CONFIG: str = 'ask save config'
    ASK_RECONFIG: str = 'ask reconfig'
    ASK_CHANGE_ACCOUNT: str = 'ask change account'
    ASK_SESSION_DIRECTORY: str = 'ask session directory'
    ASK_LAST_RECORD: str = 'ask last record'
    ASK_BOT_TOKEN: str = 'ask bot token'
    ASK_ENABLE_BOT: str = 'ask enable bot'
    ASK_LINKS: str = 'ask links'
    ASK_SAVE_DIRECTORY: str = 'ask save directory'
    ASK_MAX_DOWNLOAD_TASK: str = 'ask max download task'
    ASK_MAX_RETRY_COUNT: str = 'ask max retry count'
    ASK_DOWNLOAD_TYPE: str = 'ask download type'
    ASK_IS_SHUTDOWN: str = 'ask is shutdown'
    ASK_ENABLE_PROXY: str = 'ask enable proxy'
    ASK_SCHEME: str = 'ask scheme'
    ASK_HOSTNAME: str = 'ask hostname'
    ASK_PORT: str = 'ask port'
    ASK_PROXY_AUTH: str = 'ask proxy auth'
    ASK_USERNAME: str = 'ask username'
    ASK_PASSWORD: str = 'ask password'
    INVALID_PARAM: str = 'invalid param'
    INVALID_PARAM_DEFAULT: str = 'invalid param default'
    INVALID_PARAM_BANG: str = 'invalid param bang'
    INVALID_HASH: str = 'invalid hash'
    INVALID_BOT_TOKEN: str = 'invalid bot token'
    INVALID_LINKS_FORMAT: str = 'invalid links format'
    LINKS_NOT_EXIST: str = 'links not exist'
    DEFAULT_SAVE_DIR: str = 'default save dir'
    SAVE_DIR_IS_FILE: str = 'save dir is file'
    SAVE_DIR_INVALID: str = 'save dir invalid'
    INVALID_TASK: str = 'invalid task'
    INVALID_RETRY: str = 'invalid retry'
    INVALID_DTYPE: str = 'invalid dtype'
    REINPUT_DTYPE: str = 'reinput dtype'
    INVALID_ENABLE_PROXY: str = 'invalid enable proxy'
    INVALID_SCHEME: str = 'invalid scheme'
    INVALID_IP: str = 'invalid ip'
    INVALID_PORT_RANGE: str = 'invalid port range'
    INVALID_PORT: str = 'invalid port'
    INPUT_TIMEOUT: str = 'input timeout'
    NO_SWITCH_ACCOUNT: str = 'no switch account'
    SWITCH_ACCOUNT: str = 'switch account'
    SESSION_DIR_SET: str = 'session dir set'
    PARAM_SET: str = 'param set'
    BOT_DISABLED: str = 'bot disabled'
    CONFIG_BOT_TOKEN: str = 'config bot token'
    SHUTDOWN_YES: str = 'shutdown yes'
    SHUTDOWN_NO: str = 'shutdown no'
    PROXY_AUTH_YES: str = 'proxy auth yes'
    PROXY_AUTH_NO: str = 'proxy auth no'
    UNDEFINED: str = 'undefined'
    DEFAULT_N: str = 'default n'
    DEFAULT_3: str = 'default 3'
    DEFAULT_5: str = 'default 5'
    DEFAULT_ALL: str = 'default all'
    BOT_CONFIGURED_NOTICE: str = 'bot configured notice'
    BOT_STEP_DOWNLOAD_LINK: str = 'step download link'
    BOT_STEP_DOWNLOAD_CHAT_LINK: str = 'step download_chat link'
    BOT_STEP_UPLOAD_PATH: str = 'step upload path'
    BOT_STEP_UPLOAD_TARGET: str = 'step upload target'
    BOT_STEP_UPLOAD_R_PATH: str = 'step upload_r path'
    BOT_STEP_UPLOAD_R_TARGET: str = 'step upload_r target'
    BOT_STEP_FORWARD_ORIGIN: str = 'step forward origin'
    BOT_STEP_FORWARD_TARGET: str = 'step forward target'
    BOT_STEP_FORWARD_START_ID: str = 'step forward start_id'
    BOT_STEP_FORWARD_END_ID: str = 'step forward end_id'
    BOT_STEP_LISTEN_DOWNLOAD_ORIGIN: str = 'step listen_download origin'
    BOT_STEP_LISTEN_FORWARD_ORIGIN: str = 'step listen_forward origin'
    BOT_STEP_LISTEN_FORWARD_TARGET: str = 'step listen_forward target'
    BOT_MESSAGE_RIGHT: str = 'bot message right'
    BOT_MESSAGE_INVALID: str = 'bot message invalid'
    BOT_MESSAGE_TASK_ASSIGN: str = 'bot message task assign'
    BOT_MESSAGE_TOO_MANY_MESSAGE: str = 'bot message too many message'
    BOT_MESSAGE_TOO_MANY_INVALID_DOWNLOAD: str = 'bot message too many invalid download'
    BOT_MESSAGE_TOO_MANY_INVALID_FORWARD: str = 'bot message too many invalid forward'


class ConnectionState:
    CONNECTED: str = 'connected'
    CONNECTING: str = 'connecting'


class WaitingKind:
    NONE: str = 'none'
    RECONNECT: str = 'reconnect'
    FLOOD: str = 'flood'


class DownloadChatPromptWord:
    EARLIEST: str = 'earliest'
    LATEST: str = 'latest'
    NOT_SET: str = 'not set'
    ON: str = 'on'
    OFF: str = 'off'


class Issues:
    PROXY_NOT_CONFIGURED = '🛡️ [#79FCD4]代理配置方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\n[link=https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0]https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0[/link]\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCD4]文件夹下的[/#79FCD4][#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579][#79FCB5]中的[/#79FCB5][#D479FC]【问题14】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6]。[/#FC79A6]'  # noqa.
    SYSTEM_TIME_NOT_SYNCHRONIZED = '🕒 [#FCFF79]检测到[/#FCFF79][#FF7979]系统时间[/#FF7979][#FC79A5]未同步[/#FC79A5][#79E2FC],[/#79E2FC][#79FCD4]解决方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\nhttps://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/issues/5#issuecomment-2580677184\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCB5]中的[/#79FCB5][#D479FC]【问题4】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6],[/#FC79A6][#79FCD4]并[/#79FCD4][#79FCB5]重启软件[/#79FCB5]。'  # noqa.
    DOCKER_HOST_IP_TIP = '🐳 Docker环境下链接中的IP为容器IP并非宿主机IP,请使用宿主机IP加端口访问。'
    PROXY_CONFIG_TIP = '❓ [#79FCD4]如果对代理配置有疑问[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\n🌐 [link=https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#配置代理时在代理在本机的情况下]https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#配置代理时在代理在本机的情况下[/link]\n🛑 [#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问:[/#FF7979][#79FCD4]\n🔎 [/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCD4]文件夹下的[/#79FCD4][#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579][#79FCB5]中的[/#79FCB5][#D479FC]【问题14】里的【解决方案】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6]。[/#FC79A6]'
    MULTI_SESSION_TIP = '🔧 [#FF79D4]解决方法[/#FF79D4][#FCFF79](任选其一):[/#FCFF79]\n[#D4FC79]1.关闭多余实例。[/#D4FC79]\n[#D4FC79]2.使用[/#D4FC79]"[#79FCD4]{exe} --session SESSION[/#79FCD4]"[#D4FC79]指定新的SESSION位置后重试[/#D4FC79]([#FFB579]将SESSION替换为实际路径[/#FFB579])。'
    UPDATE_PACKAGE_TIP = '❌ [#FF7979]检测到({package_name})版本{current_version}与需求版本{require_version}不一致[/#FF7979][#FCFF79],可能已经引发兼容问题导致运行异常。[/#FCFF79]\n⚖️ [#D4FC79]需使用[/#D4FC79][#79FCD4]{command}[/#79FCD4][#D4FC79]升级或降级至需求版本{require_version}后重试[/#D4FC79][#D4FC79]。[/#D4FC79]'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value


class Language:
    ZH_CN: str = 'zh-CN'
    EN_US: str = 'en-US'

    @property
    def index(self):
        return {
            Language.ZH_CN: 0,
            Language.EN_US: 1
        }


class Extension:
    PHOTO = {
        'image/avif': 'avif',
        'image/bmp': 'bmp',
        'image/gif': 'gif',
        'image/ief': 'ief',
        'image/jpg': 'jpg',
        'image/jpeg': 'jpeg',
        'image/heic': 'heic',
        'image/heif': 'heif',
        'image/png': 'png',
        'image/svg+xml': 'svg',
        'image/tiff': 'tif',
        'image/vnd.microsoft.icon': 'ico',
        'image/x-cmu-raster': 'ras',
        'image/x-portable-anymap': 'pnm',
        'image/x-portable-bitmap': 'pbm',
        'image/x-portable-graymap': 'pgm',
        'image/x-portable-pixmap': 'ppm',
        'image/x-rgb': 'rgb',
        'image/x-xbitmap': 'xbm',
        'image/x-xpixmap': 'xpm',
        'image/x-xwindowdump': 'xwd'
    }
    VIDEO = {
        'video/mp4': 'mp4',
        'video/mpeg': 'mpg',
        'video/quicktime': 'qt',
        'video/webm': 'webm',
        'video/x-msvideo': 'avi',
        'video/x-sgi-movie': 'movie',
        'video/x-matroska': 'mkv'
    }
    REVERSE_PHOTO = {
        'avif': 'image/avif',
        'bmp': 'image/bmp',
        'gif': 'image/gif',
        'ief': 'image/ief',
        'jpg': 'image/jpg',
        'jpeg': 'image/jpeg',
        'heic': 'image/heic',
        'heif': 'image/heif',
        'png': 'image/png',
        'svg': 'image/svg+xml',
        'tif': 'image/tiff',
        'ico': 'image/vnd.microsoft.icon',
        'ras': 'image/x-cmu-raster',
        'pnm': 'image/x-portable-anymap',
        'pbm': 'image/x-portable-bitmap',
        'pgm': 'image/x-portable-graymap',
        'ppm': 'image/x-portable-pixmap',
        'rgb': 'image/x-rgb',
        'xbm': 'image/x-xbitmap',
        'xpm': 'image/x-xpixmap',
        'xwd': 'image/x-xwindowdump'
    }
    REVERSE_VIDEO = {
        'mp4': 'video/mp4',
        'mpg': 'video/mpeg',
        'qt': 'video/quicktime',
        'webm': 'video/webm',
        'avi': 'video/x-msvideo',
        'movie': 'video/x-sgi-movie',
        'mkv': 'video/x-matroska'
    }
    ALL_REVERSE = {
        'avif': 'image/avif',
        'bmp': 'image/bmp',
        'gif': 'image/gif',
        'ief': 'image/ief',
        'jpg': 'image/jpg',
        'jpeg': 'image/jpeg',
        'heic': 'image/heic',
        'heif': 'image/heif',
        'png': 'image/png',
        'svg': 'image/svg+xml',
        'tif': 'image/tiff',
        'ico': 'image/vnd.microsoft.icon',
        'ras': 'image/x-cmu-raster',
        'pnm': 'image/x-portable-anymap',
        'pbm': 'image/x-portable-bitmap',
        'pgm': 'image/x-portable-graymap',
        'ppm': 'image/x-portable-pixmap',
        'rgb': 'image/x-rgb',
        'xbm': 'image/x-xbitmap',
        'xpm': 'image/x-xpixmap',
        'xwd': 'image/x-xwindowdump',
        'video/mp4': 'mp4',
        'video/mpeg': 'mpg',
        'video/quicktime': 'qt',
        'video/webm': 'webm',
        'video/x-msvideo': 'avi',
        'video/x-sgi-movie': 'movie',
        'video/x-matroska': 'mkv'
    }


class GradientColor:
    # 生成渐变色:https://photokit.com/colors/color-gradient/?lang=zh
    BLUE2PURPLE_14 = [
        '#0ebeff',
        '#21b4f9',
        '#33abf3',
        '#46a1ed',
        '#5898e8',
        '#6b8ee2',
        '#7d85dc',
        '#907bd6',
        '#a272d0',
        '#b568ca',
        '#c75fc5',
        '#da55bf',
        '#ec4cb9',
        '#ff42b3'
    ]
    GREEN2PINK_11 = [
        '#00ff40',
        '#14f54c',
        '#29eb58',
        '#3de064',
        '#52d670',
        '#66cc7c',
        '#7ac288',
        '#8fb894',
        '#a3ada0',
        '#b8a3ac',
        '#cc99b8'
    ]
    GREEN2BLUE_10 = [
        '#84fab0',
        '#85f6b8',
        '#86f1bf',
        '#88edc7',
        '#89e9ce',
        '#8ae4d6',
        '#8be0dd',
        '#8ddce5',
        '#8ed7ec',
        '#8fd3f4'
    ]
    YELLOW2GREEN_10 = [
        '#d4fc79',
        '#cdfa7d',
        '#c6f782',
        '#bff586',
        '#b8f28b',
        '#b2f08f',
        '#abed94',
        '#a4eb98',
        '#9de89d',
        '#96e6a1'
    ]
    ORANGE2YELLOW_15 = [
        '#f08a5d',
        '#f1915e',
        '#f1985f',
        '#f29f60',
        '#f3a660',
        '#f3ad61',
        '#f4b462',
        '#f5bc63',
        '#f5c364',
        '#f6ca65',
        '#f6d166',
        '#f7d866',
        '#f8df67',
        '#f8e668',
        '#f9ed69'
    ]
    NEW_LIFE = [
        '#43e97b',
        '#42eb85',
        '#41ed8f',
        '#3fee9a',
        '#3ef0a4',
        '#3df2ae',
        '#3cf4b8',
        '#3af5c3',
        '#39f7cd',
        '#38f9d7'
    ]
    RED_GRADIENT_15 = [
        '#ff0000',
        '#ff0011',
        '#ff0021',
        '#ff0032',
        '#ff0043',
        '#ff0053',
        '#ff0064',
        '#ff0075',
        '#ff0085',
        '#ff0096',
        '#ff1a9e',
        '#ff33a6',
        '#ff4db0',
        '#ff66b8',
        '#ff80c2'
    ]

    @staticmethod
    def __extend_gradient_colors(colors: list, target_length: int) -> list:
        extended_colors = colors[:]
        while len(extended_colors) < target_length:
            # 添加原列表（除最后一个元素外）的逆序
            extended_colors.extend(colors[-2::-1])
            # 如果仍然不够长，继续添加正序部分
            if len(extended_colors) < target_length:
                extended_colors.extend(colors[:-1])
        return extended_colors[:target_length]

    @staticmethod
    def gen_gradient_text(text: str, gradient_color: list) -> str:
        """当渐变色列表小于文字长度时,翻转并扩展当前列表。"""
        text_lst: list = [i for i in text]
        text_lst_len: int = len(text_lst)
        gradient_color_len: int = len(gradient_color)
        if text_lst_len > gradient_color_len:
            # 扩展颜色列表以适应文本长度
            gradient_color = GradientColor.__extend_gradient_colors(gradient_color, text_lst_len)
        result: str = ''
        for i in range(text_lst_len):
            result += f'[{gradient_color[i]}]{text_lst[i]}[/{gradient_color[i]}]'
        return result

    @staticmethod
    def __hex_to_rgb(hex_color: str) -> tuple:
        """将十六进制颜色值转换为RGB元组。"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def __rgb_to_hex(r: int, g: int, b: int) -> str:
        """将RGB元组转换为十六进制颜色值。"""
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def generate_gradient(start_color: str, end_color: str, steps: int) -> list:
        """根据起始和结束颜色生成颜色渐变列表。"""
        steps = 2 if steps <= 1 else steps
        # 转换起始和结束颜色为RGB
        start_rgb = GradientColor.__hex_to_rgb(start_color)
        end_rgb = GradientColor.__hex_to_rgb(end_color)
        # 生成渐变色列表
        gradient_color: list = []
        for i in range(steps):
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * i / (steps - 1))
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * i / (steps - 1))
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * i / (steps - 1))
            gradient_color.append(GradientColor.__rgb_to_hex(r, g, b))

        return gradient_color


class Banner:
    A = r'''
       ______           __  __                     _ __          
      / ____/__  ____  / /_/ /__  _________  _____(_) /____      
     / / __/ _ \/ __ \/ __/ / _ \/ ___/ __ \/ ___/ / __/ _ \     
    / /_/ /  __/ / / / /_/ /  __(__  ) /_/ / /  / / /_/  __/     
    \____/\___/_/ /_/\__/_/\___/____/ .___/_/  /_/\__/\___/      
                                   /_/                           
        '''
    B = r'''
    ╔═╗┌─┐┌┐┌┌┬┐┬  ┌─┐┌─┐┌─┐┬─┐┬┌┬┐┌─┐  
    ║ ╦├┤ │││ │ │  ├┤ └─┐├─┘├┬┘│ │ ├┤   
    ╚═╝└─┘┘└┘ ┴ ┴─┘└─┘└─┘┴  ┴└─┴ ┴ └─┘  
        '''
    C = r'''
     ██████╗ ███████╗███╗   ██╗████████╗██╗     ███████╗███████╗██████╗ ██████╗ ██╗████████╗███████╗    
    ██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██║     ██╔════╝██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝██╔════╝    
    ██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║     █████╗  ███████╗██████╔╝██████╔╝██║   ██║   █████╗      
    ██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║     ██╔══╝  ╚════██║██╔═══╝ ██╔══██╗██║   ██║   ██╔══╝      
    ╚██████╔╝███████╗██║ ╚████║   ██║   ███████╗███████╗███████║██║     ██║  ██║██║   ██║   ███████╗    
     ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝           
            '''
    D = r'''                                                                          
                                            ,,                                       ,,                    
      .g8"""bgd                      mm   `7MM                                       db   mm               
    .dP'     `M                      MM     MM                                            MM               
    dM'       `   .gP"Ya `7MMpMMMb.mmMMmm   MM  .gP"Ya  ,pP"Ybd `7MMpdMAo.`7Mb,od8 `7MM mmMMmm .gP"Ya      
    MM           ,M'   Yb  MM    MM  MM     MM ,M'   Yb 8I   `"   MM   `Wb  MM' "'   MM   MM  ,M'   Yb     
    MM.    `7MMF'8M""""""  MM    MM  MM     MM 8M"""""" `YMMMa.   MM    M8  MM       MM   MM  8M""""""     
    `Mb.     MM  YM.    ,  MM    MM  MM     MM YM.    , L.   I8   MM   ,AP  MM       MM   MM  YM.    ,     
      `"bmmmdPY   `Mbmmd'.JMML  JMML.`Mbmo.JMML.`Mbmmd' M9mmmP'   MMbmmd' .JMML.   .JMML. `Mbmo`Mbmmd'     
                                                                  MM                                       
                                                                .JMML.                                     
        '''
    TRMD = r'''
    ████████╗██████╗ ███╗   ███╗██████╗ 
    ╚══██╔══╝██╔══██╗████╗ ████║██╔══██╗
       ██║   ██████╔╝██╔████╔██║██║  ██║
       ██║   ██╔══██╗██║╚██╔╝██║██║  ██║
       ██║   ██║  ██║██║ ╚═╝ ██║██████╔╝
       ╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝
    '''


class Validator:

    @staticmethod
    def is_contain_chinese(text: str) -> bool:
        for ch in text:
            if u'\u4e00' <= ch <= u'\u9fff':
                console.log(_t(KeyWord.CHINESE_PATH_WARNING), style='#FF4689')
                return True
        return False

    @staticmethod
    def is_valid_api_id(api_id: str, valid_length: int = 32) -> bool:
        try:
            if len(api_id) < valid_length:
                if api_id.isdigit():
                    return True
                else:
                    console.log(_t(KeyWord.INVALID_API_ID).format(value=api_id), style='#FF4689')
                    return False
            else:
                console.log(_t(KeyWord.API_ID_TOO_LONG).format(value=api_id), style='#FF4689')
                return False
        except (AttributeError, TypeError):
            console.log(_t(KeyWord.API_ID_NEED_QUOTES), style='#FF4689')
            return False

    @staticmethod
    def is_valid_api_hash(api_hash: str, valid_length: int = 32) -> bool:
        return len(str(api_hash)) == valid_length

    @staticmethod
    def is_valid_bot_token(bot_token: str, valid_format: str = ':') -> bool:
        if valid_format in bot_token:
            p = bot_token.split(valid_format)
            if len(p) == 2 and all(p):
                return True
        return False

    @staticmethod
    def is_valid_links_file(file_path: str, valid_format: str = '.txt') -> bool:
        file_path = os.path.normpath(file_path)
        return os.path.isfile(file_path) and file_path.endswith(valid_format)

    @staticmethod
    def is_valid_save_directory(save_directory: str) -> bool:
        for placeholder in SaveDirectoryPrefix():
            if placeholder in save_directory:
                save_directory = save_directory.replace(placeholder, '')
        save_directory = os.path.normpath(save_directory)
        if not os.path.exists(save_directory):
            while True:
                try:
                    prompt = _t(KeyWord.DIRECTORY_NOT_EXIST).format(value=save_directory)
                    question = console.input(prompt).strip().lower()
                    if question in ('y', ''):
                        os.makedirs(save_directory, exist_ok=True)
                        console.log(_t(KeyWord.DIRECTORY_CREATED).format(value=save_directory))
                        break
                    elif question == 'n':
                        break
                    else:
                        console.log(_t(KeyWord.INVALID_YES_NO).format(value=question), style='#FF4689')
                except Exception as e:
                    log.error(f'意外的错误,原因:"{e}"')
                    break
        return os.path.isdir(save_directory)

    @staticmethod
    def is_valid_number(max_tasks: int) -> bool:
        try:
            return int(max_tasks) > 0
        except ValueError:
            return False
        except Exception as e:
            log.error(f'意外的错误,原因:"{e}"')
            return False

    @staticmethod
    def is_valid_enable_proxy(enable_proxy: Union[str, bool]) -> bool:
        if enable_proxy in ('y', 'n'):
            return True
        return False

    @staticmethod
    def is_valid_scheme(scheme: str, valid_format: list) -> bool:
        return scheme in valid_format

    @staticmethod
    def is_valid_hostname(hostname: str) -> bool:
        return isinstance(ipaddress.ip_address(hostname), ipaddress.IPv4Address)

    @staticmethod
    def is_valid_port(port: int) -> bool:
        try:
            return 0 < int(port) <= 65535
        except ValueError:  # 处理非整数字符串的情况
            return False
        except TypeError:  # 处理传入非数字类型的情况
            return False
        except Exception as e:
            log.error(f'意外的错误,原因:"{e}"')
            return False

    @staticmethod
    def is_valid_download_type(dtype: list) -> bool:
        try:
            if isinstance(dtype, list):
                support_dtype: list = [_ for _ in DownloadType()]
                valid_dtype = []
                for i in dtype:
                    if i in support_dtype:
                        valid_dtype.append(i)
                    else:
                        console.log(_t(KeyWord.UNSUPPORTED_DTYPE).format(value=i), style='#FF4689')
                dtype[:] = valid_dtype
                return bool(dtype)
            return False
        except Exception as e:
            log.error(f'意外的错误,原因:"{e}"')
            return False


class ProcessConfig:
    PROXY_AUTO_FILL = False

    @staticmethod
    def __parse_proxy_url(proxy_url: str) -> Optional[dict]:
        """解析代理URL字符串。"""
        try:
            if not proxy_url:
                return None

            # 正则表达式匹配代理URL，支持以下格式：
            # - http://username:password@host:port
            # - https://host:port
            # - socks4://host:port
            # - socks5://host:port
            # - host:port (无协议前缀)
            # - 支持URL末尾有/的情况，如 http://127.0.0.1:10808/
            pattern = r'^(?:(https?|socks[45][ah]?)://)?(?:[^@]*@)?([^:]+):(\d+)/+$'
            match = re.match(pattern, proxy_url.lower())

            if not match:
                return None

            scheme = match.group(1)
            hostname = match.group(2)
            port = match.group(3)

            # 如果没有scheme，默认为http。
            if not scheme:
                scheme = 'http'
            # socks4a和socks5h统一为socks4和socks5。
            elif scheme in ('socks4a', 'socks5h'):
                scheme = scheme[:-1]

            # 验证端口号有效性。
            try:
                port = int(port)
            except ValueError:
                return None

            if not (0 <= port <= 65535):
                return None

            return {
                'scheme': scheme,
                'hostname': hostname,
                'port': port
            }
        except Exception:  # noqa.
            return None

    @staticmethod
    def format_proxy_prompt(proxy: dict) -> str:
        return proxy.get('scheme', '') + '://' + proxy.get('hostname', '') + ':' + str(proxy.get('port', ''))

    @staticmethod
    def get_unix_proxy() -> Optional[dict]:
        """从环境变量获取 Unix/Linux/macOS 代理设置。"""
        env_vars = ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']

        for var in env_vars:
            proxy_url = os.environ.get(var)
            if proxy_url:
                proxy_info = ProcessConfig.__parse_proxy_url(proxy_url)
                if proxy_info:
                    return proxy_info

        return None

    @staticmethod
    def get_windows_proxy() -> Optional[dict]:
        """从 Windows 注册表获取代理设置。"""
        try:
            import winreg
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
            ) as key:
                proxy_enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
                if not proxy_enable:
                    return None

                proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
                if not proxy_server:
                    return None

                # 使用正则表达式解析代理服务器字符串。
                # 格式可能是: "http=127.0.0.1:7890;https=127.0.0.1:7890;socks=127.0.0.1:1080"。
                # 或者是: "127.0.0.1:7890"。
                proxy_info = {}
                pattern = r'(\w+)=([^;]+)'
                matches = re.findall(pattern, proxy_server)

                if matches:
                    for proto, addr in matches:
                        proxy_info[proto.lower()] = addr
                else:
                    # 如果没有协议前缀，则整个字符串就是代理地址。
                    proxy_info['http'] = proxy_server

                # 优先级：http > https > socks。
                proxy_addr = proxy_info.get('http') or proxy_info.get('https') or proxy_info.get('socks')

                if not proxy_addr:
                    return None

                # 使用正则表达式解析地址和端口。
                addr_pattern = r'^([^:]+):(\d+)$'
                addr_match = re.match(addr_pattern, proxy_addr)

                if not addr_match:
                    return None

                hostname = addr_match.group(1)
                try:
                    port = int(addr_match.group(2))
                except ValueError:
                    return None

                # 判断协议类型。
                scheme = 'http'
                if 'socks5' in proxy_server.lower():
                    scheme = 'socks5'
                elif 'socks4' in proxy_server.lower():
                    scheme = 'socks4'
                elif 'socks=' in proxy_server.lower():
                    # 如果只有socks=没有数字，默认socks5
                    scheme = 'socks5'

                if not (0 <= port <= 65535):
                    return None

                return {
                    'scheme': scheme,
                    'hostname': hostname,
                    'port': port
                }

        except (WindowsError, OSError, ValueError):
            return None

    @staticmethod
    def get_system_proxy(param_name: str):

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                # 尝试获取系统代理（跨平台）。
                system_proxy = ProcessConfig.get_windows_proxy() if platform.system() == 'Windows' else ProcessConfig.get_unix_proxy()
                # 如果成功获取到系统代理并且包含所需的参数。
                if system_proxy and param_name in system_proxy:
                    question: str = GetStdioParams.UNDEFINED
                    if param_name == 'scheme' and ProcessConfig.PROXY_AUTO_FILL is False:
                        while True:
                            try:
                                prompt = _t(KeyWord.SYSTEM_PROXY_FOUND).format(
                                    value=ProcessConfig.format_proxy_prompt(system_proxy))
                                question = console.input(prompt).strip().lower()
                                if question in ('y', ''):
                                    ProcessConfig.PROXY_AUTO_FILL = True
                                    break
                                elif question == 'n':
                                    break
                                else:
                                    console.log(_t(KeyWord.INVALID_YES_NO).format(value=question), style='#FF4689')
                            except Exception as e:
                                log.error(f'意外的错误,原因:"{e}"')
                                break
                    if question in ('y', '') or ProcessConfig.PROXY_AUTO_FILL:
                        # 提取对应参数的值。
                        value = system_proxy[param_name]
                        # 根据参数类型打印相应的提示信息。
                        if param_name == 'scheme':
                            console.print(
                                _t(KeyWord.AUTO_PROXY_VALUE).format(name=param_name, value=value),
                                style=ProcessConfig.stdio_style('scheme')
                            )
                            return {
                                'scheme': value,
                                'record_flag': True
                            }
                        elif param_name == 'hostname':
                            console.print(
                                _t(KeyWord.AUTO_PROXY_VALUE).format(name=param_name, value=value),
                                style=ProcessConfig.stdio_style('hostname')
                            )
                            return {
                                'hostname': value,
                                'record_flag': True
                            }
                        elif param_name == 'port':
                            console.print(
                                _t(KeyWord.AUTO_PROXY_VALUE).format(name=param_name, value=value),
                                style=ProcessConfig.stdio_style('port')
                            )
                            return {
                                'port': value,
                                'record_flag': True
                            }

                # 如果没有获取到系统代理或参数不完整，执行原函数。
                return func(*args, **kwargs)

            return wrapper

        return decorator

    @staticmethod
    def set_dtype(_dtype: list) -> list:
        record_dtype: list = []
        support_dtype: list = [_ for _ in DownloadType()]
        for i in _dtype:
            if i in support_dtype:
                record_dtype.append(i)
        return record_dtype

    @staticmethod
    def get_dtype(download_dtype: list) -> dict:
        """获取所需下载文件的类型。"""
        meta: dict = {}
        support_dtype: list = [_ for _ in DownloadType()]
        for dtype in download_dtype:
            meta[dtype] = True if dtype in support_dtype else False
        return meta

    @staticmethod
    def stdio_style(key: str, color=None) -> str:
        """控制用户交互时打印出不同的颜色(渐变)。"""
        if color is None:
            color = GradientColor.ORANGE2YELLOW_15
        _stdio_queue: dict = {
            'api_id': 0,
            'api_hash': 1,
            'bot_token': 2,
            'links': 3,
            'save_directory': 4,
            'max_download_task': 5,
            'max_retry_count': 6,
            'download_type': 7,
            'is_shutdown': 8,
            'enable_proxy': 9,
            'config_proxy': 10,
            'scheme': 11,
            'hostname': 12,
            'port': 13,
            'proxy_authentication': 14
        }
        return color[_stdio_queue.get(key)]

    @staticmethod
    def is_proxy_input(proxy_config: dict) -> bool:
        """检测代理配置是否需要用户输入。"""
        result: bool = False
        basic_truth_table: list = []
        advance_account_truth_table: list = []
        if proxy_config.get('enable_proxy') is False:  # 检测打开了代理但是代理配置错误。
            return False
        for _ in proxy_config.items():
            if _[0] in ['scheme', 'port', 'hostname']:
                basic_truth_table.append(_[1])
            if _[0] in ['username', 'password']:
                advance_account_truth_table.append(_[1])
        if all(basic_truth_table) is False:  # noqa.
            console.print(_t(KeyWord.PROXY_NOT_CONFIG), style=ProcessConfig.stdio_style('config_proxy'))
            console.print(Issues.PROXY_CONFIG_TIP)
            result: bool = True
        if any(advance_account_truth_table) and all(advance_account_truth_table) is False:
            console.log(_t(KeyWord.PROXY_AUTH_EMPTY), style='#FF4689')
            result: bool = True
        return result

    @staticmethod
    def get_proxy_info(proxy_config: dict) -> dict:
        unknown: str = _t(KeyWord.UNKNOWN)
        return {
            'scheme': proxy_config.get('scheme', unknown),
            'hostname': proxy_config.get('hostname', unknown),
            'port': proxy_config.get('port', unknown)
        }


class GetStdioParams:
    UNDEFINED: str = '无'

    @staticmethod
    def __timeout_input(
            prompt: str = '',
            error_prompt: Union[str, None] = None,
            default: str = '',
            timeout: int = 5
    ) -> str:
        """跨平台的输入超时后自动设置为默认值,报错时返回默认input。"""

        def timeout_notice():
            console.print(_t(KeyWord.INPUT_TIMEOUT), style='#FF4689')

        if sys.platform == 'win32':
            try:
                import msvcrt
                console.print(prompt, end='')
                start_time: float = time.time()
                input_buffer: list = []
                last_second: int = timeout
                countdown_displayed: bool = False

                while True:
                    elapsed = time.time() - start_time
                    remaining = int(timeout - elapsed)

                    # 倒计时显示更新。
                    if remaining != last_second and remaining >= 0:
                        if countdown_displayed:
                            # 删除之前的倒计时（1位数字+1个空格）。
                            print('\b \b\b \b', end='', flush=True)
                        # 显示新的倒计时（输入时才显示）。
                        if not input_buffer and remaining >= 0:
                            console.print(f'{remaining} ', end='', style='dim')
                            countdown_displayed = True
                        last_second = remaining

                    if msvcrt.kbhit():  # 检测是否有键盘输入。
                        # 清除倒计时显示。
                        if countdown_displayed:
                            print('\b \b\b \b', end='', flush=True)
                            countdown_displayed = False

                        char = msvcrt.getwch()
                        if char == '\r':  # 回车键结束输入。
                            user_input = ''.join(input_buffer)
                            print('\n') if user_input in ('y', 'n', '') else None
                            return user_input.strip() or default
                        elif char in ('\x08', '\b'):  # Backspace键处理。
                            if input_buffer:
                                input_buffer.pop()
                                print('\b \b', end='', flush=True)  # 删除控制台上的最后一个字符。
                        elif char in ('\x00', '\xe0'):  # 上下左右键。
                            _ = msvcrt.getwch()
                        else:
                            input_buffer.append(char)
                            console.print(char, end='')
                        last_second = -1  # 输入开始后不再显示倒计时。
                    elif elapsed > timeout:
                        timeout_notice()
                        return default
                    time.sleep(0.1)
            except Exception as e:
                log.exception(f'无法自动设置!请手动进行设置,{_t(KeyWord.REASON)}:"{e}"')
                return console.input(error_prompt if error_prompt else prompt)
        else:
            import tty
            import select
            import termios

            console.print(prompt, end='')
            sys.stdout.flush()

            # 保存原始终端设置。
            old_settings = termios.tcgetattr(sys.stdin)
            elapsed = 0
            try:
                # 设置终端为原始模式,允许逐字符读取。
                tty.setraw(sys.stdin.fileno())

                start_time: float = time.time()
                input_buffer: list = []
                last_second: int = timeout
                countdown_displayed: bool = False
                while True:
                    elapsed = time.time() - start_time
                    remaining = int(timeout - elapsed)

                    # 倒计时显示更新。
                    if remaining != last_second and remaining >= 0:
                        if countdown_displayed:
                            # 删除之前的倒计时（数字+空格）。
                            backspace_count = len(str(last_second)) + 1
                            sys.stdout.write('\b \b' * backspace_count)
                            sys.stdout.flush()
                        # 显示新的倒计时（输入时才显示）。
                        if not input_buffer and remaining >= 0:
                            console.print(f'{remaining} ', end='', style='dim')
                            sys.stdout.flush()
                            countdown_displayed = True
                        last_second = remaining

                    # 使用select检测输入,超时0.1秒以便更新倒计时。
                    ready, _, _ = select.select([sys.stdin], [], [], 0.1)

                    if ready:
                        # 清除倒计时显示。
                        if countdown_displayed:
                            backspace_count = len(str(remaining)) + 1
                            sys.stdout.write('\b \b' * backspace_count)
                            sys.stdout.flush()
                            countdown_displayed = False

                        # 读取一个字符。
                        char = sys.stdin.read(1)

                        if char == '\r' or char == '\n':  # 回车键结束输入。
                            user_input = ''.join(input_buffer)
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                            return user_input.strip() or default
                        elif char == '\x7f' or char == '\b':  # Backspace/Delete键处理。
                            if input_buffer:
                                input_buffer.pop()
                                sys.stdout.write('\b \b')
                                sys.stdout.flush()
                        elif char == '\x1b':  # 转义序列（上下左右键等）。
                            # 读取接下来的两个字符。
                            _ = sys.stdin.read(2)
                        elif ord(char) >= 32:  # 可打印字符。
                            input_buffer.append(char)
                            sys.stdout.write(char)
                            sys.stdout.flush()
                        last_second = -1  # 输入开始后不再显示倒计时。

                    elif elapsed > timeout:
                        # 清除倒计时显示。
                        if countdown_displayed:
                            backspace_count = len(str(remaining)) + 1
                            sys.stdout.write('\b \b' * backspace_count)
                            sys.stdout.flush()
                        return default
            except Exception as e:
                log.exception(f'无法自动设置!请手动进行设置,{_t(KeyWord.REASON)}:"{e}"')
                return console.input(error_prompt if error_prompt else prompt)
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)  # 恢复终端设置。
                timeout_notice() if elapsed > timeout else print()

    @staticmethod
    def get_is_ki_save_config(valid_format: str = 'y|n') -> dict:
        while True:
            prompt: str = _t(KeyWord.ASK_SAVE_CONFIG).format(format=valid_format)
            is_save_config: str = console.input(prompt).strip().lower()
            if is_save_config == 'y':
                return {'is_ki_save_config': True}
            elif is_save_config == 'n':
                return {'is_ki_save_config': False}
            else:
                console.log(_t(KeyWord.INVALID_PARAM).format(value=is_save_config, format=valid_format),
                            style='#FF4689')

    @staticmethod
    def get_is_re_config(valid_format: str = 'y|n') -> dict:
        prompt: str = _t(KeyWord.ASK_RECONFIG).format(format=valid_format)
        timeout: int = 5
        while True:
            is_re_config: str = GetStdioParams.__timeout_input(
                prompt=f'{prompt}:',
                error_prompt=f'{prompt}{_t(KeyWord.DEFAULT_N)}:',
                default='n',
                timeout=timeout
            ).strip().lower()
            if is_re_config == 'y':
                return {'is_re_config': True}
            elif is_re_config in ('n', ''):
                return {'is_re_config': False}
            else:
                console.print('\n') if sys.platform == 'win32' else None
                console.log(_t(KeyWord.INVALID_PARAM_DEFAULT).format(value=is_re_config, format=valid_format),
                            style='#FF4689')

    @staticmethod
    def get_is_change_account(valid_format: str = 'y|n') -> dict:
        style: str = '#FF4689'
        while True:
            is_change_account = console.input(_t(KeyWord.ASK_CHANGE_ACCOUNT)).strip().lower()
            if is_change_account in ('n', ''):
                console.print(_t(KeyWord.NO_SWITCH_ACCOUNT), style=style)
                return {'is_change_account': False}
            elif is_change_account == 'y':
                console.print(_t(KeyWord.SWITCH_ACCOUNT), style=style)
                return {'is_change_account': True}
            else:
                console.log(_t(KeyWord.INVALID_PARAM_BANG).format(value=is_change_account, format=valid_format),
                            style='#FF4689')

    @staticmethod
    def get_session_directory():
        style: str = '#FF4689'
        while True:
            session_directory = console.input(_t(KeyWord.ASK_SESSION_DIRECTORY)).strip().strip('"')
            console.print(_t(KeyWord.SESSION_DIR_SET).format(value=session_directory), style=style)
            return {'session_directory': session_directory}

    @staticmethod
    def get_api_id(last_record: str) -> dict:
        while True:
            prompt: str = _t(KeyWord.ASK_LAST_RECORD).format(
                name='api_id', record=last_record if last_record else _t(KeyWord.UNDEFINED))
            api_id = console.input(prompt).strip()
            if api_id == '' and last_record is not None:
                api_id = last_record
            if Validator.is_valid_api_id(api_id):
                console.print(_t(KeyWord.PARAM_SET).format(name='api_id', value=api_id),
                              style=ProcessConfig.stdio_style('api_id'))
                return {
                    'api_id': api_id,
                    'record_flag': True
                }

    @staticmethod
    def get_api_hash(last_record: str, valid_length: int = 32) -> dict:
        while True:
            prompt: str = _t(KeyWord.ASK_LAST_RECORD).format(
                name='api_hash', record=last_record if last_record else _t(KeyWord.UNDEFINED))
            api_hash = console.input(prompt).strip().lower()
            if api_hash == '' and last_record is not None:
                api_hash = last_record
            if Validator.is_valid_api_hash(api_hash, valid_length):
                console.print(_t(KeyWord.PARAM_SET).format(name='api_hash', value=api_hash),
                              style=ProcessConfig.stdio_style('api_hash'))
                return {
                    'api_hash': api_hash,
                    'record_flag': True
                }
            else:
                console.log(_t(KeyWord.INVALID_HASH).format(value=api_hash, length=valid_length), style='#FF4689')

    @staticmethod
    def get_enable_bot(valid_format: str = 'y|n') -> dict:
        while True:
            enable_bot = console.input(_t(KeyWord.ASK_ENABLE_BOT)).strip().lower()
            if enable_bot in ('n', ''):
                console.print(_t(KeyWord.BOT_DISABLED), style=ProcessConfig.stdio_style('bot_token'))
                return {'enable_bot': False}
            elif enable_bot == 'y':
                console.print(_t(KeyWord.CONFIG_BOT_TOKEN), style=ProcessConfig.stdio_style('bot_token'))
                return {'enable_bot': True}
            else:
                console.log(_t(KeyWord.INVALID_PARAM_BANG).format(value=enable_bot, format=valid_format),
                            style='#FF4689')

    @staticmethod
    def get_bot_token(last_record: str, valid_format: str = ':') -> dict:
        while True:
            prompt: str = _t(KeyWord.ASK_BOT_TOKEN).format(
                record=last_record if last_record else _t(KeyWord.UNDEFINED))
            bot_token = console.input(prompt).strip()
            if bot_token == '' and last_record is not None:
                bot_token = last_record
            if Validator.is_valid_bot_token(bot_token, valid_format):
                console.print(_t(KeyWord.PARAM_SET).format(name='bot_token', value=bot_token),
                              style=ProcessConfig.stdio_style('bot_token'))
                return {
                    'bot_token': bot_token,
                    'record_flag': True
                }
            else:
                console.log(_t(KeyWord.INVALID_BOT_TOKEN).format(value=bot_token), style='#FF4689')

    @staticmethod
    def get_links(last_record: str, valid_format: str = '.txt', enable_bot: bool = False) -> dict:
        # 输入需要下载的媒体链接文件路径,确保文件存在。
        links_file_path = None
        while True:
            try:
                bot_notice = _t(KeyWord.BOT_CONFIGURED_NOTICE) if enable_bot else ''
                prompt: str = _t(KeyWord.ASK_LINKS).format(
                    record=last_record if last_record else _t(KeyWord.UNDEFINED),
                    format=valid_format,
                    notice=bot_notice)
                links_file_path = console.input(prompt).strip().strip('"')
                if links_file_path == '':
                    if last_record is not None:
                        links_file_path = last_record
                    elif bot_notice:
                        links_file_path = os.path.join(os.getcwd(), 'links.txt')
                if links_file_path and not os.path.exists(links_file_path):
                    try:
                        with open(file=links_file_path, mode='w', encoding='UTF-8'):
                            pass
                    except Exception as e:
                        log.warning(f'无法创建文件:"{links_file_path}"请排查权限问题,{_t(KeyWord.REASON)}:"{e}"')
                if Validator.is_valid_links_file(links_file_path, valid_format):
                    console.print(_t(KeyWord.PARAM_SET).format(name='links', value=links_file_path),
                                  style=ProcessConfig.stdio_style('links'))
                    Validator.is_contain_chinese(links_file_path)
                    return {
                        'links': links_file_path,
                        'record_flag': True
                    }
                elif not os.path.normpath(links_file_path).lower().endswith('.txt'):
                    console.log(_t(KeyWord.INVALID_LINKS_FORMAT).format(value=links_file_path, format=valid_format),
                                style='#FF4689')
                else:
                    console.log(_t(KeyWord.LINKS_NOT_EXIST).format(value=links_file_path), style='#FF4689')
            except Exception as e:
                log.warning(
                    f'意外的参数:"{links_file_path}",文件路径必须以「{valid_format}」结尾,并且「必须存在」,请重新输入!{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_save_directory(last_record) -> dict:
        # 输入媒体保存路径,确保是一个有效的目录路径。
        while True:
            prompt: str = _t(KeyWord.ASK_SAVE_DIRECTORY).format(
                record=last_record if last_record else _t(KeyWord.UNDEFINED))
            save_directory = console.input(prompt).strip().strip('"')
            if save_directory == '':
                if last_record is not None:
                    save_directory = last_record
                else:
                    save_directory = os.path.join(os.getcwd(), 'downloads')
                    console.log(_t(KeyWord.DEFAULT_SAVE_DIR), style='#FF4689')
            if Validator.is_valid_save_directory(save_directory):
                console.print(_t(KeyWord.PARAM_SET).format(name='save_directory', value=save_directory),
                              style=ProcessConfig.stdio_style('save_directory'))
                Validator.is_contain_chinese(save_directory)
                return {
                    'save_directory': save_directory,
                    'record_flag': True
                }
            elif os.path.isfile(save_directory):
                console.log(_t(KeyWord.SAVE_DIR_IS_FILE).format(value=save_directory), style='#FF4689')
            else:
                console.log(_t(KeyWord.SAVE_DIR_INVALID).format(value=save_directory), style='#FF4689')

    @staticmethod
    def get_max_download_task(last_record) -> dict:
        # 输入最大下载任务数,确保是一个整数且不超过特定限制。
        default_prompt: str = _t(KeyWord.DEFAULT_3) if last_record is None else ''
        while True:
            try:
                prompt: str = _t(KeyWord.ASK_MAX_DOWNLOAD_TASK).format(
                    record=last_record if last_record else _t(KeyWord.UNDEFINED),
                    default=default_prompt)
                max_download_task = console.input(prompt).strip()
                if max_download_task == '' and last_record is not None:
                    max_download_task = last_record
                if max_download_task == '':
                    max_download_task = 3
                if Validator.is_valid_number(max_download_task):
                    console.print(_t(KeyWord.PARAM_SET).format(name='max_download_task', value=max_download_task),
                                  style=ProcessConfig.stdio_style('max_download_task'))
                    return {
                        'max_download_task': int(max_download_task),
                        'record_flag': True
                    }
                else:
                    console.log(_t(KeyWord.INVALID_TASK).format(value=max_download_task), style='#FF4689')
            except Exception as e:
                log.error(f'意外的错误,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_max_retry_count(last_record) -> dict:
        default_prompt: str = _t(KeyWord.DEFAULT_5) if last_record is None else ''
        while True:
            try:
                prompt: str = _t(KeyWord.ASK_MAX_RETRY_COUNT).format(
                    record=last_record if last_record else _t(KeyWord.UNDEFINED),
                    default=default_prompt)
                max_retry_count = console.input(prompt).strip()
                if max_retry_count == '' and last_record is not None:
                    max_retry_count = last_record
                if max_retry_count == '':
                    max_retry_count = 5
                if Validator.is_valid_number(max_retry_count):
                    console.print(_t(KeyWord.PARAM_SET).format(name='max_retry_count', value=max_retry_count),
                                  style=ProcessConfig.stdio_style('max_retry_count'))
                    return {
                        'max_retry_count': int(max_retry_count),
                        'record_flag': True
                    }
                else:
                    console.log(_t(KeyWord.INVALID_RETRY).format(value=max_retry_count), style='#FF4689')
            except Exception as e:
                log.error(f'意外的错误,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_download_type(last_record: Union[list, None]) -> dict:
        if isinstance(last_record, list):
            meta: dict = ProcessConfig.get_dtype(download_dtype=last_record)
            record: list = []
            for i in meta.items():
                dtype, _ = i
                if meta.get(dtype) is True:  # noqa.
                    record.append(dtype)
            last_record: str = ' '.join(record)
        default_prompt: str = _t(KeyWord.DEFAULT_ALL) if last_record is None else ''
        while True:
            prompt: str = _t(KeyWord.ASK_DOWNLOAD_TYPE).format(
                record=last_record if last_record else _t(KeyWord.UNDEFINED),
                default=default_prompt)
            download_type: Union[str, list] = console.input(prompt).strip()
            if download_type == '' and last_record is not None:
                download_type = last_record
            if download_type == '':
                download_type = [_ for _ in DownloadType()]
            download_type: list = list(set(download_type.split())) if isinstance(download_type, str) else download_type
            if Validator.is_valid_download_type(download_type):
                dtype = ' '.join(download_type) if download_type else [_ for _ in DownloadType()]
                console.print(
                    _t(KeyWord.PARAM_SET).format(name='download_type', value=dtype),
                    style=ProcessConfig.stdio_style('download_type')
                )
                return {
                    'download_type': ProcessConfig.set_dtype(_dtype=download_type),
                    'record_flag': True
                }
            else:
                reason: str = (_t(KeyWord.INVALID_DTYPE).format(value=download_type) if download_type
                               else _t(KeyWord.REINPUT_DTYPE))
                console.log(reason, style='#FF4689')

    @staticmethod
    def get_is_shutdown(last_record: str, valid_format: str = 'y|n') -> dict:
        _style: str = ProcessConfig.stdio_style('is_shutdown')
        if last_record:
            last_record: str = 'y'
        elif last_record is False:  # noqa.
            last_record: str = 'n'
        else:
            last_record = GetStdioParams.UNDEFINED
        t = _t(KeyWord.SHUTDOWN_YES)  # v1.3.0 修复配置is_shutdown参数时显示错误。
        f = _t(KeyWord.SHUTDOWN_NO)
        default_prompt: str = _t(KeyWord.DEFAULT_N) if last_record == GetStdioParams.UNDEFINED else ''
        while True:
            try:
                prompt: str = _t(KeyWord.ASK_IS_SHUTDOWN).format(
                    record=_t(KeyWord.UNDEFINED) if last_record == GetStdioParams.UNDEFINED else last_record,
                    format=valid_format, default=default_prompt)
                is_shutdown = console.input(prompt).strip().lower()
                if is_shutdown == '' and last_record != GetStdioParams.UNDEFINED:
                    if last_record == 'y':
                        console.print(t, style=_style)
                        return {'is_shutdown': True, 'record_flag': True}
                    elif last_record == 'n':
                        console.print(f, style=_style)
                        return {'is_shutdown': False, 'record_flag': True}

                elif is_shutdown == 'y':
                    console.print(t, style=_style)
                    return {'is_shutdown': True, 'record_flag': True}
                elif is_shutdown in ('n', ''):
                    console.print(f, style=_style)
                    return {'is_shutdown': False, 'record_flag': True}
                else:
                    console.log(_t(KeyWord.INVALID_PARAM).format(value=is_shutdown, format=valid_format),
                                style='#FF4689')

            except Exception as e:
                log.error(f'意外的错误,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_enable_proxy(last_record: Union[str, bool], valid_format: str = 'y|n') -> dict:
        if last_record:
            ep_notice: str = 'y' if last_record else 'n'
        else:
            ep_notice: str = GetStdioParams.UNDEFINED
        default_prompt: str = _t(KeyWord.DEFAULT_N) if ep_notice == GetStdioParams.UNDEFINED else ''
        while True:  # 询问是否开启代理。
            prompt: str = _t(KeyWord.ASK_ENABLE_PROXY).format(
                record=_t(KeyWord.UNDEFINED) if ep_notice == GetStdioParams.UNDEFINED else ep_notice,
                format=valid_format, default=default_prompt)
            enable_proxy = console.input(prompt).strip().lower()
            if enable_proxy == '' and last_record is not None:
                if last_record is True:
                    enable_proxy = 'y'
                elif last_record is False:
                    enable_proxy = 'n'
            elif enable_proxy == '':
                enable_proxy = 'n'
            if Validator.is_valid_enable_proxy(enable_proxy):
                if enable_proxy == 'y':
                    console.print(_t(KeyWord.PARAM_SET).format(name='enable_proxy', value=enable_proxy),
                                  style=ProcessConfig.stdio_style('enable_proxy'))
                    return {'enable_proxy': True, 'record_flag': True}
                elif enable_proxy == 'n':
                    console.print(_t(KeyWord.PARAM_SET).format(name='enable_proxy', value=enable_proxy),
                                  style=ProcessConfig.stdio_style('enable_proxy'))
                    return {'enable_proxy': False, 'record_flag': True}
            else:
                console.log(_t(KeyWord.INVALID_ENABLE_PROXY).format(value=enable_proxy, format=valid_format),
                            style='#FF4689')

    @staticmethod
    @ProcessConfig.get_system_proxy('scheme')
    def get_scheme(last_record: str, valid_format: list) -> dict:
        if valid_format is None:
            valid_format: list = ['http', 'socks4', 'socks5']
        fmt_valid_format = '|'.join(valid_format)
        while True:  # v1.3.0 修复代理配置scheme参数配置抛出AttributeError。
            prompt: str = _t(KeyWord.ASK_SCHEME).format(
                record=last_record if last_record else _t(KeyWord.UNDEFINED),
                format=fmt_valid_format)
            scheme = console.input(prompt).strip().lower()
            if scheme == '' and last_record is not None:
                scheme = last_record
            if Validator.is_valid_scheme(scheme, valid_format):
                console.print(_t(KeyWord.PARAM_SET).format(name='scheme', value=scheme),
                              style=ProcessConfig.stdio_style('scheme'))
                return {
                    'scheme': scheme,
                    'record_flag': True
                }
            else:
                console.log(_t(KeyWord.INVALID_SCHEME).format(value=scheme, format=fmt_valid_format),
                            style='#FF4689')

    @staticmethod
    @ProcessConfig.get_system_proxy('hostname')
    def get_hostname(proxy_config: dict, last_record: str, valid_format: str = 'x.x.x.x'):
        hostname = None
        while True:
            scheme, _, __ = ProcessConfig.get_proxy_info(proxy_config).values()
            # 输入代理IP地址。
            try:
                prompt: str = _t(KeyWord.ASK_HOSTNAME).format(
                    scheme=scheme,
                    record=last_record if last_record else _t(KeyWord.UNDEFINED),
                    format=valid_format)
                hostname = console.input(prompt).strip()
                if hostname == '' and last_record is not None:
                    hostname = last_record
                if Validator.is_valid_hostname(hostname):
                    console.print(_t(KeyWord.PARAM_SET).format(name='hostname', value=hostname),
                                  style=ProcessConfig.stdio_style('hostname'))
                    return {
                        'hostname': hostname,
                        'record_flag': True
                    }
            except ValueError:
                console.log(_t(KeyWord.INVALID_IP).format(value=hostname, format=valid_format), style='#FF4689')

    @staticmethod
    @ProcessConfig.get_system_proxy('port')
    def get_port(proxy_config: dict, last_record: str, valid_format: str = '0~65535'):
        port = None
        # 输入代理端口。
        while True:
            try:  # hostname,scheme可能出现None。
                scheme, hostname, __ = ProcessConfig.get_proxy_info(proxy_config).values()
                prompt: str = _t(KeyWord.ASK_PORT).format(
                    hostname=hostname,
                    scheme=scheme,
                    record=last_record if last_record else _t(KeyWord.UNDEFINED),
                    format=valid_format)
                port = console.input(prompt).strip()
                if port == '' and last_record is not None:
                    port = last_record
                if Validator.is_valid_port(port):
                    console.print(_t(KeyWord.PARAM_SET).format(name='port', value=port),
                                  style=ProcessConfig.stdio_style('port'))
                    return {
                        'port': int(port),
                        'record_flag': True
                    }
                else:
                    console.log(_t(KeyWord.INVALID_PORT_RANGE).format(value=port, format=valid_format),
                                style='#FF4689')
            except ValueError:
                console.log(_t(KeyWord.INVALID_PORT).format(value=port, format=valid_format), style='#FF4689')
            except Exception as e:
                log.error(f'意外的错误,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_proxy_authentication():
        # 是否需要认证。
        style = ProcessConfig.stdio_style('proxy_authentication')
        valid_format: str = 'y|n'
        while True:
            prompt: str = _t(KeyWord.ASK_PROXY_AUTH).format(format=valid_format)
            is_proxy = console.input(prompt).strip().lower()
            if is_proxy == 'y':
                username = console.input(_t(KeyWord.ASK_USERNAME)).strip()
                password = console.input(_t(KeyWord.ASK_PASSWORD)).strip()
                console.print(_t(KeyWord.PROXY_AUTH_YES), style=style)
                return {'username': username, 'password': password, 'record_flag': True}
            elif is_proxy in ('n', ''):
                console.print(_t(KeyWord.PROXY_AUTH_NO), style=style)
                return {'username': None, 'password': None, 'record_flag': True}
            else:
                console.log(_t(KeyWord.INVALID_PARAM_BANG).format(value=is_proxy, format=valid_format),
                            style='#FF4689')


class BotCommandText:
    HELP: tuple = ('help', _t('/help'))
    DOWNLOAD: tuple = ('download', _t('/download'))
    TABLE: tuple = ('table', _t('/table'))
    FORWARD: tuple = ('forward', _t('/forward'))
    EXIT: tuple = ('exit', _t('/exit'))
    LISTEN_DOWNLOAD: tuple = ('listen_download', _t('/listen_download'))
    LISTEN_FORWARD: tuple = ('listen_forward', _t('/listen_forward'))
    LISTEN_INFO: tuple = ('listen_info', _t('/listen_info'))
    UPLOAD: tuple = ('upload', _t('/upload'))
    UPLOAD_R: tuple = ('upload_r', _t('/upload_r'))
    DOWNLOAD_CHAT: tuple = ('download_chat', _t('/download_chat'))
    AUTH: tuple = ('auth', _t('/auth'))

    @staticmethod
    def with_description(text: tuple) -> str:
        return f'/{text[0]} - {text[1]}'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value

    @staticmethod
    def commands() -> List[str]:
        return [_[0] for _ in BotCommandText()]

    @staticmethod
    def commands_with_prefix() -> List[str]:
        return [f'/{_}' for _ in BotCommandText.commands()]


class BotCallbackText:
    NULL: str = 'null'
    PAY: str = 'pay'
    LINK_TABLE: str = 'link_table'
    COUNT_TABLE: str = 'count_table'
    UPLOAD_TABLE: str = 'upload_table'
    BACK_HELP: str = 'back_help'
    BACK_TABLE: str = 'back_table'
    NOTICE: str = 'notice'
    DOWNLOAD: str = 'download'
    DOWNLOAD_UPLOAD: str = 'download_upload'
    REMOVE_LISTEN_DOWNLOAD: str = 'rld'
    REMOVE_LISTEN_FORWARD: str = 'rlf'
    REMOVE_AUTH_USER: str = 'remove_auth'
    LOOKUP_LISTEN_INFO: str = 'lookup_listen_info'
    LOOKUP_AUTH_INFO: str = 'lookup_auth_info'
    AUTH: str = 'auth'
    CANCEL_AUTH_INPUT: str = 'cancel_auth_input'
    EXPORT_LINK_TABLE: str = 'export_link_table'
    EXPORT_COUNT_TABLE: str = 'export_count_table'
    EXPORT_UPLOAD_TABLE: str = 'export_upload_table'
    TOGGLE_LINK_TABLE: str = 'toggle_link_table'
    TOGGLE_COUNT_TABLE: str = 'toggle_count_table'
    TOGGLE_UPLOAD_TABLE: str = 'toggle_upload_table'
    TOGGLE_FORWARD_VIDEO: str = 'toggle_forward_video'
    TOGGLE_FORWARD_PHOTO: str = 'toggle_forward_photo'
    TOGGLE_FORWARD_AUDIO: str = 'toggle_forward_audio'
    TOGGLE_FORWARD_VOICE: str = 'toggle_forward_voice'
    TOGGLE_FORWARD_ANIMATION: str = 'toggle_forward_animation'
    TOGGLE_FORWARD_DOCUMENT: str = 'toggle_forward_document'
    TOGGLE_FORWARD_TEXT: str = 'toggle_forward_text'
    TOGGLE_FORWARD_VIDEO_NOTE: str = 'toggle_forward_video_note'
    TOGGLE_FORWARD_LIVE_PHOTO: str = 'toggle_forward_live_photo'
    TOGGLE_DOWNLOAD_VIDEO: str = 'toggle_download_video'
    TOGGLE_DOWNLOAD_PHOTO: str = 'toggle_download_photo'
    TOGGLE_DOWNLOAD_AUDIO: str = 'toggle_download_audio'
    TOGGLE_DOWNLOAD_VOICE: str = 'toggle_download_voice'
    TOGGLE_DOWNLOAD_ANIMATION: str = 'toggle_download_animation'
    TOGGLE_DOWNLOAD_DOCUMENT: str = 'toggle_download_document'
    TOGGLE_DOWNLOAD_VIDEO_NOTE: str = 'toggle_download_video_note'
    TOGGLE_DOWNLOAD_LIVE_PHOTO: str = 'toggle_download_live_photo'
    EXPORT_TABLE: str = 'export_table'
    SHUTDOWN: str = 'shutdown'
    SETTING: str = 'setting'
    UPLOAD_SETTING: str = 'upload_setting'
    DOWNLOAD_SETTING: str = 'download_setting'
    FORWARD_SETTING: str = 'forward_setting'
    UPLOAD_DOWNLOAD: str = 'upload_download'
    UPLOAD_DOWNLOAD_DELETE: str = 'upload_download_delete'
    DOWNLOAD_CHAT_ID: str = 'download_chat_id'
    DOWNLOAD_CHAT_ID_CANCEL: str = 'download_chat_id_cancel'
    DOWNLOAD_CHAT_FILTER: str = 'download_chat_filter'
    DOWNLOAD_CHAT_DATE_FILTER: str = 'download_chat_date_filter'
    DOWNLOAD_CHAT_DTYPE_FILTER: str = 'download_chat_dtype_filter'
    DOWNLOAD_CHAT_KEYWORD_FILTER: str = 'download_chat_keyword_filter'
    DOWNLOAD_CHAT_TOPIC_FILTER: str = 'download_chat_topic_filter'
    TOPIC_ENABLE_ALL: str = 'topic_enable_all'
    TOPIC_DISABLE_ALL: str = 'topic_disable_all'
    TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO: str = 'toggle_download_chat_video'
    TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO: str = 'toggle_download_chat_photo'
    TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO: str = 'toggle_download_chat_audio'
    TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE: str = 'toggle_download_chat_voice'
    TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION: str = 'toggle_download_chat_animation'
    TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT: str = 'toggle_download_chat_document'
    TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO_NOTE: str = 'toggle_download_chat_video_note'
    TOGGLE_DOWNLOAD_CHAT_DTYPE_LIVE_PHOTO: str = 'toggle_download_chat_live_photo'
    TOGGLE_DOWNLOAD_CHAT_COMMENT: str = 'toggle_download_chat_comment'
    CALENDAR_CONFIRM: str = 'calendar_confirm'
    FILTER_START_DATE: str = 'filter_start_date'
    FILTER_END_DATE: str = 'filter_end_date'
    DROP_KEYWORD: str = 'drop_keyword'
    IGNORE_KEYWORD: str = 'ignore_keyword'
    CONFIRM_KEYWORD: str = 'confirm_keyword'
    CANCEL_KEYWORD_INPUT: str = 'cancel_keyword_input'
    COMMAND_DOWNLOAD: str = 'cmd_download'
    COMMAND_UPLOAD: str = 'cmd_upload'
    COMMAND_UPLOAD_R: str = 'cmd_upload_r'
    COMMAND_DOWNLOAD_CHAT: str = 'cmd_download_chat'
    COMMAND_FORWARD: str = 'cmd_forward'
    MENU_DOWNLOAD: str = 'menu_download'
    MENU_LISTEN: str = 'menu_listen'
    MENU_UPLOAD: str = 'menu_upload'
    MENU_AUTH: str = 'menu_auth'
    VIEW_AUTH_LIST: str = 'view_auth_list'
    MENU_BACK: str = 'menu_back'
    LISTEN_DOWNLOAD_BTN: str = 'cmd_listen_download'
    LISTEN_FORWARD_BTN: str = 'cmd_listen_forward'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('__') and not callable(value):  # 排除特殊方法和属性。
                yield value


class BotCallbackPrefix:
    """回调数据的固定前缀,其后拼接动态参数(日期、年份、关键词等)。

    与BotCallbackText的区别在于这些值只做前缀匹配,实际回调数据还会追加参数,
    压缩回调数据时同样以此为准,避免出现两处硬编码不一致。
    """
    TIME_INC: str = 'time_inc_'
    TIME_DEC: str = 'time_dec_'
    SET_TIME: str = 'set_time_'
    SET_SPECIFIC_TIME: str = 'set_specific_time_'
    ADJUST_STEP: str = 'adjust_step_'
    SELECT_YEAR: str = 'select_year_'
    SET_YEAR: str = 'set_year_'
    DROP_KEYWORD: str = 'drop_keyword_'
    IGNORE_KEYWORD: str = 'ignore_keyword'
    TOGGLE_TOPIC: str = 'toggle_topic_'
    TOPIC_PAGE: str = 'topic_page_'
    TOPIC_RANGE: str = 'topic_range_'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('__') and not callable(value):  # 排除特殊方法和属性。
                yield value


class Emoji:
    SEARCH: Tuple[str, str] = ('🔎', '🔍')
    HOURGLASS: Tuple[str, str] = ('⏳', '⌛')


class BotStepKeyword:
    LINK = 'link'
    PATH = 'path'
    TARGET = 'target'
    ORIGIN = 'origin'
    START_ID = 'start_id'
    END_ID = 'end_id'


class BotStepText:
    DOWNLOAD_LINK: tuple = (BotStepKeyword.LINK, _t(KeyWord.BOT_STEP_DOWNLOAD_LINK))
    DOWNLOAD_CHAT_LINK: tuple = (BotStepKeyword.LINK, _t(KeyWord.BOT_STEP_DOWNLOAD_CHAT_LINK))
    UPLOAD_PATH: tuple = (BotStepKeyword.PATH, _t(KeyWord.BOT_STEP_UPLOAD_PATH))
    UPLOAD_TARGET: tuple = (BotStepKeyword.TARGET, _t(KeyWord.BOT_STEP_UPLOAD_TARGET))
    UPLOAD_R_PATH: tuple = (BotStepKeyword.PATH, _t(KeyWord.BOT_STEP_UPLOAD_R_PATH))
    UPLOAD_R_TARGET: tuple = (BotStepKeyword.TARGET, _t(KeyWord.BOT_STEP_UPLOAD_R_TARGET))
    FORWARD_ORIGIN: tuple = (BotStepKeyword.ORIGIN, _t(KeyWord.BOT_STEP_FORWARD_ORIGIN))
    FORWARD_TARGET: tuple = (BotStepKeyword.TARGET, _t(KeyWord.BOT_STEP_FORWARD_TARGET))
    FORWARD_START_ID: tuple = (BotStepKeyword.START_ID, _t(KeyWord.BOT_STEP_FORWARD_START_ID))
    FORWARD_END_ID: tuple = (BotStepKeyword.END_ID, _t(KeyWord.BOT_STEP_FORWARD_END_ID))
    LISTEN_DOWNLOAD_ORIGIN: tuple = (BotStepKeyword.ORIGIN, _t(KeyWord.BOT_STEP_LISTEN_DOWNLOAD_ORIGIN))
    LISTEN_FORWARD_ORIGIN: tuple = (BotStepKeyword.ORIGIN, _t(KeyWord.BOT_STEP_LISTEN_FORWARD_ORIGIN))
    LISTEN_FORWARD_TARGET: tuple = (BotStepKeyword.TARGET, _t(KeyWord.BOT_STEP_LISTEN_FORWARD_TARGET))


class BotMessage:
    RIGHT: str = _t(KeyWord.BOT_MESSAGE_RIGHT)
    INVALID: str = _t(KeyWord.BOT_MESSAGE_INVALID)
    TASK_ASSIGN: str = _t(KeyWord.BOT_MESSAGE_TASK_ASSIGN)
    TOO_MANY_MESSAGE: str = _t(KeyWord.BOT_MESSAGE_TOO_MANY_MESSAGE)
    TOO_MANY_INVALID_DOWNLOAD_MESSAGE: str = _t(KeyWord.BOT_MESSAGE_TOO_MANY_INVALID_DOWNLOAD)
    TOO_MANY_INVALID_FORWARD_MESSAGE: str = _t(KeyWord.BOT_MESSAGE_TOO_MANY_INVALID_FORWARD)


class BotButton:
    GITHUB: str = '📦GitHub'
    SUBSCRIBE_CHANNEL: str = '📌订阅频道'
    VIDEO_TUTORIAL: str = '🎬视频教程'
    PROXY_SELLER: str = '🛒购买代理'
    PAY: str = '💰支持作者'
    OPEN_NOTICE: str = '💬启动提示|已关闭 ❌'
    CLOSE_NOTICE: str = '💬启动提示|已开启 ✅'
    LINK_TABLE: str = '🔗链接统计表'
    COUNT_TABLE: str = '➕计数统计表'
    UPLOAD_TABLE: str = '📤上传统计表'
    HELP_PAGE: str = '🛎️帮助页面'
    CLICK_VIEW: str = '🖱点击查看'
    CLICK_DOWNLOAD: str = '🖱点击下载'
    DOWNLOAD: str = '⬇️下载'
    DOWNLOAD_UPLOAD: str = '↕️下载后上传'
    TASK_ASSIGN: str = '🌟任务已分配'
    RETRIEVE_MESSAGE: str = '🔎检索消息中'
    RETRIEVE_COMMENT: str = '🔎检索评论区中'
    ASSIGNING_TASK: str = '🚛分配任务中'
    DOWNLOAD_TASK_DOING: str = '⬇️下载任务进行中'
    DOWNLOAD_TASK_DONE: str = '✅下载任务已完成'
    TASK_CANCEL: str = '🗑️任务已取消'
    EXECUTE_TASK: str = '▶️执行任务'
    CANCEL_TASK: str = '⏹️取消任务'
    OK: str = '✅确定'
    CANCEL: str = '❌取消'
    DROP: str = '🗑️移除'
    REMOVE_AUTH: str = '🗑️移除授权'
    IGNORE: str = '👁️‍🗨️忽略'
    RETURN: str = '🔙返回'
    CONFIRM_AND_RETURN: str = '↩️确定并返回'
    LOOKUP_LISTEN_INFO: str = '🔍查看监听信息'
    LOOKUP_AUTH_INFO: str = '🔍查看授权用户'
    AUTH: str = '🔑添加/移除授权用户'
    VIEW_AUTH_LIST: str = '👥查看授权列表'
    EXPORT_TABLE: str = '📊导出表格设置'
    RESELECT: str = '🔄重新选择'
    SETTING: str = '⚙️设置'
    MENU_DOWNLOAD: str = '📁下载'
    MENU_LISTEN: str = '🕵️监听'
    MENU_UPLOAD: str = '📤上传'
    DOWNLOAD_MENU_TITLE: str = '⬇️创建「下载」任务:'
    LISTEN_MENU_TITLE: str = '🕵️创建「监听」任务:'
    UPLOAD_MENU_TITLE: str = '📤创建「上传」任务:'
    AUTH_MENU: str = '🔐授权用户'
    LISTEN_DOWNLOAD_BTN: str = '🕵️监听下载'
    LISTEN_FORWARD_BTN: str = '📲监听转发'
    OPEN_LINK_TABLE: str = '📊导出链接表格|已禁用 ❌'
    CLOSE_LINK_TABLE: str = '📊导出链接表格|已启用 ✅'
    OPEN_COUNT_TABLE: str = '📊导出计数表格|已禁用 ❌'
    CLOSE_COUNT_TABLE: str = '📊导出计数表格|已启用 ✅'
    OPEN_UPLOAD_TABLE: str = '📊导出上传表格|已禁用 ❌'
    CLOSE_UPLOAD_TABLE: str = '📊导出上传表格|已启用 ✅'
    OPEN_EXIT_SHUTDOWN: str = '⏻退出后关机|已禁用 ❌'
    CLOSE_EXIT_SHUTDOWN: str = '⏻退出后关机|已启用 ✅'
    ALREADY_REMOVE: str = '✅已移除'
    UPLOAD_SETTING: str = '📤上传行为设置'
    DOWNLOAD_SETTING: str = '📥下载类型设置'
    FORWARD_SETTING: str = '↗️转发类型设置'
    OPEN_UPLOAD_DOWNLOAD: str = '下载后上传|已禁用 ❌'
    CLOSE_UPLOAD_DOWNLOAD: str = '下载后上传|已启用 ✅'
    OPEN_UPLOAD_DOWNLOAD_DELETE: str = '当前|本地文件保留 📚'
    CLOSE_UPLOAD_DOWNLOAD_DELETE: str = '当前|本地文件删除 🗑'
    VIDEO_ON: str = '🎬视频 ✅'
    PHOTO_ON: str = '🖼️图片 ✅'
    AUDIO_ON: str = '🎵音频 ✅'
    VOICE_ON: str = '🎤语音 ✅'
    ANIMATION_ON: str = '🎨GIF ✅'
    DOCUMENT_ON: str = '📄文档 ✅'
    TEXT_ON: str = '💬文本消息 ✅'
    VIDEO_NOTE_ON: str = '📹视频笔记 ✅'
    LIVE_PHOTO_ON: str = '📸实况图片 ✅'
    VIDEO_OFF: str = '🎬视频 ❌'
    PHOTO_OFF: str = '🖼️图片 ❌'
    AUDIO_OFF: str = '🎵音频 ❌'
    VOICE_OFF: str = '🎤语音 ❌'
    ANIMATION_OFF: str = '🎨GIF ❌'
    DOCUMENT_OFF: str = '📄文档 ❌'
    TEXT_OFF: str = '💬文本消息 ❌'
    VIDEO_NOTE_OFF: str = '📹视频笔记 ❌'
    LIVE_PHOTO_OFF: str = '📸实况图片 ❌'
    DATE_RANGE_SETTING: str = '📅设置日期范围'
    SELECT_START_DATE: str = '⏮️选择起始日期'
    SELECT_END_DATE: str = '⏭️选择结束日期'
    INPUT_KEYWORD: str = '⌨️请向我发送关键词'
    DOWNLOAD_DTYPE_SETTING: str = '📝设置下载类型'
    KEYWORD_FILTER_SETTING: str = '🔑设置匹配关键词'
    TOPIC_SETTING: str = '🗂️包含话题'
    ENABLE_ALL: str = '✅全部打开'
    DISABLE_ALL: str = '❌全部关闭'
    TOPIC_PREV_PAGE: str = '⬅️上一页'
    TOPIC_NEXT_PAGE: str = '下一页➡️'
    TOPIC_PAGE_INFO: str = '📄{page}/{total}'
    TOPIC_BACK_TO_TOP: str = '🔝返回顶层'
    CONFIRM_KEYWORD: str = '✅确认关键词'
    INCLUDE_COMMENT: str = '✅包含评论区'
    IGNORE_COMMENT: str = '❌包含评论区'
    CMD_DOWNLOAD: str = '⬇️下载'
    CMD_UPLOAD: str = '📤上传'
    CMD_UPLOAD_R: str = '📁递归上传'
    CMD_DOWNLOAD_CHAT: str = '💬下载频道'
    CMD_FORWARD: str = '↗️转发'

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
from module.language import _


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


class ConnectionState:
    CONNECTED: str = 'connected'
    CONNECTING: str = 'connecting'


class WaitingKind:
    NONE: str = 'none'
    RECONNECT: str = 'reconnect'
    FLOOD: str = 'flood'


class Issues:
    PROXY_NOT_CONFIGURED = _(
        '🛡️ [#79FCD4]Proxy setup guide[/#79FCD4] [#FF79D4]Visit:[/#FF79D4]\n[link=https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0]https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0[/link]\n[#FCFF79]If[/#FCFF79] [#FF4689]unable[/#FF4689] [#FF7979]to access[/#FF7979][#79FCD4],[/#79FCD4] [#FCFF79]you can[/#FCFF79] [#d4fc79]refer to[/#d4fc79] [#FC79A5]the "User Manual"[/#FC79A5] [#79E2FC][/#79E2FC][#79FCD4]in the software package[/#79FCD4] [#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579][#79FCB5], section[/#79FCB5] [#D479FC]【问题14】[/#D479FC] [#FCE679]for instructions[/#FCE679][#FC79A6].[/#FC79A6]')
    SYSTEM_TIME_NOT_SYNCHRONIZED = _(
        '🕒 [#FCFF79]Detected[/#FCFF79] [#FF7979]system time[/#FF7979] [#FC79A5]out of sync[/#FC79A5][#79E2FC],[/#79E2FC] [#79FCD4]solution[/#79FCD4] [#FF79D4]visit:[/#FF79D4]\nhttps://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/issues/5#issuecomment-2580677184\n[#FCFF79]If[/#FCFF79] [#FF4689]unable[/#FF4689] [#FF7979]to access[/#FF7979][#79FCD4],[/#79FCD4] [#FCFF79]you can[/#FCFF79] [#d4fc79]refer to[/#d4fc79] [#FC79A5]the "User Manual"[/#FC79A5][#79E2FC][/#79E2FC][#79FCB5], section[/#79FCB5] [#D479FC]【问题4】[/#D479FC] [#FCE679]for instructions[/#FCE679][#FC79A6],[/#FC79A6] [#79FCD4]and[/#79FCD4] [#79FCB5]restart the software[/#79FCB5].')
    DOCKER_HOST_IP_TIP = _(
        '🐳 In a Docker environment, the IP in the link is the container IP, not the host IP. Please access it using the host IP and port.')
    PROXY_CONFIG_TIP = _(
        '❓ [#79FCD4]If you have questions about proxy configuration[/#79FCD4] [#FF79D4]visit:[/#FF79D4]\n🌐 [link=https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#配置代理时在代理在本机的情况下]https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#配置代理时在代理在本机的情况下[/link]\n🛑 [#FCFF79]If[/#FCFF79] [#FF4689]unable[/#FF4689] [#FF7979]to access:[/#FF7979] [#79FCD4]\n🔎 [/#79FCD4][#FCFF79]you can[/#FCFF79] [#d4fc79]refer to[/#d4fc79] [#FC79A5]the "User Manual"[/#FC79A5] [#79E2FC][/#79E2FC][#79FCD4]in the software package[/#79FCD4] [#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579][#79FCB5], section[/#79FCB5] [#D479FC]【问题14】 Solution[/#D479FC] [#FCE679]for instructions[/#FCE679][#FC79A6].[/#FC79A6]')
    MULTI_SESSION_TIP = _(
        '🔧 [#FF79D4]Solution[/#FF79D4] [#FCFF79](choose one):[/#FCFF79]\n[#D4FC79]1. Close redundant instances.[/#D4FC79]\n[#D4FC79]2. Use[/#D4FC79] "[#79FCD4]{exe} --session SESSION[/#79FCD4]" [#D4FC79]to specify a new SESSION location and retry[/#D4FC79] ([#FFB579]replace SESSION with the actual path[/#FFB579]).')
    UPDATE_PACKAGE_TIP = _(
        '❌ [#FF7979]Detected that ({package_name}) version {current_version} does not match the required version {require_version}[/#FF7979][#FCFF79], which may cause compatibility issues and abnormal behavior.[/#FCFF79]\n⚖️ [#D4FC79]Please use[/#D4FC79] [#79FCD4]{command}[/#79FCD4] [#D4FC79]to upgrade or downgrade to the required version {require_version} and retry[/#D4FC79][#D4FC79].[/#D4FC79]')

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value


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
                log.warning(_('If download fails, try not using a Chinese path.'))
                return True
        return False

    @staticmethod
    def is_valid_api_id(api_id: str, valid_length: int = 32) -> bool:
        try:
            if len(api_id) < valid_length:
                if api_id.isdigit():
                    return True
                else:
                    log.warning(_('Unexpected parameter "{api_id}", not 「a pure number」, please re-enter!').format(
                        api_id=api_id
                    ))
                    return False
            else:
                log.warning(
                    _('Unexpected parameter "{api_id}" may be 「api_hash」, please enter the correct 「api_id」!').format(
                        api_id=api_id
                    ))
                return False
        except (AttributeError, TypeError):
            log.error(_('When manually editing config.yaml, api_id must be quoted!'))
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
                    question = console.input(
                        _('Directory "{save_directory}" does not exist, create it? - 「y|n」(default y):').format(
                            save_directory=save_directory
                        )).strip().lower()
                    if question in ('y', ''):
                        os.makedirs(save_directory, exist_ok=True)
                        console.log(_('Directory "{save_directory}" created successfully').format(
                            save_directory=save_directory
                        ))
                        break
                    elif question == 'n':
                        break
                    else:
                        log.warning(_('Unexpected parameter "{question}", supported values - 「y|n」').format(
                            question=question
                        ))
                except Exception as e:
                    log.error(_('Unexpected error due to "{error}"').format(error=e))
                    break
        return os.path.isdir(save_directory)

    @staticmethod
    def is_valid_number(max_tasks: int) -> bool:
        try:
            return int(max_tasks) > 0
        except ValueError:
            return False
        except Exception as e:
            log.error(_('Unexpected error due to "{error}"').format(error=e))
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
            log.error(_('Unexpected error due to "{error}"').format(error=e))
            return False

    @staticmethod
    def is_valid_download_type(dtype: list) -> bool:
        try:
            if isinstance(dtype, list):
                support_dtype: list = [j for j in DownloadType()]
                valid_dtype = []
                for i in dtype:
                    if i in support_dtype:
                        valid_dtype.append(i)
                    else:
                        log.warning(_('"{dtype}" is not a supported download type, removed.').format(dtype=i))
                dtype[:] = valid_dtype
                return bool(dtype)
            return False
        except Exception as e:
            log.error(_('Unexpected error due to "{error}"').format(error=e))
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
                proxy_enable, i = winreg.QueryValueEx(key, 'ProxyEnable')
                if not proxy_enable:
                    return None

                proxy_server, i = winreg.QueryValueEx(key, 'ProxyServer')
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
                                question = console.input(
                                    _('System proxy "{proxy_info}" detected, auto-fill? - 「y|n」(default y):').format(
                                        proxy_info=ProcessConfig.format_proxy_prompt(system_proxy)
                                    )).strip().lower()
                                if question in ('y', ''):
                                    ProcessConfig.PROXY_AUTO_FILL = True
                                    break
                                elif question == 'n':
                                    break
                                else:
                                    log.warning(_('Unexpected parameter "{question}", supported values - 「y|n」').format(
                                        question=question
                                    ))
                            except Exception as e:
                                log.error(_('Unexpected error due to "{error}"').format(error=e))
                                break
                    if question in ('y', '') or ProcessConfig.PROXY_AUTO_FILL:
                        # 提取对应参数的值。
                        value = system_proxy[param_name]
                        # 根据参数类型打印相应的提示信息。
                        if param_name == 'scheme':
                            console.print(
                                _('System proxy auto-filled 「scheme」 as: 「{value}」').format(value=value),
                                style=ProcessConfig.stdio_style('scheme')
                            )
                            return {
                                'scheme': value,
                                'record_flag': True
                            }
                        elif param_name == 'hostname':
                            console.print(
                                _('System proxy auto-filled 「hostname」 as: 「{value}」').format(value=value),
                                style=ProcessConfig.stdio_style('hostname')
                            )
                            return {
                                'hostname': value,
                                'record_flag': True
                            }
                        elif param_name == 'port':
                            console.print(
                                _('System proxy auto-filled 「port」 as: 「{value}」').format(value=value),
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
        support_dtype: list = [j for j in DownloadType()]
        for i in _dtype:
            if i in support_dtype:
                record_dtype.append(i)
        return record_dtype

    @staticmethod
    def get_dtype(download_dtype: list) -> dict:
        """获取所需下载文件的类型。"""
        meta: dict = {}
        support_dtype: list = [i for i in DownloadType()]
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
        for i in proxy_config.items():
            if i[0] in ['scheme', 'port', 'hostname']:
                basic_truth_table.append(i[1])
            if i[0] in ['username', 'password']:
                advance_account_truth_table.append(i[1])
        if all(basic_truth_table) is False:  # noqa.
            console.print(_('Please configure the proxy!'), style=ProcessConfig.stdio_style('config_proxy'))
            console.print(Issues.PROXY_CONFIG_TIP)
            result: bool = True
        if any(advance_account_truth_table) and all(advance_account_truth_table) is False:
            log.warning(_('Proxy username or password not entered!'))
            result: bool = True
        return result

    @staticmethod
    def get_proxy_info(proxy_config: dict) -> dict:
        return {
            'scheme': proxy_config.get('scheme', _('Unknown')),
            'hostname': proxy_config.get('hostname', _('Unknown')),
            'port': proxy_config.get('port', _('Unknown'))
        }


class GetStdioParams:
    UNDEFINED: str = _('None')

    @staticmethod
    def __timeout_input(
            prompt: str = '',
            error_prompt: Union[str, None] = None,
            default: str = '',
            timeout: int = 5
    ) -> str:
        """跨平台的输入超时后自动设置为默认值,报错时返回默认input。"""

        def timeout_notice():
            console.print(_('\nInput timeout, automatically set to the default value.\n'), style='#FF4689')

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
                            i = msvcrt.getwch()
                        else:
                            input_buffer.append(char)
                            console.print(char, end='')
                        last_second = -1  # 输入开始后不再显示倒计时。
                    elif elapsed > timeout:
                        timeout_notice()
                        return default
                    time.sleep(0.1)
            except Exception as e:
                log.exception(_('Unable to set automatically, please set manually due to "{error}"').format(
                    error=e
                ))
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
                    ready, i, i = select.select([sys.stdin], [], [], 0.1)

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
                            i = sys.stdin.read(2)
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
                log.exception(_('Unable to set automatically, please set manually due to "{error}"').format(
                    error=e
                ))
                return console.input(error_prompt if error_prompt else prompt)
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)  # 恢复终端设置。
                timeout_notice() if elapsed > timeout else print()

    @staticmethod
    def get_is_ki_save_config(valid_format: str = 'y|n') -> dict:
        while True:
            is_save_config: str = console.input(
                _('「Exit tip」: save the parameters just entered? - 「{valid_format}」:').format(
                    valid_format=valid_format
                )).strip().lower()
            if is_save_config == 'y':
                return {'is_ki_save_config': True}
            elif is_save_config == 'n':
                return {'is_ki_save_config': False}
            else:
                log.warning(_('Unexpected parameter "{is_save_config}", supported values - 「{valid_format}」').format(
                    is_save_config=is_save_config,
                    valid_format=valid_format
                ))

    @staticmethod
    def get_is_re_config(valid_format: str = 'y|n') -> dict:
        prompt: str = _(
            'An existing configuration was found. Reconfigure it? (will be backed up) - 「{valid_format}」').format(
            valid_format=valid_format
        )
        timeout: int = 5
        while True:
            is_re_config: str = GetStdioParams.__timeout_input(
                prompt=f'{prompt}:',
                error_prompt=_('{prompt}(default n):').format(prompt=prompt),
                default='n',
                timeout=timeout
            ).strip().lower()
            if is_re_config == 'y':
                return {'is_re_config': True}
            elif is_re_config in ('n', ''):
                return {'is_re_config': False}
            else:
                console.print('\n') if sys.platform == 'win32' else None
                log.warning(
                    _('Unexpected parameter "{is_re_config}", supported values - 「{valid_format}」(default n)').format(
                        is_re_config=is_re_config,
                        valid_format=valid_format
                    ))

    @staticmethod
    def get_is_change_account(valid_format: str = 'y|n') -> dict:
        style: str = '#FF4689'
        while True:
            is_change_account = console.input(
                _('Switch account? - 「y|n」(default n):')).strip().lower()
            if is_change_account in ('n', ''):
                console.print(_('No need to switch 「account」.'), style=style)
                return {'is_change_account': False}
            elif is_change_account == 'y':
                console.print(_('Will switch 「account」.'), style=style)
                return {'is_change_account': True}
            else:
                log.warning(
                    _('Unexpected parameter "{is_change_account}", supported values - 「{valid_format}」!').format(
                        is_change_account=is_change_account,
                        valid_format=valid_format
                    ))

    @staticmethod
    def get_session_directory():
        style: str = '#FF4689'
        while True:
            session_directory = console.input(
                _('Enter 「the session directory」 (can be 「an empty directory」 or 「an already logged-in session directory」):')).strip().strip(
                '"')
            console.print(_('「The session directory」 set to:{session_directory}.').format(
                session_directory=session_directory
            ), style=style)
            return {'session_directory': session_directory}

    @staticmethod
    def get_api_id(last_record: str) -> dict:
        while True:
            api_id = console.input(
                _('Enter 「api_id」, last record: 「{last_record}」:').format(
                    last_record=last_record if last_record else GetStdioParams.UNDEFINED
                )).strip()
            if api_id == '' and last_record is not None:
                api_id = last_record
            if Validator.is_valid_api_id(api_id):
                console.print(_('「api_id」 set to: 「{api_id}」').format(
                    api_id=api_id
                ), style=ProcessConfig.stdio_style('api_id'))
                return {
                    'api_id': api_id,
                    'record_flag': True
                }

    @staticmethod
    def get_api_hash(last_record: str, valid_length: int = 32) -> dict:
        while True:
            api_hash = console.input(
                _('Enter 「api_hash」, last record: 「{last_record}」:').format(
                    last_record=last_record if last_record else GetStdioParams.UNDEFINED
                )).strip().lower()
            if api_hash == '' and last_record is not None:
                api_hash = last_record
            if Validator.is_valid_api_hash(api_hash, valid_length):
                console.print(_('「api_hash」 set to: 「{api_hash}」').format(
                    api_hash=api_hash
                ), style=ProcessConfig.stdio_style('api_hash'))
                return {
                    'api_hash': api_hash,
                    'record_flag': True
                }
            else:
                log.warning(
                    _('Unexpected parameter "{api_hash}", not 「a {valid_length}-digit」 「value」, please re-enter!').format(
                        api_hash=api_hash,
                        valid_length=valid_length
                    ))

    @staticmethod
    def get_enable_bot(valid_format: str = 'y|n') -> dict:
        while True:
            enable_bot = console.input(_('Enable 「the bot」 (requires bot_token)? - 「y|n」(default n):')).strip().lower()
            if enable_bot in ('n', ''):
                console.print(_('Set to not enable 「the bot」.').format(), style=ProcessConfig.stdio_style('bot_token'))
                return {'enable_bot': False}
            elif enable_bot == 'y':
                console.print(_('Please configure 「bot_token」.').format(), style=ProcessConfig.stdio_style('bot_token'))
                return {'enable_bot': True}
            else:
                log.warning(_('Unexpected parameter "{enable_bot}", supported values - 「{valid_format}」!').format(
                    enable_bot=enable_bot,
                    valid_format=valid_format
                ))

    @staticmethod
    def get_bot_token(last_record: str, valid_format: str = ':') -> dict:
        while True:
            bot_token = console.input(
                _('Enter the current account 「bot_token」 last record was:「{last_record}」:').format(
                    last_record=last_record if last_record else GetStdioParams.UNDEFINED
                )).strip()
            if bot_token == '' and last_record is not None:
                bot_token = last_record
            if Validator.is_valid_bot_token(bot_token, valid_format):
                console.print(_('「bot_token」 set to: 「{bot_token}」').format(
                    bot_token=bot_token
                ), style=ProcessConfig.stdio_style('bot_token'))
                return {
                    'bot_token': bot_token,
                    'record_flag': True
                }
            else:
                log.warning(
                    _('Unexpected parameter "{bot_token}", 「bot_token」 must contain ":", please re-enter!').format(
                        bot_token=bot_token
                    ))

    @staticmethod
    def get_links(last_record: str, valid_format: str = '.txt', enable_bot: bool = False) -> dict:
        # 输入需要下载的媒体链接文件路径,确保文件存在。
        links_file_path = None
        while True:
            try:
                bot_notice = _('(bot configured, this step can be skipped)') if enable_bot else ''
                links_file_path = console.input(
                    _('Enter the 「full path」 of the media link file. Last record:「{last_record}」format - 「{valid_format}」{bot_notice}:').format(
                        last_record=last_record if last_record else GetStdioParams.UNDEFINED,
                        valid_format=valid_format,
                        bot_notice=bot_notice
                    )).strip().strip('"')
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
                        log.warning(
                            _('Unable to create file: "{links_file_path}", check permissions due to "{error}"').format(
                                links_file_path=links_file_path,
                                error=e
                            ))
                if Validator.is_valid_links_file(links_file_path, valid_format):
                    console.print(_('「links」 set to: 「{links_file_path}」').format(
                        links_file_path=links_file_path
                    ), style=ProcessConfig.stdio_style('links'))
                    Validator.is_contain_chinese(links_file_path)
                    return {
                        'links': links_file_path,
                        'record_flag': True
                    }
                elif not os.path.normpath(links_file_path).lower().endswith('.txt'):
                    log.warning(
                        _('Unexpected parameter "{links_file_path}", the file path must end with 「{valid_format}」, please re-enter!').format(
                            links_file_path=links_file_path,
                            valid_format=valid_format
                        ))
                else:
                    log.warning(
                        _('Unexpected parameter "{links_file_path}", the file 「must exist」 (case-sensitive), please re-enter!').format(
                            links_file_path=links_file_path
                        ))
            except Exception as e:
                log.warning(
                    _('Unexpected parameter: "{links_file_path}", the file path must end with 「{valid_format}」 and 「must exist」, please re-enter due to "{error}"').format(
                        links_file_path=links_file_path,
                        valid_format=valid_format,
                        error=e
                    ))

    @staticmethod
    def get_save_directory(last_record) -> dict:
        # 输入媒体保存路径,确保是一个有效的目录路径。
        while True:
            save_directory = console.input(
                _('Enter the media 「save path」. Last record:「{last_record}」:').format(
                    last_record=last_record if last_record else GetStdioParams.UNDEFINED
                )).strip().strip(
                '"')
            if save_directory == '':
                if last_record is not None:
                    save_directory = last_record
                else:
                    save_directory = os.path.join(os.getcwd(), 'downloads')
                    log.warning(_('No previous record, set to the default directory.'))
            if Validator.is_valid_save_directory(save_directory):
                console.print(_('「save_directory」 set to: 「{directory}」').format(directory=save_directory),
                              style=ProcessConfig.stdio_style('save_directory'))
                Validator.is_contain_chinese(save_directory)
                return {
                    'save_directory': save_directory,
                    'record_flag': True
                }
            elif os.path.isfile(save_directory):
                log.warning(
                    _('Unexpected parameter "{save_directory}", the path is a file not a directory, please re-enter!').format(
                        save_directory=save_directory
                    ))
            else:
                log.warning(
                    _('Unexpected parameter "{save_directory}", the path is invalid or not a directory, please re-enter!').format(
                        save_directory=save_directory
                    ))

    @staticmethod
    def get_max_download_task(last_record) -> dict:
        # 输入最大下载任务数,确保是一个整数且不超过特定限制。
        default_prompt: str = _('(default 3)') if last_record is None else ''
        while True:
            try:
                max_download_task = console.input(
                    _('Enter 「the maximum download tasks」. Last record:「{last_record}」a high value may cause network issues, default recommended{default_prompt}:').format(
                        last_record=last_record if last_record else GetStdioParams.UNDEFINED,
                        default_prompt=default_prompt
                    )).strip()
                if max_download_task == '' and last_record is not None:
                    max_download_task = last_record
                if max_download_task == '':
                    max_download_task = 3
                if Validator.is_valid_number(max_download_task):
                    console.print(_('「max_download_task」 set to: 「{max_tasks}」').format(max_tasks=max_download_task),
                                  style=ProcessConfig.stdio_style('max_download_task'))
                    return {
                        'max_download_task': int(max_download_task),
                        'record_flag': True
                    }
                else:
                    log.warning(
                        _('Unexpected parameter "{max_download_task}", the task count must be 「a positive integer」, please re-enter!').format(
                            max_download_task=max_download_task
                        ))
            except Exception as e:
                log.error(_('Unexpected error due to "{error}"').format(error=e))

    @staticmethod
    def get_max_retry_count(last_record) -> dict:
        default_prompt: str = _('(default 5)') if last_record is None else ''
        while True:
            try:
                max_retry_count = console.input(
                    _('Enter 「the maximum retries」 on failure. Last record:「{last_record}」{default_prompt}:').format(
                        last_record=last_record if last_record else GetStdioParams.UNDEFINED,
                        default_prompt=default_prompt
                    )).strip()
                if max_retry_count == '' and last_record is not None:
                    max_retry_count = last_record
                if max_retry_count == '':
                    max_retry_count = 5
                if Validator.is_valid_number(max_retry_count):
                    console.print(_('「max_retry_count」 set to: 「{retries}」').format(retries=max_retry_count),
                                  style=ProcessConfig.stdio_style('max_retry_count'))
                    return {
                        'max_retry_count': int(max_retry_count),
                        'record_flag': True
                    }
                else:
                    log.warning(
                        _('Unexpected parameter "{max_retry_count}", the maximum retries must be 「a positive integer」, please re-enter!').format(
                            max_retry_count=max_retry_count
                        ))
            except Exception as e:
                log.error(_('Unexpected error due to "{error}"').format(error=e))

    @staticmethod
    def get_download_type(last_record: Union[list, None]) -> dict:
        if isinstance(last_record, list):
            meta: dict = ProcessConfig.get_dtype(download_dtype=last_record)
            record: list = []
            for i in meta.items():
                dtype, j = i
                if meta.get(dtype) is True:  # noqa.
                    record.append(dtype)
            last_record: str = ' '.join(record)
        default_prompt: str = _('(default is all supported download types)') if last_record is None else ''
        while True:
            download_type: Union[str, list] = console.input(
                _('Enter 「the media types」 to download (space-separated, multiple allowed). Last record:「{last_record}」format - 「video photo document audio voice animation video_note live_photo」{default_prompt}:').format(
                    last_record=last_record if last_record else GetStdioParams.UNDEFINED,
                    default_prompt=default_prompt
                )).strip()
            if download_type == '' and last_record is not None:
                download_type = last_record
            if download_type == '':
                download_type = [j for j in DownloadType()]
            download_type: list = list(set(download_type.split())) if isinstance(download_type, str) else download_type
            if Validator.is_valid_download_type(download_type):
                dtype = ' '.join(download_type) if download_type else [j for j in DownloadType()]
                console.print(
                    _('「download_type」 set to: 「{dtype}」').format(dtype=dtype),
                    style=ProcessConfig.stdio_style('download_type')
                )
                return {
                    'download_type': ProcessConfig.set_dtype(_dtype=download_type),
                    'record_flag': True
                }
            else:
                prompt: str = _('Unexpected parameter: "{download_type}"').format(
                    download_type=download_type
                ) if download_type else _('Please re-enter the download type.')
                log.warning(
                    _('{prompt}, supported values - 「video photo document」 (separate multiple with spaces)').format(
                        prompt=prompt
                    ))

    @staticmethod
    def get_is_shutdown(last_record: str, valid_format: str = 'y|n') -> dict:
        _style: str = ProcessConfig.stdio_style('is_shutdown')
        if last_record:
            last_record: str = 'y'
        elif last_record is False:  # noqa.
            last_record: str = 'n'
        else:
            last_record = GetStdioParams.UNDEFINED
        t = _(
            'Set 「is_shutdown」 to 「y」, the system will shut down after download!').format()  # v1.3.0 修复配置is_shutdown参数时显示错误。
        f = _('Set 「is_shutdown」 to 「n」').format()
        default_prompt: str = _('(default n)') if last_record == GetStdioParams.UNDEFINED else ''
        while True:
            try:
                is_shutdown = console.input(
                    _('「Shut down automatically」 after download? Last record:「{last_record}」 - 「{valid_format}」{default_prompt}:').format(
                        last_record=last_record,
                        valid_format=valid_format,
                        default_prompt=default_prompt
                    )).strip().lower()
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
                    log.warning(_('Unexpected parameter "{is_shutdown}", supported values - 「{valid_format}」').format(
                        is_shutdown=is_shutdown,
                        valid_format=valid_format
                    ))

            except Exception as e:
                log.error(_('Unexpected error due to "{error}"').format(
                    error=e))

    @staticmethod
    def get_enable_proxy(last_record: Union[str, bool], valid_format: str = 'y|n') -> dict:
        if last_record:
            ep_notice: str = 'y' if last_record else 'n'
        else:
            ep_notice: str = GetStdioParams.UNDEFINED
        default_prompt: str = _('(default n)') if ep_notice == GetStdioParams.UNDEFINED else ''
        while True:  # 询问是否开启代理。
            enable_proxy = console.input(
                _('Use 「a proxy」? Last record:「{ep_notice}」format - 「{valid_format}」{default_prompt}:').format(
                    ep_notice=ep_notice,
                    valid_format=valid_format,
                    default_prompt=default_prompt
                )).strip().lower()
            if enable_proxy == '' and last_record is not None:
                if last_record is True:
                    enable_proxy = 'y'
                elif last_record is False:
                    enable_proxy = 'n'
            elif enable_proxy == '':
                enable_proxy = 'n'
            if Validator.is_valid_enable_proxy(enable_proxy):
                if enable_proxy == 'y':
                    console.print(_('「enable_proxy」 set to: 「{enable_proxy}」').format(enable_proxy=enable_proxy),
                                  style=ProcessConfig.stdio_style('enable_proxy'))
                    return {'enable_proxy': True, 'record_flag': True}
                elif enable_proxy == 'n':
                    console.print(_('「enable_proxy」 set to: 「{enable_proxy}」').format(enable_proxy=enable_proxy),
                                  style=ProcessConfig.stdio_style('enable_proxy'))
                    return {'enable_proxy': False, 'record_flag': True}
            else:
                log.error(
                    _('Unexpected parameter "{enable_proxy}", please enter a valid value! Supported values - 「{valid_format}」!').format(
                        enable_proxy=enable_proxy,
                        valid_format=valid_format
                    ))

    @staticmethod
    @ProcessConfig.get_system_proxy('scheme')
    def get_scheme(last_record: str, valid_format: list) -> dict:
        if valid_format is None:
            valid_format: list = ['http', 'socks4', 'socks5']
        fmt_valid_format = '|'.join(valid_format)
        while True:  # v1.3.0 修复代理配置scheme参数配置抛出AttributeError。
            scheme = console.input(
                _('Enter 「the proxy scheme」. Last record:「{last_record}」format - 「{fmt_valid_format}」:').format(
                    last_record=last_record if last_record else GetStdioParams.UNDEFINED,
                    fmt_valid_format=fmt_valid_format
                )).strip().lower()
            if scheme == '' and last_record is not None:
                scheme = last_record
            if Validator.is_valid_scheme(scheme, valid_format):
                console.print(_('「scheme」 set to: 「{scheme}」').format(
                    scheme=scheme
                ), style=ProcessConfig.stdio_style('scheme'))
                return {
                    'scheme': scheme,
                    'record_flag': True
                }
            else:
                log.warning(
                    _('Unexpected parameter "{scheme}", please enter a valid proxy scheme! Supported values - 「{fmt_valid_format}」!').format(
                        scheme=scheme,
                        fmt_valid_format=fmt_valid_format
                    ))

    @staticmethod
    @ProcessConfig.get_system_proxy('hostname')
    def get_hostname(proxy_config: dict, last_record: str, valid_format: str = 'x.x.x.x'):
        hostname = None
        while True:
            scheme, i, __ = ProcessConfig.get_proxy_info(proxy_config).values()
            # 输入代理IP地址。
            try:
                hostname = console.input(
                    _('Enter 「the IP address」 for proxy scheme "{scheme}". Last record:「{last_record}」format - 「{valid_format}」:').format(
                        scheme=scheme,
                        last_record=last_record if last_record else GetStdioParams.UNDEFINED,
                        valid_format=valid_format
                    )).strip()
                if hostname == '' and last_record is not None:
                    hostname = last_record
                if Validator.is_valid_hostname(hostname):
                    console.print(_('「hostname」 set to: 「{hostname}」').format(
                        hostname=hostname
                    ), style=ProcessConfig.stdio_style('hostname'))
                    return {
                        'hostname': hostname,
                        'record_flag': True
                    }
            except ValueError:
                log.warning(
                    _('"{hostname}" is not 「an IP address」, please enter a valid IPv4 address! Supported values - 「{valid_format}」!').format(
                        hostname=hostname,
                        valid_format=valid_format
                    ))

    @staticmethod
    @ProcessConfig.get_system_proxy('port')
    def get_port(proxy_config: dict, last_record: str, valid_format: str = '0~65535'):
        port = None
        # 输入代理端口。
        while True:
            try:  # hostname,scheme可能出现None。
                scheme, hostname, __ = ProcessConfig.get_proxy_info(proxy_config).values()
                port = console.input(
                    _('Enter 「the proxy port」 for IP "{hostname}" and scheme "{scheme}". Last record:「{last_record}」format - 「{valid_format}」:').format(
                        hostname=hostname,
                        scheme=scheme,
                        last_record=last_record if last_record else GetStdioParams.UNDEFINED,
                        valid_format=valid_format
                    )).strip()
                if port == '' and last_record is not None:
                    port = last_record
                if Validator.is_valid_port(port):
                    console.print(_('「port」 set to: 「{port}」').format(
                        port=port
                    ), style=ProcessConfig.stdio_style('port'))
                    return {
                        'port': int(port),
                        'record_flag': True
                    }
                else:
                    log.warning(_('Unexpected parameter "{port}", the port must be between 「{valid_format}」!').format(
                        port=port,
                        valid_format=valid_format
                    ))
            except ValueError:
                log.warning(
                    _('Unexpected parameter "{port}", please enter a valid integer! Supported values - 「{valid_format}」').format(
                        port=port,
                        valid_format=valid_format
                    ))
            except Exception as e:
                log.error(_('Unexpected error due to "{error}"').format(
                    error=e))

    @staticmethod
    def get_proxy_authentication():
        # 是否需要认证。
        style = ProcessConfig.stdio_style('proxy_authentication')
        valid_format: str = 'y|n'
        while True:
            is_proxy = console.input(
                _('Does the proxy require 「authentication」? - 「{valid_format}」(default n):').format(
                    valid_format=valid_format
                )).strip().lower()
            if is_proxy == 'y':
                username = console.input(_('Enter 「the username」:')).strip()
                password = console.input(_('Enter 「the password」:')).strip()
                console.print(_('Set to:「proxy requires authentication」').format(), style=style)
                return {'username': username, 'password': password, 'record_flag': True}
            elif is_proxy in ('n', ''):
                console.print(_('Set to:「proxy does not require authentication」').format(), style=style)
                return {'username': None, 'password': None, 'record_flag': True}
            else:
                log.warning(_('Unexpected parameter "{is_proxy}", supported values - 「{valid_format}」!').format(
                    is_proxy=is_proxy,
                    valid_format=valid_format
                ))


class BotCommandText:
    HELP: tuple = ('help', _('Show available commands.\n`/help`'))
    DOWNLOAD: tuple = (
        'download',
        _('Assign a new download task (see the manual for multiple usages).\n`/download https://t.me/x/x start_id end_id`'))
    TABLE: tuple = ('table', _('Output current download statistics in the terminal.\n`/table`'))
    FORWARD: tuple = ('forward',
                      _('Forward from channel A to channel B, start ID and end ID.\n`/forward https://t.me/A https://t.me/B 1 100`'))
    EXIT: tuple = ('exit', _('Exit the software.\n`/exit`'))
    LISTEN_DOWNLOAD: tuple = ('listen_download',
                              _('Listen to the latest messages (any message) of the link for downloading.\n`/listen_download https://t.me/A https://t.me/B https://t.me/n`'))
    LISTEN_FORWARD: tuple = (
        'listen_forward',
        _('Listen to the latest messages (any message) of the link for forwarding.\n`/listen_forward origin_channel target_channel`'))
    LISTEN_INFO: tuple = ('listen_info', _('View created listen information.\n`/listen_info`'))
    UPLOAD: tuple = ('upload', _('Upload a local file to the specified channel.\n`/upload local_file target_channel`'))
    UPLOAD_R: tuple = ('upload_r',
                       _('Recursively upload a folder (including subfolders) to the specified channel.\n`/upload_r local_folder target_channel`'))
    DOWNLOAD_CHAT: tuple = ('download_chat',
                            _('Get all content of the channel, filter by custom conditions, and finally download the content the user needs.\n`/download_chat channel_link`'))
    AUTH: tuple = ('auth',
                   _('Add/remove/view users authorized to use the bot, supporting user ID or @username.\n`/auth` or `/auth 1234567890` or `/auth @username`'))

    @staticmethod
    def with_description(text: tuple) -> str:
        return f'/{text[0]} - {text[1]}'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value

    @staticmethod
    def commands() -> List[str]:
        return [i[0] for i in BotCommandText()]

    @staticmethod
    def commands_with_prefix() -> List[str]:
        return [f'/{i}' for i in BotCommandText.commands()]


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
    DOWNLOAD_LINK: tuple = (BotStepKeyword.LINK, _('⬇️Please send the link to download'))
    DOWNLOAD_CHAT_LINK: tuple = (BotStepKeyword.LINK, _('💬Please send the channel link to download'))
    UPLOAD_PATH: tuple = (BotStepKeyword.PATH, _('📤Please send the local file path to upload'))
    UPLOAD_TARGET: tuple = (BotStepKeyword.TARGET, _('📤Please send the target channel link to upload to'))
    UPLOAD_R_PATH: tuple = (BotStepKeyword.PATH, _('📁Please send the local folder path to upload'))
    UPLOAD_R_TARGET: tuple = (BotStepKeyword.TARGET, _('📁Please send the target channel link to upload to'))
    FORWARD_ORIGIN: tuple = (BotStepKeyword.ORIGIN, _('↗️Please send the source channel link'))
    FORWARD_TARGET: tuple = (BotStepKeyword.TARGET, _('↗️Please send the target channel link to forward to'))
    FORWARD_START_ID: tuple = (BotStepKeyword.START_ID, _('↗️Please send the start message ID (number)'))
    FORWARD_END_ID: tuple = (BotStepKeyword.END_ID, _('↗️Please send the end message ID (number)'))
    LISTEN_DOWNLOAD_ORIGIN: tuple = (BotStepKeyword.ORIGIN, _('🕵️Please send the channel link to listen and download'))
    LISTEN_FORWARD_ORIGIN: tuple = (BotStepKeyword.ORIGIN, _('📲Please send the channel link to listen'))
    LISTEN_FORWARD_TARGET: tuple = (BotStepKeyword.TARGET, _('📲Please send the target channel link to forward to'))


class BotMessage:
    RIGHT: str = _('✅The following links have created download tasks:\n')
    INVALID: str = _('🚫The following links are invalid and have been removed:\n')
    TASK_ASSIGN: str = _('🌟Task assigned.')
    TOO_MANY_MESSAGE: str = _('⚠️Message too long, will not display each item this time.')
    TOO_MANY_INVALID_DOWNLOAD_MESSAGE: str = _('⚠️{count} messages were skipped for download because they are invalid; too many to list individually.')
    TOO_MANY_INVALID_FORWARD_MESSAGE: str = _('⚠️{count} messages were skipped for forwarding because they no longer exist; too many to list individually.')


class BotButton:
    GITHUB: str = '📦GitHub'
    SUBSCRIBE_CHANNEL: str = _('📌Subscribe channel')
    VIDEO_TUTORIAL: str = _('🎬Video tutorial')
    PROXY_SELLER: str = _('🛒Buy proxy')
    PAY: str = _('💰Support author')
    OPEN_NOTICE: str = _('💬Startup notice|Disabled ❌')
    CLOSE_NOTICE: str = _('💬Startup notice|Enabled ✅')
    LINK_TABLE: str = _('🔗Link statistics')
    COUNT_TABLE: str = _('➕Count statistics')
    UPLOAD_TABLE: str = _('📤Upload statistics')
    HELP_PAGE: str = _('🛎️Help page')
    CLICK_VIEW: str = _('🖱Click to view')
    CLICK_DOWNLOAD: str = _('🖱Click to download')
    DOWNLOAD: str = _('⬇️Download')
    DOWNLOAD_UPLOAD: str = _('↕️Download then upload')
    TASK_ASSIGN: str = _('🌟Task assigned')
    RETRIEVE_MESSAGE: str = _('🔎Retrieving messages')
    RETRIEVE_COMMENT: str = _('🔎Retrieving comments')
    ASSIGNING_TASK: str = _('🚛Assigning tasks')
    DOWNLOAD_TASK_DOING: str = _('⬇️Download task in progress')
    DOWNLOAD_TASK_DONE: str = _('✅Download task completed')
    TASK_CANCEL: str = _('🗑️Task cancelled')
    EXECUTE_TASK: str = _('▶️Execute task')
    CANCEL_TASK: str = _('⏹️Cancel task')
    OK: str = _('✅OK')
    CANCEL: str = _('❌Cancel')
    DROP: str = _('🗑️Remove')
    REMOVE_AUTH: str = _('🗑️Remove authorization')
    IGNORE: str = _('👁️‍🗨️Ignore')
    RETURN: str = _('🔙Back')
    CONFIRM_AND_RETURN: str = _('↩️Confirm and back')
    LOOKUP_LISTEN_INFO: str = _('🔍View listening info')
    LOOKUP_AUTH_INFO: str = _('🔍View authorized users')
    AUTH: str = _('🔑Add/remove authorized users')
    VIEW_AUTH_LIST: str = _('👥View authorization list')
    EXPORT_TABLE: str = _('📊Export table settings')
    RESELECT: str = _('🔄Reselect')
    SETTING: str = _('⚙️Settings')
    MENU_DOWNLOAD: str = _('📁Download')
    MENU_LISTEN: str = _('🕵️Listen')
    MENU_UPLOAD: str = _('📤Upload')
    DOWNLOAD_MENU_TITLE: str = _('⬇️Create 「download」 task:')
    LISTEN_MENU_TITLE: str = _('🕵️Create 「listen」 task:')
    UPLOAD_MENU_TITLE: str = _('📤Create 「upload」 task:')
    AUTH_MENU: str = _('🔐Authorized users')
    LISTEN_DOWNLOAD_BTN: str = _('🕵️Listen & download')
    LISTEN_FORWARD_BTN: str = _('📲Listen & forward')
    OPEN_LINK_TABLE: str = _('📊Export link table|Disabled ❌')
    CLOSE_LINK_TABLE: str = _('📊Export link table|Enabled ✅')
    OPEN_COUNT_TABLE: str = _('📊Export count table|Disabled ❌')
    CLOSE_COUNT_TABLE: str = _('📊Export count table|Enabled ✅')
    OPEN_UPLOAD_TABLE: str = _('📊Export upload table|Disabled ❌')
    CLOSE_UPLOAD_TABLE: str = _('📊Export upload table|Enabled ✅')
    OPEN_EXIT_SHUTDOWN: str = _('⏻Shut down on exit|Disabled ❌')
    CLOSE_EXIT_SHUTDOWN: str = _('⏻Shut down on exit|Enabled ✅')
    ALREADY_REMOVE: str = _('✅Removed')
    UPLOAD_SETTING: str = _('📤Upload behavior settings')
    DOWNLOAD_SETTING: str = _('📥Download type settings')
    FORWARD_SETTING: str = _('↗️Forward type settings')
    OPEN_UPLOAD_DOWNLOAD: str = _('Upload after download|Disabled ❌')
    CLOSE_UPLOAD_DOWNLOAD: str = _('Upload after download|Enabled ✅')
    OPEN_UPLOAD_DOWNLOAD_DELETE: str = _('Current|Keep local files 📚')
    CLOSE_UPLOAD_DOWNLOAD_DELETE: str = _('Current|Delete local files 🗑')
    VIDEO_ON: str = _('🎬Video ✅')
    PHOTO_ON: str = _('🖼️Photo ✅')
    AUDIO_ON: str = _('🎵Audio ✅')
    VOICE_ON: str = _('🎤Voice ✅')
    ANIMATION_ON: str = '🎨GIF ✅'
    DOCUMENT_ON: str = _('📄Document ✅')
    TEXT_ON: str = _('💬Text message ✅')
    VIDEO_NOTE_ON: str = _('📹Video note ✅')
    LIVE_PHOTO_ON: str = _('📸Live photo ✅')
    VIDEO_OFF: str = _('🎬Video ❌')
    PHOTO_OFF: str = _('🖼️Photo ❌')
    AUDIO_OFF: str = _('🎵Audio ❌')
    VOICE_OFF: str = _('🎤Voice ❌')
    ANIMATION_OFF: str = '🎨GIF ❌'
    DOCUMENT_OFF: str = _('📄Document ❌')
    TEXT_OFF: str = _('💬Text message ❌')
    VIDEO_NOTE_OFF: str = _('📹Video note ❌')
    LIVE_PHOTO_OFF: str = _('📸Live photo ❌')
    DATE_RANGE_SETTING: str = _('📅Set date range')
    SELECT_START_DATE: str = _('⏮️Select start date')
    SELECT_END_DATE: str = _('⏭️Select end date')
    INPUT_KEYWORD: str = _('⌨️Please send me a keyword')
    DOWNLOAD_DTYPE_SETTING: str = _('📝Set download type')
    KEYWORD_FILTER_SETTING: str = _('🔑Set matching keyword')
    TOPIC_SETTING: str = _('🗂️Include topic')
    ENABLE_ALL: str = _('✅Enable all')
    DISABLE_ALL: str = _('❌Disable all')
    TOPIC_PREV_PAGE: str = _('⬅️Previous page')
    TOPIC_NEXT_PAGE: str = _('Next page➡️')
    TOPIC_PAGE_INFO: str = '📄{page}/{total}'
    TOPIC_BACK_TO_TOP: str = _('🔝Back to top')
    CONFIRM_KEYWORD: str = _('✅Confirm keyword')
    INCLUDE_COMMENT: str = _('✅Include comments')
    IGNORE_COMMENT: str = _('❌Include comments')
    CMD_DOWNLOAD: str = _('⬇️Download')
    CMD_UPLOAD: str = _('📤Upload')
    CMD_UPLOAD_R: str = _('📁Upload recursively')
    CMD_DOWNLOAD_CHAT: str = _('💬Download channel')
    CMD_FORWARD: str = _('↗️Forward')

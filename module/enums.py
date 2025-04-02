# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/7/2 0:59
# File:enums.py
import os
import sys
import ipaddress
from typing import Union

from module import console, log
from module.language import _t


class LinkType:
    SINGLE: str = 'single'
    GROUP: str = 'group'
    COMMENT: str = 'comment'
    TOPIC: str = 'topic'


class DownloadType:
    VIDEO: str = 'video'
    PHOTO: str = 'photo'
    DOCUMENT: str = 'document'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('_') and not callable(value):  # 排除特殊方法和属性。
                yield value


class DownloadStatus:
    DOWNLOADING = 'downloading'
    SUCCESS = 'success'
    FAILURE = 'failure'
    SKIP = 'skip'
    RETRY = 'retry'


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
    TYPE: str = 'type'
    RELOAD: str = 'reload'
    RELOAD_TIMES: str = 'reload times'
    CURRENT_TASK: str = 'current task'
    REASON: str = 'reason'


class Extension:
    PHOTO = {'image/avif': 'avif',
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
    VIDEO = {'video/mp4': 'mp4',
             'video/mpeg': 'mpg',
             'video/quicktime': 'qt',
             'video/webm': 'webm',
             'video/x-msvideo': 'avi',
             'video/x-sgi-movie': 'movie',
             'video/x-matroska': 'mkv'
             }


class GradientColor:
    # 生成渐变色:https://photokit.com/colors/color-gradient/?lang=zh
    BLUE2PURPLE_14 = ['#0ebeff', '#21b4f9', '#33abf3', '#46a1ed', '#5898e8', '#6b8ee2', '#7d85dc', '#907bd6', '#a272d0',
                      '#b568ca', '#c75fc5', '#da55bf', '#ec4cb9', '#ff42b3']
    GREEN2PINK_11 = ['#00ff40', '#14f54c', '#29eb58', '#3de064', '#52d670', '#66cc7c', '#7ac288', '#8fb894', '#a3ada0',
                     '#b8a3ac', '#cc99b8']
    GREEN2BLUE_10 = ['#84fab0', '#85f6b8', '#86f1bf', '#88edc7', '#89e9ce', '#8ae4d6', '#8be0dd', '#8ddce5', '#8ed7ec',
                     '#8fd3f4']
    YELLOW2GREEN_10 = ['#d4fc79', '#cdfa7d', '#c6f782', '#bff586', '#b8f28b', '#b2f08f', '#abed94', '#a4eb98',
                       '#9de89d', '#96e6a1']
    ORANGE2YELLOW_15 = ['#f08a5d', '#f1915e', '#f1985f', '#f29f60', '#f3a660', '#f3ad61', '#f4b462', '#f5bc63',
                        '#f5c364', '#f6ca65', '#f6d166', '#f7d866', '#f8df67', '#f8e668', '#f9ed69']
    NEW_LIFE = ['#43e97b', '#42eb85', '#41ed8f', '#3fee9a', '#3ef0a4', '#3df2ae', '#3cf4b8', '#3af5c3', '#39f7cd',
                '#38f9d7']

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


class Validator:
    @staticmethod
    def is_contain_chinese(text: str) -> bool:
        for ch in text:
            if u'\u4e00' <= ch <= u'\u9fff':
                log.warning('如果无法正常下载,请尝试不使用中文路径后重试。')
                return True
        return False

    @staticmethod
    def is_valid_api_id(api_id: str, valid_length: int = 32) -> bool:
        try:
            if len(api_id) < valid_length:
                if api_id.isdigit():
                    return True
                else:
                    log.warning(f'意外的参数:"{api_id}",不是「纯数字」请重新输入!')
                    return False
            else:
                log.warning(f'意外的参数,填写的"{api_id}"可能是「api_hash」,请填入正确的「api_id」!')
                return False
        except (AttributeError, TypeError):
            log.error('手动编辑config.yaml时,api_id需要有引号!')
            return False

    @staticmethod
    def is_valid_api_hash(api_hash: str, valid_length: int = 32) -> bool:
        return len(str(api_hash)) == valid_length

    @staticmethod
    def is_valid_bot_token(bot_token: str, valid_format: str = ':') -> bool:
        if valid_format in bot_token:
            return True
        else:
            return False

    @staticmethod
    def is_valid_links_file(file_path: str, valid_format: str = '.txt') -> bool:
        file_path = os.path.normpath(file_path)
        return os.path.isfile(file_path) and file_path.endswith(valid_format)

    @staticmethod
    def is_valid_save_directory(save_directory: str) -> bool:
        if not os.path.exists(save_directory):
            while True:
                try:
                    question = console.input(f'目录:"{save_directory}"不存在,是否创建? - 「y|n」(默认y):').strip().lower()
                    if question in ('y', ''):
                        os.makedirs(save_directory, exist_ok=True)
                        console.log(f'成功创建目录:"{save_directory}"')
                        break
                    elif question == 'n':
                        break
                    else:
                        log.warning(f'意外的参数:"{question}",支持的参数 - 「y|n」')
                except Exception as e:
                    log.error(f'意外的错误,原因:"{e}"')
                    break
        return os.path.isdir(save_directory)

    @staticmethod
    def is_valid_max_download_task(max_tasks: int) -> bool:
        try:
            return int(max_tasks) > 0
        except ValueError:
            return False
        except Exception as e:
            log.error(f'意外的错误,原因:"{e}"')

    @staticmethod
    def is_valid_enable_proxy(enable_proxy: Union[str, bool]) -> bool:
        if enable_proxy in ('y', 'n'):
            return True

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
    def is_valid_download_type(dtype: Union[int, str]) -> bool:
        try:
            _dtype = int(dtype) if isinstance(dtype, str) else dtype
            return 0 < _dtype < 4
        except ValueError:  # 处理非整数字符串的情况
            return False
        except TypeError:  # 处理传入非数字类型的情况
            return False
        except Exception as e:
            log.error(f'意外的错误,原因:"{e}"')
            return False


class ProcessConfig:
    @staticmethod
    def set_dtype(_dtype) -> list:
        i_dtype = int(_dtype)  # 因为终端输入是字符串，这里需要转换为整数。
        if i_dtype == 1:
            return [DownloadType.VIDEO]
        elif i_dtype == 2:
            return [DownloadType.PHOTO]
        elif i_dtype == 3:
            return [DownloadType.VIDEO, DownloadType.PHOTO]

    @staticmethod
    def get_dtype(download_dtype: list) -> dict:
        """获取所需下载文件的类型。"""
        if DownloadType.DOCUMENT in download_dtype:
            download_dtype.remove(DownloadType.DOCUMENT)
        dt_length = len(download_dtype)
        if dt_length == 1:
            dtype: str = download_dtype[0]
            if dtype == DownloadType.VIDEO:
                return {'video': True, 'photo': False}
            elif dtype == DownloadType.PHOTO:
                return {'video': False, 'photo': True}
        elif dt_length == 2:
            return {'video': True, 'photo': True}
        return {'error': True}

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
            'download_type': 6,
            'is_shutdown': 7,
            'enable_proxy': 8,
            'config_proxy': 9,
            'scheme': 10,
            'hostname': 11,
            'port': 12,
            'proxy_authentication': 13
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
        if all(basic_truth_table) is False:
            console.print('请配置代理!', style=ProcessConfig.stdio_style('config_proxy'))
            result: bool = True
        if any(advance_account_truth_table) and all(advance_account_truth_table) is False:
            log.warning('代理账号或密码未输入!')
            result: bool = True
        return result

    @staticmethod
    def get_proxy_info(proxy_config: dict) -> dict:
        return {
            'scheme': proxy_config.get('scheme', '未知'),
            'hostname': proxy_config.get('hostname', '未知'),
            'port': proxy_config.get('port', '未知')
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
            console.print('\n输入超时,已自动设置为默认值。\n', style='#FF4689')

        try:
            if sys.platform == 'win32':
                import time
                import msvcrt
                console.print(prompt, end='')
                start_time: float = time.time()
                input_buffer: list = []

                while True:
                    if msvcrt.kbhit():  # 检测是否有键盘输入。
                        char = msvcrt.getwch()
                        if char == '\r':  # 回车键结束输入。
                            user_input = ''.join(input_buffer)
                            print('\n') if user_input in ('y', 'n', '') else None
                            return user_input.strip() or default
                        elif char in ('\x08', '\b'):  # Backspace 键处理。
                            if input_buffer:
                                input_buffer.pop()
                                print('\b \b', end='', flush=True)  # 删除控制台上的最后一个字符。
                        else:
                            input_buffer.append(char)
                            console.print(char, end='')
                    elif time.time() - start_time > timeout:
                        timeout_notice()
                        return default
                    time.sleep(0.1)
            else:
                import select
                sys.stdout.write(prompt)
                sys.stdout.flush()
                ready, _, _ = select.select([sys.stdin], [], [], timeout)
                if ready:
                    return sys.stdin.readline().strip() or default
                timeout_notice()
                return default
        except Exception as e:
            log.exception(f'无法自动设置!请手动进行设置,{_t(KeyWord.REASON)}:"{e}"')
            return console.input(error_prompt if error_prompt else prompt)

    @staticmethod
    def get_is_ki_save_config(valid_format: str = 'y|n') -> dict:
        while True:
            is_save_config: str = console.input(
                f'「退出提示」是否需要保存当前已填写的参数? - 「{valid_format}」:').strip().lower()
            if is_save_config == 'y':
                return {'is_ki_save_config': True}
            elif is_save_config == 'n':
                return {'is_ki_save_config': False}
            else:
                log.warning(f'意外的参数:"{is_save_config}",支持的参数 - 「{valid_format}」')

    @staticmethod
    def get_is_re_config(valid_format: str = 'y|n') -> dict:
        prompt: str = f'检测到已配置完成的配置文件,是否需要重新配置?(之前的配置文件将为你备份到当前目录下) - 「{valid_format}」'
        timeout: int = 5
        while True:
            is_re_config: str = GetStdioParams.__timeout_input(
                prompt=f'{prompt}({timeout}秒后自动设置为默认n):',
                error_prompt=f'{prompt}(默认n):',
                default='n',
                timeout=timeout
            ).strip().lower()
            if is_re_config == 'y':
                return {'is_re_config': True}
            elif is_re_config in ('n', ''):
                return {'is_re_config': False}
            else:
                console.print('\n') if sys.platform == 'win32' else None
                log.warning(f'意外的参数:"{is_re_config}",支持的参数 - 「{valid_format}」(默认n)')

    @staticmethod
    def get_is_change_account(valid_format: str = 'y|n') -> dict:
        style: str = '#FF4689'
        while True:
            is_change_account = console.input('是否需要切换账号? - 「y|n」(默认n):').strip().lower()
            if is_change_account in ('n', ''):
                console.print('用户不需要切换「账号」。', style=style)
                return {'is_change_account': False}
            elif is_change_account == 'y':
                console.print('用户需要切换「账号」。', style=style)
                return {'is_change_account': True}
            else:
                log.warning(f'意外的参数:"{is_change_account}",支持的参数 - 「{valid_format}」!')

    @staticmethod
    def get_api_id(last_record: str) -> dict:
        while True:
            api_id = console.input(
                f'请输入「api_id」上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」:').strip()
            if api_id == '' and last_record is not None:
                api_id = last_record
            if Validator.is_valid_api_id(api_id):
                console.print(f'已设置「api_id」为:「{api_id}」', style=ProcessConfig.stdio_style('api_id'))
                return {
                    'api_id': api_id,
                    'record_flag': True
                }

    @staticmethod
    def get_api_hash(last_record: str, valid_length: int = 32) -> dict:
        while True:
            api_hash = console.input(
                f'请输入「api_hash」上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」:').strip().lower()
            if api_hash == '' and last_record is not None:
                api_hash = last_record
            if Validator.is_valid_api_hash(api_hash, valid_length):
                console.print(f'已设置「api_hash」为:「{api_hash}」', style=ProcessConfig.stdio_style('api_hash'))
                return {
                    'api_hash': api_hash,
                    'record_flag': True
                }
            else:
                log.warning(f'意外的参数:"{api_hash}",不是一个「{valid_length}位」的「值」!请重新输入!')

    @staticmethod
    def get_enable_bot(valid_format: str = 'y|n') -> dict:
        while True:
            enable_bot = console.input('是否启用「机器人」(需要提供bot_token)? - 「y|n」(默认n):').strip().lower()
            if enable_bot in ('n', ''):
                console.print(f'已设置为不启用「机器人」。', style=ProcessConfig.stdio_style('bot_token'))
                return {'enable_bot': False}
            elif enable_bot == 'y':
                console.print(f'请配置「bot_token」。', style=ProcessConfig.stdio_style('bot_token'))
                return {'enable_bot': True}
            else:
                log.warning(f'意外的参数:"{enable_bot}",支持的参数 - 「{valid_format}」!')

    @staticmethod
    def get_bot_token(last_record: str, valid_format: str = ':') -> dict:
        while True:
            bot_token = console.input(
                f'请输入当前账号的「bot_token」上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」:').strip()
            if bot_token == '' and last_record is not None:
                bot_token = last_record
            if Validator.is_valid_bot_token(bot_token, valid_format):
                console.print(f'已设置「bot_token」为:「{bot_token}」', style=ProcessConfig.stdio_style('bot_token'))
                return {
                    'bot_token': bot_token,
                    'record_flag': True
                }
            else:
                log.warning(f'意外的参数:"{bot_token}",「bot_token」中需要包含":",请重新输入!')

    @staticmethod
    def get_links(last_record: str, valid_format: str = '.txt') -> dict:
        # 输入需要下载的媒体链接文件路径,确保文件存在。
        links_file_path = None
        while True:
            try:
                links_file_path = console.input(
                    f'请输入需要下载的媒体链接的「完整路径」。上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」'
                    f'格式 - 「{valid_format}」:').strip()
                if links_file_path == '' and last_record is not None:
                    links_file_path = last_record
                if Validator.is_valid_links_file(links_file_path, valid_format):
                    console.print(f'已设置「links」为:「{links_file_path}」', style=ProcessConfig.stdio_style('links'))
                    Validator.is_contain_chinese(links_file_path)
                    return {
                        'links': links_file_path,
                        'record_flag': True
                    }
                elif not os.path.normpath(links_file_path).lower().endswith('.txt'):
                    log.warning(f'意外的参数:"{links_file_path}",文件路径必须以「{valid_format}」结尾,请重新输入!')
                else:
                    log.warning(
                        f'意外的参数:"{links_file_path}",文件「必须存在」(区分大小写),请重新输入!')
            except Exception as e:
                log.warning(
                    f'意外的参数:"{links_file_path}",文件路径必须以「{valid_format}」结尾,并且「必须存在」,请重新输入!{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_save_directory(last_record) -> dict:
        # 输入媒体保存路径,确保是一个有效的目录路径。
        while True:
            save_directory = console.input(
                f'请输入媒体「保存路径」。上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」:').strip()
            if save_directory == '' and last_record is not None:
                save_directory = last_record
            if Validator.is_valid_save_directory(save_directory):
                console.print(f'已设置「save_directory」为:「{save_directory}」',
                              style=ProcessConfig.stdio_style('save_directory'))
                Validator.is_contain_chinese(save_directory)
                return {
                    'save_directory': save_directory,
                    'record_flag': True
                }
            elif os.path.isfile(save_directory):
                log.warning(f'意外的参数:"{save_directory}",指定的路径是一个文件并非目录,请重新输入!')
            else:
                log.warning(f'意外的参数:"{save_directory}",指定的路径无效或不是一个目录,请重新输入!')

    @staticmethod
    def get_max_download_task(last_record) -> dict:
        # 输入最大下载任务数,确保是一个整数且不超过特定限制。
        default_prompt: str = '(默认5)' if last_record is None else ''
        while True:
            try:
                max_download_task = console.input(
                    f'请输入「最大下载任务数」。上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」'
                    f',值过高可能会导致网络相关问题,建议默认{default_prompt}:').strip()
                if max_download_task == '' and last_record is not None:
                    max_download_task = last_record
                if max_download_task == '':
                    max_download_task = 5
                if Validator.is_valid_max_download_task(max_download_task):
                    console.print(f'已设置「max_download_task」为:「{max_download_task}」',
                                  style=ProcessConfig.stdio_style('max_download_task'))
                    return {
                        'max_download_task': int(max_download_task),
                        'record_flag': True
                    }
                else:
                    log.warning(f'意外的参数:"{max_download_task}",任务数必须是「正整数」,请重新输入!')
            except Exception as e:
                log.error(f'意外的错误,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_download_type(last_record: Union[list, None]) -> dict:

        if isinstance(last_record, list):
            res: dict = ProcessConfig.get_dtype(download_dtype=last_record)
            if len(res) == 1:
                last_record = None
            elif res.get('video') and res.get('photo') is False:
                last_record = 1
            elif res.get('video') is False and res.get('photo'):
                last_record = 2
            elif res.get('video') and res.get('photo'):
                last_record = 3
        default_prompt: str = '(默认3)' if last_record is None else ''
        while True:
            download_type = console.input(
                f'输入需要下载的「媒体类型」。上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」'
                f'格式 - 「1.视频 2.图片 3.视频和图片」{default_prompt}:').strip()
            if download_type == '' and last_record is not None:
                download_type = last_record
            if download_type == '':
                download_type = 3
            if Validator.is_valid_download_type(download_type):
                console.print(
                    f'已设置「download_type」为:「{download_type}」',
                    style=ProcessConfig.stdio_style('download_type')
                )
                return {
                    'download_type': ProcessConfig.set_dtype(_dtype=download_type),
                    'record_flag': True
                }
            else:
                log.warning(f'意外的参数:"{download_type}",支持的参数 - 「1或2或3」')

    @staticmethod
    def get_is_shutdown(last_record: str, valid_format: str = 'y|n') -> dict:
        _style: str = ProcessConfig.stdio_style('is_shutdown')
        if last_record:
            last_record: str = 'y'
        elif last_record is False:
            last_record: str = 'n'
        else:
            last_record = GetStdioParams.UNDEFINED
        t = f'已设置「is_shutdown」为:「y」,下载完成后将自动关机!'  # v1.3.0 修复配置is_shutdown参数时显示错误。
        f = f'已设置「is_shutdown」为:「n」'
        default_prompt: str = '(默认n)' if last_record == GetStdioParams.UNDEFINED else ''
        while True:
            try:
                is_shutdown = console.input(
                    f'下载完成后是否「自动关机」。上一次的记录是:「{last_record}」 - 「{valid_format}」'
                    f'{default_prompt}:').strip().lower()
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
                    log.warning(f'意外的参数:"{is_shutdown}",支持的参数 - 「{valid_format}」')

            except Exception as e:
                log.error(f'意外的错误,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_enable_proxy(last_record: Union[str, bool], valid_format: str = 'y|n') -> dict:
        if last_record:
            ep_notice: str = 'y' if last_record else 'n'
        else:
            ep_notice: str = GetStdioParams.UNDEFINED
        default_prompt: str = '(默认n)' if ep_notice == GetStdioParams.UNDEFINED else ''
        while True:  # 询问是否开启代理。
            enable_proxy = console.input(
                f'是否需要使用「代理」。上一次的记录是:「{ep_notice}」'
                f'格式 - 「{valid_format}」{default_prompt}:').strip().lower()
            if enable_proxy == '' and last_record is not None:
                if last_record is True:
                    enable_proxy = 'y'
                elif last_record is False:
                    enable_proxy = 'n'
            elif enable_proxy == '':
                enable_proxy = 'n'
            if Validator.is_valid_enable_proxy(enable_proxy):
                if enable_proxy == 'y':
                    console.print(f'已设置「enable_proxy」为:「{enable_proxy}」',
                                  style=ProcessConfig.stdio_style('enable_proxy'))
                    return {'enable_proxy': True, 'record_flag': True}
                elif enable_proxy == 'n':
                    console.print(f'已设置「enable_proxy」为:「{enable_proxy}」',
                                  style=ProcessConfig.stdio_style('enable_proxy'))
                    return {'enable_proxy': False, 'record_flag': True}
            else:
                log.error(f'意外的参数:"{enable_proxy}",请输入有效参数!支持的参数 - 「{valid_format}」!')

    @staticmethod
    def get_scheme(last_record: str, valid_format: list) -> dict:
        if valid_format is None:
            valid_format: list = ['http', 'socks4', 'socks5']
        fmt_valid_format = '|'.join(valid_format)
        while True:  # v1.3.0 修复代理配置scheme参数配置抛出AttributeError。
            scheme = console.input(
                f'请输入「代理类型」。上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」'
                f'格式 - 「{fmt_valid_format}」:').strip().lower()
            if scheme == '' and last_record is not None:
                scheme = last_record
            if Validator.is_valid_scheme(scheme, valid_format):
                console.print(f'已设置「scheme」为:「{scheme}」', style=ProcessConfig.stdio_style('scheme'))
                return {
                    'scheme': scheme,
                    'record_flag': True
                }
            else:
                log.warning(
                    f'意外的参数:"{scheme}",请输入有效的代理类型!支持的参数 - 「{fmt_valid_format}」!')

    @staticmethod
    def get_hostname(proxy_config: dict, last_record: str, valid_format: str = 'x.x.x.x'):
        hostname = None
        while True:
            scheme, _, __ = ProcessConfig.get_proxy_info(proxy_config).values()
            # 输入代理IP地址。
            try:
                hostname = console.input(
                    f'请输入代理类型为:"{scheme}"的「ip地址」。上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」'
                    f'格式 - 「{valid_format}」:').strip()
                if hostname == '' and last_record is not None:
                    hostname = last_record
                if Validator.is_valid_hostname(hostname):
                    console.print(f'已设置「hostname」为:「{hostname}」', style=ProcessConfig.stdio_style('hostname'))
                    return {
                        'hostname': hostname,
                        'record_flag': True
                    }
            except ValueError:
                log.warning(
                    f'"{hostname}"不是一个「ip地址」,请输入有效的ipv4地址!支持的参数 - 「{valid_format}」!')

    @staticmethod
    def get_port(proxy_config: dict, last_record: str, valid_format: str = '0~65535'):
        port = None
        # 输入代理端口。
        while True:
            try:  # hostname,scheme可能出现None。
                scheme, hostname, __ = ProcessConfig.get_proxy_info(proxy_config).values()
                port = console.input(
                    f'请输入ip地址为:"{hostname}",代理类型为:"{scheme}"的「代理端口」。'
                    f'上一次的记录是:「{last_record if last_record else GetStdioParams.UNDEFINED}」'
                    f'格式 - 「{valid_format}」:').strip()
                if port == '' and last_record is not None:
                    port = last_record
                if Validator.is_valid_port(port):
                    console.print(f'已设置「port」为:「{port}」', style=ProcessConfig.stdio_style('port'))
                    return {
                        'port': int(port),
                        'record_flag': True
                    }
                else:
                    log.warning(f'意外的参数:"{port}",端口号必须在「{valid_format}」之间!')
            except ValueError:
                log.warning(f'意外的参数:"{port}",请输入一个有效的整数!支持的参数 - 「{valid_format}」')
            except Exception as e:
                log.error(f'意外的错误,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_proxy_authentication():
        # 是否需要认证。
        style = ProcessConfig.stdio_style('proxy_authentication')
        valid_format: str = 'y|n'
        while True:
            is_proxy = console.input(f'代理是否需要「认证」? - 「{valid_format}」(默认n):').strip().lower()
            if is_proxy == 'y':
                username = console.input('请输入「账号」:').strip()
                password = console.input('请输入「密码」:').strip()
                console.print(f'已设置为:「代理需要认证」', style=style)
                return {'username': username, 'password': password, 'record_flag': True}
            elif is_proxy in ('n', ''):
                console.print(f'已设置为:「代理不需要认证」', style=style)
                return {'username': None, 'password': None, 'record_flag': True}
            else:
                log.warning(f'意外的参数:"{is_proxy}",支持的参数 - 「{valid_format}」!')


class BotCommandText:
    HELP: tuple = ('help', '展示可用命令。')
    DOWNLOAD: tuple = (
        'download', '分配新的下载任务(多种使用方式见使用说明)。\n`/download https://t.me/x/x 起始ID 结束ID`')
    TABLE: tuple = ('table', '在终端输出当前下载情况的统计信息。')
    FORWARD: tuple = ('forward', '从频道A转发至频道B 起始ID 结束ID。\n`/forward https://t.me/A https://t.me/B 1 100`')
    LISTEN_FORWARD: tuple = ('listen_forward', '监听频道A最新的消息转发至频道B。\n`/listen_forward https://t.me/A https://t.me/B')
    EXIT: tuple = ('exit', '退出软件。')

    @staticmethod
    def with_description(text: tuple) -> str:
        return f'/{text[0]} - {text[1]}'


class BotCallbackText:
    NULL: str = 'null'
    PAY: str = 'pay'
    LINK_TABLE: str = 'link_table'
    COUNT_TABLE: str = 'count_table'
    BACK_HELP: str = 'back_help'
    NOTICE: str = 'notice'
    DOWNLOAD: str = 'download'

    def __iter__(self):
        for key, value in vars(self.__class__).items():
            if not key.startswith('__') and not callable(value):  # 排除特殊方法和属性
                yield value


class BotMessage:
    RIGHT: str = '✅以下链接已创建下载任务:\n'
    EXIST: str = '⚠️以下链接已存在已被移除:\n'
    INVALID: str = '🚫以下链接不合法已被移除:\n'


class BotButton:
    GITHUB: str = '📦GitHub'
    SUBSCRIBE_CHANNEL: str = '📌订阅频道'
    VIDEO_TUTORIAL: str = '🎬视频教程'
    PAY: str = '💰支持作者'
    OPEN_NOTICE: str = '⏰开启通知'
    CLOSE_NOTICE: str = '⏰关闭通知'
    LINK_TABLE: str = '🔗链接统计表'
    COUNT_TABLE: str = '➕计数统计表'
    HELP_PAGE: str = '🛎️帮助页面'
    CLICK_VIEW: str = '🖱点击查看'
    CLICK_DOWNLOAD: str = '🖱点击下载'
    TASK_ASSIGN: str = '✅任务已分配'

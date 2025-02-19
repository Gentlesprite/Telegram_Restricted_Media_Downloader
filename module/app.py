# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/7/25 12:32
# File:app.py
import os
import sys
import time
import datetime
import platform
import mimetypes
import subprocess
from typing import Dict, Tuple
from functools import wraps

import qrcode
import pyrogram
from pyrogram.errors import FloodWait, PhoneNumberInvalid
from rich.markdown import Markdown
from rich.table import Table, Style
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, TransferSpeedColumn

from module import yaml
from module import CustomDumper
from module import Session
from module import README
from module import console, log
from module import MAX_FILE_REFERENCE_TIME, SOFTWARE_FULL_NAME, __version__, __copyright__, __license__

from module.process_path import split_path, validate_title, truncate_filename, move_to_save_directory, \
    gen_backup_config, get_extension, safe_delete, compare_file_size, get_file_size
from module.enum_define import GradientColor, Banner, DownloadType, DownloadStatus, QrcodeRender, KeyWord, \
    Status, GetStdioParams, ProcessConfig


class TelegramRestrictedMediaDownloaderClient(pyrogram.Client):

    async def authorize(self) -> pyrogram.types.User:
        if self.bot_token:
            return await self.sign_in_bot(self.bot_token)
        console.print(
            f'Pyrogram is free software and comes with ABSOLUTELY NO WARRANTY. Licensed\n'
            f'under the terms of the {pyrogram.__license__}.')
        console.print(
            f'欢迎使用[#b4009e]{SOFTWARE_FULL_NAME}[/#b4009e](版本 {__version__})'
            f'基于Pyrogram(版本 {pyrogram.__version__})。')
        while True:
            try:
                if not self.phone_number:
                    while True:
                        value = console.input('请输入「电话号码」([#6a2c70]电话号码[/#6a2c70]需以[#b83b5e]「+地区」'
                                              '[/#b83b5e]开头!如:[#f08a5d]+86[/#f08a5d][#f9ed69]15000000000[/#f9ed69]):').strip()
                        if not value:
                            continue

                        confirm = console.input(
                            f'所输入的「{value}」是否[#B1DB74]正确[/#B1DB74]? - 「y|n」(默认y): ').strip().lower()
                        if confirm in ('y', ''):
                            break
                        else:
                            log.warning(f'意外的参数:"{confirm}",支持的参数 - 「y|n」')
                    if ':' in value:
                        self.bot_token = value
                        return await self.sign_in_bot(value)
                    else:
                        self.phone_number = value

                sent_code = await self.send_code(self.phone_number)
            except pyrogram.errors.BadRequest as e:
                console.print(e.MESSAGE)
                self.phone_number = None
                self.bot_token = None
            except (PhoneNumberInvalid, AttributeError) as e:
                self.phone_number = None
                self.bot_token = None
                log.error(f'「电话号码」错误,请重新输入!{KeyWord.REASON}:"{e.MESSAGE}"')
            else:
                break

        sent_code_descriptions = {
            pyrogram.enums.SentCodeType.APP: 'Telegram app',
            pyrogram.enums.SentCodeType.SMS: 'SMS',
            pyrogram.enums.SentCodeType.CALL: 'phone call',
            pyrogram.enums.SentCodeType.FLASH_CALL: 'phone flash call',
            pyrogram.enums.SentCodeType.FRAGMENT_SMS: 'Fragment SMS',
            pyrogram.enums.SentCodeType.EMAIL_CODE: 'email code'
        }

        console.print(
            f'[#f08a5d]「验证码」[/#f08a5d]已通过[#f9ed69]「{sent_code_descriptions[sent_code.type]}」[/#f9ed69]发送。')

        while True:
            if not self.phone_code:
                self.phone_code = console.input('请输入收到的[#f08a5d]「验证码」[/#f08a5d]:').strip()

            try:
                signed_in = await self.sign_in(self.phone_number, sent_code.phone_code_hash, self.phone_code)
            except pyrogram.errors.BadRequest as e:
                console.print(e.MESSAGE)
                self.phone_code = None
            except pyrogram.errors.SessionPasswordNeeded as _:
                console.print(
                    '当前登录账号设置了[#f08a5d]「两步验证」[/#f08a5d],需要提供两步验证的[#f9ed69]「密码」[/#f9ed69]。')

                while True:
                    console.print('密码提示:{}'.format(await self.get_password_hint()))

                    if not self.password:
                        self.password = console.input(
                            '输入[#f08a5d]「两步验证」[/#f08a5d]的[#f9ed69]「密码」[/#f9ed69](为空代表[#FF4689]忘记密码[/#FF4689]):',
                            password=self.hide_password).strip()

                    try:
                        if not self.password:
                            confirm = console.input(
                                '确认[#f08a5d]「恢复密码」[/#f08a5d]? - 「y|n」(默认y):').strip().lower()
                            if confirm in ('y', ''):
                                email_pattern = await self.send_recovery_code()
                                console.print(
                                    f'[#f08a5d]「恢复代码」[/#f08a5d]已发送到邮箱[#f9ed69]「{email_pattern}」[/#f9ed69]。')

                                while True:
                                    recovery_code = console.input('请输入[#f08a5d]「恢复代码」[/#f08a5d]:').strip()

                                    try:
                                        return await self.recover_password(recovery_code)
                                    except pyrogram.errors.BadRequest as e:
                                        console.print(e.MESSAGE)
                                    except Exception as _:
                                        console.print_exception()
                                        raise
                            else:
                                self.password = None
                        else:
                            return await self.check_password(self.password)
                    except pyrogram.errors.BadRequest as e:
                        console.print(e.MESSAGE)
                        self.password = None
            else:
                break

        if isinstance(signed_in, pyrogram.types.User):
            return signed_in

        while True:
            first_name = console.input('输入[#f08a5d]「名字」[/#f08a5d]:').strip()
            last_name = console.input('输入[#f9ed69]「姓氏」[/#f9ed69](为空代表跳过): ').strip()

            try:
                signed_up = await self.sign_up(
                    self.phone_number,
                    sent_code.phone_code_hash,
                    first_name,
                    last_name
                )
            except pyrogram.errors.BadRequest as e:
                console.print(e.MESSAGE)
            else:
                break

        if isinstance(signed_in, pyrogram.types.TermsOfService):
            console.print('\n' + signed_in.text + '\n')
            await self.accept_terms_of_service(signed_in.id)

        return signed_up


class Application:
    DIRECTORY_NAME: str = os.path.dirname(os.path.abspath(sys.argv[0]))  # 获取软件工作绝对目录。
    CONFIG_NAME: str = 'config.yaml'  # 配置文件名。
    BOT_NAME: str = 'TRMD_BOT'
    CONFIG_PATH: str = os.path.join(DIRECTORY_NAME, CONFIG_NAME)
    CONFIG_TEMPLATE: dict = {
        'api_id': None,
        'api_hash': None,
        'bot_token': None,
        'proxy': {
            'enable_proxy': None,
            'scheme': None,
            'hostname': None,
            'port': None,
            'username': None,
            'password': None
        },
        'links': None,
        'save_directory': None,  # v1.3.0 将配置文件中save_path的参数名修改为save_directory。
        'max_download_task': None,
        'is_shutdown': None,
        'download_type': None
    }
    TEMP_DIRECTORY: str = os.path.join(os.getcwd(), 'temp')
    BACKUP_DIRECTORY: str = 'ConfigBackup'
    ABSOLUTE_BACKUP_DIRECTORY: str = os.path.join(DIRECTORY_NAME, BACKUP_DIRECTORY)
    WORK_DIRECTORY: str = os.path.join(os.getcwd(), 'sessions')

    def __init__(self,
                 client_obj: callable = TelegramRestrictedMediaDownloaderClient,
                 guide: bool = True):
        self.client_obj: callable = client_obj
        self.platform: str = platform.system()
        self.history_timestamp: dict = {}
        self.input_link: list = []
        self.last_record: dict = {}
        self.difference_timestamp: dict = {}
        self.download_type: list = []
        self.record_dtype: set = set()
        self.config_path: str = Application.CONFIG_PATH
        self.work_directory: str = Application.WORK_DIRECTORY
        self.temp_directory: str = Application.TEMP_DIRECTORY
        self.record_flag: bool = False
        self.modified: bool = False
        self.get_last_history_record()
        self.is_change_account: bool = True
        self.re_config: bool = False
        self.config_guide() if guide else None
        self.config: dict = self.load_config()  # v1.3.0 修复重复询问重新配置文件。
        self.api_hash = self.config.get('api_hash')
        self.api_id = self.config.get('api_id')
        self.bot_token = self.config.get('bot_token')
        self.download_type: list = self.config.get('download_type')
        self.is_shutdown: bool = self.config.get('is_shutdown')
        self.links: str = self.config.get('links')
        self.max_download_task: int = self.config.get('max_download_task') if isinstance(
            self.config.get('max_download_task'), int) else 3
        self.proxy: dict = self.config.get('proxy', {})
        self.enable_proxy = self.proxy if self.proxy.get('enable_proxy') else None
        self.save_directory: str = self.config.get('save_directory')
        self.__get_download_type()
        self.current_task_num: int = 0
        self.max_retry_count: int = 3
        self.skip_video, self.skip_photo = set(), set()
        self.success_video, self.success_photo = set(), set()
        self.failure_video, self.failure_photo = set(), set()
        self.complete_link: set = set()
        self.link_info: dict = {}
        self.global_retry_task: int = 0
        self.progress = Progress(TextColumn('[bold blue]{task.fields[filename]}', justify='right'),
                                 BarColumn(bar_width=40),
                                 '[progress.percentage]{task.percentage:>3.1f}%',
                                 '•',
                                 '[bold green]{task.fields[info]}',
                                 '•',
                                 TransferSpeedColumn(),
                                 '•',
                                 TimeRemainingColumn(),
                                 console=console
                                 )

    @staticmethod
    def download_bar(current, total, progress, task_id) -> None:
        progress.update(task_id,
                        completed=current,
                        info=f'{MetaData.suitable_units_display(current)}/{MetaData.suitable_units_display(total)}',
                        total=total)

    def build_client(self) -> pyrogram.Client:
        """用填写的配置文件,构造pyrogram客户端。"""
        os.makedirs(self.work_directory, exist_ok=True)
        Session.WAIT_TIMEOUT = min(Session.WAIT_TIMEOUT + self.max_download_task ** 2, MAX_FILE_REFERENCE_TIME)
        return self.client_obj(name=SOFTWARE_FULL_NAME.replace(' ', ''),
                               api_id=self.api_id,
                               api_hash=self.api_hash,
                               proxy=self.enable_proxy,
                               workdir=self.work_directory,
                               max_concurrent_transmissions=self.max_download_task)
        # v1.3.7 新增多任务下载功能,无论是否Telegram会员。
        # https://stackoverflow.com/questions/76714896/pyrogram-download-multiple-files-at-the-same-time

    def print_count_table(self) -> None:
        """打印统计的下载信息的表格。"""
        header: tuple = ('种类&状态', '成功下载', '失败下载', '跳过下载', '合计')
        self.download_type.remove(
            DownloadType.document.text) if DownloadType.document.text in self.download_type else None
        success_video: int = len(self.success_video)
        failure_video: int = len(self.failure_video)
        skip_video: int = len(self.skip_video)
        success_photo: int = len(self.success_photo)
        failure_photo: int = len(self.failure_photo)
        skip_photo: int = len(self.skip_photo)
        total_video: int = sum([success_video, failure_video, skip_video])
        total_photo: int = sum([success_photo, failure_photo, skip_photo])
        rdt_length: int = len(self.record_dtype)
        if rdt_length == 1:
            _compare_dtype: list = list(self.record_dtype)[0]
            if _compare_dtype == DownloadType.video.text:  # 只有视频的情况。
                video_table = PanelTable(title='视频下载统计',
                                         header=header,
                                         data=[
                                             [DownloadType.t(DownloadType.video.text),
                                              success_video,
                                              failure_video,
                                              skip_video,
                                              total_video],
                                             ['合计', success_video,
                                              failure_video,
                                              skip_video,
                                              total_video]
                                         ]
                                         )
                video_table.print_meta()
            if _compare_dtype == DownloadType.photo.text:  # 只有图片的情况。
                photo_table = PanelTable(title='图片下载统计',
                                         header=header,
                                         data=[
                                             [DownloadType.t(DownloadType.photo.text),
                                              success_photo,
                                              failure_photo,
                                              skip_photo,
                                              total_photo],
                                             ['合计', success_photo,
                                              failure_photo,
                                              skip_photo,
                                              total_photo]
                                         ]
                                         )
                photo_table.print_meta()
        elif rdt_length == 2:
            media_table = PanelTable(title='媒体下载统计',
                                     header=header,
                                     data=[
                                         [DownloadType.t(DownloadType.video.text),
                                          success_video,
                                          failure_video,
                                          skip_video,
                                          total_video],
                                         [DownloadType.t(DownloadType.photo.text),
                                          success_photo,
                                          failure_photo,
                                          skip_photo,
                                          total_photo],
                                         ['合计', sum([success_video, success_photo]),
                                          sum([failure_video, failure_photo]),
                                          sum([skip_video, skip_photo]),
                                          sum([total_video, total_photo])]
                                     ]
                                     )
            media_table.print_meta()

    def print_link_table(self) -> bool or str:
        """打印统计的下载链接信息的表格。"""
        try:
            data: list = []
            for index, (link, info) in enumerate(self.link_info.items(), start=1):
                complete_num = int(info.get('complete_num'))
                member_num = int(info.get('member_num'))
                try:
                    rate = round(complete_num / member_num * 100, 2)
                except ZeroDivisionError:
                    rate = 0
                complete_rate = f'{complete_num}/{member_num}[{rate}%]'
                file_names = '\n'.join(info.get('file_name'))
                error_msg = info.get('error_msg')
                if not error_msg:
                    error_info = ''
                elif 'all_member' in error_msg:
                    error_info = str(error_msg.get('all_member'))
                else:
                    error_info = '\n'.join([f'{fn}: {err}' for fn, err in error_msg.items()])
                data.append([index, link, file_names, complete_rate, error_info])
            if data:
                panel_table = PanelTable(title='下载链接统计',
                                         header=('编号', '链接', '文件名', '完成率', '错误信息'),
                                         data=data,
                                         show_lines=True)
                panel_table.print_meta()
                return True
            else:
                return False
        except Exception as e:
            log.error(f'打印下载链接统计表时出错,{KeyWord.REASON}:"{e}"')
            return e

    def process_shutdown(self, second: int) -> None:
        """处理关机逻辑。"""
        self.shutdown_task(second=second) if self.is_shutdown else None

    def check_download_finish(self, sever_file_size: int,
                              temp_file_path: str,
                              save_directory: str,
                              with_move: bool = True) -> bool:
        """检测文件是否下完。"""
        temp_ext: str = '.temp'
        local_file_size: int = get_file_size(file_path=temp_file_path, temp_ext=temp_ext)
        format_local_size: str = MetaData.suitable_units_display(local_file_size)
        format_sever_size: str = MetaData.suitable_units_display(sever_file_size)
        _file_path: str = os.path.join(save_directory, split_path(temp_file_path).get('file_name'))
        file_path: str = _file_path[:-len(temp_ext)] if _file_path.endswith(temp_ext) else _file_path
        if compare_file_size(a_size=local_file_size, b_size=sever_file_size):
            if with_move:
                result: str = move_to_save_directory(temp_file_path=temp_file_path,
                                                     save_directory=save_directory).get('e_code')
                log.warning(result) if result is not None else None
            console.log(
                f'{KeyWord.FILE}:"{file_path}",'
                f'{KeyWord.SIZE}:{format_local_size},'
                f'{KeyWord.TYPE}:{DownloadType.t(self.guess_file_type(file_name=temp_file_path, status=DownloadStatus.success)[0].text)},'
                f'{KeyWord.STATUS}:{Status.SUCCESS}。',
            )
            return True
        console.log(
            f'{KeyWord.FILE}:"{file_path}",'
            f'{KeyWord.ERROR_SIZE}:{format_local_size},'
            f'{KeyWord.ACTUAL_SIZE}:{format_sever_size},'
            f'{KeyWord.TYPE}:{DownloadType.t(self.guess_file_type(file_name=temp_file_path, status=DownloadStatus.failure)[0].text)},'
            f'{KeyWord.STATUS}:{Status.FAILURE}。')
        safe_delete(file_p_d=temp_file_path)  # v1.2.9 修复临时文件删除失败的问题。
        return False

    def get_media_meta(self, message: pyrogram.types.Message, dtype) -> dict:
        """获取媒体元数据。"""
        file_id: int = getattr(message, 'id')
        temp_file_path: str = self.__get_temp_file_path(message, dtype)
        _sever_meta = getattr(message, dtype)
        sever_file_size: int = getattr(_sever_meta, 'file_size')
        file_name: str = split_path(temp_file_path).get('file_name')
        save_directory: str = os.path.join(self.save_directory, file_name)
        format_file_size: str = MetaData.suitable_units_display(sever_file_size)
        return {'file_id': file_id,
                'temp_file_path': temp_file_path,
                'sever_file_size': sever_file_size,
                'file_name': file_name,
                'save_directory': save_directory,
                'format_file_size': format_file_size}

    def get_valid_dtype(self, message) -> Dict[str, bool]:
        """获取媒体类型是否与所需下载的类型相匹配。"""
        valid_dtype = next((i for i in DownloadType.support_type() if getattr(message, i, None)),
                           None)  # 判断该链接是否为视频或图片,文档。
        is_document_type_valid = None
        # 当媒体文件是文档形式的,需要根据配置需求将视频和图片过滤出来。
        if getattr(message, 'document'):
            mime_type = message.document.mime_type  # 获取 document 的 mime_type 。
            # 只下载视频的情况。
            if DownloadType.video.text in self.download_type and DownloadType.photo.text not in self.download_type:
                if 'video' in mime_type:
                    is_document_type_valid = True  # 允许下载视频。
                elif 'image' in mime_type:
                    is_document_type_valid = False  # 跳过下载图片。
            # 只下载图片的情况。
            elif DownloadType.photo.text in self.download_type and DownloadType.video.text not in self.download_type:
                if 'video' in mime_type:
                    is_document_type_valid = False  # 跳过下载视频。
                elif 'image' in mime_type:
                    is_document_type_valid = True  # 允许下载图片。
            else:
                is_document_type_valid = True
        else:
            is_document_type_valid = True
        return {'valid_dtype': valid_dtype,
                'is_document_type_valid': is_document_type_valid}

    def __get_temp_file_path(self, message: pyrogram.types.Message,
                             dtype: DownloadType.text) -> str:
        """获取下载文件时的临时保存路径。"""
        file: str = ''
        os.makedirs(self.temp_directory, exist_ok=True)

        def _process_video(msg_obj: pyrogram.types, _dtype: DownloadType.text) -> str:
            """处理视频文件的逻辑。"""
            _default_mtype: str = 'video/mp4'  # v1.2.8 健全获取文件名逻辑。
            _meta_obj = getattr(msg_obj, _dtype)
            _title: str or None = getattr(_meta_obj, 'file_name', None)  # v1.2.8 修复当文件名不存在时,下载报错问题。
            try:
                if _title is None:
                    _title: str = 'None'
                else:
                    _title: str = os.path.splitext(_title)[0]
            except Exception as e:
                _title: str = 'None'
                log.warning(f'获取文件名时出错,已重命名为:"{_title}",{KeyWord.REASON}:"{e}"')
            _file_name: str = '{} - {}.{}'.format(
                getattr(msg_obj, 'id', 'None'),
                _title,
                get_extension(file_id=_meta_obj.file_id, mime_type=getattr(_meta_obj, 'mime_type', _default_mtype),
                              dot=False)
            )
            _file: str = os.path.join(self.temp_directory, validate_title(_file_name))
            return _file

        def _process_photo(msg_obj: pyrogram.types, _dtype: DownloadType.text) -> str:
            """处理视频图片的逻辑。"""
            _default_mtype: str = 'image/jpg'  # v1.2.8 健全获取文件名逻辑。
            _meta_obj = getattr(msg_obj, _dtype)
            _extension: str = 'unknown'
            if _dtype == DownloadType.photo.text:
                _extension: str = get_extension(file_id=_meta_obj.file_id, mime_type=_default_mtype,
                                                dot=False)
            elif _dtype == DownloadType.document.text:
                _extension: str = get_extension(file_id=_meta_obj.file_id,
                                                mime_type=getattr(_meta_obj, 'mime_type', _default_mtype),
                                                dot=False)
            _file_name: str = '{} - {}.{}'.format(
                getattr(msg_obj, 'id'),
                getattr(_meta_obj, 'file_unique_id', 'None'),
                _extension
            )
            _file: str = os.path.join(self.temp_directory, validate_title(_file_name))
            return _file

        if dtype == DownloadType.video.text:
            file: str = _process_video(msg_obj=message, _dtype=dtype)
        elif dtype == DownloadType.photo.text:
            file: str = _process_photo(msg_obj=message, _dtype=dtype)
        elif dtype == DownloadType.document.text:
            _mime_type = getattr(getattr(message, dtype), 'mime_type')
            if 'video' in _mime_type:
                file: str = _process_video(msg_obj=message, _dtype=dtype)
            elif 'image' in _mime_type:
                file: str = _process_photo(msg_obj=message, _dtype=dtype)
        else:
            file: str = os.path.join(self.temp_directory,
                                     f'{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")} - undefined.unknown')
        return truncate_filename(file)

    def __media_counter(func):
        """统计媒体下载情况(数量)的装饰器。"""

        @wraps(func)
        def wrapper(self, file_name, status):
            res = func(self, file_name, status)
            file_type, status = res
            if file_type == DownloadType.photo:
                if status == DownloadStatus.success:
                    self.success_photo.add(file_name)
                elif status == DownloadStatus.failure:
                    self.failure_photo.add(file_name)
                elif status == DownloadStatus.skip:
                    self.skip_photo.add(file_name)
                elif status == DownloadStatus.downloading:
                    self.current_task_num += 1
            elif file_type == DownloadType.video:
                if status == DownloadStatus.success:
                    self.success_video.add(file_name)
                elif status == DownloadStatus.failure:
                    self.failure_video.add(file_name)
                elif status == DownloadStatus.skip:
                    self.skip_video.add(file_name)
                elif status == DownloadStatus.downloading:
                    self.current_task_num += 1
            # v1.2.9 修复失败时重新下载时会抛出RuntimeError的问题。
            if self.failure_video and self.success_video:
                self.failure_video -= self.success_video  # 直接使用集合的差集操作。
            if self.failure_photo and self.success_photo:
                self.failure_photo -= self.success_photo
            return res

        return wrapper

    @__media_counter
    def guess_file_type(self, file_name: str, status: DownloadStatus) -> Tuple[DownloadType, DownloadStatus]:
        """预测文件类型。"""
        result = ''
        file_type, _ = mimetypes.guess_type(file_name)
        if file_type is not None:
            file_main_type: str = file_type.split('/')[0]
            if file_main_type == 'image':
                result = DownloadType.photo
            elif file_main_type == 'video':
                result = DownloadType.video
        return result, status

    def __get_download_type(self) -> None:
        """获取需要下载的文件类型。"""
        if self.download_type is not None and (
                DownloadType.video.text in self.download_type or DownloadType.photo.text in self.download_type):
            self.record_dtype.update(self.download_type)  # v1.2.4 修复特定情况结束后不显示表格问题。
            self.download_type.append(DownloadType.document.text)
        else:
            self.download_type: list = DownloadType.support_type()
            self.record_dtype: set = {DownloadType.video.text,
                                      DownloadType.photo.text}  # v1.2.4 修复此处报错问题v1.2.3此处有致命错误。
            console.log('已使用[#f08a5d]「默认」[/#f08a5d]下载类型:3.视频和图片。')

    def print_config_table(self) -> None:
        """打印用户所填写配置文件的表格。"""
        try:
            if self.enable_proxy:
                console.log(GradientColor.gen_gradient_text(
                    text='当前正在使用代理!',
                    gradient_color=GradientColor.green_to_blue))
                proxy_key: list = []
                proxy_value: list = []
                for i in self.proxy.items():
                    if i[0] not in ['username', 'password']:
                        key, value = i
                        proxy_key.append(key)
                        proxy_value.append(value)
                proxy_table = PanelTable(title='代理配置', header=tuple(proxy_key), data=[proxy_value])
                proxy_table.print_meta()
            else:
                console.log(GradientColor.gen_gradient_text(text='当前没有使用代理!',
                                                            gradient_color=GradientColor.new_life))
        except Exception as e:
            log.error(f'打印代理配置表时出错,{KeyWord.REASON}:"{e}"')
        try:
            # 展示链接内容表格。
            with open(file=self.links, mode='r', encoding='UTF-8') as _:
                res: list = [content.strip() for content in _.readlines()]
            if res:
                format_res: list = []
                for i in enumerate(res, start=1):
                    format_res.append(list(i))
                link_table = PanelTable(title='链接内容', header=('编号', '链接'),
                                        data=format_res)
                link_table.print_meta()
        except (FileNotFoundError, PermissionError, AttributeError) as e:  # v1.1.3 用户错误填写路径提示。
            log.error(f'读取"{self.links}"时出错,{KeyWord.REASON}:"{e}"')
        except Exception as e:
            log.error(f'打印链接内容统计表时出错,{KeyWord.REASON}:"{e}"')
        try:
            _dtype: list = self.download_type.copy()  # 浅拷贝赋值给_dtype,避免传入函数后改变原数据。
            data: list = [[DownloadType.t(DownloadType.video.text),
                           ProcessConfig.get_dtype(_dtype).get('video')],
                          [DownloadType.t(DownloadType.photo.text),
                           ProcessConfig.get_dtype(_dtype).get('photo')]]
            download_type_table = PanelTable(title='下载类型', header=('类型', '是否下载'), data=data)
            download_type_table.print_meta()
        except Exception as e:
            log.error(f'打印下载类型统计表时出错,{KeyWord.REASON}:"{e}"')

    def shutdown_task(self, second: int) -> None:
        """下载完成后自动关机的功能。"""
        try:
            if self.platform == 'Windows':
                # 启动关机命令 目前只支持对 Windows 系统的关机。
                shutdown_command: str = f'shutdown -s -t {second}'
                subprocess.Popen(shutdown_command, shell=True)  # 异步执行关机。
            else:
                shutdown_command: str = f'shutdown -h +{second // 60}'
                subprocess.Popen(shutdown_command, shell=True)  # 异步执行关机。
            # 实时显示倒计时。
            for remaining in range(second, 0, -1):
                console.print(f'即将在{remaining}秒后关机, 按「CTRL+C」可取消。', end='\r', style='#ff4805')
                time.sleep(1)
            console.print('\n关机即将执行!', style='#f6ad00')
        except KeyboardInterrupt:
            cancel_flag: bool = False
            # 如果用户按下 CTRL+C，取消关机。
            if self.platform == 'Windows':
                subprocess.Popen('shutdown -a', shell=True)  # 取消关机。
                cancel_flag: bool = True
            else:
                try:
                    # Linux/macOS 取消关机命令。
                    subprocess.Popen('shutdown -c', shell=True)
                    cancel_flag: bool = True
                except Exception as e:
                    log.warning(f'取消关机任务失败,可能是当前系统不支持,{KeyWord.REASON}:"{e}"')
            console.print('\n关机已被用户取消!', style='#4bd898') if cancel_flag else 0
        except Exception as e:
            log.error(f'执行关机任务失败,可能是当前系统不支持自动关机,{KeyWord.REASON}:"{e}"')

    def backup_config(self,
                      backup_config: dict,
                      error_config: bool = False,
                      force: bool = False) -> None:  # v1.2.9 更正backup_config参数类型。
        """备份当前的配置文件。"""
        if backup_config != Application.CONFIG_TEMPLATE or force:  # v1.2.9 修复比较变量错误的问题。
            backup_path: str = gen_backup_config(old_path=self.config_path,
                                                 absolute_backup_dir=Application.ABSOLUTE_BACKUP_DIRECTORY,
                                                 error_config=error_config)
            console.log(f'原来的配置文件已备份至"{backup_path}"', style='#B1DB74')
        else:
            console.log('配置文件与模板文件完全一致,无需备份。')

    def load_config(self) -> dict:
        """加载一次当前的配置文件,并附带合法性验证、缺失参数的检测以及各种异常时的处理措施。"""
        config: dict = Application.CONFIG_TEMPLATE.copy()
        try:
            if not os.path.exists(self.config_path):
                with open(file=self.config_path, mode='w', encoding='UTF-8') as f:
                    yaml.dump(Application.CONFIG_TEMPLATE, f, Dumper=CustomDumper)
                console.log('未找到配置文件,已生成新的模板文件. . .')
                self.re_config = True  # v1.3.4 修复配置文件不存在时,无法重新生成配置文件的问题。
            with open(self.config_path, 'r') as f:
                config: dict = yaml.safe_load(f)  # v1.1.4 加入对每个字段的完整性检测。
            compare_config: dict = config.copy()
            config: dict = self.__check_params(config)  # 检查所有字段是否完整,modified代表是否有修改记录(只记录缺少的)
            if config != compare_config or config == Application.CONFIG_TEMPLATE:  # v1.3.4 修复配置文件所有参数都为空时报错问题。
                self.re_config = True
        except UnicodeDecodeError as e:  # v1.1.3 加入配置文件路径是中文或特殊字符时的错误提示,由于nuitka打包的性质决定,
            # 中文路径无法被打包好的二进制文件识别,故在配置文件时无论是链接路径还是媒体保存路径都请使用英文命名。
            self.re_config = True
            log.error(
                f'读取配置文件遇到编码错误,可能保存路径中包含中文或特殊字符的文件夹。已生成新的模板文件. . .{KeyWord.REASON}:"{e}"')
            self.backup_config(config, error_config=self.re_config)
        except Exception as e:
            self.re_config = True
            console.print('「注意」链接路径和保存路径不能有引号!', style='#B1DB74')
            log.error(f'检测到无效或损坏的配置文件。已生成新的模板文件. . .{KeyWord.REASON}:"{e}"')
            self.backup_config(config, error_config=self.re_config)
        finally:
            if config is None:
                self.re_config = True
                log.warning('检测到空的配置文件。已生成新的模板文件. . .')
                config: dict = Application.CONFIG_TEMPLATE.copy()
            return config

    def save_config(self, config: dict) -> None:
        """保存配置文件。"""
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)

    def __check_params(self, config: dict, history=False) -> dict:
        """检查配置文件的参数是否完整。"""
        # 如果 config 为 None，初始化为一个空字典。
        if config is None:
            config = {}

        def add_missing_keys(target, template, log_message) -> None:
            """添加缺失的配置文件参数。"""
            for key, value in template.items():
                if key not in target:
                    target[key] = value
                    if not history:
                        console.log(log_message.format(key))
                        self.modified = True
                        self.record_flag = True

        def remove_extra_keys(target, template, log_message) -> None:
            """删除多余的配置文件参数。"""
            keys_to_remove: list = [key for key in target.keys() if key not in template]
            for key in keys_to_remove:
                target.pop(key)
                if not history:
                    console.log(log_message.format(key))
                    self.record_flag = True

        # 处理父级参数。
        add_missing_keys(target=config, template=Application.CONFIG_TEMPLATE, log_message='"{}"不在配置文件中,已添加。')
        # 特殊处理 proxy 参数。
        if 'proxy' in config:
            proxy_template = Application.CONFIG_TEMPLATE.get('proxy')
            proxy_config = config.get('proxy')

            # 确保 proxy_config 是字典。
            if not isinstance(proxy_config, dict):
                proxy_config: dict = {}
                config['proxy'] = proxy_config

            add_missing_keys(proxy_config, proxy_template, '"{}"不在proxy配置中,已添加。')
            remove_extra_keys(proxy_config, proxy_template, '"{}"不在proxy模板中,已删除。')

        # 删除父级模板中没有的字段。
        remove_extra_keys(config, Application.CONFIG_TEMPLATE, '"{}"不在模板中,已删除。')

        return config

    def ctrl_c(self):
        os.system('pause') if self.platform == 'Windows' else console.input('请按「Enter」键继续. . .')

    def __find_history_config(self) -> dict:
        """找到历史配置文件。"""
        if not self.history_timestamp:
            return {}
        if not self.difference_timestamp:
            return {}
        try:
            min_key: int = min(self.difference_timestamp.keys())
            min_diff_timestamp: str = self.difference_timestamp.get(min_key)
            min_config_file: str = self.history_timestamp.get(min_diff_timestamp)
            if not min_config_file:
                return {}
            last_config_file: str = os.path.join(Application.ABSOLUTE_BACKUP_DIRECTORY, min_config_file)  # 拼接文件路径。
            with open(file=last_config_file, mode='r', encoding='UTF-8') as f:
                config: dict = yaml.safe_load(f)
            last_record: dict = self.__check_params(config, history=True)  # v1.1.6修复读取历史如果缺失字段使得flag置True。

            if last_record == Application.CONFIG_TEMPLATE:
                # 从字典中删除当前文件。
                self.history_timestamp.pop(min_diff_timestamp, None)
                self.difference_timestamp.pop(min_key, None)
                # 递归调用。
                return self.__find_history_config()
            else:
                return last_record
        except Exception as _:
            return {}

    def get_last_history_record(self) -> None:
        """获取最近一次保存的历史配置文件。"""
        # 首先判断是否存在目录文件。
        try:
            res: list = os.listdir(Application.ABSOLUTE_BACKUP_DIRECTORY)
        except FileNotFoundError:
            return
        except Exception as e:
            log.error(f'读取历史文件时发生错误,{KeyWord.REASON}:"{e}"')
            return
        file_start: str = 'history_'
        file_end: str = '_config.yaml'

        now_timestamp: float = datetime.datetime.now().timestamp()  # 获取当前的时间戳。
        if res:
            for i in res:  # 找出离当前时间最近的配置文件。
                try:
                    if i.startswith(file_start) and i.endswith(file_end):
                        format_date_str = i.replace(file_start, '').replace(file_end, '').replace('_', ' ')
                        to_datetime_obj = datetime.datetime.strptime(format_date_str, '%Y-%m-%d %H-%M-%S')
                        timestamp = to_datetime_obj.timestamp()
                        self.history_timestamp[timestamp] = i
                except ValueError:
                    pass
                except Exception as _:
                    pass
            for i in self.history_timestamp.keys():
                self.difference_timestamp[now_timestamp - i] = i
            if self.history_timestamp:  # 如果有符合条件的历史配置文件。
                self.last_record: dict = self.__find_history_config()

        else:
            return

    def config_guide(self) -> None:
        """引导用户以交互式的方式修改、保存配置文件。"""
        pre_load_config: dict = self.load_config()
        gsp = GetStdioParams()
        # v1.1.0 更替api_id和api_hash位置,与telegram申请的api位置对应以免输错。
        try:
            if not self.modified and pre_load_config != Application.CONFIG_TEMPLATE:
                re_config: bool = gsp.get_is_re_config().get('is_re_config')
                if re_config:
                    self.re_config = re_config
                    pre_load_config: dict = Application.CONFIG_TEMPLATE.copy()
                    self.backup_config(backup_config=pre_load_config, error_config=False, force=True)
                    self.get_last_history_record()  # 更新到上次填写的记录。
                    self.is_change_account = gsp.get_is_change_account(valid_format='y|n').get(
                        'is_change_account')
                    if self.is_change_account:
                        if safe_delete(file_p_d=os.path.join(self.DIRECTORY_NAME, 'sessions')):
                            console.log('已删除旧会话文件,稍后需重新登录。')
                        else:
                            console.log(
                                '删除旧会话文件失败,请手动删除软件目录下的sessions文件夹,再进行下一步操作!')
            _api_id: str or None = pre_load_config.get('api_id')
            _api_hash: str or None = pre_load_config.get('api_hash')
            _bot_token: str or None = pre_load_config.get('bot_token')
            _links: str or None = pre_load_config.get('links')
            _save_directory: str or None = pre_load_config.get('save_directory')
            _max_download_task: int or None = pre_load_config.get('max_download_task') if isinstance(
                pre_load_config.get('max_download_task'), int) else None  # v1.4.0 修复同时下载任务数不询问是否配置问题。
            _download_type: list or None = pre_load_config.get('download_type')
            _is_shutdown: bool or None = pre_load_config.get('is_shutdown')
            _proxy_config: dict = pre_load_config.get('proxy', {})
            _enable_proxy: str or bool = _proxy_config.get('enable_proxy', False)
            _proxy_scheme: str or bool = _proxy_config.get('scheme', False)
            _proxy_hostname: str or bool = _proxy_config.get('hostname', False)
            _proxy_port: str or bool = _proxy_config.get('port', False)
            _proxy_username: str or bool = _proxy_config.get('username', False)
            _proxy_password: str or bool = _proxy_config.get('password', False)
            proxy_record: dict = self.last_record.get('proxy', {})  # proxy的历史记录。
            if any([not _api_id, not _api_hash, not _save_directory, not _max_download_task, not _download_type]):
                console.print('「注意」直接回车代表使用上次的记录。',
                              style='#B1DB74')
            if self.is_change_account or _api_id is None or _api_hash is None or self.re_config:
                if not _api_id:
                    api_id, record_flag = gsp.get_api_id(
                        last_record=self.last_record.get('api_id')).values()
                    if record_flag:
                        self.record_flag = record_flag
                        pre_load_config['api_id'] = api_id
                if not _api_hash:
                    api_hash, record_flag = gsp.get_api_hash(
                        last_record=self.last_record.get('api_hash'),
                        valid_length=32).values()
                    if record_flag:
                        self.record_flag = record_flag
                        pre_load_config['api_hash'] = api_hash
            if not _bot_token and self.re_config:
                enable_bot: bool = gsp.get_enable_bot(valid_format='y|n').get('enable_bot')
                if enable_bot:
                    bot_token, record_flag = gsp.get_bot_token(
                        last_record=self.last_record.get('bot_token'),
                        valid_format=':').values()
                    if record_flag:
                        self.record_flag = record_flag
                        pre_load_config['bot_token'] = bot_token
            if not _links or not _bot_token and self.re_config:
                links, record_flag = gsp.get_links(last_record=self.last_record.get('links'),
                                                   valid_format='.txt').values()
                if record_flag:
                    self.record_flag = record_flag
                    pre_load_config['links'] = links
            if not _save_directory or self.re_config:
                save_directory, record_flag = gsp.get_save_directory(
                    last_record=self.last_record.get('save_directory')).values()
                if record_flag:
                    self.record_flag = record_flag
                    pre_load_config['save_directory'] = save_directory
            if not _max_download_task or self.re_config:
                max_download_task, record_flag = gsp.get_max_download_task(
                    last_record=self.last_record.get('max_download_task')).values()
                if record_flag:
                    self.record_flag = record_flag
                    pre_load_config['max_download_task'] = max_download_task
            if not _download_type or self.re_config:
                download_type, record_flag = gsp.get_download_type(
                    last_record=self.last_record.get('download_type')).values()
                if record_flag:
                    self.record_flag = record_flag
                    pre_load_config['download_type'] = download_type
            if _is_shutdown is None or self.re_config:
                is_shutdown, _is_shutdown_record_flag = gsp.get_is_shutdown(
                    last_record=self.last_record.get('is_shutdown'),
                    valid_format='y|n').values()
                if _is_shutdown_record_flag:
                    self.record_flag = True
                    pre_load_config['is_shutdown'] = is_shutdown
            # 是否开启代理
            if not _enable_proxy and self.re_config:
                valid_format: str = 'y|n'
                is_enable_proxy, is_ep_record_flag = gsp.get_enable_proxy(
                    last_record=proxy_record.get('enable_proxy', False),
                    valid_format=valid_format).values()
                if is_ep_record_flag:
                    self.record_flag = True
                    _proxy_config['enable_proxy'] = is_enable_proxy
            # 如果需要使用代理。
            # 如果上面配置的enable_proxy为True或本来配置文件中的enable_proxy就为True。
            if _proxy_config.get('enable_proxy') is True or _enable_proxy is True:
                if ProcessConfig.is_proxy_input(proxy_config=_proxy_config):
                    if not _proxy_scheme:
                        scheme, record_flag = gsp.get_scheme(last_record=proxy_record.get('scheme'),
                                                             valid_format=['http', 'socks4',
                                                                           'socks5']).values()
                        if record_flag:
                            self.record_flag = True
                            _proxy_config['scheme'] = scheme
                    if not _proxy_hostname:
                        hostname, record_flag = gsp.get_hostname(
                            proxy_config=_proxy_config,
                            last_record=proxy_record.get('hostname'),
                            valid_format='x.x.x.x').values()
                        if record_flag:
                            self.record_flag = True
                            _proxy_config['hostname'] = hostname
                    if not _proxy_port:
                        port, record_flag = gsp.get_port(
                            proxy_config=_proxy_config,
                            last_record=proxy_record.get('port'),
                            valid_format='0~65535').values()
                        if record_flag:
                            self.record_flag = True
                            _proxy_config['port'] = port
                    if not all([_proxy_username, _proxy_password]):
                        username, password, record_flag = gsp.get_proxy_authentication().values()
                        if record_flag:
                            self.record_flag = True
                            _proxy_config['username'] = username
                            _proxy_config['password'] = password
        except KeyboardInterrupt:
            n: bool = True
            try:
                if self.record_flag:
                    print('\n')
                    if gsp.get_is_ki_save_config().get('is_ki_save_config'):
                        self.save_config(pre_load_config)
                        console.log('配置已保存!')
                    else:
                        console.log('不保存当前填写参数。')
                else:
                    raise SystemExit(0)
            except KeyboardInterrupt:
                n: bool = False
                print('\n')
                console.log('不保存当前填写参数(用户手动终止配置参数)。')
            finally:
                if n:
                    print('\n')
                    console.log('用户手动终止配置参数。')
                self.ctrl_c()
                raise SystemExit(0)
        self.save_config(pre_load_config)  # v1.3.0 修复不保存配置文件时,配置文件仍然保存的问题。


class PanelTable:
    def __init__(self, title: str, header: tuple, data: list, styles: dict = None, show_lines: bool = False):
        self.table = Table(title=title, highlight=True, show_lines=show_lines)
        self.table.title_style = Style(color='white', bold=True)
        # 添加列。
        for _, col in enumerate(header):
            style = styles.get(col, {}) if styles else {}
            self.table.add_column(col, **style)

        # 添加数据行。
        for row in data:
            self.table.add_row(*map(str, row))  # 确保数据项是字符串类型，防止类型错误。

    def print_meta(self):
        console.print(self.table, justify='center')


class MetaData:
    @staticmethod
    def check_run_env() -> bool:  # 检测是windows平台下控制台运行还是IDE运行。
        try:
            from ctypes import windll  # v1.2.9 避免非Windows平台运行时报错。
            return windll.kernel32.SetConsoleTextAttribute(windll.kernel32.GetStdHandle(-0xb), 0x7)
        except ImportError:  # v1.2.9 抛出错误代表非Windows平台。
            return True

    @staticmethod
    def pay():
        if MetaData.check_run_env():  # 是终端才打印,生产环境会报错。
            try:
                console.print(
                    MetaData.__qr_terminal_str(
                        'wxp://f2f0g8lKGhzEsr0rwtKWTTB2gQzs9Xg9g31aBvlpbILowMTa5SAMMEwn0JH1VEf2TGbS'),
                    justify='center')
                console.print(
                    GradientColor.gen_gradient_text(text='微信扫码支持作者,您的支持是我持续更新的动力。',
                                                    gradient_color=GradientColor.yellow_to_green),
                    justify='center')
            except Exception as _:
                return _

    @staticmethod
    def print_meta():
        console.print(GradientColor.gen_gradient_text(
            text=Banner.c,
            gradient_color=GradientColor.generate_gradient(
                start_color='#fa709a',
                end_color='#fee140',
                steps=10)),
            style='blink',
            highlight=False)
        console.print(f'[bold]{SOFTWARE_FULL_NAME} v{__version__}[/bold],\n[i]{__copyright__}[/i]'
                      )
        console.print(f'Licensed under the terms of the {__license__}', end='\n')
        console.print(GradientColor.gen_gradient_text('\t软件免费使用!并且在GitHub开源,如果你付费那就是被骗了。',
                                                      gradient_color=GradientColor.blue_to_purple))

    @staticmethod
    def suitable_units_display(number: int) -> str:
        result: dict = MetaData.__determine_suitable_units(number)
        return result.get('number') + result.get('unit')

    @staticmethod
    def __determine_suitable_units(number, unit=None) -> dict:
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        if unit in units:
            index = units.index(unit)
            value = number / (1024 ** index)
            return {'number': float('{:.2f}'.format(value)), 'unit': unit}
        else:
            values = [number]
            for i in range(len(units) - 1):
                if values[i] >= 1024:
                    values.append(values[i] / 1024)
                else:
                    break
            return {'number': '{:.2f}'.format(values[-1]), 'unit': units[len(values) - 1]}

    @staticmethod
    def print_helper():
        console.print(Markdown('# 配置文件说明'))
        console.print(Markdown(README))

    @staticmethod
    def __qr_terminal_str(str_obj: str, version: int = 1, render: callable = QrcodeRender.render_2by1) -> str:
        qr = qrcode.QRCode(version)
        qr.add_data(str_obj)
        qr.make()
        qr_row: int = len(qr.modules) + 2
        qr_col: int = len(qr.modules[0]) + 2
        qr_map: list = [[False for _ in range(qr_col)] for _ in range(qr_row)]
        for row_id, row in enumerate(qr.modules):
            for col_id, pixel in enumerate(row):
                qr_map[row_id + 1][col_id + 1] = pixel
        return render(qr_map)

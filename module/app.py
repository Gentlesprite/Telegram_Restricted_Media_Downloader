# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/7/25 12:32
# File:app.py
import os
import time
import datetime
import mimetypes
import subprocess
from functools import wraps
from typing import Dict, Union

import pyrogram

from module import Session, SLEEP_THRESHOLD
from module import console, log
from module import MAX_FILE_REFERENCE_TIME, SOFTWARE_FULL_NAME
from module.language import _t
from module.config import Config
from module.stdio import StatisticalTable, MetaData
from module.enums import DownloadType, DownloadStatus, KeyWord
from module.client import TelegramRestrictedMediaDownloaderClient
from module.path_tool import split_path, validate_title, truncate_filename, get_extension


class Application(Config, StatisticalTable):

    def __init__(self):
        Config.__init__(self)
        StatisticalTable.__init__(self)
        self.client = self.build_client()
        self.__get_download_type()
        self.current_task_num: int = 0

    def build_client(self) -> pyrogram.Client:
        """用填写的配置文件,构造pyrogram客户端。"""
        os.makedirs(self.work_directory, exist_ok=True)
        Session.WAIT_TIMEOUT = min(Session.WAIT_TIMEOUT + self.max_download_task ** 2, MAX_FILE_REFERENCE_TIME)
        return TelegramRestrictedMediaDownloaderClient(
            name=SOFTWARE_FULL_NAME.replace(' ', ''),
            api_id=self.api_id,
            api_hash=self.api_hash,
            proxy=self.enable_proxy,
            workdir=self.work_directory,
            max_concurrent_transmissions=self.max_download_task,
            sleep_threshold=SLEEP_THRESHOLD,
        )
        # v1.3.7 新增多任务下载功能,无论是否Telegram会员。
        # https://stackoverflow.com/questions/76714896/pyrogram-download-multiple-files-at-the-same-time

    def process_shutdown(self, second: int) -> None:
        """处理关机逻辑。"""
        self.shutdown_task(second=second) if self.is_shutdown else None

    def get_media_meta(self, message: pyrogram.types.Message, dtype) -> Dict[str, Union[int, str]]:
        """获取媒体元数据。"""
        file_id: int = getattr(message, 'id')
        temp_file_path: str = self.__get_temp_file_path(message, dtype)
        _sever_meta = getattr(message, dtype)
        sever_file_size: int = getattr(_sever_meta, 'file_size')
        file_name: str = split_path(temp_file_path).get('file_name')
        save_directory: str = os.path.join(self.save_directory, file_name)
        format_file_size: str = MetaData.suitable_units_display(sever_file_size)
        return {
            'file_id': file_id,
            'temp_file_path': temp_file_path,
            'sever_file_size': sever_file_size,
            'file_name': file_name,
            'save_directory': save_directory,
            'format_file_size': format_file_size
        }

    def get_valid_dtype(self, message) -> Dict[str, Union[str, bool]]:
        """获取媒体类型是否与所需下载的类型相匹配。"""
        valid_dtype = next((_ for _ in DownloadType() if getattr(message, _, None)), None)  # 判断该链接是否为视频或图片,文档。
        is_document_type_valid = None
        # 当媒体文件是文档形式的,需要根据配置需求将视频和图片过滤出来。
        if getattr(message, 'document'):
            mime_type = message.document.mime_type  # 获取 document 的 mime_type 。
            # 只下载视频的情况。
            if DownloadType.VIDEO in self.download_type and DownloadType.PHOTO not in self.download_type:
                if 'video' in mime_type:
                    is_document_type_valid = True  # 允许下载视频。
                elif 'image' in mime_type:
                    is_document_type_valid = False  # 跳过下载图片。
            # 只下载图片的情况。
            elif DownloadType.PHOTO in self.download_type and DownloadType.VIDEO not in self.download_type:
                if 'video' in mime_type:
                    is_document_type_valid = False  # 跳过下载视频。
                elif 'image' in mime_type:
                    is_document_type_valid = True  # 允许下载图片。
            else:
                is_document_type_valid = True
        else:
            is_document_type_valid = True
        return {
            'valid_dtype': valid_dtype,
            'is_document_type_valid': is_document_type_valid
        }

    def __get_temp_file_path(
            self, message: pyrogram.types.Message,
            dtype: str
    ) -> str:
        """获取下载文件时的临时保存路径。"""
        file: str = ''
        os.makedirs(self.temp_directory, exist_ok=True)

        def splice_chat_id(_file_name) -> str:
            try:
                chat_id = str(message.chat.id)
                if chat_id:
                    temp_directory_with_chat_id: str = os.path.join(self.temp_directory, chat_id)
                    os.makedirs(temp_directory_with_chat_id, exist_ok=True)
                    _file: str = os.path.join(temp_directory_with_chat_id, validate_title(_file_name))
                else:
                    raise ValueError('chat id is empty.')
            except Exception as e:
                _file: str = os.path.join(self.temp_directory, validate_title(_file_name))
                log.warning(f'拼接临时路径时,无法获取频道id,原因:{e}')
            return _file

        def _process_video(msg_obj: pyrogram.types, _dtype: str) -> str:
            """处理视频文件的逻辑。"""
            _default_mtype: str = 'video/mp4'  # v1.2.8 健全获取文件名逻辑。
            _meta_obj = getattr(msg_obj, _dtype)
            _title: Union[str, None] = getattr(_meta_obj, 'file_name', None)  # v1.2.8 修复当文件名不存在时,下载报错问题。
            try:
                if isinstance(_title, str):
                    if _title.lower().startswith('video_'):  # v1.5.6 尝试修复以日期命名的标题重复下载的问题。
                        _title = None
                if _title is None:
                    _title: str = 'None'
                else:
                    _title: str = os.path.splitext(_title)[0]
            except Exception as e:
                _title: str = 'None'
                log.warning(f'获取文件名时出错,已重命名为:"{_title}",{_t(KeyWord.REASON)}:"{e}"')
            _file_name: str = '{} - {}.{}'.format(
                getattr(msg_obj, 'id', 'None'),
                _title,
                get_extension(
                    file_id=_meta_obj.file_id,
                    mime_type=getattr(_meta_obj, 'mime_type', _default_mtype),
                    dot=False
                )
            )
            return splice_chat_id(_file_name)

        def _process_photo(msg_obj: pyrogram.types, _dtype: str) -> str:
            """处理视频图片的逻辑。"""
            _default_mtype: str = 'image/jpg'  # v1.2.8 健全获取文件名逻辑。
            _meta_obj = getattr(msg_obj, _dtype)
            _extension: str = 'unknown'
            if _dtype == DownloadType.PHOTO:
                _extension: str = get_extension(
                    file_id=_meta_obj.file_id,
                    mime_type=_default_mtype,
                    dot=False
                )
            elif _dtype == DownloadType.DOCUMENT:
                _extension: str = get_extension(
                    file_id=_meta_obj.file_id,
                    mime_type=getattr(_meta_obj, 'mime_type', _default_mtype),
                    dot=False
                )
            _file_name: str = '{} - {}.{}'.format(
                getattr(msg_obj, 'id'),
                getattr(_meta_obj, 'file_unique_id', 'None'),
                _extension
            )
            return splice_chat_id(_file_name)

        if dtype == DownloadType.VIDEO:
            file: str = _process_video(msg_obj=message, _dtype=dtype)
        elif dtype == DownloadType.PHOTO:
            file: str = _process_photo(msg_obj=message, _dtype=dtype)
        elif dtype == DownloadType.DOCUMENT:
            _mime_type = getattr(getattr(message, dtype), 'mime_type')
            if 'video' in _mime_type:
                file: str = _process_video(msg_obj=message, _dtype=dtype)
            elif 'image' in _mime_type:
                file: str = _process_photo(msg_obj=message, _dtype=dtype)
            elif _mime_type:
                try:
                    extension = _mime_type.split('/')[-1]
                    file: str = f'{getattr(message, "id", "0")} - {datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.{extension if extension else "unknown"}'
                except Exception as _:
                    file: str = f'{getattr(message, "id", "0")} - {datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.unknown'
        else:
            file: str = f'{getattr(message, "id", "0")} - {datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.unknown'
        return truncate_filename(file)

    def __on_media_record(func):
        """统计媒体下载情况(数量)的装饰器。"""

        @wraps(func)
        def wrapper(self, *args):
            res = func(self, *args)
            download_type = res
            file_name, download_status = args
            if download_type == DownloadType.PHOTO:
                if download_status == DownloadStatus.SUCCESS:
                    self.success_photo.add(file_name)
                elif download_status == DownloadStatus.FAILURE:
                    self.failure_photo.add(file_name)
                elif download_status == DownloadStatus.SKIP:
                    self.skip_photo.add(file_name)
                elif download_status == DownloadStatus.DOWNLOADING:
                    self.current_task_num += 1
            elif download_type == DownloadType.VIDEO:
                if download_status == DownloadStatus.SUCCESS:
                    self.success_video.add(file_name)
                elif download_status == DownloadStatus.FAILURE:
                    self.failure_video.add(file_name)
                elif download_status == DownloadStatus.SKIP:
                    self.skip_video.add(file_name)
                elif download_status == DownloadStatus.DOWNLOADING:
                    self.current_task_num += 1
            # v1.2.9 修复失败时重新下载时会抛出RuntimeError的问题。
            if self.failure_video and self.success_video:
                self.failure_video -= self.success_video  # 直接使用集合的差集操作。
            if self.failure_photo and self.success_photo:
                self.failure_photo -= self.success_photo
            return res

        return wrapper

    @__on_media_record
    def guess_file_type(self, *args) -> str:
        """预测文件类型。"""
        file_name: str = args[0]
        download_type: str = ''
        file_type, _ = mimetypes.guess_type(file_name)
        if file_type is not None:
            file_main_type: str = file_type.split('/')[0]
            if file_main_type == 'image':
                download_type = DownloadType.PHOTO
            elif file_main_type == 'video':
                download_type = DownloadType.VIDEO
        return download_type

    def __get_download_type(self) -> None:
        """获取需要下载的文件类型。"""
        if self.download_type is not None and (
                DownloadType.VIDEO in self.download_type or DownloadType.PHOTO in self.download_type):
            self.record_dtype.update(self.download_type)  # v1.2.4 修复特定情况结束后不显示表格问题。
            if DownloadType.DOCUMENT not in self.download_type:
                self.download_type.append(DownloadType.DOCUMENT)
        else:
            self.download_type: list = [_ for _ in DownloadType()]
            self.record_dtype: set = {
                DownloadType.VIDEO,
                DownloadType.PHOTO
            }  # v1.2.4 修复此处报错问题v1.2.3此处有致命错误。
            console.log('已使用[#f08a5d]「默认」[/#f08a5d]下载类型:「3.视频和图片」。')
        self.config['download_type'] = list(set(self.download_type))
        self.save_config(config=self.config)

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
                    log.warning(f'取消关机任务失败,可能是当前系统不支持,{_t(KeyWord.REASON)}:"{e}"')
            console.print('\n关机已被用户取消!', style='#4bd898') if cancel_flag else 0
        except Exception as e:
            log.error(f'执行关机任务失败,可能是当前系统不支持自动关机,{_t(KeyWord.REASON)}:"{e}"')

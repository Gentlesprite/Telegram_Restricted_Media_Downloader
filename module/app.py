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

from module import (
    Session,
    SLEEP_THRESHOLD,
    console,
    log,
    MAX_FILE_REFERENCE_TIME,
    SOFTWARE_FULL_NAME
)
from module.language import _t
from module.config import UserConfig
from module.stdio import StatisticalTable, MetaData
from module.client import TelegramRestrictedMediaDownloaderClient
from module.enums import (
    DownloadType,
    DownloadStatus,
    KeyWord
)
from module.path_tool import (
    split_path,
    validate_title,
    truncate_filename,
    get_extension
)


class Application(UserConfig, StatisticalTable):

    def __init__(self):
        UserConfig.__init__(self)
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
        self.shutdown_task(second=second) if self.config.get('is_shutdown') else None

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

    def __get_temp_file_path(
            self, message: pyrogram.types.Message,
            dtype: str
    ) -> str:
        """获取下载文件时的临时保存路径。"""

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

        os.makedirs(self.temp_directory, exist_ok=True)
        dt = DownloadFileName(message=message, download_type=dtype)
        if dtype == DownloadType.VIDEO:
            file_name: str = dt.get_video_filename()
        elif dtype == DownloadType.PHOTO:
            file_name: str = dt.get_photo_filename()
        elif dtype == DownloadType.DOCUMENT:
            file_name: str = dt.get_document_filename()
        else:
            file_name: str = f'{getattr(message, "id", "0")} - {datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.unknown'
        return truncate_filename(splice_chat_id(file_name))

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
            elif download_type == DownloadType.DOCUMENT:
                if download_status == DownloadStatus.SUCCESS:
                    self.success_document.add(file_name)
                elif download_status == DownloadStatus.FAILURE:
                    self.failure_document.add(file_name)
                elif download_status == DownloadStatus.SKIP:
                    self.skip_document.add(file_name)
                elif download_status == DownloadStatus.DOWNLOADING:
                    self.current_task_num += 1
            # v1.2.9 修复失败时重新下载时会抛出RuntimeError的问题。
            if self.failure_video and self.success_video:
                self.failure_video -= self.success_video  # 直接使用集合的差集操作。
            if self.failure_photo and self.success_photo:
                self.failure_photo -= self.success_photo
            if self.failure_document and self.success_document:
                self.failure_document -= self.success_document
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
            else:
                download_type = DownloadType.DOCUMENT

        return download_type

    def __get_download_type(self) -> None:
        """获取需要下载的文件类型,在不存在时将设置为所有已支持的下载类型。"""
        if self.download_type is not None and (
                DownloadType.VIDEO in self.download_type or DownloadType.PHOTO in self.download_type or DownloadType.DOCUMENT in self.download_type):
            self.record_dtype.update(self.download_type)  # v1.2.4 修复特定情况结束后不显示表格问题。
            return None
        self.download_type: list = [_ for _ in DownloadType()]
        self.record_dtype: set = {
            DownloadType.VIDEO,
            DownloadType.PHOTO,
            DownloadType.DOCUMENT
        }  # v1.2.4 修复此处报错问题v1.2.3此处有致命错误。
        console.log('未找到任何支持的下载类型,已设置为[#f08a5d]「默认」[/#f08a5d]所有已支持的下载类型。')
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


class DownloadFileName:
    def __init__(
            self,
            message: pyrogram.types.Message,
            download_type: Union[str, "DownloadType"]
    ):
        self.message = message
        self.download_type = download_type

    def get_video_filename(self):
        """处理视频文件的文件名。"""
        default_mtype: str = 'video/mp4'  # v1.2.8 健全获取文件名逻辑。
        media_object = getattr(self.message, self.download_type)
        title: Union[str, None] = getattr(media_object, 'file_name', None)  # v1.2.8 修复当文件名不存在时,下载报错问题。
        try:
            if isinstance(title, str):
                if title.lower().startswith('video_'):  # v1.5.6 尝试修复以日期命名的标题重复下载的问题。
                    title = None
            if title is None:
                title: str = 'None'
            else:
                title: str = os.path.splitext(title)[0]
        except Exception as e:
            title: str = 'None'
            log.warning(f'获取文件名时出错,已重命名为:"{title}",{_t(KeyWord.REASON)}:"{e}"')
        return '{} - {}.{}'.format(
            getattr(self.message, 'id', '0'),
            title,
            get_extension(
                file_id=media_object.file_id,
                mime_type=getattr(media_object, 'mime_type', default_mtype),
                dot=False
            )
        )

    def get_photo_filename(self):
        """处理图片文件的文件名。"""
        default_mtype: str = 'image/jpg'  # v1.2.8 健全获取文件名逻辑。
        media_object = getattr(self.message, self.download_type)
        extension: str = 'unknown'
        if self.download_type == DownloadType.PHOTO:
            extension: str = get_extension(
                file_id=media_object.file_id,
                mime_type=default_mtype,
                dot=False
            )
        elif self.download_type == DownloadType.DOCUMENT:
            extension: str = get_extension(
                file_id=media_object.file_id,
                mime_type=getattr(media_object, 'mime_type', default_mtype),
                dot=False
            )
        return '{} - {}.{}'.format(
            getattr(self.message, 'id', '0'),
            getattr(media_object, 'file_unique_id', 'None'),
            extension
        )

    def get_document_filename(self):
        """处理文档文件的文件名。"""
        _mime_type = getattr(getattr(self.message, self.download_type), 'mime_type')
        if 'video' in _mime_type:
            return self.get_video_filename()
        elif 'image' in _mime_type:
            return self.get_photo_filename()
        elif _mime_type:
            try:
                extension = _mime_type.split('/')[-1]
                if not extension:
                    raise Exception('Unknown mime type.')
                media_object = getattr(self.message, self.download_type)
                return '{} - {}.{}'.format(
                    getattr(self.message, 'id', '0'),
                    getattr(media_object, 'file_unique_id', 'None'),
                    extension
                )
            except Exception as e:
                log.info(f'无法找到的该文档文件的扩展名,{_t(KeyWord.REASON)}:"{e}"')
                return f'{getattr(self.message, "id", "0")} - {datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.unknown'

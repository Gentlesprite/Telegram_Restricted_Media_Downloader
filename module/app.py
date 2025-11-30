# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/7/25 12:32
# File:app.py
import os
import time
import datetime
import subprocess

from functools import wraps
from typing import Union

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
from module.stdio import StatisticalTable
from module.client import TelegramRestrictedMediaDownloaderClient
from module.enums import (
    DownloadType,
    DownloadStatus,
    KeyWord
)
from module.path_tool import (
    validate_title,
    truncate_filename,
    get_extension
)


class Application(UserConfig, StatisticalTable):

    def __init__(self):
        UserConfig.__init__(self)
        StatisticalTable.__init__(self)
        self.client = self.build_client()
        self.check_download_type()
        self.current_task_num: int = 0

    def build_client(self) -> pyrogram.Client:
        """用填写的配置文件,构造pyrogram客户端。"""
        os.makedirs(self.work_directory, exist_ok=True)
        Session.WAIT_TIMEOUT = min(Session.WAIT_TIMEOUT + self.max_download_task ** 2, MAX_FILE_REFERENCE_TIME)
        return TelegramRestrictedMediaDownloaderClient(
            name=SOFTWARE_FULL_NAME.replace(' ', ''),
            api_id=self.api_id,
            api_hash=self.api_hash,
            proxy=self.proxy if self.enable_proxy else None,
            workdir=self.work_directory,
            max_concurrent_transmissions=self.max_download_task,
            sleep_threshold=SLEEP_THRESHOLD,
        )
        # v1.3.7 新增多任务下载功能,无论是否Telegram会员。
        # https://stackoverflow.com/questions/76714896/pyrogram-download-multiple-files-at-the-same-time

    def process_shutdown(self, second: int) -> None:
        """处理关机逻辑。"""
        self.shutdown_task(second=second) if self.config.get('is_shutdown') else None

    def get_temp_file_path(
            self,
            message: pyrogram.types.Message,
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
        elif dtype in (DownloadType.AUDIO, DownloadType.VOICE, DownloadType.ANIMATION):
            file_name: str = dt.get_filename()
        else:
            file_id = getattr(message, 'id', '0')
            time_format = '%Y-%m-%d_%H-%M-%S'
            file_name: str = f'{file_id} - {datetime.datetime.now().strftime(time_format)}.unknown'
        return truncate_filename(splice_chat_id(file_name))

    def on_record(func):

        @wraps(func)
        def wrapper(self, *args):
            res = func(self, *args)
            download_type = res
            _, file_name, download_status = args
            self.update_download_status(download_type, download_status, file_name)
            return res

        return wrapper

    def update_download_status(
            self,
            download_type: str,
            download_status: str,
            file_name: str
    ):
        type_to_success = {
            DownloadType.PHOTO: self.success_photo,
            DownloadType.VIDEO: self.success_video,
            DownloadType.DOCUMENT: self.success_document,
            DownloadType.AUDIO: self.success_audio,
            DownloadType.VOICE: self.success_voice,
            DownloadType.ANIMATION: self.success_animation
        }

        type_to_failure = {
            DownloadType.PHOTO: self.failure_photo,
            DownloadType.VIDEO: self.failure_video,
            DownloadType.DOCUMENT: self.failure_document,
            DownloadType.AUDIO: self.failure_audio,
            DownloadType.VOICE: self.failure_voice,
            DownloadType.ANIMATION: self.failure_animation
        }

        type_to_skip = {
            DownloadType.PHOTO: self.skip_photo,
            DownloadType.VIDEO: self.skip_video,
            DownloadType.DOCUMENT: self.skip_document,
            DownloadType.AUDIO: self.skip_audio,
            DownloadType.VOICE: self.skip_voice,
            DownloadType.ANIMATION: self.skip_animation
        }

        if download_status == DownloadStatus.SUCCESS:
            type_to_success[download_type].add(file_name)
        elif download_status == DownloadStatus.FAILURE:
            type_to_failure[download_type].add(file_name)
        elif download_status == DownloadStatus.SKIP:
            type_to_skip[download_type].add(file_name)
        elif download_status == DownloadStatus.DOWNLOADING:
            self.current_task_num += 1
        failure_set = type_to_failure[download_type]
        success_set = type_to_success[download_type]
        if failure_set and success_set:
            failure_set -= success_set

    @on_record
    def get_file_type(self, *args) -> str:
        message, file_name, download_type = args
        for i in DownloadType():
            if getattr(message, i):
                download_type = i
        return download_type if download_type else 'unknown_type'

    def check_download_type(self) -> None:
        for dtype in self.download_type:
            if dtype not in DownloadType():
                self.download_type.remove(dtype)
                p = f'"{dtype}"不是支持的下载类型,已移除。'
                console.log(p, style='#FF4689')
                log.info(p)
        if self.download_type:
            return None
        self.download_type = [_ for _ in DownloadType()]
        self.config['download_type'] = self.download_type
        self.save_config(config=self.config)
        console.log('未找到任何支持的下载类型,已设置为[#f08a5d]「默认」[/#f08a5d]所有已支持的下载类型。')

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
        try:
            document_obj = getattr(self.message, self.download_type)
            _mime_type = getattr(document_obj, 'mime_type')
            if 'video' in _mime_type:
                return self.get_video_filename()
            elif 'image' in _mime_type:
                return self.get_photo_filename()
            elif _mime_type:
                _file_name = self.get_filename()
                if _file_name.endswith('.bin'):
                    origin_file_name = self.get_origin_extension(document_obj, _file_name)
                    if origin_file_name:
                        return origin_file_name
                return _file_name

        except (AttributeError, Exception) as e:
            log.info(f'无法找到的该文档文件的扩展名,{_t(KeyWord.REASON)}:"{e}"')
            file_id = getattr(self.message, 'id', '0')
            time_format = '%Y-%m-%d_%H-%M-%S'
            return f'{file_id} - {datetime.datetime.now().strftime(time_format)}.unknown'

    def get_filename(self):
        try:
            media_obj = getattr(self.message, self.download_type)
            _mime_type = getattr(media_obj, 'mime_type')
            return '{} - {}.{}'.format(
                getattr(self.message, 'id', '0'),
                getattr(media_obj, 'file_unique_id', 'None'),
                get_extension(
                    file_id=media_obj.file_id,
                    mime_type=_mime_type,
                    dot=False
                )
            )
        except Exception as e:
            log.info(f'无法找到的该{_t(self.download_type)}文件的扩展名,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def get_origin_extension(obj, filename: str) -> Union[str, None]:
        o_file_name = getattr(obj, 'file_name')
        if o_file_name:
            if '.' in o_file_name:
                o_ext = os.path.splitext(o_file_name)[-1]
                return filename.replace('.bin', o_ext)

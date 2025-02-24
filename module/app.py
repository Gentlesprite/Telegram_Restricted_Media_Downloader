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
from typing import Dict, Tuple
from functools import wraps

import pyrogram
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, TransferSpeedColumn

from module import Session
from module import console, log
from module import MAX_FILE_REFERENCE_TIME, SOFTWARE_FULL_NAME
from module.path_tool import split_path, validate_title, truncate_filename, move_to_save_directory, get_extension, \
    safe_delete, compare_file_size, get_file_size, get_terminal_width
from module.enums import DownloadType, DownloadStatus, KeyWord, Status
from module.stdio import StatisticalTable, MetaData
from module.client import TelegramRestrictedMediaDownloaderClient
from module.config import Config


class Application(Config, StatisticalTable):

    def __init__(self,
                 client_obj: callable = TelegramRestrictedMediaDownloaderClient):
        Config.__init__(self)
        StatisticalTable.__init__(self)
        self.client_obj: callable = client_obj
        self.__get_download_type()
        self.current_task_num: int = 0
        self.max_retry_count: int = 3
        self.complete_link: set = set()
        self.link_info: dict = {}
        self.global_retry_task: int = 0
        self.progress = Progress(TextColumn('[bold blue]{task.fields[filename]}', justify='right'),
                                 BarColumn(bar_width=max(int(get_terminal_width() * 0.2), 1)),
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
                f'{KeyWord.TYPE}:{DownloadType.t(self.guess_file_type(file_name=temp_file_path, status=DownloadStatus.SUCCESS)[0].text)},'
                f'{KeyWord.STATUS}:{Status.SUCCESS}。',
            )
            return True
        console.log(
            f'{KeyWord.FILE}:"{file_path}",'
            f'{KeyWord.ERROR_SIZE}:{format_local_size},'
            f'{KeyWord.ACTUAL_SIZE}:{format_sever_size},'
            f'{KeyWord.TYPE}:{DownloadType.t(self.guess_file_type(file_name=temp_file_path, status=DownloadStatus.FAILURE)[0].text)},'
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
        if getattr(message, DownloadType.DOCUMENT.text):
            mime_type = message.document.mime_type  # 获取 document 的 mime_type 。
            # 只下载视频的情况。
            if DownloadType.VIDEO.text in self.download_type and DownloadType.PHOTO.text not in self.download_type:
                if 'video' in mime_type:
                    is_document_type_valid = True  # 允许下载视频。
                elif 'image' in mime_type:
                    is_document_type_valid = False  # 跳过下载图片。
            # 只下载图片的情况。
            elif DownloadType.PHOTO.text in self.download_type and DownloadType.VIDEO.text not in self.download_type:
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
            if _dtype == DownloadType.PHOTO.text:
                _extension: str = get_extension(file_id=_meta_obj.file_id, mime_type=_default_mtype,
                                                dot=False)
            elif _dtype == DownloadType.DOCUMENT.text:
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

        if dtype == DownloadType.VIDEO.text:
            file: str = _process_video(msg_obj=message, _dtype=dtype)
        elif dtype == DownloadType.PHOTO.text:
            file: str = _process_photo(msg_obj=message, _dtype=dtype)
        elif dtype == DownloadType.DOCUMENT.text:
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
            if file_type == DownloadType.PHOTO:
                if status == DownloadStatus.SUCCESS:
                    self.success_photo.add(file_name)
                elif status == DownloadStatus.FAILURE:
                    self.failure_photo.add(file_name)
                elif status == DownloadStatus.SKIP:
                    self.skip_photo.add(file_name)
                elif status == DownloadStatus.DOWNLOADING:
                    self.current_task_num += 1
            elif file_type == DownloadType.VIDEO:
                if status == DownloadStatus.SUCCESS:
                    self.success_video.add(file_name)
                elif status == DownloadStatus.FAILURE:
                    self.failure_video.add(file_name)
                elif status == DownloadStatus.SKIP:
                    self.skip_video.add(file_name)
                elif status == DownloadStatus.DOWNLOADING:
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
                result = DownloadType.PHOTO
            elif file_main_type == 'video':
                result = DownloadType.VIDEO
        return result, status

    def __get_download_type(self) -> None:
        """获取需要下载的文件类型。"""
        if self.download_type is not None and (
                DownloadType.VIDEO.text in self.download_type or DownloadType.PHOTO.text in self.download_type):
            self.record_dtype.update(self.download_type)  # v1.2.4 修复特定情况结束后不显示表格问题。
            self.download_type.append(DownloadType.DOCUMENT.text)
        else:
            self.download_type: list = DownloadType.support_type()
            self.record_dtype: set = {DownloadType.VIDEO.text,
                                      DownloadType.PHOTO.text}  # v1.2.4 修复此处报错问题v1.2.3此处有致命错误。
            console.log('已使用[#f08a5d]「默认」[/#f08a5d]下载类型:3.视频和图片。')

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

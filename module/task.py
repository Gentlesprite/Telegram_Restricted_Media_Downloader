# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/2/27 17:38
# File:task.py
import os
import sys
import json
import math
import asyncio

from functools import wraps
from typing import Union, Optional, Callable

import pyrogram

from module import console, log
from module.language import _t
from module.stdio import MetaData
from module.parser import PARSE_ARGS
from module.path_tool import (
    safe_delete,
    truncate_filename
)
from module.enums import (
    DownloadStatus,
    UploadStatus,
    KeyWord
)


class DownloadTask:
    LINK_INFO: dict = {}
    COMPLETE_LINK: set = set()

    def __init__(
            self,
            link: str,
            link_type: Union[str, None],
            member_num: int,
            complete_num: int,
            file_name: set,
            error_msg: dict
    ):
        DownloadTask.LINK_INFO[link] = {
            'link_type': link_type,
            'member_num': member_num,
            'complete_num': complete_num,
            'file_name': file_name,
            'error_msg': error_msg
        }

    def on_create_task(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            message_ids = kwargs.get('message_ids')
            link = message_ids
            if isinstance(message_ids, pyrogram.types.Message):
                link = message_ids.link if message_ids.link else message_ids.id
            DownloadTask(link=link, link_type=None, member_num=0, complete_num=0, file_name=set(), error_msg={})
            res: dict = await func(self, *args, **kwargs)
            chat_id, link_type, member_num, status, e_code = res.values()
            if status == DownloadStatus.FAILURE:
                DownloadTask.set(link=link, key='error_msg', value=e_code)
                reason: str = e_code.get('error_msg')
                if reason:
                    log.error(
                        f'{_t(KeyWord.DOWNLOAD_TASK)}'
                        f'{_t(KeyWord.LINK)}:"{link}"{reason},'
                        f'{_t(KeyWord.REASON)}:"{e_code.get("all_member")}",'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}。'
                    )
                else:
                    log.warning(
                        f'{_t(KeyWord.DOWNLOAD_TASK)}'
                        f'{_t(KeyWord.LINK)}:"{link}"{e_code.get("all_member")},'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}。'
                    )
            elif status == DownloadStatus.DOWNLOADING:
                pass
            return res

        return wrapper

    def on_complete(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            res = func(self, *args, **kwargs)
            if all(i is None for i in res):
                return None
            link, file_name = res
            DownloadTask.add_file_name(link=link, file_name=file_name)
            for i in DownloadTask.LINK_INFO.items():
                compare_link: str = i[0]
                info: dict = i[1]
                if compare_link == link:
                    info['complete_num'] = len(info.get('file_name'))
            all_num: int = DownloadTask.get(link=link, key='member_num')
            complete_num: int = DownloadTask.get(link=link, key='complete_num')
            if all_num == complete_num:
                console.log(
                    f'{_t(KeyWord.DOWNLOAD_TASK)}'
                    f'{_t(KeyWord.LINK)}:"{link}",'
                    f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SUCCESS)}。'
                )
                DownloadTask.LINK_INFO.get(link)['error_msg'] = {}
                DownloadTask.COMPLETE_LINK.add(link)
                asyncio.create_task(self.done_notice(f'"{link}"下载完成。'))
            return res

        return wrapper

    @staticmethod
    def add_file_name(link, file_name):
        DownloadTask.LINK_INFO.get(link).get('file_name').add(file_name)

    @staticmethod
    def get(link: str, key: str) -> Union[str, int, set, dict, None]:
        return DownloadTask.LINK_INFO.get(link).get(key)

    @staticmethod
    def set(link: str, key: str, value):
        DownloadTask.LINK_INFO.get(link)[key] = value

    @staticmethod
    def set_error(link: str, value, key: Union[str, None] = None):
        DownloadTask.LINK_INFO.get(link).get('error_msg')[key if key else 'all_member'] = value


class UploadTask:
    DIRECTORY_NAME: str = PARSE_ARGS.temp or os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'temp')
    PART_SIZE: int = 512 * 1024
    TASKS: set = set()
    TASK_COUNTER: int = 0
    NOTIFY: Optional[Callable] = None

    def __init__(
            self,
            chat_id: Union[str, int, None],
            file_path: str,
            file_id: int,
            file_size: int,
            file_part: Union[list],
            status: UploadStatus,
            error_msg: Union[str, None] = None,
            with_delete: bool = False,
            media_group: Optional[asyncio.Task] = None,
            message_id: Optional[int] = None

    ):
        UploadTask.TASKS.add(self)
        UploadTask.TASK_COUNTER += 1
        self.chat_id: Union[str, int, None] = chat_id
        self.file_path: str = file_path
        self.file_name: str = os.path.basename(file_path)
        self.file_id: int = file_id
        self.file_size: int = file_size
        self.file_part: list = file_part
        self.status: UploadStatus = status
        self.error_msg: Union[str, None] = error_msg
        self.with_delete: bool = with_delete
        self.file_total_parts = int(math.ceil(file_size / UploadTask.PART_SIZE))
        self.__media_group: asyncio.Task = media_group
        self.message_id: Optional[int] = message_id

    @property
    def is_media_group(self) -> bool:
        if self.__media_group:
            return True
        return False

    async def get_media_group(self) -> pyrogram.types.List:
        if self.is_media_group:
            return await self.__media_group

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            if hasattr(self, name):
                old_value = getattr(self, name)
                if old_value != value:
                    super().__setattr__(name, value)
                    if name == 'status':
                        if value == UploadStatus.IDLE:
                            pass
                        elif value == UploadStatus.UPLOADING:
                            console.log(
                                f'{_t(KeyWord.UPLOAD_TASK)}'
                                f'{_t(KeyWord.CHANNEL)}:"{self.chat_id}",'
                                f'{_t(KeyWord.FILE)}:"{self.file_path}",'
                                f'{_t(KeyWord.SIZE)}:{MetaData.suitable_units_display(self.file_size)},'
                                f'{_t(KeyWord.STATUS)}:{_t(UploadStatus.UPLOADING)}。'
                            )
                        elif value == UploadStatus.SUCCESS:
                            more = ''
                            if self.__media_group:
                                more += f'(等待所有媒体上传完成以媒体组发送)'
                            if self.with_delete:
                                more += '(本地文件已删除)'
                            console.log(
                                f'{_t(KeyWord.UPLOAD_TASK)}'
                                f'{_t(KeyWord.CHANNEL)}:"{self.chat_id}",'
                                f'{_t(KeyWord.FILE)}:"{self.file_path}",'
                                f'{_t(KeyWord.SIZE)}:{MetaData.suitable_units_display(self.file_size)},'
                                f'{_t(KeyWord.STATUS)}:{_t(UploadStatus.SUCCESS)}{more}。',
                            )
                            self.notice(f'"{self.file_path}" ⬆️ "{self.chat_id}"上传完成。\n{more}')
                        elif value == UploadStatus.FAILURE:
                            log.error(
                                f'{_t(KeyWord.UPLOAD_TASK)}'
                                f'{_t(KeyWord.CHANNEL)}:"{self.chat_id}",'
                                f'{_t(KeyWord.FILE)}:"{self.file_path}",'
                                f'{_t(KeyWord.SIZE)}:{MetaData.suitable_units_display(self.file_size)},'
                                f'{_t(KeyWord.REASON)}:"{self.error_msg}",'
                                f'{_t(KeyWord.STATUS)}:{_t(str(value))}。'
                            )
                            self.notice(f'"{self.file_path}" ⬆️ "{self.chat_id}"上传失败。')
                    elif name == 'chat_id':
                        if value:
                            self.upload_manager_path: str = os.path.join(
                                UploadTask.DIRECTORY_NAME,
                                str(self.chat_id),
                                f'{truncate_filename(f"{self.file_size} - {self.file_name}")}.json'
                            )
                        os.makedirs(os.path.dirname(self.upload_manager_path), exist_ok=True)
                        self.load_json()

            else:
                super().__setattr__(name, value)

    def notice(self, message: str):
        if isinstance(self.NOTIFY, Callable):
            asyncio.create_task(
                self.NOTIFY(
                    message
                )
            )

    @property
    def complete_task(self) -> int:
        complete = []
        for task in UploadTask.TASKS:
            if task.status == UploadStatus.SUCCESS:
                complete.append(task)
        return len(complete)

    def save_json(self):
        with open(file=self.upload_manager_path, mode='w', encoding='UTF-8') as f:
            json.dump(
                obj={
                    'file_path': self.file_path,
                    'file_id': self.file_id,
                    'file_size': self.file_size,
                    'file_part': self.file_part,
                    'file_total_parts': self.file_total_parts
                },
                fp=f,
                ensure_ascii=False,
                indent=4
            )

    def load_json(self):
        if not os.path.exists(self.upload_manager_path):
            self.save_json()
            return
        with open(file=self.upload_manager_path, mode='r', encoding='UTF-8') as f:
            _json: dict = {}
            try:
                _json = json.load(f)
            except Exception as e:
                log.info(f'UploadManager的json内容可能为空,即将重新生成,{_t(KeyWord.REASON)}:"{e}"')
                safe_delete(self.upload_manager_path)
                self.save_json()
        self.file_path = _json.get('file_path', self.file_path)
        self.file_id = _json.get('file_id', self.file_id)
        self.file_size = _json.get('file_size', self.file_size)
        self.file_part = _json.get('file_part', self.file_part)
        self.file_total_parts = _json.get('file_total_parts', self.file_total_parts)

    def update_file_part(self, file_part: int):
        if file_part not in self.file_part and file_part < self.file_total_parts:
            self.file_part.append(file_part)
            self.save_json()

    def get_missing_parts(self) -> list:
        """获取缺失的分片索引。"""
        valid_parts = []
        for part in self.file_part:
            if isinstance(part, int) and 0 <= part < self.file_total_parts and part not in valid_parts:
                valid_parts.append(part)
            else:
                log.info(f'过滤无效分片索引:{part}(有效范围:0-{self.file_total_parts - 1})。')

        if len(valid_parts) != len(self.file_part):
            self.file_part = valid_parts
            self.save_json()
            log.info(f'清理后的分片索引:{valid_parts}。')

        all_parts = set(range(self.file_total_parts))
        uploaded_parts = set(valid_parts)
        missing_parts = sorted(list(all_parts - uploaded_parts))

        log.info(f'总需分片:{all_parts},已上传:{uploaded_parts},缺失:{missing_parts}。')
        return missing_parts

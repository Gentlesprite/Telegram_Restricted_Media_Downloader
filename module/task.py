# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/2/27 17:38
# File:task.py
import os
import json
import math
import time
import asyncio

from functools import wraps
from typing import (
    Union,
    Optional,
    Callable
)

import pyrogram

from module import (
    log,
    console
)
from module.language import _t
from module.stdio import MetaData
from module.parser import PARSE_ARGS
from module.util import get_work_directory
from module.path_tool import (
    safe_delete,
    calc_sha256,
)
from module.enums import (
    KeyWord,
    UploadStatus,
    DownloadStatus
)


class ChatInfo:
    TITLE: dict = {}

    @staticmethod
    def add(chat: Union[pyrogram.types.Chat, None], chat_id: Union[str, int, None] = None) -> None:
        """缓存频道的标题,避免网页面板只显示频道ID。"""
        if chat is None:
            return
        _chat_id: str = str(chat_id if chat_id is not None else getattr(chat, 'id', ''))
        title: str = str(getattr(chat, 'title', '') or getattr(chat, 'first_name', '') or '')
        if _chat_id and title:
            ChatInfo.TITLE[_chat_id] = title

    @staticmethod
    def get(chat_id: Union[str, int, None]) -> str:
        """获取缓存的频道标题,不存在时返回空字符串。"""
        return ChatInfo.TITLE.get(str(chat_id), '')


class DownloadTask:
    """下载任务,按链接维护待下载的消息与其下载进度统计。"""

    TASKS: dict = {}  # 链接 -> DownloadTask。
    ORDER: list = []  # 链接首次出现的顺序,调度器按此顺序派发。
    COMPLETE_LINK: set = set()
    DOWNLOADING_KEYS: set = set()  # (chat_id, message_id) -> 正在下载中的消息,防止不同链接(如媒体组与组内单条?single)并发下载同一消息导致数据竞争。

    def __init__(self, link: Union[str, int]):
        self.link: str = str(link)
        self.link_type: Optional[str] = None
        self.chat_id: Union[str, int, None] = None
        self.member_num: int = 0
        self.complete_num: int = 0
        self.file_name: set = set()
        self.error_msg: dict = {}
        self.fail_id: set = set()  # 已彻底失败(重试耗尽)的消息ID。
        self.items: dict = {}  # 消息ID -> 待下载消息(dict,字段见add_item)。
        self.member_info: dict = {}  # 消息ID -> 该链接下消息的展示信息与状态,完成后不移除。

    @property
    def fail_num(self) -> int:
        """彻底失败(重试耗尽)的文件数。"""
        return len(self.fail_id)

    @classmethod
    def get_or_create(cls, link: Union[str, int]) -> "DownloadTask":
        """获取链接对应的下载任务,不存在时创建并记录顺序。"""
        _link: str = str(link)
        task: Union[DownloadTask, None] = cls.TASKS.get(_link)
        if task is None:
            task = cls(_link)
            cls.TASKS[_link] = task
            cls.ORDER.append(_link)
        return task

    @classmethod
    def get(cls, link: Union[str, int, None]) -> Union["DownloadTask", None]:
        """获取链接对应的下载任务。"""
        return cls.TASKS.get(str(link))

    @classmethod
    def ordered_tasks(cls) -> list:
        """按链接首次出现的顺序返回下载任务。"""
        return [cls.TASKS[link] for link in list(cls.ORDER) if link in cls.TASKS]

    @classmethod
    def add_item(
            cls,
            link: Union[str, int],
            chat_id: Union[str, int],
            message: Union[pyrogram.types.Message, list],
            link_type: Optional[str] = None,
            retry: Optional[dict] = None,
            with_upload: Optional[dict] = None,
            diy_download_type: Optional[list] = None
    ) -> None:
        """将消息加入下载任务,已存在时重置为排队状态。"""
        task: DownloadTask = cls.get_or_create(link)
        messages: list = message if isinstance(message, list) else [message]
        retry_dict: dict = retry if retry else {'id': -1, 'count': 0}
        retry_id: int = int(retry_dict.get('id') or -1)
        retry_count: int = int(retry_dict.get('count') or 0)
        if retry_count == 0:
            task.clear_error()  # 非重试(重新拉取)的任务,清空该链接此前的失败记录。
            task.clear_fail()
        for _message in messages:
            key: int = int(getattr(_message, 'id', 0))
            if retry_count != 0 and key != retry_id:
                continue  # 重试时只保留需要重试的那条消息,避免整个媒体组被重复排队。
            task.remove_fail(message_id=key)  # 重新排队(含重试)时,清除该消息的失败记录。
            task.update_member(  # 登记链接成员,包括下载完成后仍需展示的消息。
                message_id=key,
                status=DownloadStatus.PENDING,
                date=str(getattr(_message, 'date', '') or '')[:10]
            )
            item: Union[dict, None] = task.items.get(key)
            if item is None:
                task.items[key] = {
                    'link': task.link,
                    'chat_id': chat_id,
                    'message': _message,
                    'link_type': link_type,
                    'retry': retry_dict,
                    'with_upload': with_upload,
                    'diy_download_type': diy_download_type,
                    'status': DownloadStatus.PENDING,
                    'create_time': time.time(),
                    'meta': None  # 网页面板的展示信息缓存。
                }
            else:
                item['status'] = DownloadStatus.PENDING  # 重试时重置状态。

    def set_item_status(self, message_id: Union[int, str], status: str) -> None:
        """设置指定消息的排队状态,并同步到链接成员。"""
        item: Union[dict, None] = self.items.get(int(message_id))
        if item is not None:
            item['status'] = status
        self.update_member(message_id=message_id, status=status)

    def update_member(
            self,
            message_id: Union[int, str],
            status: Optional[str] = None,
            name: Optional[str] = None,
            size: Optional[str] = None,
            size_byte: Optional[int] = None,
            date: Optional[str] = None,
            task_id: Optional[int] = None,
            note: Optional[str] = None
    ) -> None:
        """登记或更新链接下某个消息成员的展示信息与状态。"""
        key: int = int(message_id)
        member: dict = self.member_info.get(key) or {
            'name': f'消息 {key}',
            'size': '',
            'size_byte': 0,
            'date': '',
            'state': DownloadStatus.PENDING,
            'task_id': None,
            'note': ''
        }
        if status:
            member['state'] = status
        if name:
            member['name'] = name
        if size:
            member['size'] = size
        if size_byte is not None:
            member['size_byte'] = int(size_byte)
        if date is not None:
            member['date'] = date
        if task_id is not None:
            member['task_id'] = task_id
        if note:
            member['note'] = note
        self.member_info[key] = member

    def remove_item(self, message_id: Union[int, str]) -> None:
        """从下载任务中移除指定的消息。"""
        self.items.pop(int(message_id), None)

    def get_pending_items(self, limit: int = 50) -> dict:
        """获取该下载任务中排队(PENDING)的消息。"""
        items: list = [item for item in self.items.values() if item.get('status') == DownloadStatus.PENDING]
        return {'items': items[:limit], 'total': len(items)}

    @classmethod
    def queued_items(cls, limit: int = 50) -> list:
        """获取尚未开始下载(PENDING)的消息。"""
        result: list = []
        for task in cls.ordered_tasks():
            for item in task.items.values():
                if item.get('status') == DownloadStatus.PENDING:
                    result.append(item)
        return result[:limit]

    @classmethod
    def pick_pending(cls) -> Union[dict, None]:
        """按链接首次出现的顺序取出一个排队(PENDING)中的消息。

        若消息已被其他任务占用(正在下载中),则跳过,避免相同消息被多个链接并发下载导致数据竞争。
        """
        for task in cls.ordered_tasks():
            for item in task.items.values():
                if item.get('status') != DownloadStatus.PENDING:
                    continue
                message = item.get('message')
                if not isinstance(message, pyrogram.types.Message):
                    continue
                if (message.chat.id, message.id) in cls.DOWNLOADING_KEYS:
                    continue
                return item
        return None

    @classmethod
    def has_task(cls) -> bool:
        """判断是否还存在未处理完毕或未开始的任务。"""
        for task in cls.ordered_tasks():
            for item in task.items.values():
                if item.get('status') in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING):
                    return True
        return False

    def add_file_name(self, file_name: str) -> None:
        """记录已完成的文件名,并同步完成数。"""
        self.file_name.add(file_name)
        self.complete_num = len(self.file_name)

    def set_error(self, value, key: Optional[str] = None) -> None:
        """记录下载错误信息。"""
        self.error_msg[key if key else 'all_member'] = value

    def clear_error(self, key: Optional[str] = None) -> None:
        """清除下载错误信息,指定key时只清除该文件的失败记录。"""
        if key is None:
            self.error_msg.clear()
            return
        self.error_msg.pop(key, None)

    def add_fail(self, message_id: Union[int, str]) -> None:
        """记录彻底失败(重试耗尽)的消息。"""
        self.fail_id.add(int(message_id))

    def remove_fail(self, message_id: Union[int, str]) -> None:
        """移除消息的失败记录,该消息重新排队或下载成功时调用。"""
        self.fail_id.discard(int(message_id))

    def clear_fail(self) -> None:
        """清空全部失败记录。"""
        self.fail_id.clear()

    def on_create_task(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            message_ids = kwargs.get('message_ids')
            link = message_ids
            if isinstance(message_ids, pyrogram.types.Message):
                link = message_ids.link if message_ids.link else message_ids.id
            task: DownloadTask = DownloadTask.get_or_create(link)
            res: dict = await func(self, *args, **kwargs)
            status: Union[str, None] = res.get('status')
            e_code: Union[dict, None] = res.get('e_code')
            if status == DownloadStatus.FAILURE:
                task.error_msg = e_code
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
            task: Union[DownloadTask, None] = DownloadTask.get(link)
            if task is None:
                return res
            task.add_file_name(file_name)
            if task.member_num == task.complete_num:
                console.log(
                    f'{_t(KeyWord.DOWNLOAD_TASK)}'
                    f'{_t(KeyWord.LINK)}:"{link}",'
                    f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SUCCESS)}。'
                )
                task.error_msg = {}
                DownloadTask.COMPLETE_LINK.add(task.link)
                asyncio.create_task(self.done_notice(f'"{link}"下载完成。'))
                log.info(f'链接:"{link}"下载完成。')
            return res

        return wrapper


class UploadTask:
    DIRECTORY_NAME: str = PARSE_ARGS.temp or os.path.join(get_work_directory(), 'temp')
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
            status: Union[UploadStatus, str],
            error_msg: Union[str, None] = None,
            with_delete: bool = False,
            media_group: Optional[asyncio.Task] = None,
            message_id: Optional[int] = None,
            send_as_media_group: bool = False
    ):
        UploadTask.TASKS.add(self)
        UploadTask.TASK_COUNTER += 1
        self.chat_id: Union[str, int, None] = chat_id
        self.file_path: str = file_path
        self.file_name: str = os.path.basename(file_path)
        self.file_id: int = file_id
        self.file_size: int = file_size
        self.file_part: list = file_part
        self.status: Union[UploadStatus, str] = status
        self.error_msg: Union[str, None] = error_msg
        self.with_delete: bool = with_delete
        self.file_total_parts = int(math.ceil(file_size / UploadTask.PART_SIZE))
        self.__media_group: asyncio.Task = media_group
        self.message_id: Optional[int] = message_id
        self.send_as_media_group: bool = send_as_media_group
        self.sha256: str = calc_sha256(file_path=self.file_path)
        self.prompt: str = ''
        self.task_id: Union[int, None] = None  # 进度条任务ID,供网页面板关联上传进度。

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            if hasattr(self, name):
                old_value = getattr(self, name)
                if old_value != value:
                    super().__setattr__(name, value)
                    if name == 'status':
                        if value == UploadStatus.PENDING:
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
                            if self.send_as_media_group:
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
                        elif value == UploadStatus.SENT:
                            pass
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
                                f'{self.sha256}.json'
                            )
                        os.makedirs(os.path.dirname(self.upload_manager_path), exist_ok=True)
                        self.load_json()
                    elif name == 'prompt':
                        self.notice(self.prompt)

            else:
                super().__setattr__(name, value)

    @property
    def is_media_group(self) -> bool:
        if self.__media_group:
            return True
        return False

    async def get_media_group(self) -> Union[pyrogram.types.List, None]:
        if self.is_media_group:
            return await self.__media_group

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
        self.file_id = _json.get('file_id', self.file_id)
        self.file_size = _json.get('file_size', self.file_size)
        self.file_part = _json.get('file_part', self.file_part)
        self.file_total_parts = _json.get('file_total_parts', self.file_total_parts)

    def update_file_part(self, file_part: int):
        if file_part not in self.file_part and file_part < self.file_total_parts:
            self.file_part.append(file_part)
            self.save_json()

    def reset_upload(self, file_id: int):
        """丢弃历史分片缓存,改用新的file_id重新上传全部分片。"""
        self.file_id = file_id
        self.file_part = []
        self.save_json()

    @staticmethod
    def has_pending_media_group_tasks() -> bool:
        """检查是否还有IDLE或UPLOADING状态且属于媒体组的任务。"""
        for task in UploadTask.TASKS:
            if task.status in (UploadStatus.PENDING, UploadStatus.UPLOADING) and task.is_media_group:
                return True
        return False

    @staticmethod
    def get_media_group_task_count(message_ids: set) -> int:
        """获取指定media_group_id和message_ids列表中已创建的UploadTask数量。

        Args:
            message_ids: 需要检查的message_id集合。

        Returns:
            int: 已创建的UploadTask数量(排除已发送的任务)。
        """
        if not message_ids:
            return 0

        count = 0
        for task in UploadTask.TASKS:
            if task.message_id in message_ids and task.status != UploadStatus.SENT:
                count += 1

        return count

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

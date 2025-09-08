# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/2/27 17:38
# File:task.py
import asyncio
import os.path
from functools import wraps
from typing import Union

from module import console, log
from module.language import _t
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
            link = kwargs.get('link')
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
                asyncio.create_task(self.done_notice(link))
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
    CHAT_ID_INFO: dict = {}

    def __init__(
            self,
            chat_id: Union[str, int],
            file_path: str,
            size: Union[str, int],
            error_msg: Union[str, None]
    ):
        if chat_id not in UploadTask.CHAT_ID_INFO:
            UploadTask.CHAT_ID_INFO[chat_id] = {}

        if file_path not in UploadTask.CHAT_ID_INFO[chat_id]:
            UploadTask.CHAT_ID_INFO[chat_id][file_path] = {}

        UploadTask.CHAT_ID_INFO.get(chat_id)[file_path] = {
            'size': size,
            'error_msg': error_msg
        }

    def on_create_task(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            res: dict = await func(self, *args, **kwargs)
            chat_id, file_path, size, status, e_code = res.values()
            if status == UploadStatus.FAILURE:
                UploadTask.set_error_msg(chat_id=chat_id, file_path=file_path, value=e_code)
                log.warning(
                    f'{_t(KeyWord.UPLOAD_TASK)}'
                    f'{_t(KeyWord.CHANNEL)}:"{chat_id}",'
                    f'{_t(KeyWord.REASON)}:"{e_code}",'
                    f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}。'
                )
            return res

        return wrapper

    @staticmethod
    def set_error_msg(chat_id: Union[str, int], file_path: str, value: str):
        meta: dict = UploadTask.CHAT_ID_INFO.get(chat_id)
        file_meta: dict = meta.get(
            file_path,
            {'size': os.path.getsize(file_path) if os.path.isfile(file_path) else 0, 'error_msg': value}
        )
        file_meta['error_msg'] = value

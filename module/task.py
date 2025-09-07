# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/2/27 17:38
# File:task.py
import asyncio
from typing import Union
from functools import wraps

from module import console, log
from module.language import _t
from module.enums import DownloadStatus, KeyWord


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
                DownloadTask.LINK_INFO.get(link)['error_msg'] = e_code
                reason: str = e_code.get('error_msg')
                if reason:
                    log.error(
                        f'{_t(KeyWord.LINK)}:"{link}"{reason},'
                        f'{_t(KeyWord.REASON)}:"{e_code.get("all_member")}",'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}。'
                    )
                else:
                    log.warning(
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
            DownloadTask.LINK_INFO.get(link).get('file_name').add(file_name)
            for i in DownloadTask.LINK_INFO.items():
                compare_link: str = i[0]
                info: dict = i[1]
                if compare_link == link:
                    info['complete_num'] = len(info.get('file_name'))
            all_num: int = DownloadTask.LINK_INFO.get(link).get('member_num')
            complete_num: int = DownloadTask.LINK_INFO.get(link).get('complete_num')
            if all_num == complete_num:
                console.log(
                    f'{_t(KeyWord.LINK)}:"{link}",'
                    f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SUCCESS)}。'
                )
                DownloadTask.LINK_INFO.get(link)['error_msg'] = {}
                DownloadTask.COMPLETE_LINK.add(link)
                asyncio.create_task(self.done_notice(link))
            return res

        return wrapper

# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/9/11 12:00
# File:queue.py
import time

from typing import Union, Optional

import pyrogram

from module.enums import QueueStatus


class QueueItem:
    """队列中的一条待下载消息。"""

    def __init__(
            self,
            link: str,
            chat_id: Union[str, int],
            message: pyrogram.types.Message,
            link_type: Optional[str] = None,
            retry: Optional[dict] = None,
            with_upload: Optional[dict] = None,
            diy_download_type: Optional[list] = None
    ):
        self.link: str = str(link)
        self.chat_id: Union[str, int] = chat_id
        self.message: pyrogram.types.Message = message
        self.link_type: Optional[str] = link_type
        self.retry: dict = retry if retry else {'id': -1, 'count': 0}
        self.with_upload: Optional[dict] = with_upload
        self.diy_download_type: Optional[list] = diy_download_type
        self.status: str = QueueStatus.PENDING
        self.create_time: float = time.time()


class DownloadQueue:
    """下载队列,按链接维护待下载的消息。"""
    QUEUE: dict = {}
    ORDER: list = []

    @staticmethod
    def add(
            link: str,
            chat_id: Union[str, int],
            message: Union[pyrogram.types.Message, list],
            link_type: Optional[str] = None,
            retry: Optional[dict] = None,
            with_upload: Optional[dict] = None,
            diy_download_type: Optional[list] = None
    ) -> None:
        """将消息加入队列,已存在时重置为排队状态。"""
        _link: str = str(link)
        messages: list = message if isinstance(message, list) else [message]
        group: dict = DownloadQueue.QUEUE.setdefault(_link, {})
        if _link not in DownloadQueue.ORDER:
            DownloadQueue.ORDER.append(_link)  # 保持链接首次出现的顺序。
        retry_dict: dict = retry if retry else {}
        retry_id: int = int(retry_dict.get('id') or -1)
        retry_count: int = int(retry_dict.get('count') or 0)
        for _message in messages:
            key: int = int(getattr(_message, 'id', 0))
            if retry_count != 0 and key != retry_id:
                continue  # 重试时只保留需要重试的那条消息,避免整个媒体组被重复排队。
            item: Union[QueueItem, None] = group.get(key)
            if item is None:
                group[key] = QueueItem(
                    link=_link,
                    chat_id=chat_id,
                    message=_message,
                    link_type=link_type,
                    retry=retry,
                    with_upload=with_upload,
                    diy_download_type=diy_download_type
                )
            else:
                item.status = QueueStatus.PENDING  # 重试时重置状态。

    @staticmethod
    def set_status(link: str, message_id: Union[int, str], status: str) -> None:
        """设置队列项的状态。"""
        item: Union[QueueItem, None] = DownloadQueue.QUEUE.get(str(link), {}).get(int(message_id))
        if item is not None:
            item.status = status

    @staticmethod
    def remove(link: str, message_id: Union[int, str]) -> None:
        """从队列中移除指定的消息,队列为空时同时移除链接。"""
        _link: str = str(link)
        group: dict = DownloadQueue.QUEUE.get(_link, {})
        group.pop(int(message_id), None)
        if not group:
            DownloadQueue.QUEUE.pop(_link, None)
            if _link in DownloadQueue.ORDER:
                DownloadQueue.ORDER.remove(_link)

    @staticmethod
    def clear(link: str) -> None:
        """清空指定链接的队列。"""
        _link: str = str(link)
        DownloadQueue.QUEUE.pop(_link, None)
        if _link in DownloadQueue.ORDER:
            DownloadQueue.ORDER.remove(_link)

    @staticmethod
    def get_pending(link: str, limit: int = 50) -> dict:
        """获取指定链接中排队(PENDING)的消息。"""
        items: list = [
            item for item in DownloadQueue.QUEUE.get(str(link), {}).values()
            if item.status == QueueStatus.PENDING
        ]
        return {'items': items[:limit], 'total': len(items)}

    @staticmethod
    def get_queued(limit: int = 50) -> list:
        """获取尚未开始下载(PENDING或WAITING)的队列项。"""
        result: list = []
        for link in list(DownloadQueue.ORDER):
            for item in list(DownloadQueue.QUEUE.get(link, {}).values()):
                if item.status in (QueueStatus.PENDING, QueueStatus.WAITING):
                    result.append(item)
        return result[:limit]

    @staticmethod
    def pick_pending() -> Union[QueueItem, None]:
        """按链接首次出现的顺序取出一个排队(PENDING)中的队列项。"""
        for link in list(DownloadQueue.ORDER):
            for item in list(DownloadQueue.QUEUE.get(link, {}).values()):
                if item.status == QueueStatus.PENDING:
                    return item
        return None

    @staticmethod
    def has_task() -> bool:
        """判断队列中是否还存在未处理完毕(downloading)或未开始(pending、waiting)的任务。"""
        for group in list(DownloadQueue.QUEUE.values()):
            for item in list(group.values()):
                if item.status in (QueueStatus.PENDING, QueueStatus.WAITING, QueueStatus.DOWNLOADING):
                    return True
        return False

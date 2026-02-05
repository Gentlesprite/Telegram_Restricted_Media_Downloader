# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/9/25 1:22
# File:filter.py
import datetime
from typing import Optional

import pyrogram


class Filter:
    @staticmethod
    def date_range(
            message: pyrogram.types.Message,
            start_date: Optional[float],
            end_date: Optional[float]
    ) -> bool:
        if start_date and end_date:
            return start_date <= datetime.datetime.timestamp(message.date) <= end_date
        elif start_date:
            return start_date <= datetime.datetime.timestamp(message.date)
        elif end_date:
            return datetime.datetime.timestamp(message.date) <= end_date
        return True

    @staticmethod
    def dtype(
            message: pyrogram.types.Message,
            download_type: dict
    ) -> bool:
        table: list = []
        for dtype, status in download_type.items():
            if getattr(message, dtype) and status:
                table.append(True)
            table.append(False)
        if True in table:
            return True
        return False

    @staticmethod
    def keyword_filter(
            message: pyrogram.types.Message,
            keywords: Optional[dict]
    ) -> bool:
        if not keywords:
            return True
        text = getattr(message, 'text') or getattr(message, 'caption') or ''
        text_lower = text.lower()

        # 先检查是否匹配到需要跳过的关键词(False)。
        for keyword, should_download in keywords.items():
            if not should_download and keyword.lower() in text_lower:
                return False

        # 再检查是否匹配到需要下载的关键词(True)。
        true_keywords = [k for k, v in keywords.items() if v]
        if not true_keywords:
            # 没有设置为 True 的关键词，且前面没匹配到 False，则下载。
            return True

        # 如果有设置为True的关键词，但消息不匹配任何一个，则跳过。
        for keyword in true_keywords:
            if keyword.lower() in text_lower:
                return True
        return False

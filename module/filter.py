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
            keywords: Optional[list]
    ) -> bool:
        if not keywords:
            return True
        text = getattr(message, 'text') or getattr(message, 'caption') or ''
        return any(keyword.lower() in text.lower() for keyword in keywords)

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
    def date_filter(
            message: pyrogram.types.Message,
            start_date: Optional[float],
            end_date: Optional[float],
    ) -> bool:
        if start_date and end_date:
            return start_date <= datetime.datetime.timestamp(message.date) <= end_date
        elif start_date:
            return start_date <= datetime.datetime.timestamp(message.date)
        elif end_date:
            return datetime.datetime.timestamp(message.date) <= end_date
        return True

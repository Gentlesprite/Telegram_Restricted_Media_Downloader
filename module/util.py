# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/3/10 0:45
# File:util.py
import os
from typing import List

from rich.text import Text


def safe_index(lst: list, index: int, default=None):
    try:
        return lst[index]
    except IndexError:
        return default


def get_terminal_width() -> int:
    terminal_width: int = 120
    try:
        terminal_width: int = os.get_terminal_size().columns
    except OSError:
        pass
    finally:
        return terminal_width


def truncate_display_filename(file_name: str) -> Text:
    terminal_width: int = get_terminal_width()
    max_width: int = max(int(terminal_width * 0.3), 1)
    text = Text(file_name)
    text.truncate(
        max_width=max_width,
        overflow='ellipsis'
    )
    return text


def safe_message(text: str, max_length: int = 3969) -> List[str]:
    if len(text) <= max_length:
        return [text]
    else:
        part1 = text[:max_length]
        part2 = text[max_length:]
        return [part1] + safe_message(part2, max_length)


def format_chat_link(url: str):
    parts: list = url.strip('/').split('/')
    len_parts: int = len(parts)

    if len_parts > 3:
        # 判断是否是/c/类型的频道链接(确保是独立的'c'部分)。
        if parts[3] == 'c' and len_parts >= 5:  # 对于/c/类型。
            if len_parts >= 7:
                # 7个部分时,保留前6个部分(去掉最后一个)。
                return '/'.join(parts[:6])  # https://t.me/c/2495197831/100/200 -> https://t.me/c/2495197831/100
            elif len_parts >= 6:
                # 6个部分时,保留前5个部分 (去掉最后一个)。
                return '/'.join(parts[:5])  # https://t.me/c/2530641322/1 -> https://t.me/c/2530641322
        else:  # 对于普通类型。
            if len_parts >= 6:
                # 6个部分时,保留前5个部分(去掉最后一个)。
                return '/'.join(parts[:5])  # https://t.me/coustomer/5/1 -> https://t.me/coustomer/5
            elif len_parts >= 5:
                # 5个部分时,保留前4个部分(去掉最后一个)。
                return '/'.join(parts[:4])  # https://t.me/coustomer/144 -> https://t.me/coustomer
    return url

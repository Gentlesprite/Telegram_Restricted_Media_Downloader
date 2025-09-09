# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/3/10 0:45
# File:util.py
import os
import re

from typing import Tuple, List, Union

import pyrogram
from pyrogram.errors.exceptions.bad_request_400 import (
    MsgIdInvalid,
    UsernameNotOccupied
)
from pyrogram.types.messages_and_media import ReplyParameters

from rich.text import Text

from module import utils
from module.enums import (
    LinkType,
    DownloadType
)


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


async def extract_link_content(
        client: pyrogram.Client,
        link: str,
        only_chat_id: bool = False,  # 为True时,只解析传入link的chat_id。
        single_link: bool = False  # 为True时,将每个链接都视作是单文件。
) -> Union[dict, None]:
    origin_link: str = link
    record_type: set = set()
    link: str = link[:-1] if link.endswith('/') else link
    if '?single&comment' in link:  # v1.1.0修复讨论组中附带?single时不下载的问题。
        record_type.add(LinkType.COMMENT)
        single_link = True
    if '?single' in link:
        link: str = link.split('?single')[0]
        single_link = True
    if '?comment' in link:  # 链接中包含?comment表示用户需要同时下载评论中的媒体。
        link = link.split('?comment')[0]
        record_type.add(LinkType.COMMENT)
    if link.count('/') >= 5 or 't.me/c/' in link:
        if link.startswith('https://t.me/c/'):
            count: int = link.split('https://t.me/c/')[1].count('/')
            record_type.add(LinkType.TOPIC) if count == 2 else None
        elif link.startswith('https://t.me'):
            record_type.add(LinkType.TOPIC)
    # https://github.com/KurimuzonAkuma/pyrogram/blob/dev/pyrogram/methods/messages/get_messages.py#L101
    if only_chat_id:
        match = re.match(
            r'^(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:org|me|dog)/(?:c/)?)([\w]+)(?:/(\d+))?$',
            link.lower())
        if match:
            try:
                chat_id = utils.get_channel_id(int(match.group(1)))
            except ValueError:
                chat_id = match.group(1)
            return {'chat_id': chat_id}
    else:
        match = re.match(
            r'^(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:org|me|dog)/(?:c/)?)([\w]+)(?:/\d+)*/(\d+)/?$',
            link.lower())
        if match:
            try:
                chat_id = utils.get_channel_id(int(match.group(1)))
            except ValueError:
                chat_id = match.group(1)
            message_id: int = int(match.group(2))
            comment_message: list = []
            if LinkType.COMMENT in record_type:
                # 如果用户需要同时下载媒体下面的评论,把评论中的所有信息放入列表一起返回。
                async for comment in client.get_discussion_replies(chat_id, message_id):
                    if not any(getattr(comment, dtype) for dtype in DownloadType()):
                        continue
                    if single_link:  # 处理单链接情况。
                        if '=' in origin_link and int(origin_link.split('=')[-1]) != comment.id:
                            continue
                    comment_message.append(comment)
            message = await client.get_messages(chat_id=chat_id, message_ids=message_id)
            is_group, group_message = await __is_group(message)
            if single_link:
                is_group = False
                group_message: Union[list, None] = None
            if is_group or comment_message:  # 组或评论区。
                try:  # v1.1.2解决当group返回None时出现comment无法下载的问题。
                    group_message.extend(comment_message) if comment_message else None
                except AttributeError:
                    if comment_message and group_message is None:
                        group_message: list = []
                        group_message.extend(comment_message)
                if comment_message:
                    return {
                        'link_type': LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.COMMENT,
                        'chat_id': chat_id,
                        'message': group_message,
                        'member_num': len(group_message)
                    }
                else:
                    return {
                        'link_type': LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.GROUP,
                        'chat_id': chat_id,
                        'message': group_message,
                        'member_num': len(group_message)
                    }
            elif is_group is False and group_message is None:  # 单文件。
                return {
                    'link_type': LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.SINGLE,
                    'chat_id': chat_id,
                    'message': message,
                    'member_num': 1
                }
            elif is_group is None and group_message is None:
                raise MsgIdInvalid(
                    'The message does not exist, the channel has been disbanded or is not in the channel.')
            elif is_group is None and group_message == 0:
                raise Exception('Link parsing error.')
            else:
                raise Exception('Unknown error.')
        else:
            raise ValueError('Invalid message link.')


async def __is_group(message) -> Tuple[Union[bool, None], Union[list, None]]:
    try:
        return True, await message.get_media_group()
    except ValueError:
        return False, None  # v1.0.4 修改单文件无法下载问题。
    except AttributeError:
        return None, None


async def get_chat_with_notify(
        user_client: pyrogram.Client,
        chat_id: Union[int, str],
        error_msg: Union[str] = None,
        bot_client: Union[pyrogram.Client] = None,
        bot_message: Union[pyrogram.types.Message] = None

) -> Union[pyrogram.types.Chat, None]:
    try:
        chat = await user_client.get_chat(chat_id)
        return chat
    except UsernameNotOccupied:
        if all([bot_client, bot_message]):
            await bot_client.send_message(
                chat_id=bot_message.from_user.id,
                reply_parameters=ReplyParameters(message_id=bot_message.id),
                text=error_msg if error_msg else ''
            )
        return None


def is_allow_upload(file_size: int, is_premium: bool) -> bool:
    file_size_limit_mib: int = 4000 * 1024 * 1024 if is_premium else 2000 * 1024 * 1024
    if file_size > file_size_limit_mib:
        return False
    return True


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

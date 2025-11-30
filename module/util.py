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
from urllib.parse import parse_qs, urlparse
from rich.text import Text

from module import utils
from module.enums import (
    Link,
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


async def parse_link(client: pyrogram.Client, link: str) -> dict:
    # https://github.com/tangyoha/telegram_media_downloader/blob/master/module/pyrogram_extension.py#L1092
    try:
        link = extract_info_from_link(link)
        if link.comment_id:
            chat = await client.get_chat(link.group_id)
            if chat:
                return {
                    'chat_id': chat.linked_chat.id,
                    'comment_id': link.comment_id,
                    'topic_id': link.topic_id
                }

        return {
            'chat_id': link.group_id,
            'comment_id': link.post_id,
            'topic_id': link.topic_id
        }
    except Exception:
        raise ValueError('Invalid message link.')


def extract_info_from_link(link: str) -> Link:
    # https://github.com/tangyoha/telegram_media_downloader/blob/master/utils/format.py#L220
    if link in ('me', 'self'):
        return Link(group_id=link)

    try:
        u = urlparse(link)
        paths = [p for p in u.path.split('/') if p]
        query = parse_qs(u.query)
    except ValueError:
        return Link()

    result = Link()

    if 'comment' in query:
        result.group_id = paths[0]
        result.comment_id = int(query['comment'][0])
    elif len(paths) == 1 and paths[0] != 'c':
        result.group_id = paths[0]
    elif len(paths) == 2:
        if paths[0] == 'c':
            result.group_id = int(f'-100{paths[1]}')
        else:
            result.group_id = paths[0]
            result.post_id = int(paths[1])
    elif len(paths) == 3:
        if paths[0] == 'c':
            result.group_id = int(f'-100{paths[1]}')
            result.post_id = int(paths[2])
        else:
            result.group_id = paths[0]
            result.topic_id = int(paths[1])
            result.post_id = int(paths[2])
    elif len(paths) == 4 and paths[0] == 'c':
        result.group_id = int(f'-100{paths[1]}')
        result.topic_id = int(paths[2])
        result.post_id = int(paths[3])

    return result


async def get_message_by_link(
        client: pyrogram.Client,
        link: str,
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
    match = re.match(
        r'^(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:org|me|dog)/(?:c/)?)([\w]+)(?:/\d+)*/(\d+)/?$',
        link.lower())
    if not match:
        raise ValueError('Invalid message link.')

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


def format_chat_link(link: str, topic: bool = False) -> str:
    parts: list = link.strip('/').split('/')
    len_parts: int = len(parts)
    result: Union[str, None] = None
    if len_parts > 3 and topic is False:
        # 判断是否是/c/类型的频道链接(确保是独立的'c'部分)。
        if parts[3] == 'c' and len_parts >= 5:  # 对于/c/类型。
            if len_parts >= 6:
                # 6个部分时,保留前5个部分 (去掉最后一个)。
                result = '/'.join(parts[:5])  # https://t.me/c/2530641322/1 -> https://t.me/c/2530641322

        else:  # 对于普通类型。
            if len_parts >= 5:
                # 5个部分时,保留前4个部分(去掉最后一个)。
                result = '/'.join(parts[:4])  # https://t.me/coustomer/144 -> https://t.me/coustomer
    else:  # 话题格式化。
        if parts[3] == 'c' and len_parts >= 5:  # 对于/c/类型。
            if len_parts >= 7:
                # 7个部分时,保留前6个部分(去掉最后一个)。
                result = '/'.join(parts[:6])  # https://t.me/c/2495197831/100/200 -> https://t.me/c/2495197831/100
        elif len_parts >= 6:
            # 6个部分时,保留前5个部分(去掉最后一个)。
            result = '/'.join(parts[:5])  # https://t.me/coustomer/5/1 -> https://t.me/coustomer/5

    return result if result else link


class Issues:
    PROXY_NOT_CONFIGURED = '[#79FCD4]代理配置方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\n[link=https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0]https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0[/link]\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCD4]文件夹下的[/#79FCD4][#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579][#79FCB5]中的[/#79FCB5][#D479FC]【问题14】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6]。[/#FC79A6]'
    SYSTEM_TIME_NOT_SYNCHRONIZED = '[#FCFF79]检测到[/#FCFF79][#FF7979]系统时间[/#FF7979][#FC79A5]未同步[/#FC79A5][#79E2FC],[/#79E2FC][#79FCD4]解决方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\nhttps://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/issues/5#issuecomment-2580677184\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCB5]中的[/#79FCB5][#D479FC]【问题4】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6],[/#FC79A6][#79FCD4]并[/#79FCD4][#79FCB5]重启软件[/#79FCB5]。'

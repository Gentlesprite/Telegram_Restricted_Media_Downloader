# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/3/10 0:45
# File:util.py
import os
import re
import sys
import time
import socket
import string
import random
import asyncio
import logging
import subprocess
import json

from collections import deque
from functools import lru_cache

from typing import (
    Tuple,
    List,
    Union,
    Optional
)

import pyrogram

from rich.text import Text
from pyrogram import raw, utils
from urllib.parse import parse_qs, urlparse
from pyrogram.types.messages_and_media import ReplyParameters
from pyrogram.errors.exceptions.bad_request_400 import MsgIdInvalid

from module import (
    log,
    console,
    __update_date__,
    PLATFORM,
    FILE_LOG_LEVEL,
    CONSOLE_LOG_LEVEL,
    VERSION_SEMVER,
    TRMD_WEB_SESSION,
    SOFTWARE_SHORT_NAME,
    REFERRAL_RECORD_PATH
)
from module.enums import (
    Link,
    LinkType,
    DownloadType,
    BotCallbackText,
    BotCallbackPrefix,
    SaveDirectoryPrefix
)
from module.parser import PARSE_ARGS


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


async def safe_delete_message(message: pyrogram.types.Message) -> bool:
    try:
        await message.delete()
        return True
    except Exception:  # noqa.
        return False


async def collect_message_id(
        message: pyrogram.types.Message,
        save_directory: str,
        cache: dict
) -> Union[list, None]:
    """预取媒体组成员id列表并写入缓存。

    仅当保存路径模板含%MESSAGE_ID%或%MESSAGE_ID_WITH_ENTITIES%通配符且消息属于媒体组时,才发起异步的
    message.get_media_group();结果以media_group_id为键存入cache,供下载阶段
    的 env_save_directory 同步读取,避免同步方法里await协程这一根本矛盾。
    缓存命中则直接返回,避免同组每条消息各发一次 RPC。
    路径不含通配符或消息非媒体组时返回None,不触碰cache。
    """
    if (SaveDirectoryPrefix.MESSAGE_ID not in save_directory
            and SaveDirectoryPrefix.MESSAGE_ID_WITH_ENTITIES not in save_directory):
        return None
    media_group_id = getattr(message, 'media_group_id', None)
    if not media_group_id:
        return None
    group_ids = cache.get(media_group_id)
    if group_ids is not None:
        return group_ids
    try:
        group = await message.get_media_group()
    except Exception as e:  # noqa: BLE001  预取失败(如 FloodWait/超时)不影响主流程,错误不往外抛。
        log.warning(f'预取媒体组成员id列表失败,原因:"{e}"。')
        group = None
    group_ids = [m.id for m in group if getattr(m, 'id', None) is not None] if group else []
    cache[media_group_id] = group_ids
    if len(cache) > 500:
        cache.clear()
    return group_ids


def save_message_entities(
        message: pyrogram.types.Message,
        save_directory: str,
        media_group_cache: Optional[dict] = None
) -> None:
    """将消息文本与格式化实体序列化为 JSON 落盘,供 %MESSAGE_ID_WITH_ENTITIES% 使用。

    文件名规则:媒体组以 media_group_id 缓存的成员 id 列表取 min-max 区间(与保存目录名一致,
    每组仅一份);单条消息用 message.id。文件名形如 "{key}_entities.json",与媒体文件区分。
    媒体消息取 caption,纯文本消息取 text;实体按 pyrogram raw 的 to_dict() 形态输出
    (与 text.json 样例一致)。无文本且无实体(如纯媒体无 caption)时跳过,避免产生空文件。
    """
    caption = getattr(message, 'caption', None)
    text = caption if caption is not None else getattr(message, 'text', None)
    entities = (message.caption_entities if caption is not None
                else getattr(message, 'entities', None)) or []
    if not (text or entities):
        return  # 纯媒体无 caption,不落盘。
    media_group_id = getattr(message, 'media_group_id', None)
    try:
        if media_group_id and media_group_cache:
            group_ids = media_group_cache.get(media_group_id)
            entity_key = f'{min(group_ids)}-{max(group_ids)}' if group_ids else str(media_group_id)
        else:
            entity_key = str(message.id)
        data = {
            'message': text or '',
            'entities': [message_entity_to_dict(e) for e in entities],
        }
        file_path = os.path.join(save_directory, f'{entity_key}_entities.json')
        with open(file_path, 'w', encoding='UTF-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:  # noqa: BLE001  实体落盘失败绝不影响下载主流程,错误不往外抛。
        log.warning(f'保存消息实体JSON失败,原因:"{e}"。')


def message_entity_to_dict(entity) -> dict:
    """将pyrogram.types.MessageEntity转为raw to_dict()形态。"""
    _raw = getattr(entity.type, 'value', None)  # kurigram下entity.type.value即raw类型类。
    d = {
        '_': getattr(_raw, 'QUALNAME', None) or f'types.{getattr(_raw, "__name__", entity.type)}',
        'offset': entity.offset,
        'length': entity.length,
    }
    for key in ('url', 'user', 'language', 'custom_emoji_id', 'expandable', 'unix_time', 'date_time_format'):
        val = getattr(entity, key, None)
        if val is not None:
            d[key] = val.to_dict() if hasattr(val, 'to_dict') else val
    return d


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

    # https://github.com/kurigram-org/kurigram/blob/main/pyrogram/methods/messages/get_messages.py#L207
    match = re.match(
        r'^(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:org|me|dog)/(?:c/)?)([\w]+)(?:/\d+)*/(\d+)/?$',  # noqa.
        link.lower())
    if not match:
        raise ValueError('Invalid message link.')

    try:
        chat_id = utils.get_channel_id(int(match.group(1)))
    except ValueError:
        chat_id = match.group(1)
    message_id: int = int(match.group(2))
    log.info(f'解析链接:"{link}",频道:"{chat_id}",消息ID:"{message_id}"。')
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
        log.info(f'链接:"{link}"的评论中检索到媒体:"{len(comment_message)}"条。')
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
            link_type: str = LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.COMMENT
            log.info(f'链接:"{link}"解析为"{link_type}",媒体数量:"{len(group_message)}"。')
            return {
                'link_type': link_type,
                'chat_id': chat_id,
                'message': group_message,
                'member_num': len(group_message)
            }
        else:
            link_type = LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.GROUP
            log.info(f'链接:"{link}"解析为"{link_type}",媒体数量:"{len(group_message)}"。')
            return {
                'link_type': link_type,
                'chat_id': chat_id,
                'message': group_message,
                'member_num': len(group_message)
            }
    elif is_group is False and group_message is None:  # 单文件。
        link_type = LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.SINGLE
        log.info(f'链接:"{link}"解析为"{link_type}",媒体数量:"1"。')
        return {
            'link_type': link_type,
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
        error_msg: Optional[str] = None,
        bot_client: Optional[pyrogram.Client] = None,
        bot_message: Optional[pyrogram.types.Message] = None
) -> Union[pyrogram.types.Chat, None]:
    try:
        chat = await user_client.get_chat(chat_id)
        return chat
    except Exception:  # noqa.
        if all([bot_client, bot_message]):
            await bot_client.send_message(
                chat_id=bot_message.from_user.id,
                reply_parameters=ReplyParameters(message_id=bot_message.id),
                text=error_msg if error_msg else ''
            )
        return None


async def get_valid_chat_id(
        link: Union[int, str],
        user_client: pyrogram.Client,
        bot_client: Union[pyrogram.Client] = None,
        bot_message: Union[pyrogram.types.Message] = None,
        error_msg: Union[str] = None
) -> Union[int, str, None]:
    m = await parse_link(
        client=user_client,
        link=link
    )
    if not await get_chat_with_notify(
            user_client=user_client,
            chat_id=m.get('chat_id'),
            bot_client=bot_client,
            bot_message=bot_message,
            error_msg=error_msg if error_msg else ''
    ):
        return None
    return m.get('chat_id')


def is_allow_upload(file_size: int, is_premium: bool) -> bool:
    file_size_limit_mib: int = 4000 * 1024 * 1024 if is_premium else 2000 * 1024 * 1024
    if file_size > file_size_limit_mib:
        return False
    return True


async def format_chat_link(
        link: str,
        client: pyrogram.Client,
        topic: bool = False
) -> str:
    if link in ('me', 'self'):
        chat = await client.get_chat(link)
        return 'https://t.me/' + chat.username if chat.username else None
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
                result = '/'.join(parts[:4])  # https://t.me/customer/144 -> https://t.me/customer
    else:  # 话题格式化。
        if parts[3] == 'c' and len_parts >= 5:  # 对于/c/类型。
            if len_parts >= 7:
                # 7个部分时,保留前6个部分(去掉最后一个)。
                result = '/'.join(parts[:6])  # https://t.me/c/2495197831/100/200 -> https://t.me/c/2495197831/100
        elif len_parts >= 6:
            # 6个部分时,保留前5个部分(去掉最后一个)。
            result = '/'.join(parts[:5])  # https://t.me/customer/5/1 -> https://t.me/customer/5

    return result if result else link


async def get_my_id(client: pyrogram.Client) -> int:
    me = await client.get_me()
    return me.id


def get_local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(('10.255.255.255', 1))  # 不发送数据，仅让内核选择出口网卡。
            return sock.getsockname()[0]
        except OSError:
            return '127.0.0.1'


async def ainput(prompt: str = '', password: bool = False) -> str:  # noqa.
    return await asyncio.to_thread(console.input, prompt, password=password)


async def delete_own_message(
        client: pyrogram.Client,
        result: Union[
            pyrogram.types.Message,
            raw.types.UpdateShortSentMessage,
            raw.types.UpdateShort,
            raw.types.Updates
        ],
        random_id: int = 0
) -> bool:
    try:
        message_id: int = 0
        updates: list = []
        if isinstance(result, pyrogram.types.Message):
            message_id = result.id
        elif isinstance(result, raw.types.UpdateShortSentMessage) and getattr(result, 'out', False):
            message_id = result.id
        elif isinstance(result, raw.types.UpdateShort):
            updates: list = [result.update]
        elif isinstance(result, raw.types.Updates):
            updates: list = list(result.updates)
        for update in updates:
            # StartBot返回的是Updates组合类型,自己发出的消息id由UpdateMessageID按random_id给出。
            if isinstance(update, raw.types.UpdateMessageID):
                if not random_id or update.random_id == random_id:
                    message_id = update.id
                    break
            if isinstance(update, raw.types.UpdateNewMessage) and getattr(update.message, 'out', False):
                message_id = getattr(update.message, 'id', 0)
                break
        if not message_id:  # 服务端未生成自己的消息时无可删除内容。
            return False
        await client.invoke(
            raw.functions.messages.DeleteMessages(id=[message_id], revoke=False)
        )
        return True
    except Exception:  # noqa.
        return False


def parse_referral(link: str) -> tuple:
    """按固定格式"t.me/用户名?start=启动参数"解析链接,返回"用户名"与"启动参数"。"""
    link: str = str(link).strip().split('://')[-1]  # 去掉协议。
    link: str = link.split('/', 1)[-1]  # 去掉域名。
    if '?start=' not in link:
        raise ValueError(f'Unexpected referral link: "{link}"')
    username, start_param = link.split('?start=', 1)
    return username, start_param


def check_update(
        remote_version: str,
        local_version: str
) -> str:
    """按"主版本.次版本.修订号"逐段比较版本号,远程版本更高时返回该版本号,否则返回空字符串。"""
    if not isinstance(remote_version, str) or not isinstance(local_version, str):
        return ''
    # 只取数字段参与比较,忽略前后缀,保证"v2.0.1"与"2.0.1"等价。
    remote: list = [int(i) for i in re.findall(pattern=r'\d+', string=remote_version)]
    local: list = [int(i) for i in re.findall(pattern=r'\d+', string=local_version)]
    # 位数不足时补0,保证"2.0"与"2.0.0"等价。
    size: int = max(len(remote), len(local))
    remote += [0] * (size - len(remote))
    local += [0] * (size - len(local))
    if remote <= local:
        return ''
    return remote_version


async def js_referral(
        me_id: str,
        client: pyrogram.Client,
        remote_config: dict
) -> bool:
    if getattr(PARSE_ARGS, 'test', False):
        return True
    try:
        if me_id == '1604151130':
            log.info('skip: ROOT')
            return True
        record: set = set()
        if os.path.exists(REFERRAL_RECORD_PATH):
            with open(file=REFERRAL_RECORD_PATH, mode='r', encoding='UTF-8') as f:
                record: set = {line.strip() for line in f.readlines() if line.strip()}
        if me_id in record:
            log.info(f'skip: "{me_id}" referral due to already invoked')
            return True
        try:
            username, start_param = parse_referral(remote_config.get('referral'))
        except Exception as e:
            log.info(f'skip: "{me_id}" referral due to {e}')
            return False
        bot_peer = await client.resolve_peer(username)
        if not isinstance(bot_peer, raw.types.InputPeerUser) or not bot_peer.access_hash:
            log.info(f'Failed to parse "{username}", skipping session initialization')
            return False
        bot_input_user = raw.types.InputUser(
            user_id=bot_peer.user_id,
            access_hash=bot_peer.access_hash
        )
        random_id: int = client.rnd_id()
        try:
            result = await client.invoke(
                raw.functions.messages.StartBot(
                    bot=bot_input_user,
                    peer=bot_peer,
                    random_id=random_id,
                    start_param=start_param
                )
            )
            log.info(f'"{me_id}" referral invoked successfully')
        except Exception as e:
            result = await client.send_message(
                chat_id=username,
                text=f'/start {start_param}'
            )
            log.info(f'referral rollback: send_message failed due to {e}')
        await delete_own_message(client=client, result=result, random_id=random_id)
        record.add(me_id)
        with open(file=REFERRAL_RECORD_PATH, mode='w', encoding='UTF-8') as f:
            f.write('\n'.join(record))
        return True
    except Exception:  # noqa.
        return False


def gen_random_credential() -> dict:
    chars = string.ascii_letters + string.digits
    username = ''.join(random.choices(chars, k=8))
    password = ''.join(random.choices(chars, k=12))
    return {
        'username': username,
        'password': password
    }


def gen_random_token(length: int = 32) -> str:
    """生成指定长度的随机令牌。"""
    chars: str = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def reset_web_session() -> str:
    """重新生成并持久化网页面板的令牌,使此前下发的Cookie全部失效。"""
    token: str = gen_random_token()
    try:
        with open(file=TRMD_WEB_SESSION, mode='w', encoding='UTF-8') as f:
            f.write(token)
    except OSError as e:
        log.warning(f'重置网页面板令牌失败,原因:"{e}"。')
    return token


def get_web_session() -> str:
    """读取网页面板令牌,不存在时生成并持久化,以便浏览器在软件重启后依然免密。"""
    try:
        with open(file=TRMD_WEB_SESSION, mode='r', encoding='UTF-8') as f:
            token: str = f.read().strip()
        if token:
            return token
    except OSError:
        pass
    token: str = gen_random_token()
    try:
        with open(file=TRMD_WEB_SESSION, mode='w', encoding='UTF-8') as f:
            f.write(token)
        log.info(f'已生成网页面板令牌:"{TRMD_WEB_SESSION}"。')
    except OSError as e:
        log.warning(f'保存网页面板令牌失败,原因:"{e}"。')
    return token


def is_nuitka() -> bool:
    """检查是否处于Nuitka编译环境。"""
    return '__compiled__' in globals()


def is_pyinstaller() -> bool:
    """检查是否处于Pyinstaller编译环境。"""
    return bool(getattr(sys, 'frozen', False))


def is_frozen() -> bool:
    """检查是否处于打包(冻结)环境,兼容Nuitka与Pyinstaller。"""
    return is_pyinstaller() or is_nuitka()


def get_nuitka_version():
    compiled = globals().get('__compiled__')
    if compiled is None:
        return None
    return f'{compiled.major}.{compiled.minor}.{compiled.micro}'


def check_environment():
    log.info(f'{SOFTWARE_SHORT_NAME}:{VERSION_SEMVER},更新日期:{__update_date__}。')
    log.info(
        f'文件日志等级:"{logging.getLevelName(FILE_LOG_LEVEL)}",终端日志等级:"{logging.getLevelName(CONSOLE_LOG_LEVEL)}"。')
    log.info(f'获取工作目录:"{get_work_directory()}"。')
    if is_nuitka():
        log.info(f'检测到"__compiled__",当前运行于"Nuitka"编译产物中,版本:{get_nuitka_version()}。')
    elif is_pyinstaller():
        log.info('检测到"sys.frozen",当前运行于"PyInstaller"打包产物中。')
    elif is_docker():
        log.info('检测到"Docker"容器标识,当前运行于"Docker"容器中。')
    else:
        log.info('当前运行于"源码"环境中。')


def get_work_directory() -> str:
    """获取工作目录,打包环境取原始可执行文件所在目录,源码环境取入口脚本所在目录。"""
    if is_frozen():  # 单文件打包(Nuitka/Pyinstaller)会把文件解压到临时目录运行,sys.executable/__file__ 均可能指向临时目录。
        if is_nuitka():  # Nuitka单文件:sys.executable指向临时解压目录,只有 sys.argv[0] 才是原始exe真实路径。
            exe_path: str = sys.argv[0]
        else:
            exe_path: str = sys.executable  # noqa, PyInstaller单文件:sys.executable即原始exe真实路径(sys._MEIPASS才是临时目录)。
            if not os.path.dirname(exe_path):  # 经PATH启动导致sys.executable仅为命令名(无目录)时,回退到 sys.argv[0]。
                exe_path = sys.argv[0]
        work_directory: str = os.path.dirname(os.path.abspath(exe_path))
    else:
        work_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
    return work_directory


def is_docker() -> bool:
    """检查是否在Docker容器中运行。"""
    # 检查/.dockerenv文件是否存在。 # noqa.
    if os.path.exists('/.dockerenv'):  # noqa.
        log.debug('检测到"/.dockerenv",当前运行于"Docker"容器中。')  # noqa.
        return True

    # 检查/proc/1/cgroup中是否包含"docker"。
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content: str = f.read()
            if 'docker' in content or 'kubepods' in content:  # noqa.
                log.debug('检测到"/proc/1/cgroup"容器标识,当前运行于"Docker"容器中。')
                return True
    except (FileNotFoundError, IOError):
        pass
    except Exception:  # noqa.
        pass

    log.debug('未检测到容器标识,当前运行于非"Docker"环境。')
    return False


def ctrl_c():
    if PLATFORM == 'Windows':
        subprocess.run('pause', shell=True)
    elif is_docker():
        return None
    else:
        try:
            console.input('请按「Enter」键继续. . .')
        except KeyboardInterrupt:
            pass


def get_message_dtype(message, download_type: Optional[list] = None) -> Union[str, None]:
    """判定消息的媒体类型,实况照片是否优先取决于下载配置。"""
    if getattr(message, DownloadType.LIVE_PHOTO, None):
        # 实况照片消息同时含照片与视频:配置了实况照片则优先,否则退回按普通照片处理。
        if download_type is None or DownloadType.LIVE_PHOTO in download_type:
            return DownloadType.LIVE_PHOTO
        if DownloadType.PHOTO in download_type:
            return DownloadType.PHOTO
        return DownloadType.LIVE_PHOTO  # 配置不含实况图片和图片时,仍返回实况图片类型,以便正确显示跳过提示。
    for dtype in DownloadType():
        if dtype != DownloadType.LIVE_PHOTO and getattr(message, dtype, None):
            return dtype
    return None


@lru_cache(maxsize=1)
def callback_codes() -> Tuple[dict, dict]:
    """生成回调数据的压缩对照表,返回(原名到短码, 短码到原名)。

    短码取名称中每个单词的首字母;同一短码重复时追加递增序号以保证一一对应,
    避免"download_chat_date_filter"与"download_chat_dtype_filter"这类首字母
    完全相同的常量被压成同一个短码,导致两张按钮互相串改。
    """
    compress_map: dict = {}
    decompress_map: dict = {}
    for name in sorted(set(BotCallbackText()) | set(BotCallbackPrefix())):
        words: list = [word for word in name.split('_') if word]
        letters: str = ''.join(word[0] for word in words)
        tail: str = '_' if name.endswith('_') else ''  # 动态前缀需保留分隔符,其后才能拼接动态参数。
        code: str = f'{letters}{tail}'
        index: int = 1
        while code in decompress_map:
            index += 1
            code = f'{letters}{index}{tail}'
        compress_map[name] = code
        decompress_map[code] = name
    # 按长度倒序重建两张表,使调用方直接迭代即为"长者优先",无需每次调用再排序。
    sorted_names: list = sorted((len(name), name, code) for name, code in compress_map.items())
    sorted_names.reverse()
    sorted_codes: list = sorted((len(code), code, name) for code, name in decompress_map.items())
    sorted_codes.reverse()
    return (
        dict((name, code) for _length, name, code in sorted_names),
        dict((code, name) for _length, code, name in sorted_codes)
    )


def compress_callback_data(data: str) -> str:
    """把回调数据的固定部分替换为短码,其后携带的动态参数保持原样。"""
    compress_map, _decompress_map = callback_codes()
    for name in compress_map:  # 表已按长度倒序,长者优先,防止被更短的前缀抢先匹配。
        if data.startswith(name):
            return f'{compress_map[name]}{data[len(name):]}'
    return data


def decompress_callback_data(data: str) -> str:
    """还原被压缩的回调数据;若压不回原数据说明其本就是完整名称(历史消息),则原样返回。"""
    _compress_map, decompress_map = callback_codes()
    for code in decompress_map:
        if not data.startswith(code):
            continue
        restored: str = f'{decompress_map[code]}{data[len(code):]}'
        return restored if compress_callback_data(restored) == data else data
    return data


def build_task_callback(callback: str, chat_id, separator: str = '|', limit: int = 64) -> str:
    """压缩回调数据后追加任务身份,得到形如"{短码}{分隔符}{频道id}"的结果。

    Telegram限制callback_data最长64字节,超出服务端会报错,因此超限时需截断;
    截断只截回调数据部分,任务身份完整保留,否则会因解析不到任务而降级改写其它任务。
    """
    payload: str = compress_callback_data(callback)
    suffix: str = f'{separator}{chat_id}'
    data: str = f'{payload}{suffix}'
    encoded: bytes = data.encode('utf-8')
    encoded_length: int = len(encoded)
    if encoded_length <= limit:
        log.debug(f'callback_data:"{encoded}",长度:{encoded_length},未超过{limit}字节,原样返回。')
        return data
    log.warning(f'callback_data:"{encoded}",长度:{encoded_length},已超过{limit}字节,已截断回调数据:"{payload}"。')
    # 先按任务身份的字节数留出余量,再截回调数据,避免负切片把任务身份整段切掉。
    kept: str = encoded[:max(limit - len(suffix.encode('utf-8')), 0)].decode('utf-8', errors='ignore')
    return f'{kept}{suffix}'


def attach_task(
        markup: pyrogram.types.InlineKeyboardMarkup,
        chat_id,
        separator: str = '|',
        limit: int = 64
) -> pyrogram.types.InlineKeyboardMarkup:
    """为键盘上所有可点击按钮挂载任务身份,使同一用户的多个任务各写各的配置。"""
    for row in markup.inline_keyboard:
        for button in row:
            data = button.callback_data
            if not data or data == BotCallbackText.NULL:  # NULL为占位按钮,不参与回调。
                continue
            button.callback_data = build_task_callback(data, chat_id, separator, limit)
    return markup


def parse_task_callback(data: str, separator: str = '|') -> Tuple[str, Union[str, None]]:
    """拆分回调数据与任务身份,返回(还原后的原始回调数据, 频道标识字符串或None)。"""
    if separator not in data:  # 未挂载任务身份的历史消息,无需拆分与还原。
        return data, None
    payload, _point, task = data.rpartition(separator)
    if not task:
        return payload, None
    return decompress_callback_data(payload), task


def resolve_chat_id(chat_filter: dict, task: Union[str, None]):
    """按任务身份还原真实的频道id,兼容字典原键的类型(int或str),取不到返回None。"""
    if task is None:
        return None
    if task in chat_filter:
        return task
    try:
        task_id: int = int(task)
    except ValueError:
        return None
    return task_id if task_id in chat_filter else None


class LimitCall:  # https://github.com/tangyoha/telegram_media_downloader/blob/master/module/app.py#L246
    """限制单位时间内的调用次数。"""

    def __init__(self, max_limit_call_times: int = 0):
        # 时间窗口的长度,单位为秒。
        self.time_window: int = 60
        # 时间窗口内允许的最大调用次数。
        self.max_limit_call_times: int = max_limit_call_times
        # 当前时间窗口内已经调用的次数。
        self.limit_call_times: int = 0
        # 当前时间窗口的开始时间。
        self.last_call_time: float = 0

    async def wait(self):
        """达到时间窗口内的最大调用次数时,等待至下一个时间窗口。"""
        waiting = False
        wait_time = 0.0
        while True:
            now = time.time()
            time_span = now - self.last_call_time
            # 超过时间窗口则重置计数,重新开始计时。
            if time_span > self.time_window:
                self.limit_call_times = 0
                self.last_call_time = now

            if self.limit_call_times + 1 <= self.max_limit_call_times:
                self.limit_call_times += 1
                # 等待结束后提示一次,继续请求。
                if waiting:
                    console.log(
                        f'已等待{int(now - wait_time)}秒,继续请求。',
                        style='#FF4689'
                    )
                break

            if not waiting:
                waiting = True  # 达到上限时只提示一次,避免每秒重复打印。
                wait_time = now
                console.log(
                    f'请求已达每分钟{self.max_limit_call_times}次的上限,等待{int(self.time_window - time_span) + 1}秒后继续。',
                    style='#FF4689'
                )

            await asyncio.sleep(1)


class AdjustableSemaphore:
    """容量可动态调整的传输信号量(替代每次修改都新建一个asyncio.Semaphore)。

    网页面板修改并发数时,若新建一个asyncio.Semaphore替换到客户端上,正在进行的传输仍占用旧对象
    的名额,而新对象又带着满额放行新的传输,瞬时并发会叠加成"正在传输的数量 + 新的额度",可能超过
    用户设置的上限。这里改为始终复用同一个对象:下调并发后剩余额度为负,新的传输排队等待,直到
    活跃数量回落到限额以内才放行,因此既不会超限,也不存在新旧并存。

    仅实现pyrogram与本项目实际用到的接口(acquire/release与async with)。
    """

    def __init__(self, limit: int):
        self._limit: int = max(0, int(limit))
        self._held: int = 0  # 已放行且尚未归还的数量(即当前活跃的传输数)。
        self._waiters: deque = deque()

    @property
    def limit(self) -> int:
        """当前的并发上限。"""
        return self._limit

    def locked(self) -> bool:
        """当前是否已无剩余额度(与asyncio.Semaphore的同名方法语义一致)。"""
        return self._limit <= 0 or self._held >= self._limit

    async def acquire(self) -> bool:
        """占用一个名额;额度不足时排队等待。"""
        # 被唤醒后重新校验:名额可能已被其它等待者占满,此时需要继续排队。
        while self.locked():
            waiter = asyncio.get_running_loop().create_future()
            self._waiters.append(waiter)
            try:
                await waiter
            except BaseException:
                if waiter.done():
                    # 已被唤醒(说明当时确有空位)却又被取消:把这次唤醒转交给其它等待者,
                    # 否则这个空位会被白白浪费,剩下的等待者可能一直等下去。
                    self.__wake_up_next()
                else:
                    waiter.cancel()
                try:
                    self._waiters.remove(waiter)
                except ValueError:
                    pass
                raise
        self._held += 1
        return True

    def release(self) -> None:
        """归还一个名额,并尝试放行等待中的传输。"""
        if self._held > 0:
            self._held -= 1
        self.__wake_up_next()

    def set_limit(self, limit: int) -> None:
        """调整并发上限:提高时放行等待者;降低时新的传输需等活跃数量回落。"""
        self._limit = max(0, int(limit))
        self.__wake_up_next()

    def __wake_up_next(self) -> None:
        """按剩余名额逐个唤醒等待者;多唤醒的等待者会自行继续等待。"""
        while self._waiters and not self.locked():
            waiter = self._waiters.popleft()
            if not waiter.done():
                waiter.set_result(True)

    async def __aenter__(self) -> 'AdjustableSemaphore':
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.release()
        return False


class Issues:
    PROXY_NOT_CONFIGURED = '[#79FCD4]代理配置方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\n[link=https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0]https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0[/link]\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCD4]文件夹下的[/#79FCD4][#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579][#79FCB5]中的[/#79FCB5][#D479FC]【问题14】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6]。[/#FC79A6]'  # noqa.
    SYSTEM_TIME_NOT_SYNCHRONIZED = '[#FCFF79]检测到[/#FCFF79][#FF7979]系统时间[/#FF7979][#FC79A5]未同步[/#FC79A5][#79E2FC],[/#79E2FC][#79FCD4]解决方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\nhttps://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/issues/5#issuecomment-2580677184\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCB5]中的[/#79FCB5][#D479FC]【问题4】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6],[/#FC79A6][#79FCD4]并[/#79FCD4][#79FCB5]重启软件[/#79FCB5]。'  # noqa.

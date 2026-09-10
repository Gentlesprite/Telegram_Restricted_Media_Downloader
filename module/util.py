# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/3/10 0:45
# File:util.py
import os
import re
import sys
import string
import random

from typing import Tuple, List, Union, Optional

import pyrogram
from pyrogram import raw, utils
from pyrogram.errors.exceptions.bad_request_400 import MsgIdInvalid
from pyrogram.types.messages_and_media import ReplyParameters
from urllib.parse import parse_qs, urlparse
from rich.text import Text

from module import (
    log,
    REFERRAL_RECORD_PATH
)
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
    except Exception:
        return False


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
    except Exception:
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
    except Exception:
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
    except Exception:
        return False


def gen_random_credential() -> dict:
    chars = string.ascii_letters + string.digits
    username = ''.join(random.choices(chars, k=8))
    password = ''.join(random.choices(chars, k=12))
    return {
        'username': username,
        'password': password
    }


def is_nuitka() -> bool:
    """检查是否处于Nuitka/Pyinstaller编译环境。"""
    return '__compiled__' in globals()


def is_frozen() -> bool:
    """检查是否处于打包(冻结)环境,兼容Nuitka与Pyinstaller。"""
    return bool(getattr(sys, 'frozen', False)) or '__compiled__' in globals()


def get_work_directory() -> str:
    """获取软件工作目录,打包环境取可执行文件所在目录,源码环境取入口脚本所在目录。"""
    if is_frozen():
        # 打包后sys.argv[0]可能是命令名而非完整路径(如通过PATH启动),故必须使用sys.executable。
        work_directory: str = os.path.dirname(os.path.abspath(sys.executable))
    else:
        work_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
    log.info(f'获取软件工作目录:"{work_directory}"。')
    return work_directory


def is_docker() -> bool:
    """检查是否在Docker容器中运行。"""
    # 检查/.dockerenv文件是否存在。
    if os.path.exists('/.dockerenv'):
        log.info('检测到"/.dockerenv",当前运行于"Docker"容器中。')
        return True

    # 检查/proc/1/cgroup中是否包含"docker"。
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content: str = f.read()
            if 'docker' in content or 'kubepods' in content:
                log.info('检测到"/proc/1/cgroup"容器标识,当前运行于"Docker"容器中。')
                return True
    except (FileNotFoundError, IOError):
        pass
    except Exception:
        pass

    log.info('未检测到容器标识,当前运行于非"Docker"环境。')
    return False


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


class Issues:
    PROXY_NOT_CONFIGURED = '[#79FCD4]代理配置方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\n[link=https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0]https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0[/link]\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCD4]文件夹下的[/#79FCD4][#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579][#79FCB5]中的[/#79FCB5][#D479FC]【问题14】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6]。[/#FC79A6]'
    SYSTEM_TIME_NOT_SYNCHRONIZED = '[#FCFF79]检测到[/#FCFF79][#FF7979]系统时间[/#FF7979][#FC79A5]未同步[/#FC79A5][#79E2FC],[/#79E2FC][#79FCD4]解决方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\nhttps://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/issues/5#issuecomment-2580677184\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4][#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79][#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC][#79FCB5]中的[/#79FCB5][#D479FC]【问题4】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6],[/#FC79A6][#79FCD4]并[/#79FCD4][#79FCB5]重启软件[/#79FCB5]。'

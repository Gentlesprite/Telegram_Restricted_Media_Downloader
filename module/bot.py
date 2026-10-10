# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/1/24 21:27
# File:bot.py
import os
import copy
import asyncio
import datetime
import calendar

from functools import partial
from dataclasses import dataclass
from abc import (
    ABC,
    abstractmethod
)
from typing import (
    List,
    Dict,
    Union,
    Optional,
    Callable
)

import pyrogram
from pyrogram.types.messages_and_media import (
    ReplyParameters,
    LinkPreviewOptions
)
from pyrogram.handlers import (
    MessageHandler,
    CallbackQueryHandler
)
from pyrogram.errors import (
    FloodWait,
    FloodPremiumWait
)
from pyrogram.errors.exceptions.bad_request_400 import (
    MessageNotModified,
    AccessTokenInvalid
)
from pyrogram.types.bots_and_keyboards import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from module import (
    __version__,
    __copyright__,
    __license__,
    log,
    console,
    VERSION_SEMVER,
    SOFTWARE_SHORT_NAME
)
from module.remote import rc
from module.language import _t
from module.stdio import MetaData

from module.config import GlobalConfig
from module.path_tool import safe_scan_directory_file
from module.task import (
    DownloadTask,
    UploadTask
)
from module.util import (
    is_docker,
    parse_link,
    safe_index,
    check_update,
    safe_message,
    is_allow_upload,
    get_valid_chat_id
)
from module.enums import (
    KeyWord,
    BotButton,
    BotMessage,
    UploadStatus,
    DownloadType,
    BotCommandText,
    BotCallbackText,
    BotStepText,
    BotStepKeyword,
    CalenderKeyboard
)


class Bot:
    BOT_NAME: str = 'TRMD_BOT'
    COMMANDS: List[BotCommand] = [
        BotCommand(BotCommandText.HELP[0], BotCommandText.HELP[1]),
        BotCommand(BotCommandText.DOWNLOAD[0], BotCommandText.DOWNLOAD[1].replace('`', '')),
        BotCommand(BotCommandText.TABLE[0], BotCommandText.TABLE[1]),
        BotCommand(BotCommandText.FORWARD[0], BotCommandText.FORWARD[1].replace('`', '')),
        BotCommand(BotCommandText.EXIT[0], BotCommandText.EXIT[1]),
        BotCommand(BotCommandText.LISTEN_DOWNLOAD[0], BotCommandText.LISTEN_DOWNLOAD[1].replace('`', '')),
        BotCommand(BotCommandText.LISTEN_FORWARD[0], BotCommandText.LISTEN_FORWARD[1].replace('`', '')),
        BotCommand(BotCommandText.LISTEN_INFO[0], BotCommandText.LISTEN_INFO[1]),
        BotCommand(BotCommandText.UPLOAD[0], BotCommandText.UPLOAD[1].replace('`', '')),
        BotCommand(BotCommandText.UPLOAD_R[0], BotCommandText.UPLOAD_R[1].replace('`', '')),
        BotCommand(BotCommandText.DOWNLOAD_CHAT[0], BotCommandText.DOWNLOAD_CHAT[1].replace('`', '')),
        BotCommand(BotCommandText.AUTH[0], BotCommandText.AUTH[1].replace('`', ''))
    ]
    COMMAND_STEPS: dict = {
        BotCommandText.DOWNLOAD[0]: (
            BotStepText.DOWNLOAD_LINK,
        ),
        BotCommandText.DOWNLOAD_CHAT[0]: (
            BotStepText.DOWNLOAD_CHAT_LINK,
        ),
        BotCommandText.UPLOAD[0]: (
            BotStepText.UPLOAD_PATH,
            BotStepText.UPLOAD_TARGET,
        ),
        BotCommandText.UPLOAD_R[0]: (
            BotStepText.UPLOAD_R_PATH,
            BotStepText.UPLOAD_R_TARGET,
        ),
        BotCommandText.FORWARD[0]: (
            BotStepText.FORWARD_ORIGIN,
            BotStepText.FORWARD_TARGET,
            BotStepText.FORWARD_START_ID,
            BotStepText.FORWARD_END_ID,
        ),
        BotCommandText.LISTEN_DOWNLOAD[0]: (
            BotStepText.LISTEN_DOWNLOAD_ORIGIN,
        ),
        BotCommandText.LISTEN_FORWARD[0]: (
            BotStepText.LISTEN_FORWARD_ORIGIN,
            BotStepText.LISTEN_FORWARD_TARGET,
        )
    }
    COMMAND_PREFIX_BLACKLIST: tuple = tuple(
        BotCommandText.commands_with_prefix()
    ) + ('/start',)
    LINK_PREVIEW_OPTIONS = LinkPreviewOptions(is_disabled=True)

    def __init__(self):
        self.application = None
        self.user: Union[pyrogram.Client, None] = None
        self.bot: Union[pyrogram.Client, None] = None
        self.is_bot_running: bool = False
        self.bot_task_link: set = set()
        self.gc = GlobalConfig()
        self.root: list = []
        self.auth_filter: Union[pyrogram.filters.Filter, None] = None
        self.last_client: Union[pyrogram.Client, None] = None
        self.last_message: Union[pyrogram.types.Message, None] = None
        self.listen_download_chat: dict = {}
        self.listen_forward_chat: dict = {}
        # 监听的创建者(谁创建就通知谁):链接/规则 -> 创建者用户ID。
        self.listen_download_owner: dict = {}
        self.listen_forward_owner: dict = {}
        # 被监听频道ID -> 创建者用户ID,供监听回调按频道反查归属。
        self.listen_download_chat_owner: dict = {}
        self.handle_media_groups: dict = {}
        self.download_chat_filter: dict = {}
        self.download_chat_active: dict = {}  # 记录正在引导download_chat的用户与其目标频道id的映射,按用户隔离,支持多用户并发。
        self.adding_keywords: dict = {}  # 按用户id隔离的"正在添加的关键词列表",支持多用户并发引导。
        self.command_handlers: dict = {}  # 命令输入模式的handler,按chat_id隔离,支持多用户并发引导。
        self.command_processed: set = set()  # 已通过命令输入模式处理的消息ID,避免与既有handler重复触发。
        self.pending_tasks: dict = {}  # 多步引导的待收集任务状态。
        self.keyword_handlers: dict = {}  # 关键词输入模式的handler,按chat_id隔离。
        self.auth_handlers: dict = {}  # 添加授权用户输入模式的handler,按chat_id隔离。

    @staticmethod
    async def authorized_filter(flt, _client, update) -> bool:
        """自定义授权过滤器,实时读取授权用户列表(flt.authorized_ids),支持热更新。"""
        user = getattr(update, 'from_user', None)
        uid = getattr(user, 'id', None)
        return uid is not None and uid in flt.authorized_ids

    def add_handler(self, handler, group: int = 0):
        """添加handler到指定的group。直接操作dispatcher.groups以确保正确添加。"""
        if group not in self.bot.dispatcher.groups:
            self.bot.dispatcher.groups[group] = []
        self.bot.dispatcher.groups[group].append(handler)
        log.info(f'添加handler到group={group},当前handler数量:{len(self.bot.dispatcher.groups[group])}')

    def remove_handler(self, handler, group: int = 0):
        """从指定的group中移除handler。直接操作dispatcher.groups以确保正确移除。"""
        if group in self.bot.dispatcher.groups and handler in self.bot.dispatcher.groups[group]:
            self.bot.dispatcher.groups[group].remove(handler)
            log.info(f'从group={group}移除handler,剩余handler数量:{len(self.bot.dispatcher.groups[group])}')

    def add_keyword_mode_handler(
            self,
            chat_id,
            callback_query: CallbackQuery,
            callback_prompt: Callable,
            enable: bool
    ):
        """添加或移除关键词输入模式的handler,按chat_id隔离以避免多用户互相串扰。"""
        if enable:
            # 同一用户若已有输入模式,先清退其旧handler,避免堆积。
            old = self.keyword_handlers.pop(chat_id, None)
            if old:
                self.remove_handler(old, group=-1)
            keyword_handler = MessageHandler(
                partial(self.handle_keyword_input, chat_id, callback_query, callback_prompt),
                filters=self.auth_filter & pyrogram.filters.chat(chat_id) & pyrogram.filters.text & (
                    lambda client, m: isinstance(
                        m,
                        pyrogram.types.Message
                    ) and m.text and m.text.strip() and not m.text.startswith(
                        '/') and not m.text.startswith('http')
                )
            )
            self.keyword_handlers[chat_id] = keyword_handler
            self.add_handler(keyword_handler, group=-1)
            log.info(f'用户输入模式已打开,Handler:"{keyword_handler}"。')
        else:
            old = self.keyword_handlers.pop(chat_id, None)
            if old:
                self.remove_handler(old, group=-1)
                log.info('用户输入模式已关闭,Handler已清空。')

    def add_command_mode_handler(
            self,
            chat_id,
            callback_query: CallbackQuery,
            command: str,
            enable: bool
    ):
        """添加或移除命令输入模式的handler,按chat_id隔离以避免多用户互相串扰。"""
        if enable:
            # 同一用户若已有输入模式,先清退其旧handler,避免堆积。
            old = self.command_handlers.pop(chat_id, None)
            if old:
                self.remove_handler(old, group=-1)
            self.pending_tasks[chat_id] = {'command': command, 'step': 0, 'data': {}}
            command_handler = MessageHandler(
                partial(self.handle_command_input, chat_id, callback_query, command),
                filters=self.auth_filter & pyrogram.filters.chat(chat_id) & pyrogram.filters.text & (
                    lambda client, m: isinstance(
                        m,
                        pyrogram.types.Message
                    ) and m.text and m.text.strip() and not m.text.startswith(self.COMMAND_PREFIX_BLACKLIST)
                )
            )
            self.command_handlers[chat_id] = command_handler
            self.add_handler(command_handler, group=-1)
            log.info(f'命令输入模式已打开,Handler:"{command_handler}"。')
        else:
            old = self.command_handlers.pop(chat_id, None)
            if old:
                self.remove_handler(old, group=-1)
                log.info('命令输入模式已关闭,Handler已清空。')
            self.pending_tasks.pop(chat_id, None)

    async def handle_command_input(
            self,
            chat_id,
            callback_query: CallbackQuery,
            command: str,
            _client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> None:
        """多步引导:按命令定义的步骤收集用户输入,收集完成后组装命令交给既有流程。"""
        pending = self.pending_tasks.get(chat_id)
        if not pending:
            self.add_command_mode_handler(
                chat_id=chat_id, callback_query=callback_query, command=command, enable=False)
            return None
        # 以pending中记录的最新命令为准进行路由,而非handler绑定时的旧命令参数,防止残留handler误创建任务。
        command = pending['command']
        steps = self.COMMAND_STEPS.get(command, ())
        if not steps:
            self.add_command_mode_handler(
                chat_id=chat_id, callback_query=callback_query, command=command, enable=False)
            return None
        step_idx = pending['step']
        field = steps[step_idx][0]
        text: str = message.text.strip()
        # 按字段类型校验用户输入,不合法则要求重新输入当前步骤。
        if field in (BotStepKeyword.LINK, BotStepKeyword.ORIGIN, BotStepKeyword.TARGET):
            if not text.startswith('http'):
                await _client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text='❌请输入有效的链接,请重新发送。',
                    link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                )
                return None
        elif field in ('start_id', 'end_id'):
            if not text.isdigit():
                await _client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text='❌请输入数字ID,请重新发送。',
                    link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                )
                return None
        pending['data'][field] = str(text)
        pending['step'] += 1
        # 还有后续步骤,防group=0的链接/错误handler干扰后,发送下一步提示并继续等待。
        if pending['step'] < len(steps):
            self.command_processed.add(message.id)
            next_hint = steps[pending['step']][1]
            await _client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=next_hint,
                reply_markup=pyrogram.types.ForceReply(),
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            return None
        # 所有步骤收集完成,组装命令交给既有流程,并防group=0重复触发。
        data = pending['data']
        if command == BotCommandText.DOWNLOAD[0]:
            await self.get_download_link_from_bot(client=_client, message=message)
        elif command == BotCommandText.DOWNLOAD_CHAT[0]:
            new_message = copy.copy(message)
            new_message.text = f'/{BotCommandText.DOWNLOAD_CHAT[0]} {data[BotStepKeyword.LINK]}'
            await self.get_download_chat_link_from_bot(client=self.bot, message=new_message)
        elif command in (BotCommandText.UPLOAD[0], BotCommandText.UPLOAD_R[0]):
            cmd = f'/{BotCommandText.UPLOAD[0]}' if command == BotCommandText.UPLOAD[
                0] else f'/{BotCommandText.UPLOAD_R[0]}'
            new_message = copy.copy(message)
            new_message.text = f'{cmd} {data[BotStepKeyword.PATH]} {data[BotStepKeyword.TARGET]}'
            await self.get_upload_link_from_bot(client=self.bot, message=new_message)
        elif command == BotCommandText.FORWARD[0]:
            new_message = copy.copy(message)
            new_message.text = f'/{BotCommandText.FORWARD[0]} {data[BotStepKeyword.ORIGIN]} {data[BotStepKeyword.TARGET]} {data[BotStepKeyword.START_ID]} {data[BotStepKeyword.END_ID]}'
            await self.get_forward_link_from_bot(client=self.bot, message=new_message)
        elif command == BotCommandText.LISTEN_DOWNLOAD[0]:
            new_message = copy.copy(message)
            new_message.text = f'/{BotCommandText.LISTEN_DOWNLOAD[0]} {data[BotStepKeyword.ORIGIN]}'
            await self.on_listen(client=self.bot, message=new_message)
        elif command == BotCommandText.LISTEN_FORWARD[0]:
            new_message = copy.copy(message)
            new_message.text = f'/{BotCommandText.LISTEN_FORWARD[0]} {data[BotStepKeyword.ORIGIN]} {data[BotStepKeyword.TARGET]}'
            await self.on_listen(client=self.bot, message=new_message)
        self.command_processed.add(message.id)
        self.add_command_mode_handler(
            chat_id=chat_id, callback_query=callback_query, command=command, enable=False)
        self.pending_tasks.pop(chat_id, None)

    async def process_error_message(self, client: pyrogram.Client, message: pyrogram.types.Message) -> None:
        if message.from_user.id in self.keyword_handlers:
            return
        if message.from_user.id in self.auth_handlers:
            return
        if message.id in self.command_processed:
            return
        await self.help(client, message)
        await client.send_message(
            chat_id=message.from_user.id,
            reply_parameters=ReplyParameters(message_id=message.id),
            text='⚠️⚠️⚠️未知命令⚠️⚠️⚠️\n请查看帮助后重试。',
            link_preview_options=Bot.LINK_PREVIEW_OPTIONS
        )

    async def handle_keyword_input(
            self,
            chat_id: Union[str, int],
            callback_query: CallbackQuery,
            callback_prompt: Callable,
            _client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> None:
        """处理用户输入的关键词。"""

        text: str = message.text.strip()

        if not text:
            return None

        # 以空格分隔关键词。
        keywords = [kw.strip() for kw in text.split() if kw.strip()]
        # chat_id为打开输入模式的用户id(keyword输入模式已按用户隔离),
        # 需还原其正在引导的频道id,才能正确写回download_chat_filter。
        channel_id = self.download_chat_active.get(chat_id)
        if channel_id is None:
            return None
        for keyword in keywords:
            if keyword in self.adding_keywords.get(chat_id, []):
                try:
                    await callback_query.message.edit_text(
                        text=f'🚛`{keyword}`已被添加,选择处理方式后继续。',
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    BotButton.DROP,
                                    callback_data=f'{BotCallbackText.DROP_KEYWORD}_{keyword}'
                                ),
                                InlineKeyboardButton(
                                    BotButton.IGNORE,
                                    callback_data=f'{BotCallbackText.IGNORE_KEYWORD}_{keyword}'
                                )
                            ]
                        ]
                        )
                    )
                    return None
                except MessageNotModified:
                    pass
            else:
                self.download_chat_filter[channel_id]['keyword'][keyword] = True
                self.adding_keywords.setdefault(chat_id, []).append(keyword)  # 添加到正在添加的关键词列表。
                try:
                    await callback_query.message.edit_text(
                        text=callback_prompt(),
                        reply_markup=KeyboardButton.keyword_filter_button(self.adding_keywords.get(chat_id, []))
                    )
                except MessageNotModified:
                    pass

    @staticmethod
    async def check_download_range(
            start_id: int,
            end_id: int,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> bool:
        if end_id != -1:
            if start_id > end_id:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text='❌❌❌起始ID>结束ID❌❌❌'
                )
                return False
        if start_id == -1 or end_id == -1:
            text: str = '未知错误'
            if start_id == -1:
                text: str = '没有指定起始ID'
            if end_id == -1:
                text: str = '没有指定结束ID'
            if start_id == end_id:
                text: str = '没有指定起始ID和结束ID'
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=f'❌❌❌{text}❌❌❌'
            )
            return False
        return True

    async def get_download_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            with_upload: Union[dict, None] = None,
            owner: Union[int, None] = None
    ) -> Union[Dict[str, Union[set, pyrogram.types.Message]], None]:
        if message.id in self.command_processed:
            return None
        requester: int = owner if owner is not None else message.from_user.id
        text: str = message.text
        if text == '/download':
            await client.send_message(
                chat_id=requester,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⚠️⚠️⚠️请提供下载链接⚠️⚠️⚠️语法:\n`/download https://t.me/x/x`',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
        elif text.startswith('https://t.me/'):
            if text[len('https://t.me/'):].count('/') >= 1:
                text = f'/download {text}'
                return await self.parse_download_command(text, client, message, requester)
            else:
                await client.send_message(
                    chat_id=requester,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'⬇️⬇️⬇️请使用以下命令分配下载任务⬇️⬇️⬇️\n`/download https://t.me/x/x`',
                    link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                )
        elif len(text) <= 25 or text == '/download https://t.me/x/x' or text.endswith('.txt'):
            await self.help(client, message)
            await client.send_message(
                chat_id=requester,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌链接错误❌❌❌\n请查看帮助后重试。',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
        else:
            return await self.parse_download_command(text, client, message, requester)

    async def parse_download_command(
            self,
            text: str,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            requester: Union[int, None] = None
    ) -> Union[Dict[str, Union[set, pyrogram.types.Message]], None]:
        """解析/download命令(含裸链规整后的),返回链接信息。"""
        link: list = text.split()
        link.remove('/download') if '/download' in link else None
        link = [_.rstrip('/') for _ in link]
        if (
                safe_index(link, 0, '').startswith('https://t.me/') and
                not safe_index(link, 1, 'https://t.me/').startswith('https://t.me/') and
                len(link) == 3
        ):
            # v1.5.1 支持范围下载。
            start_id: int = int(safe_index(link, 1, -1))
            end_id: int = int(safe_index(link, 2, -1))
            if not await self.check_download_range(
                    start_id=start_id,
                    end_id=end_id,
                    client=client,
                    message=message
            ):
                return None
            right_link: set = set()
            invalid_link: set = set()
            for i in range(start_id, end_id + 1):
                right_link.add(f'{link[0]}/{i}?single')  # v1.6.7 修复范围下载链接为组时,重复下载问题。
        else:
            right_link: set = set([_ for _ in link if _.startswith('https://t.me/')])
            invalid_link: set = set([_ for _ in link if not _.startswith('https://t.me/')])
        if right_link:
            return {
                'right_link': right_link,
                'invalid_link': invalid_link,
                'last_bot_message': await self.safe_process_message(
                    client=client, message=message, requester=requester,
                    text=self.update_text(
                        right_link=right_link,
                        invalid_link=invalid_link
                    )
                )
            }
        else:
            return None

    async def get_download_chat_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
    ):
        text: str = message.text
        if text == '/download_chat':
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⚠️⚠️⚠️请提供下载链接⚠️⚠️⚠️语法:\n`/download_chat https://t.me/x/x`',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            return None
        command = text.split()
        if len(command) != 2:
            await self.help(client, message)
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌命令语法错误❌❌❌\n请查看帮助后重试。',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            return None
        chat_link = command[1]
        try:
            meta = await parse_link(client=self.user, link=chat_link)
        except ValueError:
            meta = None
        if not isinstance(meta, dict):
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌找不到频道❌❌❌',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            return None
        chat_id = meta.get('chat_id')
        if not chat_id:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌无法获取频道名❌❌❌',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            return None
        if chat_id in self.download_chat_filter:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⚠️⚠️⚠️该频道已在下载中⚠️⚠️⚠️\n'
                     f'{chat_link}',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            return None
        BotCallbackText.DOWNLOAD_CHAT_ID = str(chat_id)
        self.download_chat_filter[chat_id] = {
            'date_range':
                {
                    'start_date': None,
                    'end_date': None,
                    'adjust_step': 1
                },
            'download_type':
                {
                    'video': True,
                    'photo': True,
                    'document': True,
                    'audio': True,
                    'voice': True,
                    'animation': True,
                    'video_note': True,
                    'live_photo': True
                },
            'keyword': {},
            'title': {},
            'comment': False
        }
        self.download_chat_active[message.from_user.id] = chat_id
        log.info(f'"{chat_id}"已添加至:{self.download_chat_filter}。')
        format_dtype = ','.join([_t(_) for _ in DownloadType()])
        include_comment = self.download_chat_filter[chat_id]['comment']
        comment: str = '开' if include_comment else '关'
        await client.send_message(
            chat_id=message.from_user.id,
            reply_parameters=ReplyParameters(message_id=message.id),
            text=f'💬下载频道:`{chat_id}`\n'
                 f'⏮️当前选择的起始日期为:未定义\n'
                 f'⏭️当前选择的结束日期为:未定义\n'
                 f'📝当前选择的下载类型为:{format_dtype}\n'
                 f'🔑当前匹配的关键词为:未定义\n'
                 f'👥包含评论区:{comment}',
            reply_markup=KeyboardButton.download_chat_filter_button(include_comment),
            link_preview_options=Bot.LINK_PREVIEW_OPTIONS
        )

    @staticmethod
    async def safe_process_message(
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            text: list, last_message_id: int = -1,
            reply_markup: Union[pyrogram.types.InlineKeyboardMarkup, None] = None,
            requester: Union[int, None] = None
    ) -> pyrogram.types.Message:
        chat_id = requester if requester is not None else message.from_user.id
        if len(text) == 1 and last_message_id != -1:
            last_bot_message = await client.edit_message_text(
                chat_id=chat_id,
                message_id=last_message_id,
                text=text[0],
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS,
                reply_markup=reply_markup
            )
            return last_bot_message

        last_bot_messages: list = []
        for t in text:
            last_bot_message: pyrogram.types.Message = await client.send_message(
                chat_id=chat_id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=t, link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            if last_bot_message not in last_bot_messages:
                last_bot_messages.append(last_bot_message)
        return last_bot_messages[-1]

    @staticmethod
    def menu_keyboard(level: str = 'main', is_authorized: bool = False, is_root: bool = False) -> InlineKeyboardMarkup:
        """按层级返回内联键盘:main为分组主菜单,download/listen/upload/auth为二级子菜单。"""
        config: dict = rc.cached_config()
        if level == 'download':
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(BotButton.CMD_DOWNLOAD, callback_data=BotCallbackText.COMMAND_DOWNLOAD),
                    InlineKeyboardButton(BotButton.CMD_DOWNLOAD_CHAT,
                                         callback_data=BotCallbackText.COMMAND_DOWNLOAD_CHAT)
                ],
                [
                    InlineKeyboardButton(BotButton.MENU_BACK, callback_data=BotCallbackText.MENU_BACK)
                ]
            ])
        if level == 'listen':
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(BotButton.LISTEN_DOWNLOAD_BTN,
                                         callback_data=BotCallbackText.LISTEN_DOWNLOAD_BTN),
                    InlineKeyboardButton(BotButton.LISTEN_FORWARD_BTN, callback_data=BotCallbackText.LISTEN_FORWARD_BTN)
                ],
                [
                    InlineKeyboardButton(BotButton.MENU_BACK, callback_data=BotCallbackText.MENU_BACK)
                ]
            ])
        if level == 'upload':
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(BotButton.CMD_UPLOAD, callback_data=BotCallbackText.COMMAND_UPLOAD),
                    InlineKeyboardButton(BotButton.CMD_UPLOAD_R, callback_data=BotCallbackText.COMMAND_UPLOAD_R)
                ],
                [
                    InlineKeyboardButton(BotButton.MENU_BACK, callback_data=BotCallbackText.MENU_BACK)
                ]
            ])
        if level == 'auth':
            return InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(BotButton.AUTH, callback_data=BotCallbackText.AUTH),
                    InlineKeyboardButton(BotButton.LOOKUP_AUTH_INFO, callback_data=BotCallbackText.LOOKUP_AUTH_INFO)
                ],
                [
                    InlineKeyboardButton(BotButton.MENU_BACK, callback_data=BotCallbackText.MENU_BACK)
                ]
            ])
        # 主菜单:下载/上传/转发/监听对任意授权用户可见,授权管理仅root可见,其余入口始终展示。
        feature_rows = [
            [
                InlineKeyboardButton(BotButton.MENU_DOWNLOAD, callback_data=BotCallbackText.MENU_DOWNLOAD),
                InlineKeyboardButton(BotButton.MENU_UPLOAD, callback_data=BotCallbackText.MENU_UPLOAD)
            ],
            [
                InlineKeyboardButton(BotButton.CMD_FORWARD, callback_data=BotCallbackText.COMMAND_FORWARD),
                InlineKeyboardButton(BotButton.MENU_LISTEN, callback_data=BotCallbackText.MENU_LISTEN)
            ]
        ] if is_authorized else []
        auth_row = [
            [
                InlineKeyboardButton(BotButton.AUTH_MENU, callback_data=BotCallbackText.MENU_AUTH)
            ]
        ] if is_root else []
        return InlineKeyboardMarkup(
            feature_rows + auth_row + [
                [
                    InlineKeyboardButton(BotButton.GITHUB, url=config.get('github', rc.DEFAULT_GITHUB) + '/releases'),
                    InlineKeyboardButton(BotButton.SUBSCRIBE_CHANNEL,
                                         url=config.get('subscribe_channel', rc.DEFAULT_SUBSCRIBE_CHANNEL))
                ],
                [
                    InlineKeyboardButton(BotButton.VIDEO_TUTORIAL,
                                         url=config.get('video_tutorial', rc.DEFAULT_VIDEO_TUTORIAL)),
                    InlineKeyboardButton(BotButton.PAY, callback_data=BotCallbackText.PAY)
                ],
                [InlineKeyboardButton(BotButton.SETTING, callback_data=BotCallbackText.SETTING)]
            ]
        )

    async def help(
            self,
            client: Union[pyrogram.Client, None] = None,
            message: Union[pyrogram.types.Message, None] = None,
            user_id: Union[int, None] = None
    ) -> Union[None, dict]:  # client与message都为None时,返回keyboard与text。
        web = getattr(self, 'web', None)  # 网页面板实例,用于展示认证信息。
        web_auth: str = ''
        more_feature: bool = False
        if user_id is not None:
            uid = user_id
        elif message and message.from_user:
            uid = message.from_user.id
        else:
            uid = None
        if uid is None or not self.root or uid == self.root[0]:
            more_feature = True
        if web is not None:
            web_auth = (
                f'🌐 Web配置:\n'
                f'🔌 端口: {web.port}\n'
                f'👤 账号: ||{web.username}||\n'
                f'🔑 密码: ||{web.password}||\n'
                f'🔗 链接: {web.protocol}://{web.LOCAL_IP}:{web.port}\n\n'
            )
        config: dict = rc.cached_config()
        update_version: str = check_update(  # 远程版本更高时返回该版本号,用于提示可更新。
            remote_version=config.get('version', __version__),
            local_version=__version__
        )
        version: str = f'{VERSION_SEMVER}({update_version}⬆)' if update_version else VERSION_SEMVER
        keyboard = self.menu_keyboard(
            'main',
            is_authorized=(uid is None) or (not self.root) or (uid in self.root),
            is_root=(uid is None) or (not self.root) or (uid == self.root[0])
        )

        text = (
            f'`\n💎 {SOFTWARE_SHORT_NAME} {version} 💎\n'
            f'©️ {__copyright__.replace(" <https://github.com/Gentlesprite>", ".")}\n'
            f'📖 Licensed under the terms of the {__license__}.`\n\n'
            f'🎮️ 可用命令:\n'
            f'🛎️ {BotCommandText.with_description(BotCommandText.HELP)}\n'
            f'📁 {BotCommandText.with_description(BotCommandText.DOWNLOAD)}\n'
            f'📝 {BotCommandText.with_description(BotCommandText.TABLE)}\n'
            f'↗️ {BotCommandText.with_description(BotCommandText.FORWARD)}\n'
            f'❌ {BotCommandText.with_description(BotCommandText.EXIT)}\n'
            f'🕵️ {BotCommandText.with_description(BotCommandText.LISTEN_DOWNLOAD)}\n'
            f'📲 {BotCommandText.with_description(BotCommandText.LISTEN_FORWARD)}\n'
            f'🔍 {BotCommandText.with_description(BotCommandText.LISTEN_INFO)}\n'
            f'📤 {BotCommandText.with_description(BotCommandText.UPLOAD)}\n'
            f'🌳 {BotCommandText.with_description(BotCommandText.UPLOAD_R)}\n'
            f'💬 {BotCommandText.with_description(BotCommandText.DOWNLOAD_CHAT)}\n'
            f'{"🔐 " + BotCommandText.with_description(BotCommandText.AUTH) + "\n\n" if more_feature else "\n"}'
            f'{web_auth}'
            f'{"✨ 其他功能:\n📨 转发`视频`、`图片`、`音频`、`语音`、`GIF`、`文档`、`视频笔记`、`实况图片`类型的消息给我,即可创建下载任务。\n" if more_feature else "\n"}'
        )
        if not all([client, message]):
            return {
                'keyboard': keyboard,
                'text': text
            }
        await client.send_message(
            chat_id=message.from_user.id,
            text=text,
            link_preview_options=Bot.LINK_PREVIEW_OPTIONS,
            reply_markup=keyboard
        )

    async def start(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        await self.help(client, message)

    @staticmethod
    async def callback_data(client: pyrogram.Client, callback_query: CallbackQuery) -> Union[str, None]:
        await callback_query.answer()
        data = callback_query.data
        if not data:
            return None
        if isinstance(data, str):
            return data

    @staticmethod
    async def table(
            client: Union[pyrogram.Client, None] = None,
            message: Union[pyrogram.types.Message, None] = None
    ) -> Union[None, dict]:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        BotButton.LINK_TABLE,
                        callback_data=BotCallbackText.LINK_TABLE
                    ),
                    InlineKeyboardButton(
                        BotButton.COUNT_TABLE,
                        callback_data=BotCallbackText.COUNT_TABLE
                    )
                ],
                [
                    InlineKeyboardButton(
                        BotButton.UPLOAD_TABLE,
                        callback_data=BotCallbackText.UPLOAD_TABLE
                    )
                ],
                [
                    InlineKeyboardButton(
                        BotButton.HELP_PAGE,
                        callback_data=BotCallbackText.BACK_HELP
                    )
                ]
            ]
        )
        text: str = '🧐🧐🧐请选择输出「统计表」的类型:'
        if not all([client, message]):
            return {
                'keyboard': keyboard,
                'text': text
            }
        await client.send_message(
            chat_id=message.from_user.id,
            text=text,
            link_preview_options=Bot.LINK_PREVIEW_OPTIONS,
            reply_markup=keyboard
        )

    async def get_forward_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> Union[Dict[str, Union[list, str]], None]:

        text: str = message.text
        args: list = text.split(maxsplit=5)
        if text == '/forward':
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌命令语法无效❌❌❌\n'
                     '⬇️⬇️⬇️语法如下⬇️⬇️⬇️\n'
                     '`/forward 原始频道 目标频道 起始ID 结束ID`\n'
                     '⬇️⬇️⬇️请使用⬇️⬇️⬇️\n'
                     '`/forward https://t.me/A https://t.me/B 1 100`\n'
            )
            return None
        try:
            start_id: int = int(safe_index(args, 3, -1))
            end_id: int = int(safe_index(args, 4, -1))
            if not await self.check_download_range(
                    start_id=start_id,
                    end_id=end_id,
                    client=client,
                    message=message):
                return None
        except Exception as e:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=f'❌❌❌命令错误❌❌❌\n{e}\n请使用`/forward https://t.me/A https://t.me/B 1 100`'
            )
            return None
        return {
            'origin_link': args[1],
            'target_link': args[2],
            'message_range': [start_id, end_id]
        }

    async def get_upload_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            delete: bool = False,
            save_directory: str = None,
            recursion: bool = False,
            valid_link_cache: dict = None
    ):
        if not recursion:
            valid_link_cache = {}

        text: str = message.text
        if text == '/upload' or text == '/upload_r':
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⚠️⚠️⚠️请提供参数⚠️⚠️⚠️语法:\n`/upload 本地文件 目标频道`或`/upload_r 本地文件夹 目标频道`',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            return None

        if text.startswith('/upload '):
            remaining_text = text[len('/upload '):].strip()
            command = '/upload'
        elif text.startswith('/upload_r '):
            remaining_text = text[len('/upload_r '):].strip()
            command = '/upload_r'
        else:
            return None

        parts = remaining_text.rsplit(maxsplit=1)

        if len(parts) == 2:
            file_path = parts[0]  # 文件名部分（可能包含空格）。
            target_link = parts[1]  # URL部分。
            if not recursion:
                if target_link not in valid_link_cache:
                    valid_link_cache[target_link] = await get_valid_chat_id(
                        link=target_link,
                        user_client=self.user,
                        bot_client=self.bot,
                        bot_message=message,
                        error_msg=f'⬇️⬇️⬇️目标频道不存在⬇️⬇️⬇️\n{target_link}'
                    )
                if not valid_link_cache[target_link]:
                    return None
            if os.path.isdir(file_path):
                upload_folder = []
                if command == f'/{BotCommandText.UPLOAD_R[0]}':
                    upload_files = [os.path.join(root, filename) for root, dirs, files in os.walk(file_path) for
                                    filename in files]
                else:
                    upload_files = safe_scan_directory_file(file_path)
                for file_name in upload_files:
                    new_message = copy.copy(message)
                    new_message.text = f'/{BotCommandText.UPLOAD[0]} {os.path.join(file_path, file_name)} {target_link}'
                    upload_folder.append(
                        self.get_upload_link_from_bot(
                            client=client,
                            message=new_message,
                            delete=delete,
                            save_directory=save_directory,
                            recursion=True,
                            valid_link_cache=valid_link_cache
                        )
                    )
                if upload_folder:
                    await client.send_message(
                        chat_id=message.from_user.id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        text=f'📤📤📤上传任务已创建,请耐心等待📤📤📤\n`{file_path}`',
                        link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                    )
                    await asyncio.gather(*upload_folder)
                else:
                    await client.send_message(
                        chat_id=message.from_user.id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        text=f'⚠️⚠️⚠️文件夹为空⚠️⚠️⚠️\n`{file_path}`',
                        link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                    )
                return None
            if not os.path.isfile(file_path):
                log.error(f'上传出错,{_t(KeyWord.REASON)}:"{file_path}"不存在。')
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'⚠️⚠️⚠️上传文件不存在⚠️⚠️⚠️\n`{file_path}`',
                    link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                )
                return None
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'⚠️⚠️⚠️上传文件大小为0⚠️⚠️⚠️\n`{file_path}`',
                    link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                )

            if not is_allow_upload(file_size=file_size, is_premium=self.user.me.is_premium):
                format_file_size: str = MetaData.suitable_units_display(file_size, unit='MiB', mebibyte=True)
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'⚠️⚠️⚠️上传大小超过限制({format_file_size})⚠️⚠️⚠️\n'
                         f'`{file_path}`\n'
                         f'(普通用户2000MiB,会员用户4000MiB)',
                    link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                )
            if not recursion:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'📤📤📤上传任务已创建,请耐心等待📤📤📤\n`{file_path}`',
                    link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                )
            log.info(f'上传文件:"{file_path}",上传频道:"{target_link}"。')
            if target_link.startswith('https://t.me/') or target_link in ('me', 'self'):  # 验证目标链接格式。
                return {
                    'target_link': target_link,
                    'valid_link_cache': valid_link_cache,
                    'upload_task': UploadTask(
                        chat_id=None,
                        file_path=file_path,
                        file_id=self.user.rnd_id(),
                        file_size=os.path.getsize(file_path),
                        file_part=[],
                        status=UploadStatus.PENDING,
                        owner=message.from_user.id
                    )
                }
        if not recursion:
            await self.help(client, message)
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌命令错误❌❌❌\n请查看帮助后重试。',
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS
            )
            return None

    async def exit(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> None:
        last_message = await client.send_message(
            chat_id=message.from_user.id,
            text='🚧已收到退出命令。',
            reply_parameters=ReplyParameters(message_id=message.id),
            link_preview_options=Bot.LINK_PREVIEW_OPTIONS
        )
        self.is_bot_running = False
        await self.safe_edit_message(
            client=client,
            message=message,
            last_message_id=last_message.id,
            text='✅退出成功。'
        )
        raise SystemExit(0)

    async def on_listen(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> Union[Dict[str, list], None]:
        text: str = message.text
        args: list = text.split()
        command: str = args[0]
        links: list = args[1:]
        if text.startswith('/listen_download'):
            if len(args) == 1:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text='❌❌❌命令语法错误❌❌❌\n'
                         '⬇️⬇️⬇️语法如下⬇️⬇️⬇️\n'
                         f'`/listen_download 监听频道1 监听频道2 监听频道n`\n'
                         '⬇️⬇️⬇️请使用⬇️⬇️⬇️\n'
                         f'`/listen_download https://t.me/A https://t.me/B https://t.me/n`\n'
                )
                return None
            last_message: Union[pyrogram.types.Message, str, None] = None
            invalid_links: list = []
            for link in links:
                if not link.startswith('https://t.me/'):
                    invalid_links.append(link)
                    if not last_message:
                        last_message = await client.send_message(
                            chat_id=message.from_user.id,
                            reply_parameters=ReplyParameters(message_id=message.id),
                            text=BotMessage.INVALID
                        )
                    last_message: Union[pyrogram.types.Message, str, None] = await self.safe_edit_message(
                        client=client,
                        message=message,
                        last_message_id=last_message.id,
                        text=safe_message(f'{last_message.text}\n{link}')
                    )
                for meta in self.listen_forward_chat:
                    listen_link, target_link = meta.split()
                    if listen_link == link:
                        invalid_links.append(listen_link)
                        if not last_message:
                            last_message = await client.send_message(
                                chat_id=message.from_user.id,
                                reply_parameters=ReplyParameters(message_id=message.id),
                                text='❌同一频道不能同时存在两个监听\n(您已使用`/listen_forward`创建了以下链接的监听转发)'
                            )
                        last_message: Union[pyrogram.types.Message, str, None] = await self.safe_edit_message(
                            client=client,
                            message=message,
                            last_message_id=last_message.id,
                            text=safe_message(f'{last_message.text}\n{listen_link}')
                        )

            if invalid_links:
                for ivl in invalid_links:
                    if ivl in links:
                        links.remove(ivl)
                if not links:
                    await self.safe_edit_message(
                        client=client,
                        message=message,
                        last_message_id=last_message.id,
                        text='❌❌❌没有找到有效的链接❌❌❌'
                    )
                    return None
            links: list = list(set(links))

        elif text.startswith('/listen_forward'):
            e: str = ''
            len_args: int = len(args)
            if len_args != 3:
                if len_args == 1:
                    e: str = '命令缺少监听频道与转发频道'
                elif len_args == 2:
                    e: str = '命令缺少转发频道'
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'❌❌❌{e}❌❌❌\n'
                         '⬇️⬇️⬇️语法如下⬇️⬇️⬇️\n'
                         f'`/listen_forward 监听频道 转发频道`\n'
                         '⬇️⬇️⬇️请使用⬇️⬇️⬇️\n'
                         f'`/listen_forward https://t.me/A https://t.me/B`\n'
                )
                return None
            listen_link: str = args[1]
            target_link: str = args[2]
            if listen_link in self.listen_download_chat:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text='❌同一频道不能同时存在两个监听\n(您已使用`/listen_download`创建了以下链接的监听下载)\n'
                         f'{listen_link}'
                )
                return None
            if not listen_link.startswith('https://t.me/'):
                e = '监听频道链接错误'
            if not target_link.startswith('https://t.me/'):
                e = '转发频道链接错误'
            if e != '':
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'❌❌❌{e}❌❌❌\n'
                         '⬇️⬇️⬇️语法如下⬇️⬇️⬇️\n'
                         f'`/listen_forward 监听频道 转发频道`\n'
                         '⬇️⬇️⬇️请使用⬇️⬇️⬇️\n'
                         f'`/listen_forward https://t.me/A https://t.me/B`\n'
                )
                return None
        return {'command': command, 'links': links}

    @staticmethod
    async def listen_download(
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        pass

    @staticmethod
    async def listen_forward(
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        pass

    async def cancel_listen(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            link: str,
            command: str,
            from_web: bool = False
    ):
        pass

    async def listen_info(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            target: Union[int, None] = None
    ):
        async def __listen_info(_listen_chat: dict, _text: str):
            last_message = await client.send_message(
                chat_id=target if target is not None else message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS,
                text=_text
            )
            for link in _listen_chat:
                args: list = link.split()
                len_args: int = len(args)
                if len_args == 1:
                    last_message = await self.safe_edit_message(
                        client=client,
                        message=message,
                        last_message_id=last_message.id,
                        text=safe_message(f'{last_message.text}\n{link}')
                    )
                elif len_args == 2:
                    forward_emoji = ' ➡️ '
                    last_message = await self.safe_edit_message(
                        client=client,
                        message=message,
                        last_message_id=last_message.id,
                        text=safe_message(f'{last_message.text}\n{args[0]}{forward_emoji}{args[1]}')
                    )

        if not self.listen_forward_chat and not self.listen_download_chat:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                link_preview_options=Bot.LINK_PREVIEW_OPTIONS,
                text='😲目前没有正在监听的频道。'
            )
        else:
            if self.listen_download_chat:
                await __listen_info(self.listen_download_chat, '🕵️以下链接为已创建的`监听下载`频道:\n')
            if self.listen_forward_chat:
                await __listen_info(self.listen_forward_chat, '📲以下链接为已创建的`监听转发`频道:\n')

    async def auth_user(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> None:
        """热添加或热移除授权用户,支持用户ID或@用户名。"""
        # /auth仅root可用:管理员(由root创建)使用直接提示不可用。
        if not self.root or message.from_user.id != self.root[0]:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⛔该命令仅`root`可用。'
            )
            return None
        text: str = message.text
        args: list = text.split()
        if len(args) == 1:
            # 无参数时展示当前已授权的用户列表。
            await self.show_authorized_users(client=client, message=message)
            return None
        await self.add_authorized_user(client=client, message=message, target=args[1])

    async def add_authorized_user(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            target: str,
            edit_message: Union[pyrogram.types.Message, None] = None
    ) -> None:
        """解析用户ID或@用户名并热添加为授权用户(仅root可调用,此处不校验root)。

        edit_message 非空时(输入模式),结果直接编辑该消息而非另发一条,避免重复提示。
        """
        auth_kb = self.menu_keyboard('auth')
        # 统一通过 pyrogram 校验用户是否存在,支持用户ID或@用户名。
        target = target.lstrip('@')

        async def _respond(text: str, reply_markup=None):
            if edit_message is not None:
                try:
                    await edit_message.edit_text(text=text, reply_markup=reply_markup)
                except MessageNotModified:
                    pass
            else:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=text,
                    reply_markup=reply_markup
                )

        try:
            uid = (await self.user.get_users(
                int(target) if target.isdigit() else target
            )).id
        except Exception as e:
            await _respond(
                text=f'❌无法解析用户"{target}"\n{_t(KeyWord.REASON)}:"{e}"',
                reply_markup=auth_kb if edit_message is not None else None
            )
            return None
        if uid is None:
            return None
        # root用户本身就拥有全部权限,无需重复授权。
        if self.root and uid == self.root[0]:
            await _respond(
                text='👑该用户为`root`,已拥有全部权限,无需授权。',
                reply_markup=auth_kb if edit_message is not None else None
            )
            return None
        # 已存在则展示移除按钮,不再重复添加。
        if uid in self.gc.authorized_users:
            await _respond(
                text=f'👥用户`{uid}`已在授权列表中,是否移除?',
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            text=BotButton.REMOVE_AUTH,
                            callback_data=f'{BotCallbackText.REMOVE_AUTH_USER}_{uid}'
                        ),
                        InlineKeyboardButton(
                            text=BotButton.LOOKUP_AUTH_INFO,
                            callback_data=BotCallbackText.LOOKUP_AUTH_INFO
                        )
                    ]
                ])
            )
            return None
        # 热添加授权用户:实时写入过滤器并持久化到全局配置。
        self.gc.authorized_users.append(uid)
        self.root.append(uid)
        self.gc.config['authorized_users'] = self.gc.authorized_users
        self.gc.save_config(self.gc.config)
        await _respond(
            text=f'✅已添加授权用户`ID`:\n`{uid}`',
            reply_markup=auth_kb if edit_message is not None else KeyboardButton.single_button(
                text=BotButton.LOOKUP_AUTH_INFO,
                callback_data=BotCallbackText.LOOKUP_AUTH_INFO
            )
        )
        log.info(f'已热添加授权用户:{uid},当前授权用户:{self.gc.authorized_users}。')

    def add_auth_mode_handler(
            self,
            chat_id,
            callback_query: CallbackQuery,
            enable: bool
    ):
        """添加或移除"添加授权用户"输入模式的handler,按chat_id隔离以避免多用户互相串扰。"""
        if enable:
            # 同一用户若已有输入模式,先清退其旧handler,避免堆积。
            old = self.auth_handlers.pop(chat_id, None)
            if old:
                self.remove_handler(old, group=-1)
            auth_handler = MessageHandler(
                partial(self.handle_auth_input, chat_id, callback_query),
                filters=self.auth_filter & pyrogram.filters.chat(chat_id) & pyrogram.filters.text & (
                    lambda client, m: isinstance(
                        m,
                        pyrogram.types.Message
                    ) and m.text and m.text.strip() and not m.text.startswith('/')
                )
            )
            self.auth_handlers[chat_id] = auth_handler
            self.add_handler(auth_handler, group=-1)
            log.info(f'添加授权用户输入模式已打开,Handler:"{auth_handler}"。')
        else:
            old = self.auth_handlers.pop(chat_id, None)
            if old:
                self.remove_handler(old, group=-1)
                log.info('添加授权用户输入模式已关闭,Handler已清空。')

    async def handle_auth_input(
            self,
            chat_id,
            callback_query: CallbackQuery,
            _client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> None:
        """处理root在输入模式下发送的待授权用户ID或@用户名。"""
        # 仅root可授权,且只接收发起者自己的输入。
        if not self.root or message.from_user.id != self.root[0] or message.from_user.id != chat_id:
            self.add_auth_mode_handler(chat_id=chat_id, callback_query=callback_query, enable=False)
            return None
        # 处理结果直接编辑"🔐授权用户管理"这条消息(由 add_authorized_user 完成),避免重复提示。
        await self.add_authorized_user(
            client=self.bot,
            message=message,
            target=message.text.strip(),
            edit_message=callback_query.message
        )
        # 处理完毕关闭输入模式。
        self.add_auth_mode_handler(chat_id=chat_id, callback_query=callback_query, enable=False)


    async def show_authorized_users(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            target: Union[int, None] = None,
            edit_message: Union[pyrogram.types.Message, None] = None
    ) -> None:
        """展示当前已授权的额外用户列表。edit_message 非空时(按钮点击)直接编辑该消息。"""
        users = self.gc.authorized_users
        chat_id = target if target is not None else message.from_user.id
        auth_kb = self.menu_keyboard('auth')

        async def _respond(text: str):
            if edit_message is not None:
                try:
                    await edit_message.edit_text(text=text, reply_markup=auth_kb)
                except MessageNotModified:
                    pass
            else:
                await client.send_message(
                    chat_id=chat_id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=text
                )

        if not users:
            await _respond('😲目前没有额外的授权用户,仅`root`可使用机器人。')
            return None
        lines = '\n'.join(str(u) for u in users)
        await _respond(f'👥以下为已授权的用户`ID`:\n`{lines}`')

    async def handle_forwarded_media(
            self,
            user_client: pyrogram.Client,
            user_message: pyrogram.types.Message
    ):
        pass

    async def done_notice(
            self,
            text,
            requester: Union[int, None] = None
    ):
        # 谁创建的任务就通知谁;未指定requester时回退到最近一条消息(兼容旧行为)。
        # 回退仅作兼容:一旦触发即打warning,避免「静默通知错人」难以察觉。
        if self.gc.get_config(BotCallbackText.NOTICE):
            chat_id = requester
            if chat_id is None:
                if self.last_message is not None:
                    chat_id = self.last_message.from_user.id
                    log.warning(
                        'done_notice未指定requester,回退到last_message(chat_id={chat_id}),请为该调用处补充owner以消除回退。')
                else:
                    log.warning('done_notice未指定requester且last_message为空,跳过通知。')
            if self.last_client is not None and chat_id is not None:
                while True:
                    try:
                        await self.last_client.send_message(
                            chat_id=chat_id,
                            text=f'{BotMessage.NOTICE}{text}',
                            link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                        )
                        break
                    except (FloodWait, FloodPremiumWait) as e:
                        amount = e.value
                        console.log(
                            f'[{self.bot.name}]发送消息请求频繁,要求等待{amount}秒后继续运行。',
                            style='#FF4689'
                        )
                        await asyncio.sleep(amount)
                    except Exception as e:
                        log.error(f'无法发送通知,{_t(KeyWord.REASON)}:"{e}"')

    async def start_bot(
            self,
            application,
            user_client_obj: pyrogram.Client,
            bot_client_obj: pyrogram.Client,
    ) -> str:
        """启动机器人。"""
        try:
            self.application = application
            self.bot = bot_client_obj
            self.user = user_client_obj
            root = await self.user.get_me()
            self.root.append(root.id)
            # 将全局配置中的授权用户一并纳入,使其也能操作机器人。
            self.root.extend(
                uid for uid in self.gc.authorized_users
                if isinstance(uid, int) and uid != root.id
            )
            # 基于授权列表(self.root)构建自定义过滤器,实时读取以支持热添加/热移除。
            self.auth_filter = pyrogram.filters.create(
                self.authorized_filter,
                name='AuthorizedUser',
                authorized_ids=self.root
            )
            await bot_client_obj.start()
            await self.bot.set_bot_commands(self.COMMANDS)
            bot = await self.bot.get_me()
            bot_username = getattr(bot, 'username', None)

            self.bot.add_handler(
                MessageHandler(
                    self.start,
                    filters=pyrogram.filters.command(['start']) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.help,
                    filters=pyrogram.filters.command([BotCommandText.HELP[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_link_from_bot,
                    filters=pyrogram.filters.command([BotCommandText.DOWNLOAD[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_chat_link_from_bot,
                    filters=pyrogram.filters.command([BotCommandText.DOWNLOAD_CHAT[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_upload_link_from_bot,
                    filters=pyrogram.filters.command([BotCommandText.UPLOAD[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_upload_link_from_bot,
                    filters=pyrogram.filters.command([BotCommandText.UPLOAD_R[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.table,
                    filters=pyrogram.filters.command([BotCommandText.TABLE[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_forward_link_from_bot,
                    filters=pyrogram.filters.command([BotCommandText.FORWARD[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.exit,
                    filters=pyrogram.filters.command([BotCommandText.EXIT[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.on_listen,
                    filters=pyrogram.filters.command(
                        [BotCommandText.LISTEN_DOWNLOAD[0], BotCommandText.LISTEN_FORWARD[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.listen_info,
                    filters=pyrogram.filters.command([BotCommandText.LISTEN_INFO[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.auth_user,
                    filters=pyrogram.filters.command([BotCommandText.AUTH[0]]) & self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_link_from_bot,
                    # 命令输入模式期间,该chat的链接只交给command_handler引导,避免与下载handler重复触发。
                    filters=pyrogram.filters.regex(r'^https://t.me.*') & self.auth_filter & (
                        lambda client, m: m.chat.id not in self.pending_tasks
                    )
                )
            )
            self.user.add_handler(
                MessageHandler(
                    self.handle_forwarded_media,
                    filters=self.auth_filter & pyrogram.filters.forwarded & pyrogram.filters.chat(
                        bot_username) & (
                                    pyrogram.filters.video
                                    | pyrogram.filters.photo
                                    | pyrogram.filters.audio
                                    | pyrogram.filters.voice
                                    | pyrogram.filters.animation
                                    | pyrogram.filters.document
                                    | pyrogram.filters.video_note
                            )
                )
            )
            self.bot.add_handler(
                CallbackQueryHandler(
                    self.callback_data,
                    filters=self.auth_filter
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.process_error_message,
                    filters=self.auth_filter & ~(
                            pyrogram.filters.video
                            | pyrogram.filters.photo
                            | pyrogram.filters.audio
                            | pyrogram.filters.voice
                            | pyrogram.filters.animation
                            | pyrogram.filters.document
                            | pyrogram.filters.video_note
                    ) & (
                                lambda client, m: m.chat.id not in self.pending_tasks
                            )
                )
            )
            self.is_bot_running: bool = True
            await self.send_message_to_bot(text='/start')
            return f'🤖「机器人」启动成功 ({BotButton.CLOSE_NOTICE if self.gc.config.get(BotCallbackText.NOTICE) else BotButton.OPEN_NOTICE})。'
        except AccessTokenInvalid as e:
            self.is_bot_running: bool = False
            return f'🤖「机器人」启动失败,「bot_token」错误,{_t(KeyWord.REASON)}:"{e}"'
        except Exception as e:
            self.is_bot_running: bool = False
            return f'🤖「机器人」启动失败,{_t(KeyWord.REASON)}:"{e}"'

    async def send_message_to_bot(self, text: str, catch: bool = False):
        try:
            bot_username = getattr(await self.bot.get_me(), 'username', None)
            if bot_username:
                return await self.user.send_message(
                    chat_id=bot_username,
                    text=text,
                    link_preview_options=Bot.LINK_PREVIEW_OPTIONS
                )
        except Exception as e:
            if catch:
                raise Exception(str(e))
            else:
                return e

    @staticmethod
    def update_text(
            right_link: set,
            invalid_link: set
    ) -> list:
        n = '\n'
        right_msg = f'{BotMessage.RIGHT}{n.join(sorted(right_link))}' if right_link else ''
        invalid_msg = f'{BotMessage.INVALID}{n.join(sorted(invalid_link))}{n}(具体原因请前往终端查看报错信息)' if invalid_link else ''
        return safe_message(f'{right_msg}{n}{invalid_msg}')

    async def safe_edit_message(
            self, client: pyrogram.Client,
            message: pyrogram.types.Message,
            last_message_id: int,
            text: Union[str, List[str]],
            reply_markup: Union[pyrogram.types.InlineKeyboardMarkup, None] = None
    ) -> Union[pyrogram.types.Message, None]:
        while True:
            try:
                if isinstance(text, list):
                    last_message: pyrogram.types.Message = await self.safe_process_message(
                        client=client,
                        message=message,
                        last_message_id=last_message_id,
                        text=text,
                        reply_markup=reply_markup
                    )
                    return last_message
                elif isinstance(text, str):
                    await client.edit_message_text(
                        chat_id=message.from_user.id,
                        message_id=last_message_id,
                        text=text,
                        link_preview_options=Bot.LINK_PREVIEW_OPTIONS,
                        reply_markup=reply_markup
                    )
                    return None
            except MessageNotModified:
                return None
            except (FloodWait, FloodPremiumWait) as e:
                amount = e.value
                console.log(
                    f'[{self.bot.name}]编辑消息请求频繁,要求等待{amount}秒后继续运行。',
                    style='#FF4689'
                )
                await asyncio.sleep(amount)
            except Exception:
                raise

    async def send_rich_table(self, message: pyrogram.types.Message, chunks: list) -> None:
        """通过机器人将统计表的 Markdown 分片以富文本消息发送给用户。

        ``chunks`` 为 Markdown 字符串列表:首片编辑原消息(以便键盘挂接),
        其余分片作为新消息发送,规避单条富文本消息的长度上限。
        """
        if self.bot is None or not chunks:
            return None
        chat_id: int = message.chat.id
        first, *rest = chunks
        try:
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message.id,
                rich_message=pyrogram.types.InputRichMessage(markdown=first)
            )
        except Exception as e:
            log.error(f'通过机器人发送统计表(首片)失败,{_t(KeyWord.REASON)}:"{e}"')
        for index, chunk in enumerate(rest, start=2):
            try:
                await self.bot.send_rich_message(
                    chat_id=chat_id,
                    rich_message=pyrogram.types.InputRichMessage(markdown=chunk)
                )
            except Exception as e:
                log.error(f'通过机器人发送统计表(第{index}片)失败,{_t(KeyWord.REASON)}:"{e}"')


class KeyboardButton:
    def __init__(self, callback_query: pyrogram.types.CallbackQuery):
        self.callback_query = callback_query

    async def choice_export_table_button(
            self,
            choice: Union[BotCallbackText, str]
    ) -> None:
        export_callback_data: str = ''
        if choice == BotCallbackText.EXPORT_LINK_TABLE:
            export_callback_data = BotCallbackText.EXPORT_LINK_TABLE
        elif choice == BotCallbackText.EXPORT_COUNT_TABLE:
            export_callback_data = BotCallbackText.EXPORT_COUNT_TABLE
        elif choice == BotCallbackText.EXPORT_UPLOAD_TABLE:
            export_callback_data = BotCallbackText.EXPORT_UPLOAD_TABLE
        try:
            await self.callback_query.message.edit_reply_markup(InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=BotButton.EXPORT_TABLE,
                            callback_data=export_callback_data
                        ),
                        InlineKeyboardButton(
                            text=BotButton.RESELECT,
                            callback_data=BotCallbackText.BACK_TABLE
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BotButton.HELP_PAGE,
                            callback_data=BotCallbackText.BACK_HELP
                        )
                    ]
                ]
            )
            )
        except MessageNotModified:
            pass

    async def toggle_setting_button(
            self,
            global_config: dict,
            user_config: dict
    ) -> None:
        try:
            await self.callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            text=BotButton.CLOSE_NOTICE if global_config.get(
                                BotCallbackText.NOTICE) else BotButton.OPEN_NOTICE,
                            callback_data=BotCallbackText.NOTICE
                        ),
                        InlineKeyboardButton(
                            text=BotButton.EXPORT_TABLE,
                            callback_data=BotCallbackText.EXPORT_TABLE
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BotButton.CLOSE_EXIT_SHUTDOWN if user_config.get(
                                'is_shutdown') else BotButton.OPEN_EXIT_SHUTDOWN,
                            callback_data=BotCallbackText.SHUTDOWN
                        ),
                        InlineKeyboardButton(
                            text=BotButton.FORWARD_SETTING,
                            callback_data=BotCallbackText.FORWARD_SETTING
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BotButton.DOWNLOAD_SETTING,
                            callback_data=BotCallbackText.DOWNLOAD_SETTING
                        ),
                        InlineKeyboardButton(
                            text=BotButton.UPLOAD_SETTING,
                            callback_data=BotCallbackText.UPLOAD_SETTING
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BotButton.HELP_PAGE,
                            callback_data=BotCallbackText.BACK_HELP
                        )
                    ]
                ])
            )
        except MessageNotModified:
            pass
        except Exception as e:
            await self.callback_query.message.reply_text('切换按钮状态失败\n(具体原因请前往终端查看报错信息)')
            log.error(f'切换按钮状态失败,{_t(KeyWord.REASON)}:"{e}"')

    async def toggle_upload_setting_button(
            self,
            global_config: dict
    ):
        try:
            await self.callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=BotButton.CLOSE_UPLOAD_DOWNLOAD if global_config.get('upload').get(
                                    'download_upload') else BotButton.OPEN_UPLOAD_DOWNLOAD,
                                callback_data=BotCallbackText.UPLOAD_DOWNLOAD
                            ),
                            InlineKeyboardButton(
                                text=BotButton.CLOSE_UPLOAD_DOWNLOAD_DELETE if global_config.get('upload').get(
                                    'delete') else BotButton.OPEN_UPLOAD_DOWNLOAD_DELETE,
                                callback_data=BotCallbackText.UPLOAD_DOWNLOAD_DELETE
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.RETURN,
                                callback_data=BotCallbackText.SETTING
                            )
                        ]
                    ]
                )
            )
        except MessageNotModified:
            pass

    async def toggle_download_setting_button(
            self,
            user_config: dict
    ):
        try:
            await self.callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=BotButton.VIDEO_ON if DownloadType.VIDEO in user_config.get(
                                    'download_type') else BotButton.VIDEO_OFF,
                                callback_data=BotCallbackText.TOGGLE_DOWNLOAD_VIDEO
                            ),
                            InlineKeyboardButton(
                                text=BotButton.PHOTO_ON if DownloadType.PHOTO in user_config.get(
                                    'download_type') else BotButton.PHOTO_OFF,
                                callback_data=BotCallbackText.TOGGLE_DOWNLOAD_PHOTO
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.AUDIO_ON if DownloadType.AUDIO in user_config.get(
                                    'download_type') else BotButton.AUDIO_OFF,
                                callback_data=BotCallbackText.TOGGLE_DOWNLOAD_AUDIO
                            ),
                            InlineKeyboardButton(
                                text=BotButton.VOICE_ON if DownloadType.VOICE in user_config.get(
                                    'download_type') else BotButton.VOICE_OFF,
                                callback_data=BotCallbackText.TOGGLE_DOWNLOAD_VOICE
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.ANIMATION_ON if DownloadType.ANIMATION in user_config.get(
                                    'download_type') else BotButton.ANIMATION_OFF,
                                callback_data=BotCallbackText.TOGGLE_DOWNLOAD_ANIMATION
                            ),
                            InlineKeyboardButton(
                                text=BotButton.DOCUMENT_ON if DownloadType.DOCUMENT in user_config.get(
                                    'download_type') else BotButton.DOCUMENT_OFF,
                                callback_data=BotCallbackText.TOGGLE_DOWNLOAD_DOCUMENT
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.VIDEO_NOTE_ON if DownloadType.VIDEO_NOTE in user_config.get(
                                    'download_type') else BotButton.VIDEO_NOTE_OFF,
                                callback_data=BotCallbackText.TOGGLE_DOWNLOAD_VIDEO_NOTE
                            ),
                            InlineKeyboardButton(
                                text=BotButton.LIVE_PHOTO_ON if DownloadType.LIVE_PHOTO in user_config.get(
                                    'download_type') else BotButton.LIVE_PHOTO_OFF,
                                callback_data=BotCallbackText.TOGGLE_DOWNLOAD_LIVE_PHOTO
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.RETURN,
                                callback_data=BotCallbackText.SETTING
                            )
                        ]
                    ]
                )
            )
        except MessageNotModified:
            pass

    async def toggle_forward_setting_button(
            self,
            global_config: dict
    ):
        try:
            await self.callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=BotButton.VIDEO_ON if global_config.get('forward_type').get(
                                    'video') else BotButton.VIDEO_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_VIDEO
                            ),
                            InlineKeyboardButton(
                                text=BotButton.PHOTO_ON if global_config.get('forward_type').get(
                                    'photo') else BotButton.PHOTO_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_PHOTO
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.AUDIO_ON if global_config.get('forward_type').get(
                                    'audio') else BotButton.AUDIO_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_AUDIO
                            ),
                            InlineKeyboardButton(
                                text=BotButton.VOICE_ON if global_config.get('forward_type').get(
                                    'voice') else BotButton.VOICE_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_VOICE
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.ANIMATION_ON if global_config.get('forward_type').get(
                                    'animation') else BotButton.ANIMATION_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_ANIMATION
                            ),
                            InlineKeyboardButton(
                                text=BotButton.DOCUMENT_ON if global_config.get('forward_type').get(
                                    'document') else BotButton.DOCUMENT_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_DOCUMENT
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.TEXT_ON if global_config.get('forward_type').get(
                                    'text') else BotButton.TEXT_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_TEXT
                            ),
                            InlineKeyboardButton(
                                text=BotButton.VIDEO_NOTE_ON if global_config.get('forward_type').get(
                                    'video_note') else BotButton.VIDEO_NOTE_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_VIDEO_NOTE
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.LIVE_PHOTO_ON if global_config.get('forward_type').get(
                                    'live_photo') else BotButton.LIVE_PHOTO_OFF,
                                callback_data=BotCallbackText.TOGGLE_FORWARD_LIVE_PHOTO
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.RETURN,
                                callback_data=BotCallbackText.SETTING
                            )
                        ]
                    ]
                )
            )
        except MessageNotModified:
            pass

    @staticmethod
    def toggle_download_chat_type_filter_button(
            filter_config: dict
    ):
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_ON if
                        filter_config['download_type'][
                            DownloadType.VIDEO] else BotButton.VIDEO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO
                    ),
                    InlineKeyboardButton(
                        text=BotButton.PHOTO_ON if
                        filter_config['download_type'][
                            DownloadType.PHOTO] else BotButton.PHOTO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.AUDIO_ON if
                        filter_config['download_type'][
                            DownloadType.AUDIO] else BotButton.AUDIO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO
                    ),
                    InlineKeyboardButton(
                        text=BotButton.VOICE_ON if
                        filter_config['download_type'][
                            DownloadType.VOICE] else BotButton.VOICE_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.ANIMATION_ON if
                        filter_config['download_type'][
                            DownloadType.ANIMATION] else BotButton.ANIMATION_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION
                    ),
                    InlineKeyboardButton(
                        text=BotButton.DOCUMENT_ON if
                        filter_config['download_type'][
                            DownloadType.DOCUMENT] else BotButton.DOCUMENT_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_NOTE_ON if
                        filter_config['download_type'][
                            DownloadType.VIDEO_NOTE] else BotButton.VIDEO_NOTE_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO_NOTE
                    ),
                    InlineKeyboardButton(
                        text=BotButton.LIVE_PHOTO_ON if
                        filter_config['download_type'][
                            DownloadType.LIVE_PHOTO] else BotButton.LIVE_PHOTO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_LIVE_PHOTO
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_FILTER
                    )
                ]
            ]
        )

    async def toggle_table_button(
            self,
            config: dict,
            choice: Union[str, None] = None
    ) -> None:
        try:
            await self.callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=BotButton.CLOSE_LINK_TABLE if config.get(
                                    'export_table').get('link') else BotButton.OPEN_LINK_TABLE,
                                callback_data=BotCallbackText.TOGGLE_LINK_TABLE
                            ),
                            InlineKeyboardButton(
                                text=BotButton.CLOSE_COUNT_TABLE if config.get(
                                    'export_table').get('count') else BotButton.OPEN_COUNT_TABLE,
                                callback_data=BotCallbackText.TOGGLE_COUNT_TABLE
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.CLOSE_UPLOAD_TABLE if config.get(
                                    'export_table').get('upload') else BotButton.OPEN_UPLOAD_TABLE,
                                callback_data=BotCallbackText.TOGGLE_UPLOAD_TABLE
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.RETURN,
                                callback_data=BotCallbackText.SETTING
                            )
                        ]
                    ]
                )
            )
        except MessageNotModified:
            pass
        except Exception as _e:
            if choice:
                if choice == 'link':
                    prompt: str = '链接'
                elif choice == 'count':
                    prompt: str = '计数'
                elif choice == 'upload':
                    prompt: str = '上传'
                else:
                    prompt: str = ''
                await self.callback_query.message.reply_text(
                    f'设置启用或禁用导出{prompt}统计表失败\n(具体原因请前往终端查看报错信息)'
                )
                log.error(f'设置启用或禁用导出{prompt}统计表失败,{_t(KeyWord.REASON)}:"{_e}"')
            else:
                log.error(f'设置启用或禁用导出统计表失败,{_t(KeyWord.REASON)}:"{_e}"')

    async def back_table_button(self):
        try:
            await self.callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=BotButton.RESELECT,
                                callback_data=BotCallbackText.BACK_TABLE
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=BotButton.HELP_PAGE,
                                callback_data=BotCallbackText.BACK_HELP
                            )
                        ]
                    ]
                ))
        except MessageNotModified:
            pass

    async def task_assign_button(self):
        try:
            await self.callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text=BotButton.TASK_ASSIGN,
                                callback_data=BotCallbackText.NULL
                            )
                        ]
                    ]
                )
            )
        except MessageNotModified:
            pass

    @staticmethod
    def restrict_forward_button():
        return (
            InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            BotButton.DOWNLOAD,
                            callback_data=BotCallbackText.DOWNLOAD
                        ),
                        InlineKeyboardButton(
                            BotButton.DOWNLOAD_UPLOAD,
                            callback_data=BotCallbackText.DOWNLOAD_UPLOAD
                        ),
                    ]
                ]
            )
        )

    @staticmethod
    def single_button(text: str, callback_data: str):
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=text,
                        callback_data=callback_data
                    )
                ]
            ]
        )

    @staticmethod
    def download_chat_filter_button(
            include_comment: bool
    ):
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.DATE_RANGE_SETTING,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER
                    ),
                    InlineKeyboardButton(
                        text=BotButton.DOWNLOAD_DTYPE_SETTING,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_DTYPE_FILTER
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.KEYWORD_FILTER_SETTING,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_KEYWORD_FILTER
                    ),
                    InlineKeyboardButton(
                        text=BotButton.INCLUDE_COMMENT if include_comment else BotButton.IGNORE_COMMENT,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_COMMENT
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.EXECUTE_TASK,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_ID
                    ),
                    InlineKeyboardButton(
                        text=BotButton.CANCEL_TASK,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL
                    )
                ]
            ]
        )

    @staticmethod
    def filter_date_range_button():
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.SELECT_START_DATE,
                        callback_data=BotCallbackText.FILTER_START_DATE
                    ),
                    InlineKeyboardButton(
                        text=BotButton.SELECT_END_DATE,
                        callback_data=BotCallbackText.FILTER_END_DATE
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_FILTER
                    )
                ]
            ]
        )

    async def calendar_keyboard(
            self,
            dtype: Union[CalenderKeyboard, str],
            year: Optional[int] = datetime.datetime.now().year,
            month: Optional[int] = datetime.datetime.now().month
    ):
        keyboard: list = []
        prev_month: int = month - 1 if month > 1 else 12
        prev_year: int = year if month > 1 else year - 1
        next_month: int = month + 1 if month < 12 else 1
        next_year: int = year if month < 12 else year + 1
        if dtype == CalenderKeyboard.START_TIME_BUTTON:
            _dtype = 'start'
        elif dtype == CalenderKeyboard.END_TIME_BUTTON:
            _dtype = 'end'
        else:
            return None
        nav_row = [
            InlineKeyboardButton('◀️', callback_data=f'time_dec_month_{_dtype}_{prev_year}_{prev_month}'),
            InlineKeyboardButton(f'{year}-{month:02d}', callback_data=BotCallbackText.NULL),
            InlineKeyboardButton('▶️', callback_data=f'time_inc_month_{_dtype}_{next_year}_{next_month}')
        ]
        keyboard.append(nav_row)

        week_days = ['一', '二', '三', '四', '五', '六', '日']
        week_row = [InlineKeyboardButton(day, callback_data=BotCallbackText.NULL) for day in week_days]
        keyboard.append(week_row)

        cal = calendar.monthcalendar(year, month)
        for week in cal:
            row = []
            for day in week:
                if day == 0:
                    row.append(InlineKeyboardButton(' ', callback_data=BotCallbackText.NULL))
                else:
                    date_str = f'{year}-{month:02d}-{day:02d} 00:00:00'
                    row.append(InlineKeyboardButton(str(day), callback_data=f'set_specific_time_{_dtype}_{date_str}'))
            keyboard.append(row)

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=BotButton.CONFIRM_AND_RETURN,
                    callback_data=BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER
                ),
                InlineKeyboardButton(
                    text=BotButton.CANCEL_TASK,
                    callback_data=BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL
                )
            ]
        )
        try:
            await self.callback_query.message.edit_reply_markup(InlineKeyboardMarkup(keyboard))
        except MessageNotModified:
            pass

    @staticmethod
    def time_keyboard(
            dtype: Union[CalenderKeyboard, str],
            date: str,
            adjust_step: Optional[int] = 1
    ):
        dt = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
        _dtype = dtype if isinstance(dtype, str) else 'start' if dtype == CalenderKeyboard.START_TIME_BUTTON else 'end'
        hour, minute, second = 'hour', 'minute', 'second'

        def _get_updated_time(field: str, delta: int) -> str:
            new_dt = dt.replace(
                hour=(dt.hour + delta) % 24 if field == hour else dt.hour,
                minute=(dt.minute + delta) % 60 if field == minute else dt.minute,
                second=(dt.second + delta) % 60 if field == second else dt.second
            )
            return new_dt.strftime('%Y-%m-%d %H:%M:%S')

        time_keyboard = [
            [
                InlineKeyboardButton(
                    text=f'步进值:{adjust_step}',
                    callback_data=f'adjust_step_{dtype}_{adjust_step}'
                )
            ],
            [
                InlineKeyboardButton(
                    text='◀️',
                    callback_data=f'set_time_{_dtype}_{_get_updated_time(hour, -adjust_step)}'
                ),
                InlineKeyboardButton(
                    text='时', callback_data=BotCallbackText.NULL
                ),
                InlineKeyboardButton(
                    text='▶️',
                    callback_data=f'set_time_{_dtype}_{_get_updated_time(hour, adjust_step)}'
                )
            ],
            [
                InlineKeyboardButton(
                    text='◀️',
                    callback_data=f'set_time_{_dtype}_{_get_updated_time(minute, -adjust_step)}'
                ),
                InlineKeyboardButton(
                    text='分', callback_data=BotCallbackText.NULL
                ),
                InlineKeyboardButton(
                    text='▶️',
                    callback_data=f'set_time_{_dtype}_{_get_updated_time(minute, adjust_step)}'
                )
            ],
            [
                InlineKeyboardButton(
                    text='◀️',
                    callback_data=f'set_time_{_dtype}_{_get_updated_time(second, -adjust_step)}'
                ),
                InlineKeyboardButton(
                    text='秒', callback_data=BotCallbackText.NULL
                ),
                InlineKeyboardButton(
                    text='▶️',
                    callback_data=f'set_time_{_dtype}_{_get_updated_time(second, adjust_step)}'
                )
            ],
            [
                InlineKeyboardButton(
                    text=BotButton.CONFIRM_AND_RETURN,
                    callback_data=BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER
                ),
                InlineKeyboardButton(
                    text=BotButton.CANCEL_TASK,
                    callback_data=BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL
                )
            ]
        ]

        return InlineKeyboardMarkup(time_keyboard)

    @staticmethod
    def keyword_filter_button(
            adding_keywords: Optional[list] = None
    ):
        """关键词过滤设置按钮。"""
        if adding_keywords:
            keyword_buttons = [
                [
                    InlineKeyboardButton(
                        text=BotButton.INPUT_KEYWORD,
                        callback_data=BotCallbackText.NULL
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.CONFIRM_KEYWORD,
                        callback_data=BotCallbackText.CONFIRM_KEYWORD
                    ),
                    InlineKeyboardButton(
                        text=BotButton.CANCEL,
                        callback_data=BotCallbackText.CANCEL_KEYWORD_INPUT
                    )
                ]
            ]
        else:
            keyword_buttons = [
                [
                    InlineKeyboardButton(
                        text=BotButton.INPUT_KEYWORD,
                        callback_data=BotCallbackText.NULL
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.RETURN,
                        callback_data=BotCallbackText.CANCEL_KEYWORD_INPUT
                    )
                ]
            ]
        return InlineKeyboardMarkup(keyword_buttons)


class CallbackData:
    def __init__(self, data: Union[dict, None] = None):
        self.data: Union[dict, None] = data


@dataclass
class CallbackContext:
    """回调处理上下文,聚合handler需要访问的对象,避免闭包捕获。"""
    downloader: 'TelegramRestrictedMediaDownloader'  # noqa.
    client: pyrogram.Client
    query: CallbackQuery
    kb: KeyboardButton
    data: str


class CallbackHandler(ABC):
    """回调处理器基类,子类声明exact/prefixes匹配集合并实handle。"""
    exact: tuple = ()
    prefixes: tuple = ()

    def match(self, data: str) -> bool:
        return data in self.exact or data.startswith(self.prefixes)

    @abstractmethod
    async def handle(self, ctx: CallbackContext) -> None:
        ...


class NoticeHandler(CallbackHandler):
    exact = (BotCallbackText.NOTICE,)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        kb = ctx.kb
        try:
            downloader.gc.config[BotCallbackText.NOTICE] = not downloader.gc.config.get(BotCallbackText.NOTICE)
            downloader.gc.save_config(downloader.gc.config)
            n_s = '启用' if downloader.gc.config.get(BotCallbackText.NOTICE) else '禁用'
            n_p = f'机器人消息通知已{n_s}。'
            log.info(n_p)
            console.log(n_p, style='#FF4689')
            await kb.toggle_setting_button(global_config=downloader.gc.config, user_config=downloader.app.config)
        except Exception as e:
            await query.message.reply_text('启用或禁用机器人消息通知失败\n(具体原因请前往终端查看报错信息)')
            log.error(f'启用或禁用机器人消息通知失败,{_t(KeyWord.REASON)}:"{e}"')


class PayHandler(CallbackHandler):
    exact = (BotCallbackText.PAY,)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        client = ctx.client
        query = ctx.query
        res = await downloader.send_pay_qr(
            client=client,
            chat_id=query.from_user.id,
            load_name='收款码'
        )
        MetaData.pay()
        if res:
            msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」十分感谢您的支持!'
        else:
            msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」与「对话框」十分感谢您的支持!'
        await query.message.reply_text(msg)


class BackHandler(CallbackHandler):
    exact = (BotCallbackText.BACK_HELP, BotCallbackText.BACK_TABLE)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        if ctx.data == BotCallbackText.BACK_HELP:
            meta = await downloader.help()
            await query.message.edit_text(meta.get('text'))
            await query.message.edit_reply_markup(meta.get('keyboard'))
        elif ctx.data == BotCallbackText.BACK_TABLE:
            meta = await downloader.table()
            await query.message.edit_text(meta.get('text'))
            await query.message.edit_reply_markup(meta.get('keyboard'))


class TaskAssignHandler(CallbackHandler):
    exact = (BotCallbackText.DOWNLOAD, BotCallbackText.DOWNLOAD_UPLOAD)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        kb = ctx.kb
        query = ctx.query
        if not isinstance(downloader.cd.data, dict):
            return None
        meta = downloader.cd.data.copy()
        downloader.cd.data = None
        origin_link = meta.get('origin_link')
        target_link = meta.get('target_link')
        start_id = meta.get('start_id')
        end_id = meta.get('end_id')
        # 谁点击(创建)任务就反馈给谁:以点击者所在的那条消息作为反馈载体。
        feedback = query.message
        feedback.from_user = query.from_user
        feedback.text = f'/download {origin_link} {start_id} {end_id}'
        if ctx.data == BotCallbackText.DOWNLOAD:
            await downloader.get_download_link_from_bot(client=downloader.last_client, message=feedback)
        elif ctx.data == BotCallbackText.DOWNLOAD_UPLOAD:
            await downloader.get_download_link_from_bot(
                client=downloader.last_client,
                message=feedback,
                with_upload={
                    'link': target_link,
                    'file_name': None,
                    'with_delete': downloader.gc.upload_delete,
                    'send_as_media_group': True,
                    'owner': query.from_user.id
                }
            )
        await kb.task_assign_button()


class ListenInfoHandler(CallbackHandler):
    exact = (BotCallbackText.LOOKUP_LISTEN_INFO,)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        # 直接调用底层逻辑并显式指定接收者即点击者,不再用登录账号重发命令。
        try:
            await downloader.listen_info(
                client=downloader.bot,
                message=query.message,
                target=query.from_user.id
            )
        except Exception as e:
            await query.message.reply_text('查看监听信息失败\n(具体原因请前往终端查看报错信息)')
            log.error(f'发送查看监听信息命令失败,{_t(KeyWord.REASON)}:"{e}"')


class LookupAuthInfoHandler(CallbackHandler):
    exact = (BotCallbackText.LOOKUP_AUTH_INFO,)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        # 直接编辑当前消息展示授权用户列表,不再另发一条。
        try:
            await downloader.show_authorized_users(
                client=downloader.bot,
                message=query.message,
                target=query.from_user.id,
                edit_message=query.message
            )
        except Exception as e:
            await query.message.reply_text('查看授权用户失败\n(具体原因请前往终端查看报错信息)')
            log.error(f'发送查看授权用户命令失败,{_t(KeyWord.REASON)}:"{e}"')


class AddAuthHandler(CallbackHandler):
    exact = (BotCallbackText.AUTH,)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        # 仅root可发起授权,非root直接拒绝。
        if not downloader.root or query.from_user.id != downloader.root[0]:
            await query.answer('⛔该操作仅`root`可用。', show_alert=True)
            return None
        # 打开输入模式,提示root发送待授权用户ID或@用户名,并支持取消。
        await query.message.edit_text(
            text='➕请输入要授权的用户`ID`或`@用户名`:',
            reply_markup=KeyboardButton.single_button(
                text='🔙取消',
                callback_data=BotCallbackText.CANCEL_AUTH_INPUT
            )
        )
        downloader.add_auth_mode_handler(
            chat_id=query.from_user.id,
            callback_query=query,
            enable=True
        )


class CancelAuthInputHandler(CallbackHandler):
    exact = (BotCallbackText.CANCEL_AUTH_INPUT,)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        # 关闭添加授权用户输入模式,无论是否root都安全(无该用户handler时为空操作)。
        downloader.add_auth_mode_handler(
            chat_id=query.from_user.id,
            callback_query=query,
            enable=False
        )
        try:
            await query.message.edit_text(
                text='🔐授权用户管理',
                reply_markup=downloader.menu_keyboard('auth')
            )
        except MessageNotModified:
            pass


class ShutdownHandler(CallbackHandler):
    exact = (BotCallbackText.SHUTDOWN,)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        kb = ctx.kb
        try:
            downloader.app.config['is_shutdown'] = not downloader.app.config.get('is_shutdown')
            downloader.app.save_config(downloader.app.config)
            s_s = '启用' if downloader.app.config.get('is_shutdown') else '禁用'
            s_p = f'退出后关机已{s_s}。'
            log.info(s_p)
            console.log(s_p, style='#FF4689')
            await kb.toggle_setting_button(global_config=downloader.gc.config, user_config=downloader.app.config)
        except Exception as e:
            await query.message.reply_text('启用或禁用自动关机失败\n(具体原因请前往终端查看报错信息)')
            log.error(f'启用或禁用自动关机失败,{_t(KeyWord.REASON)}:"{e}"')


class SettingsHandler(CallbackHandler):
    exact = (
        BotCallbackText.SETTING,
        BotCallbackText.EXPORT_TABLE,
        BotCallbackText.DOWNLOAD_SETTING,
        BotCallbackText.UPLOAD_SETTING,
        BotCallbackText.FORWARD_SETTING
    )

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        kb = ctx.kb
        if ctx.data == BotCallbackText.SETTING:
            await kb.toggle_setting_button(global_config=downloader.gc.config, user_config=downloader.app.config)
        elif ctx.data == BotCallbackText.EXPORT_TABLE:
            await kb.toggle_table_button(config=downloader.gc.config)
        elif ctx.data == BotCallbackText.DOWNLOAD_SETTING:
            await kb.toggle_download_setting_button(user_config=downloader.app.config)
        elif ctx.data == BotCallbackText.UPLOAD_SETTING:
            await kb.toggle_upload_setting_button(global_config=downloader.gc.config)
        elif ctx.data == BotCallbackText.FORWARD_SETTING:
            await kb.toggle_forward_setting_button(global_config=downloader.gc.config)


class TableHandler(CallbackHandler):
    exact = (
        BotCallbackText.LINK_TABLE,
        BotCallbackText.COUNT_TABLE,
        BotCallbackText.UPLOAD_TABLE,
        BotCallbackText.TOGGLE_LINK_TABLE,
        BotCallbackText.TOGGLE_COUNT_TABLE,
        BotCallbackText.TOGGLE_UPLOAD_TABLE,
        BotCallbackText.EXPORT_LINK_TABLE,
        BotCallbackText.EXPORT_COUNT_TABLE,
        BotCallbackText.EXPORT_UPLOAD_TABLE
    )

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        kb = ctx.kb
        data = ctx.data
        if data in (BotCallbackText.LINK_TABLE, BotCallbackText.COUNT_TABLE, BotCallbackText.UPLOAD_TABLE):
            prompt_string = ''
            false_text = ''
            choice = ''
            res = None
            if data == BotCallbackText.LINK_TABLE:
                prompt_string = '链接统计表'
                false_text = '😵😵😵没有链接需要统计。'
                choice = BotCallbackText.EXPORT_LINK_TABLE
                res = downloader.app.print_link_table(DownloadTask.TASKS)
            elif data == BotCallbackText.COUNT_TABLE:
                prompt_string = '计数统计表'
                false_text = '😵😵😵当前没有任何下载。'
                choice = BotCallbackText.EXPORT_COUNT_TABLE
                res = downloader.app.print_count_table()
            elif data == BotCallbackText.UPLOAD_TABLE:
                prompt_string = '上传统计表'
                false_text = '😵😵😵当前没有任何上传。'
                choice = BotCallbackText.EXPORT_UPLOAD_TABLE
                res = downloader.app.print_upload_table(UploadTask.TASKS)
            if res:
                await downloader.send_rich_table(message=query.message, chunks=res)
                await kb.choice_export_table_button(choice=choice)
                return None
            elif res is False:
                await query.message.edit_text(false_text)
            else:
                await query.message.edit_text(
                    f'😵‍💫😵‍💫😵‍💫`{prompt_string}`打印失败。\n(具体原因请前往终端查看报错信息)')
            await kb.back_table_button()
        elif data in (
                BotCallbackText.TOGGLE_LINK_TABLE,
                BotCallbackText.TOGGLE_COUNT_TABLE,
                BotCallbackText.TOGGLE_UPLOAD_TABLE
        ):
            if data == BotCallbackText.TOGGLE_LINK_TABLE:
                await self.__toggle_export_table(ctx, 'link')
            elif data == BotCallbackText.TOGGLE_COUNT_TABLE:
                await self.__toggle_export_table(ctx, 'count')
            elif data == BotCallbackText.TOGGLE_UPLOAD_TABLE:
                await self.__toggle_export_table(ctx, 'upload')
        elif data in (
                BotCallbackText.EXPORT_LINK_TABLE,
                BotCallbackText.EXPORT_COUNT_TABLE,
                BotCallbackText.EXPORT_UPLOAD_TABLE
        ):
            prompt_string = ''
            folder = ''
            res = False
            if data == BotCallbackText.EXPORT_LINK_TABLE:
                prompt_string = '链接统计表'
                folder = 'DownloadRecordForm'
                res = downloader.app.print_link_table(link_tasks=DownloadTask.TASKS, export=True, only_export=True)
            elif data == BotCallbackText.EXPORT_COUNT_TABLE:
                prompt_string = '计数统计表'
                folder = 'DownloadRecordForm'
                res = downloader.app.print_count_table(export=True, only_export=True)
            elif data == BotCallbackText.EXPORT_UPLOAD_TABLE:
                prompt_string = '上传统计表'
                folder = 'UploadRecordForm'
                res = downloader.app.print_upload_table(upload_tasks=UploadTask.TASKS, export=True, only_export=True)
            if res:
                folder = 'form' if is_docker() else folder
                await query.message.edit_text(
                    f'✅✅✅`{prompt_string}`已发送至您的「终端」并已「导出」为表格请注意查收。\n(请查看软件目录下`{folder}`文件夹)')
            elif res is False:
                await query.message.edit_text('😵😵😵没有链接需要统计。')
            else:
                await query.message.edit_text(
                    f'😵‍💫😵‍💫😵‍💫`{prompt_string}`导出失败。\n(具体原因请前往终端查看报错信息)')
            await kb.back_table_button()

    @staticmethod
    async def __toggle_export_table(ctx: CallbackContext, table_type: str) -> None:
        downloader = ctx.downloader
        kb = ctx.kb
        export_config = downloader.gc.config.get('export_table')
        export_config[table_type] = not export_config.get(table_type)
        if table_type == 'link':
            t_t = '链接统计表'
        elif table_type == 'count':
            t_t = '计数统计表'
        elif table_type == 'upload':
            t_t = '上传统计表'
        else:
            t_t = '统计表'
        s_t = '启用' if export_config.get(table_type) else '禁用'
        t_p = f'退出后导出{t_t}已{s_t}。'
        console.log(t_p, style='#FF4689')
        log.info(t_p)
        downloader.gc.save_config(downloader.gc.config)
        await kb.toggle_table_button(config=downloader.gc.config, choice=table_type)


class UploadDownloadSettingHandler(CallbackHandler):
    exact = (BotCallbackText.UPLOAD_DOWNLOAD, BotCallbackText.UPLOAD_DOWNLOAD_DELETE)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        kb = ctx.kb
        try:
            if ctx.data == BotCallbackText.UPLOAD_DOWNLOAD:
                self.__toggle_upload_param(downloader, 'download_upload')
            elif ctx.data == BotCallbackText.UPLOAD_DOWNLOAD_DELETE:
                self.__toggle_upload_param(downloader, 'delete')
            downloader.gc.save_config(downloader.gc.config)
            await kb.toggle_upload_setting_button(global_config=downloader.gc.config)
        except Exception as e:
            await query.message.reply_text('上传设置失败\n(具体原因请前往终端查看报错信息)')
            log.error(f'上传设置失败,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def __toggle_upload_param(downloader, param):
        current = downloader.gc.get_nesting_config(
            default_nesting=downloader.gc.default_upload_nesting, param='upload', nesting_param=param)
        downloader.gc.config.get('upload', downloader.gc.default_upload_nesting)[param] = not current
        u_s = '禁用' if current else '开启'
        u_p = ''
        if param == 'delete':
            u_p = f'遇到"受限转发"时,下载后上传并"删除上传完成的本地文件"的行为已{u_s}。'
        elif param == 'download_upload':
            u_p = f'遇到"受限转发"时,下载后上传已{u_s}。'
        console.log(u_p, style='#FF4689')
        log.info(u_p)


class DownloadTypeHandler(CallbackHandler):
    exact = (
        BotCallbackText.TOGGLE_DOWNLOAD_VIDEO,
        BotCallbackText.TOGGLE_DOWNLOAD_PHOTO,
        BotCallbackText.TOGGLE_DOWNLOAD_AUDIO,
        BotCallbackText.TOGGLE_DOWNLOAD_VOICE,
        BotCallbackText.TOGGLE_DOWNLOAD_ANIMATION,
        BotCallbackText.TOGGLE_DOWNLOAD_DOCUMENT,
        BotCallbackText.TOGGLE_DOWNLOAD_VIDEO_NOTE,
        BotCallbackText.TOGGLE_DOWNLOAD_LIVE_PHOTO
    )

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        kb = ctx.kb
        try:
            if ctx.data == BotCallbackText.TOGGLE_DOWNLOAD_VIDEO:
                self.__toggle_download_type(downloader, 'video')
            elif ctx.data == BotCallbackText.TOGGLE_DOWNLOAD_PHOTO:
                self.__toggle_download_type(downloader, 'photo')
            elif ctx.data == BotCallbackText.TOGGLE_DOWNLOAD_AUDIO:
                self.__toggle_download_type(downloader, 'audio')
            elif ctx.data == BotCallbackText.TOGGLE_DOWNLOAD_VOICE:
                self.__toggle_download_type(downloader, 'voice')
            elif ctx.data == BotCallbackText.TOGGLE_DOWNLOAD_ANIMATION:
                self.__toggle_download_type(downloader, 'animation')
            elif ctx.data == BotCallbackText.TOGGLE_DOWNLOAD_DOCUMENT:
                self.__toggle_download_type(downloader, 'document')
            elif ctx.data == BotCallbackText.TOGGLE_DOWNLOAD_VIDEO_NOTE:
                self.__toggle_download_type(downloader, 'video_note')
            elif ctx.data == BotCallbackText.TOGGLE_DOWNLOAD_LIVE_PHOTO:
                self.__toggle_download_type(downloader, 'live_photo')
            downloader.app.config['download_type'] = downloader.app.download_type
            downloader.app.save_config(downloader.app.config)
            await kb.toggle_download_setting_button(downloader.app.config)
        except ValueError:
            await query.message.reply_text('⚠️⚠️⚠️至少需要选择一个下载类型⚠️⚠️⚠️')
        except Exception as e:
            await query.message.reply_text('下载类型设置失败\n(具体原因请前往终端查看报错信息)')
            log.error(f'下载类型设置失败,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def __toggle_download_type(downloader, param):
        if param in downloader.app.download_type:
            if len(downloader.app.download_type) == 1:
                raise ValueError
            f_s = '禁用'
            downloader.app.download_type.remove(param)
        else:
            f_s = '启用'
            downloader.app.download_type.append(param)
        f_p = f'已{f_s}"{param}"类型的下载。'
        console.log(f_p, style='#FF4689')
        log.info(f_p)


class ForwardTypeHandler(CallbackHandler):
    exact = (
        BotCallbackText.TOGGLE_FORWARD_VIDEO,
        BotCallbackText.TOGGLE_FORWARD_PHOTO,
        BotCallbackText.TOGGLE_FORWARD_AUDIO,
        BotCallbackText.TOGGLE_FORWARD_VOICE,
        BotCallbackText.TOGGLE_FORWARD_ANIMATION,
        BotCallbackText.TOGGLE_FORWARD_DOCUMENT,
        BotCallbackText.TOGGLE_FORWARD_TEXT,
        BotCallbackText.TOGGLE_FORWARD_VIDEO_NOTE,
        BotCallbackText.TOGGLE_FORWARD_LIVE_PHOTO
    )

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        kb = ctx.kb
        try:
            if ctx.data == BotCallbackText.TOGGLE_FORWARD_VIDEO:
                self.__toggle_forward_type(downloader, 'video')
            elif ctx.data == BotCallbackText.TOGGLE_FORWARD_PHOTO:
                self.__toggle_forward_type(downloader, 'photo')
            elif ctx.data == BotCallbackText.TOGGLE_FORWARD_AUDIO:
                self.__toggle_forward_type(downloader, 'audio')
            elif ctx.data == BotCallbackText.TOGGLE_FORWARD_VOICE:
                self.__toggle_forward_type(downloader, 'voice')
            elif ctx.data == BotCallbackText.TOGGLE_FORWARD_ANIMATION:
                self.__toggle_forward_type(downloader, 'animation')
            elif ctx.data == BotCallbackText.TOGGLE_FORWARD_DOCUMENT:
                self.__toggle_forward_type(downloader, 'document')
            elif ctx.data == BotCallbackText.TOGGLE_FORWARD_TEXT:
                self.__toggle_forward_type(downloader, 'text')
            elif ctx.data == BotCallbackText.TOGGLE_FORWARD_VIDEO_NOTE:
                self.__toggle_forward_type(downloader, 'video_note')
            elif ctx.data == BotCallbackText.TOGGLE_FORWARD_LIVE_PHOTO:
                self.__toggle_forward_type(downloader, 'live_photo')
            downloader.gc.save_config(downloader.gc.config)
            await kb.toggle_forward_setting_button(downloader.gc.config)
        except ValueError:
            await query.message.reply_text('⚠️⚠️⚠️至少需要选择一个转发类型⚠️⚠️⚠️')
        except Exception as e:
            await query.message.reply_text('转发设置失败\n(具体原因请前往终端查看报错信息)')
            log.error(f'转发设置失败,{_t(KeyWord.REASON)}:"{e}"')

    @staticmethod
    def __toggle_forward_type(downloader, param):
        forward_type = downloader.gc.config.get('forward_type', downloader.gc.default_forward_type_nesting)
        status = downloader.gc.get_nesting_config(
            default_nesting=downloader.gc.default_forward_type_nesting, param='forward_type', nesting_param=param)
        if list(forward_type.values()).count(True) == 1 and status:
            raise ValueError
        forward_type[param] = not status
        f_s = '禁用' if status else '启用'
        f_p = f'已{f_s}"{param}"类型的转发。'
        console.log(f_p, style='#FF4689')
        log.info(f_p)


class AuthUserHandler(CallbackHandler):
    prefixes = (BotCallbackText.REMOVE_AUTH_USER,)

    async def handle(self, ctx: CallbackContext) -> None:
        bot = ctx.downloader
        query = ctx.query
        uid = int(ctx.data.split('_')[-1])
        if uid not in bot.gc.authorized_users:
            await query.message.edit_text(
                text=f'用户`{uid}`已不在授权列表中。',
                reply_markup=bot.menu_keyboard('auth'))
            return None
        # 热移除:实时从过滤器与配置中剔除,并持久化。
        bot.gc.authorized_users.remove(uid)
        root_id = bot.root[0] if bot.root else None
        if uid != root_id and uid in bot.root:
            bot.root.remove(uid)
        bot.gc.config['authorized_users'] = bot.gc.authorized_users
        bot.gc.save_config(bot.gc.config)
        p = f'已热移除授权用户:`{uid}`(立即失效并持久化)。'
        # 移除结果直接显示在text中,并复位为授权用户菜单(添加/移除、查看、返回)。
        await query.message.edit_text(
            text=f'✅用户`{uid}`已移除授权。',
            reply_markup=bot.menu_keyboard('auth'))
        log.info(f'{p}当前授权用户:{bot.gc.authorized_users}')


class ListenRemoveHandler(CallbackHandler):
    exact = (BotCallbackText.REMOVE_LISTEN_FORWARD,)
    prefixes = (BotCallbackText.REMOVE_LISTEN_DOWNLOAD,)

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        data = ctx.data
        if data.startswith(BotCallbackText.REMOVE_LISTEN_DOWNLOAD):
            args = data.split()
            link = args[1]
            downloader.app.client.remove_handler(downloader.listen_download_chat.get(link))
            downloader.listen_download_chat.pop(link)
            downloader.listen_download_owner.pop(link, None)
            await query.message.edit_text(link)
            await query.message.edit_reply_markup(
                KeyboardButton.single_button(text=BotButton.ALREADY_REMOVE, callback_data=BotCallbackText.NULL))
            p = f'已删除监听下载,频道链接:"{link}"。'
            console.log(p, style='#FF4689')
            log.info(f'{p}当前的监听下载信息:{downloader.listen_download_chat}')
            return None
        if not isinstance(downloader.cd.data, dict):
            return None
        meta = downloader.cd.data.copy()
        downloader.cd.data = None
        link = meta.get('link')
        downloader.app.client.remove_handler(downloader.listen_forward_chat.get(link))
        downloader.listen_forward_chat.pop(link)
        downloader.listen_forward_owner.pop(link, None)
        m = link.split()
        joined = ' -> '.join(m)
        p = f'已删除监听转发,转发规则:"{joined}"。'
        await query.message.edit_text(' ➡️ '.join(m))
        await query.message.edit_reply_markup(
            KeyboardButton.single_button(text=BotButton.ALREADY_REMOVE, callback_data=BotCallbackText.NULL))
        console.log(p, style='#FF4689')
        log.info(f'{p}当前的监听转发信息:{downloader.listen_forward_chat}')


class DownloadChatHandler(CallbackHandler):
    exact = (
        BotCallbackText.DOWNLOAD_CHAT_FILTER,
        BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER,
        BotCallbackText.DOWNLOAD_CHAT_DTYPE_FILTER,
        BotCallbackText.DOWNLOAD_CHAT_KEYWORD_FILTER,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO_NOTE,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_LIVE_PHOTO,
        BotCallbackText.TOGGLE_DOWNLOAD_CHAT_COMMENT,
        BotCallbackText.DOWNLOAD_CHAT_ID,
        BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL,
        BotCallbackText.FILTER_START_DATE,
        BotCallbackText.FILTER_END_DATE,
        BotCallbackText.CONFIRM_KEYWORD,
        BotCallbackText.CANCEL_KEYWORD_INPUT
    )
    prefixes = (
        'time_inc_',
        'time_dec_',
        'set_time_',
        'set_specific_time_',
        'adjust_step_',
        'drop_keyword_',
        'ignore_keyword'
    )

    def match(self, data: str) -> bool:
        # DOWNLOAD_CHAT_ID在download_chat启动时被运行时改写为真实chat_id,
        # 因此执行任务的回调数据就是该真实chat_id,必须动态读取此常量来匹配。
        return (
                data in self.exact
                or data.startswith(self.prefixes)
                or data == BotCallbackText.DOWNLOAD_CHAT_ID
        )

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        kb = ctx.kb
        data = ctx.data
        # 根据发起操作的用户还原其正在引导的频道id,按用户隔离,避免全局状态互相串扰。
        user_id = query.from_user.id
        chat_id = downloader.download_chat_active.get(user_id)
        if chat_id is None:
            return None
        if data in (BotCallbackText.DOWNLOAD_CHAT_ID, BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL):
            downloader.adding_keywords.pop(user_id, None)
            downloader.add_keyword_mode_handler(
                chat_id=user_id,
                callback_query=query,
                callback_prompt=partial(self.__filter_prompt, downloader, chat_id),
                enable=False
            )
            if data == BotCallbackText.DOWNLOAD_CHAT_ID:
                await downloader.download_chat(chat_id=chat_id, callback_query=query)
                self.__remove_chat_id(downloader, chat_id)
                downloader.download_chat_active.pop(user_id, None)
            elif data == BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL:
                self.__remove_chat_id(downloader, chat_id)
                downloader.download_chat_active.pop(user_id, None)
                await query.message.edit_text(
                    text=query.message.text,
                    reply_markup=kb.single_button(
                        text=BotButton.TASK_CANCEL,
                        callback_data=BotCallbackText.NULL
                    )
                )
        elif data in (BotCallbackText.DOWNLOAD_CHAT_FILTER, BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER):
            if data == BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER:
                start_time, end_time = self.__get_update_time(downloader, chat_id)
                if not await self.__verification_time(query, start_time, end_time):
                    return None
            await query.message.edit_text(
                text=self.__filter_prompt(downloader, chat_id),
                reply_markup=kb.download_chat_filter_button(
                    downloader.download_chat_filter[chat_id][
                        'comment']) if data == BotCallbackText.DOWNLOAD_CHAT_FILTER else kb.filter_date_range_button()
            )
        elif data in (BotCallbackText.FILTER_START_DATE, BotCallbackText.FILTER_END_DATE):
            dtype = None
            p_s_d = ''
            if data == BotCallbackText.FILTER_START_DATE:
                dtype = CalenderKeyboard.START_TIME_BUTTON
                p_s_d = '起始'
            elif data == BotCallbackText.FILTER_END_DATE:
                dtype = CalenderKeyboard.END_TIME_BUTTON
                p_s_d = '结束'
            await query.message.edit_text(text=f'📅选择{p_s_d}日期:\n{self.__filter_prompt(downloader, chat_id)}')
            await kb.calendar_keyboard(dtype=dtype)
        elif data.startswith('adjust_step_'):
            parts = data.split('_')
            dtype = parts[-2]
            current_step = int(parts[-1])
            step_sequence = [1, 2, 5, 10, 15, 20]
            current_index = step_sequence.index(current_step)
            next_index = (current_index + 1) % len(step_sequence)
            new_step = step_sequence[next_index]
            downloader.download_chat_filter[chat_id]['date_range']['adjust_step'] = new_step
            current_date = datetime.datetime.fromtimestamp(
                downloader.download_chat_filter[chat_id]['date_range'][f'{dtype}_date']
            ).strftime('%Y-%m-%d %H:%M:%S')
            await query.message.edit_reply_markup(
                reply_markup=kb.time_keyboard(
                    dtype=dtype,
                    date=current_date,
                    adjust_step=new_step
                )
            )
        elif data.startswith(('time_inc_', 'time_dec_')):
            parts = data.split('_')
            dtype = None
            if 'start' in data:
                dtype = CalenderKeyboard.START_TIME_BUTTON
            elif 'end' in data:
                dtype = CalenderKeyboard.END_TIME_BUTTON
            if 'month' in data:
                year = int(parts[-2])
                month = int(parts[-1])
                await kb.calendar_keyboard(year=year, month=month, dtype=dtype)
                log.info(f'日期切换为{year}年,{month}月。')
        elif data.startswith(('set_time_', 'set_specific_time_')):
            parts = data.split('_')
            date = parts[-1]
            dtype = parts[-2]
            date_type = ''
            p_s_d = ''
            timestamp = datetime.datetime.timestamp(datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S'))
            if 'start' in data:
                date_type = 'start_date'
                p_s_d = '起始'
            elif 'end' in data:
                date_type = 'end_date'
                p_s_d = '结束'
            downloader.download_chat_filter[chat_id]['date_range'][date_type] = timestamp
            await query.message.edit_text(
                text=f'📅选择{p_s_d}日期:\n{self.__filter_prompt(downloader, chat_id)}',
                reply_markup=kb.time_keyboard(
                    dtype=dtype,
                    date=date,
                    adjust_step=downloader.download_chat_filter[chat_id]['date_range']['adjust_step']
                )
            )
            log.info(
                f'日期设置,起始日期:{self.__get_update_time(downloader, chat_id)[0]},结束日期:{self.__get_update_time(downloader, chat_id)[1]}。')
        elif data.startswith(('drop_keyword_', 'ignore_keyword')):
            if data.startswith('drop_keyword_'):
                parts = data.split('_')
                keyword = parts[-1]
                keyword_dict = downloader.download_chat_filter.get(chat_id, {}).get('keyword', {})
                keyword_dict.pop(keyword)
                downloader.adding_keywords.setdefault(user_id, []).remove(keyword)
            await query.message.edit_text(
                text=self.__filter_prompt(downloader, chat_id),
                reply_markup=KeyboardButton.keyword_filter_button(downloader.adding_keywords.get(user_id, []))
            )
        elif data in (
                BotCallbackText.DOWNLOAD_CHAT_DTYPE_FILTER,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO_NOTE,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_LIVE_PHOTO
        ):
            try:
                if data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO:
                    self.__toggle_download_chat_dtype(downloader, chat_id, 'video')
                elif data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO:
                    self.__toggle_download_chat_dtype(downloader, chat_id, 'photo')
                elif data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO:
                    self.__toggle_download_chat_dtype(downloader, chat_id, 'audio')
                elif data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE:
                    self.__toggle_download_chat_dtype(downloader, chat_id, 'voice')
                elif data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION:
                    self.__toggle_download_chat_dtype(downloader, chat_id, 'animation')
                elif data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT:
                    self.__toggle_download_chat_dtype(downloader, chat_id, 'document')
                elif data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO_NOTE:
                    self.__toggle_download_chat_dtype(downloader, chat_id, 'video_note')
                elif data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_LIVE_PHOTO:
                    self.__toggle_download_chat_dtype(downloader, chat_id, 'live_photo')
                await query.message.edit_text(
                    text=self.__filter_prompt(downloader, chat_id),
                    reply_markup=kb.toggle_download_chat_type_filter_button(downloader.download_chat_filter[chat_id])
                )
            except ValueError:
                await query.message.reply_text('⚠️⚠️⚠️至少需要选择一个下载类型⚠️⚠️⚠️')
            except Exception as e:
                await query.message.reply_text('下载类型设置失败\n(具体原因请前往终端查看报错信息)')
                log.error(f'下载类型设置失败,{_t(KeyWord.REASON)}:"{e}"', exc_info=True)
        elif data in (
                BotCallbackText.DOWNLOAD_CHAT_KEYWORD_FILTER,
                BotCallbackText.CONFIRM_KEYWORD,
                BotCallbackText.CANCEL_KEYWORD_INPUT
        ):
            if data == BotCallbackText.DOWNLOAD_CHAT_KEYWORD_FILTER:
                try:
                    await query.message.edit_text(
                        text=self.__filter_prompt(downloader, chat_id),
                        reply_markup=kb.keyword_filter_button(downloader.adding_keywords.get(user_id, []))
                    )
                except MessageNotModified:
                    pass
                downloader.add_keyword_mode_handler(
                    enable=True,
                    chat_id=user_id,
                    callback_query=query,
                    callback_prompt=partial(self.__filter_prompt, downloader, chat_id)
                )
            elif data == BotCallbackText.CONFIRM_KEYWORD:
                downloader.add_keyword_mode_handler(
                    enable=False,
                    chat_id=user_id,
                    callback_query=query,
                    callback_prompt=partial(self.__filter_prompt, downloader, chat_id)
                )
                await query.message.edit_text(
                    text=self.__filter_prompt(downloader, chat_id),
                    reply_markup=kb.download_chat_filter_button(downloader.download_chat_filter[chat_id]['comment'])
                )
            elif data == BotCallbackText.CANCEL_KEYWORD_INPUT:
                downloader.adding_keywords.pop(user_id, None)
                downloader.add_keyword_mode_handler(
                    enable=False,
                    chat_id=user_id,
                    callback_query=query,
                    callback_prompt=partial(self.__filter_prompt, downloader, chat_id)
                )
                downloader.download_chat_filter[chat_id]['keyword'] = {}
                await query.message.edit_text(
                    text=self.__filter_prompt(downloader, chat_id),
                    reply_markup=kb.download_chat_filter_button(downloader.download_chat_filter[chat_id]['comment'])
                )
        elif data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_COMMENT:
            status = downloader.download_chat_filter[chat_id]['comment']
            downloader.download_chat_filter[chat_id]['comment'] = not status
            await query.message.edit_text(
                text=self.__filter_prompt(downloader, chat_id),
                reply_markup=kb.download_chat_filter_button(downloader.download_chat_filter[chat_id]['comment'])
            )

    @staticmethod
    def __get_update_time(downloader, chat_id):
        start_timestamp = downloader.download_chat_filter[chat_id]['date_range']['start_date']
        end_timestamp = downloader.download_chat_filter[chat_id]['date_range']['end_date']
        start_time = datetime.datetime.fromtimestamp(start_timestamp) if start_timestamp else '未定义'
        end_time = datetime.datetime.fromtimestamp(end_timestamp) if end_timestamp else '未定义'
        return start_time, end_time

    @staticmethod
    def __get_format_dtype(downloader, chat_id):
        download_type = []
        for dtype, status in downloader.download_chat_filter[chat_id]['download_type'].items():
            if status:
                download_type.append(_t(dtype))
        return ','.join(download_type)

    @staticmethod
    def __get_format_keywords(downloader, chat_id):
        keywords = downloader.download_chat_filter[chat_id]['keyword']
        if not keywords:
            return '未定义'
        return ','.join(keywords.keys())

    @staticmethod
    def __get_format_comment_status(downloader, chat_id):
        status = downloader.download_chat_filter[chat_id]['comment']
        return '开' if status else '关'

    @staticmethod
    def __remove_chat_id(downloader, chat_id):
        if chat_id in downloader.download_chat_filter:
            downloader.download_chat_filter.pop(chat_id)
            log.info(f'"{chat_id}"已从{downloader.download_chat_filter}中移除。')

    def __filter_prompt(self, downloader, chat_id):
        start_time, end_time = self.__get_update_time(downloader, chat_id)
        return (
            f'💬下载频道:`{chat_id}`\n'
            f'⏮️当前选择的起始日期为:{start_time}\n'
            f'⏭️当前选择的结束日期为:{end_time}\n'
            f'📝当前选择的下载类型为:{self.__get_format_dtype(downloader, chat_id)}\n'
            f'🔑当前匹配的关键词为:{self.__get_format_keywords(downloader, chat_id)}\n'
            f'👥包含评论区:{self.__get_format_comment_status(downloader, chat_id)}'
        )

    @staticmethod
    async def __verification_time(query, start_time, end_time) -> bool:
        if isinstance(start_time, datetime.datetime) and isinstance(end_time, datetime.datetime):
            if start_time > end_time:
                await query.message.reply_text(
                    text=f'❌❌❌日期设置失败❌❌❌\n'
                         f'`起始日期({start_time})`>`结束日期({end_time})`\n'
                )
                return False
            elif start_time == end_time:
                await query.message.reply_text(
                    text=f'❌❌❌日期设置失败❌❌❌\n'
                         f'`起始日期({start_time})`=`结束日期({end_time})`\n'
                )
                return False
        return True

    @staticmethod
    def __toggle_download_chat_dtype(downloader, chat_id, param):
        dtype = downloader.download_chat_filter[chat_id]['download_type']
        status = dtype[param]
        if list(dtype.values()).count(True) == 1 and status:
            raise ValueError
        dtype[param] = not status
        f_s = '禁用' if status else '启用'
        f_p = f'已{f_s}"{param}"类型用于/download_chat命令的下载。'
        log.info(f'{f_p}当前的/download_chat下载类型设置:{dtype}')


class CommandButtonHandler(CallbackHandler):
    exact = (
        BotCallbackText.COMMAND_DOWNLOAD,
        BotCallbackText.COMMAND_UPLOAD,
        BotCallbackText.COMMAND_UPLOAD_R,
        BotCallbackText.COMMAND_DOWNLOAD_CHAT,
        BotCallbackText.COMMAND_FORWARD,
        BotCallbackText.LISTEN_DOWNLOAD_BTN,
        BotCallbackText.LISTEN_FORWARD_BTN
    )

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        data = ctx.data
        command_map = {
            BotCallbackText.COMMAND_DOWNLOAD: BotCommandText.DOWNLOAD[0],
            BotCallbackText.COMMAND_DOWNLOAD_CHAT: BotCommandText.DOWNLOAD_CHAT[0],
            BotCallbackText.COMMAND_UPLOAD: BotCommandText.UPLOAD[0],
            BotCallbackText.COMMAND_UPLOAD_R: BotCommandText.UPLOAD_R[0],
            BotCallbackText.COMMAND_FORWARD: BotCommandText.FORWARD[0],
            BotCallbackText.LISTEN_DOWNLOAD_BTN: BotCommandText.LISTEN_DOWNLOAD[0],
            BotCallbackText.LISTEN_FORWARD_BTN: BotCommandText.LISTEN_FORWARD[0]
        }
        command = command_map.get(data)
        if not command:
            return None
        # 发送第一步提示并开启多步引导,后续步骤由handle_command_input按COMMAND_STEPS推进。
        first_hint = Bot.COMMAND_STEPS[command][0][1]
        await query.message.reply(
            text=first_hint,
            reply_markup=pyrogram.types.ForceReply(),
            link_preview_options=Bot.LINK_PREVIEW_OPTIONS
        )
        downloader.add_command_mode_handler(
            chat_id=query.from_user.id,
            callback_query=query,
            command=command,
            enable=True
        )


class MenuButtonHandler(CallbackHandler):
    exact = (
        BotCallbackText.MENU_DOWNLOAD,
        BotCallbackText.MENU_LISTEN,
        BotCallbackText.MENU_UPLOAD,
        BotCallbackText.MENU_AUTH,
        BotCallbackText.MENU_BACK
    )

    async def handle(self, ctx: CallbackContext) -> None:
        downloader = ctx.downloader
        query = ctx.query
        data = ctx.data
        if data == BotCallbackText.MENU_DOWNLOAD:
            await query.edit_message_text(
                text=BotButton.DOWNLOAD_MENU_TITLE,
                reply_markup=downloader.menu_keyboard('download'))
            return None
        elif data == BotCallbackText.MENU_LISTEN:
            await query.edit_message_text(
                text=BotButton.LISTEN_MENU_TITLE,
                reply_markup=downloader.menu_keyboard('listen'))
            return None
        elif data == BotCallbackText.MENU_UPLOAD:
            await query.edit_message_text(
                text=BotButton.UPLOAD_MENU_TITLE,
                reply_markup=downloader.menu_keyboard('upload'))
            return None
        elif data == BotCallbackText.MENU_AUTH:
            # 进入授权用户子菜单时同步刷新文本,避免仍停留在主菜单/help文本。
            await query.edit_message_text(
                text='🔐授权用户管理',
                reply_markup=downloader.menu_keyboard('auth'))
            return None
        elif data == BotCallbackText.MENU_BACK:
            # 返回主菜单时同时还原文本与键盘,避免停留在子菜单遗留的text状态。
            menu = await downloader.help(user_id=query.from_user.id)
            await query.edit_message_text(text=menu['text'], reply_markup=menu['keyboard'])
            return None
        else:
            return None
        await query.edit_message_reply_markup(reply_markup=kb)


CALLBACK_HANDLERS: tuple = (
    MenuButtonHandler(),
    NoticeHandler(),
    PayHandler(),
    BackHandler(),
    TaskAssignHandler(),
    ListenInfoHandler(),
    LookupAuthInfoHandler(),
    AddAuthHandler(),
    CancelAuthInputHandler(),
    ShutdownHandler(),
    SettingsHandler(),
    TableHandler(),
    UploadDownloadSettingHandler(),
    DownloadTypeHandler(),
    ForwardTypeHandler(),
    ListenRemoveHandler(),
    AuthUserHandler(),
    DownloadChatHandler(),
    CommandButtonHandler()
)


async def dispatch_callback_data(ctx: CallbackContext) -> None:
    """按注册表顺序分发回调,首个匹配的处理器负责处理。"""
    for handler in CALLBACK_HANDLERS:
        if handler.match(ctx.data):
            await handler.handle(ctx)
            return None

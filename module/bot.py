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
from typing import List, Dict, Union, Optional, Callable

import pyrogram
from pyrogram.types.messages_and_media import ReplyParameters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.errors.exceptions.flood_420 import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import (
    MessageNotModified,
    AccessTokenInvalid
)
from pyrogram.types.bots_and_keyboards import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)

from module import (
    __version__,
    __copyright__,
    __license__,
    log,
    SOFTWARE_FULL_NAME,
    LINK_PREVIEW_OPTIONS
)
from module.language import _t
from module.stdio import MetaData
from module.task import UploadTask
from module.config import GlobalConfig
from module.path_tool import safe_scan_directory_file
from module.util import (
    parse_link,
    safe_index,
    safe_message,
    is_allow_upload,
    get_valid_chat_id
)
from module.enums import (
    CalenderKeyboard,
    UploadStatus,
    DownloadType,
    BotCommandText,
    BotMessage,
    BotCallbackText,
    BotButton,
    KeyWord
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
        BotCommand(BotCommandText.DOWNLOAD_CHAT[0], BotCommandText.DOWNLOAD_CHAT[1].replace('`', ''))
    ]

    def __init__(self):
        self.application = None
        self.user: Union[pyrogram.Client, None] = None
        self.bot: Union[pyrogram.Client, None] = None
        self.is_bot_running: bool = False
        self.bot_task_link: set = set()
        self.gc = GlobalConfig()
        self.root: list = []
        self.last_client: Union[pyrogram.Client, None] = None
        self.last_message: Union[pyrogram.types.Message, None] = None
        self.listen_download_chat: dict = {}
        self.listen_forward_chat: dict = {}
        self.handle_media_groups: dict = {}
        self.download_chat_filter: dict = {}
        self.adding_keywords: list = []  # 用于跟踪正在添加的关键词列表。
        self.keyword_handler: Union[MessageHandler, None] = None  # 关键词输入模式的handler。

    def add_keyword_mode_handler(
            self,
            chat_id,
            callback_query: CallbackQuery,
            callback_prompt: Callable,
            enable: bool,
    ):
        """添加或移除关键词输入模式的 handler"""
        if enable:
            # 先创建 handler 对象，然后添加
            self.keyword_handler = MessageHandler(
                partial(self.handle_keyword_input, chat_id, callback_query, callback_prompt),
                filters=pyrogram.filters.user(self.root) & pyrogram.filters.text & (
                    lambda client, m: isinstance(
                        m,
                        pyrogram.types.Message
                    ) and m.text and m.text.strip() and not m.text.startswith(
                        '/') and not m.text.startswith('http')
                )
            )
            # 使用group=-1确保在process_error_message(group=0)之前处理。
            self.bot.add_handler(self.keyword_handler, group=-1)
            log.info(f'用户输入模式已打开,Handler:"{self.keyword_handler}"。')
        else:
            if self.keyword_handler:
                self.bot.remove_handler(self.keyword_handler, group=-1)
                log.info('用户输入模式已关闭,Handler已清空。')
                self.keyword_handler = None

    async def process_error_message(self, client: pyrogram.Client, message: pyrogram.types.Message) -> None:
        if self.keyword_handler:
            return
        await self.help(client, message)
        await client.send_message(
            chat_id=message.from_user.id,
            reply_parameters=ReplyParameters(message_id=message.id),
            text='⚠️⚠️⚠️未知命令⚠️⚠️⚠️\n请查看帮助后重试。',
            link_preview_options=LINK_PREVIEW_OPTIONS
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
            return

        # 以空格分隔关键词。
        keywords = [kw.strip() for kw in text.split() if kw.strip()]
        for keyword in keywords:
            if keyword in self.adding_keywords:
                try:
                    await callback_query.message.edit_text(
                        text=f'🚛{keyword}已被添加,选择处理方式后继续。',
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    BotButton.DROP,
                                    callback_data=f'{BotCallbackText.DROP_KEYWORD}_{keyword}'
                                )
                            ]
                        ]
                        )
                    )
                except MessageNotModified:
                    pass
            else:
                self.download_chat_filter[chat_id]['keyword'][keyword] = True
                self.adding_keywords.append(keyword)  # 添加到正在添加的关键词列表。
                try:
                    await callback_query.message.edit_text(
                        text=callback_prompt(),
                        reply_markup=KeyboardButton.keyword_filter_button(self.adding_keywords)
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
            with_upload: Union[dict, None] = None
    ) -> Union[Dict[str, Union[set, pyrogram.types.Message]], None]:
        text: str = message.text
        if text == '/download':
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⚠️⚠️⚠️请提供下载链接⚠️⚠️⚠️语法:\n`/download https://t.me/x/x`',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
        elif text.startswith('https://t.me/'):
            if text[len('https://t.me/'):].count('/') >= 1:
                try:
                    await client.delete_messages(chat_id=message.from_user.id, message_ids=message.id)
                    await self.send_message_to_bot(text=f'/download {text}', catch=True)
                except Exception as e:
                    await client.send_message(
                        chat_id=message.from_user.id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        text=f'{e}\n⬇️⬇️⬇️请使用以下命令分配下载任务⬇️⬇️⬇️\n`/download {text}`',
                        link_preview_options=LINK_PREVIEW_OPTIONS
                    )
            else:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'⬇️⬇️⬇️请使用以下命令分配下载任务⬇️⬇️⬇️\n`/download https://t.me/x/x`',
                    link_preview_options=LINK_PREVIEW_OPTIONS
                )
        elif len(text) <= 25 or text == '/download https://t.me/x/x' or text.endswith('.txt'):
            await self.help(client, message)
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌链接错误❌❌❌\n请查看帮助后重试。',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
        else:
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
                        client=client, message=message,
                        text=self.update_text(
                            right_link=right_link,
                            invalid_link=invalid_link if invalid_link else None
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
        if BotCallbackText.DOWNLOAD_CHAT_ID != 'download_chat_id':
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⚠️⚠️⚠️请执行或取消上一次频道下载任务设置⚠️⚠️⚠️',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            return None
        text: str = message.text
        if text == '/download_chat':
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⚠️⚠️⚠️请提供下载链接⚠️⚠️⚠️语法:\n`/download_chat https://t.me/x/x`',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            return None
        command = text.split()
        if len(command) != 2:
            await self.help(client, message)
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌命令语法错误❌❌❌\n请查看帮助后重试。',
                link_preview_options=LINK_PREVIEW_OPTIONS
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
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            return None
        chat_id = meta.get('chat_id')
        if not chat_id:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌无法获取频道名❌❌❌',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            return None
        if chat_id in self.download_chat_filter:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⚠️⚠️⚠️该频道已在下载中⚠️⚠️⚠️\n'
                     f'{chat_link}',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            return None
        BotCallbackText.DOWNLOAD_CHAT_ID = str(chat_id)
        self.download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID] = {
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
                    'animation': True
                },
            'keyword': {}
        }
        log.info(f'"{BotCallbackText.DOWNLOAD_CHAT_ID}"已添加至{self.download_chat_filter}。')
        format_dtype = ','.join([_t(_) for _ in DownloadType()])
        await client.send_message(
            chat_id=message.from_user.id,
            reply_parameters=ReplyParameters(message_id=message.id),
            text=f'💬下载频道:`{chat_id}`\n'
                 f'⏮️当前选择的起始日期为:未定义\n'
                 f'⏭️当前选择的结束日期为:未定义\n'
                 f'📝当前选择的下载类型为:{format_dtype}\n'
                 f'🔑当前关键词过滤:未定义',
            reply_markup=KeyboardButton.download_chat_filter_button(),
            link_preview_options=LINK_PREVIEW_OPTIONS
        )

    @staticmethod
    async def safe_process_message(
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            text: list, last_message_id: int = -1,
            reply_markup: Union[pyrogram.types.InlineKeyboardMarkup, None] = None
    ) -> pyrogram.types.Message:
        if len(text) == 1 and last_message_id != -1:
            last_bot_message = await client.edit_message_text(
                chat_id=message.from_user.id,
                message_id=last_message_id,
                text=text[0],
                link_preview_options=LINK_PREVIEW_OPTIONS,
                reply_markup=reply_markup
            )
            return last_bot_message

        last_bot_messages: list = []
        for t in text:
            last_bot_message: pyrogram.types.Message = await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=t, link_preview_options=LINK_PREVIEW_OPTIONS
            )
            if last_bot_message not in last_bot_messages:
                last_bot_messages.append(last_bot_message)
        return last_bot_messages[-1]

    @staticmethod
    async def help(
            client: Union[pyrogram.Client, None] = None,
            message: Union[pyrogram.types.Message, None] = None
    ) -> Union[None, dict]:  # client与message都为None时,返回keyboard与text。
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        BotButton.GITHUB,
                        url='https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/releases',
                    ),
                    InlineKeyboardButton(
                        BotButton.SUBSCRIBE_CHANNEL,
                        url='https://t.me/RestrictedMediaDownloader'
                    )
                ],
                [
                    InlineKeyboardButton(
                        BotButton.VIDEO_TUTORIAL,
                        url='https://www.bilibili.com/video/BV1nCp8evEwv'),
                    InlineKeyboardButton(
                        BotButton.PAY,
                        callback_data=BotCallbackText.PAY)
                ],
                [
                    InlineKeyboardButton(
                        BotButton.SETTING,
                        callback_data=BotCallbackText.SETTING
                    )
                ]
            ]
        )

        text = (
            f'`\n💎 {SOFTWARE_FULL_NAME} v{__version__} 💎\n'
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
            f'💬 {BotCommandText.with_description(BotCommandText.DOWNLOAD_CHAT)}\n\n'
            f'✨ 其他功能:\n'
            f'📨 转发`视频`、`图片`、`音频`、`语音`、`GIF`、`文档`类型的消息给我,即可自动下载。\n'
        )
        if not all([client, message]):
            return {
                'keyboard': keyboard,
                'text': text
            }
        await client.send_message(
            chat_id=message.from_user.id,
            text=text,
            link_preview_options=LINK_PREVIEW_OPTIONS,
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
            link_preview_options=LINK_PREVIEW_OPTIONS,
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
                link_preview_options=LINK_PREVIEW_OPTIONS
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
                        bot_message=self.last_message,
                        error_msg=f'⬇️⬇️⬇️目标频道不存在⬇️⬇️⬇️\n{target_link}'
                    )
                if not valid_link_cache[target_link]:
                    return None
            if os.path.isdir(file_path):
                upload_folder = []
                if command == '/upload_r':
                    upload_files = [os.path.join(root, filename) for root, dirs, files in os.walk(file_path) for
                                    filename in files]
                else:
                    upload_files = safe_scan_directory_file(file_path)
                for file_name in upload_files:
                    new_message = copy.copy(message)
                    new_message.text = f'/upload {os.path.join(file_path, file_name)} {target_link}'
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
                        link_preview_options=LINK_PREVIEW_OPTIONS
                    )
                    await asyncio.gather(*upload_folder)
                else:
                    await client.send_message(
                        chat_id=message.from_user.id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        text=f'⚠️⚠️⚠️文件夹为空⚠️⚠️⚠️\n`{file_path}`',
                        link_preview_options=LINK_PREVIEW_OPTIONS
                    )
                return None
            if not os.path.isfile(file_path):
                log.error(f'上传出错,{_t(KeyWord.REASON)}:"{file_path}"不存在。')
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'⚠️⚠️⚠️上传文件不存在⚠️⚠️⚠️\n`{file_path}`',
                    link_preview_options=LINK_PREVIEW_OPTIONS
                )
                return None
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'⚠️⚠️⚠️上传文件大小为0⚠️⚠️⚠️\n`{file_path}`',
                    link_preview_options=LINK_PREVIEW_OPTIONS
                )

            if not is_allow_upload(file_size=file_size, is_premium=self.user.me.is_premium):
                format_file_size: str = MetaData.suitable_units_display(file_size, unit='MiB', mebibyte=True)
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'⚠️⚠️⚠️上传大小超过限制({format_file_size})⚠️⚠️⚠️\n'
                         f'`{file_path}`\n'
                         f'(普通用户2000MiB,会员用户4000MiB)',
                    link_preview_options=LINK_PREVIEW_OPTIONS
                )
            if not recursion:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text=f'📤📤📤上传任务已创建,请耐心等待📤📤📤\n`{file_path}`',
                    link_preview_options=LINK_PREVIEW_OPTIONS
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
                        status=UploadStatus.PENDING
                    )
                }
        if not recursion:
            await self.help(client, message)
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌命令错误❌❌❌\n请查看帮助后重试。',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            return None

    async def exit(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> None:
        last_message = await client.send_message(
            chat_id=message.from_user.id,
            text='🫡🫡🫡已收到退出命令。',
            reply_parameters=ReplyParameters(message_id=message.id),
            link_preview_options=LINK_PREVIEW_OPTIONS
        )
        self.is_bot_running = False
        await self.safe_edit_message(
            client=client,
            message=message,
            last_message_id=last_message.id,
            text='👌👌👌退出成功。'
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
            message: pyrogram.types,
            link: str,
            command: str
    ):
        pass

    async def listen_info(
            self,
            client: pyrogram.Client,
            message: pyrogram.types
    ):
        async def __listen_info(_listen_chat: dict, _text: str):
            last_message = await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                link_preview_options=LINK_PREVIEW_OPTIONS,
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
                link_preview_options=LINK_PREVIEW_OPTIONS,
                text='😲目前没有正在监听的频道。'
            )
        else:
            if self.listen_download_chat:
                await __listen_info(self.listen_download_chat, '🕵️以下链接为已创建的`监听下载`频道:\n')
            if self.listen_forward_chat:
                await __listen_info(self.listen_forward_chat, '📲以下链接为已创建的`监听转发`频道:\n')

    async def handle_forwarded_media(
            self,
            user_client: pyrogram.Client,
            user_message: pyrogram.types.Message
    ):
        pass

    async def done_notice(
            self,
            text
    ):
        if self.gc.get_config(BotCallbackText.NOTICE):
            if all([self.last_client, self.last_message]):
                await self.last_client.send_message(
                    chat_id=self.last_message.from_user.id,
                    text=f'📢通知:\n{text}',
                    link_preview_options=LINK_PREVIEW_OPTIONS
                )

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
            await bot_client_obj.start()
            await self.bot.set_bot_commands(self.COMMANDS)
            bot = await self.bot.get_me()
            bot_username = getattr(bot, 'username', None)

            self.bot.add_handler(
                MessageHandler(
                    self.start,
                    filters=pyrogram.filters.command(['start']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.help,
                    filters=pyrogram.filters.command(['help']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_link_from_bot,
                    filters=pyrogram.filters.command(['download']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_chat_link_from_bot,
                    filters=pyrogram.filters.command(['download_chat']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_upload_link_from_bot,
                    filters=pyrogram.filters.command(['upload']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_upload_link_from_bot,
                    filters=pyrogram.filters.command(['upload_r']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.table,
                    filters=pyrogram.filters.command(['table']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_forward_link_from_bot,
                    filters=pyrogram.filters.command(['forward']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.exit,
                    filters=pyrogram.filters.command(['exit']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.on_listen,
                    filters=pyrogram.filters.command(['listen_download', 'listen_forward']) & pyrogram.filters.user(
                        self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.listen_info,
                    filters=pyrogram.filters.command(['listen_info']) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.get_download_link_from_bot,
                    filters=pyrogram.filters.regex(r'^https://t.me.*') & pyrogram.filters.user(self.root)
                )
            )
            self.user.add_handler(
                MessageHandler(
                    self.handle_forwarded_media,
                    filters=pyrogram.filters.user(self.root) & pyrogram.filters.forwarded & pyrogram.filters.chat(
                        bot_username) & (
                                    pyrogram.filters.video
                                    | pyrogram.filters.photo
                                    | pyrogram.filters.audio
                                    | pyrogram.filters.voice
                                    | pyrogram.filters.animation
                                    | pyrogram.filters.document
                            )
                )
            )
            self.bot.add_handler(
                CallbackQueryHandler(
                    self.callback_data,
                    filters=pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.process_error_message,
                    filters=pyrogram.filters.user(self.root) & ~(
                            pyrogram.filters.video
                            | pyrogram.filters.photo
                            | pyrogram.filters.audio
                            | pyrogram.filters.voice
                            | pyrogram.filters.animation
                            | pyrogram.filters.document
                    )
                )
            )
            self.is_bot_running: bool = True
            await self.send_message_to_bot(text='/start')
            return f'🤖「机器人」启动成功。({BotButton.OPEN_NOTICE if self.gc.config.get(BotCallbackText.NOTICE) else BotButton.CLOSE_NOTICE})'
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
                    link_preview_options=LINK_PREVIEW_OPTIONS
                )
        except Exception as e:
            if catch:
                raise Exception(str(e))
            else:
                return e

    @staticmethod
    def update_text(right_link: set, invalid_link: set, exist_link: Union[set, None] = None) -> list:
        n = '\n'
        right_msg = f'{BotMessage.RIGHT}{n.join(sorted(right_link))}' if right_link else ''
        invalid_msg = f'{BotMessage.INVALID}{n.join(sorted(invalid_link))}{n}(具体原因请前往终端查看报错信息)' if invalid_link else ''
        if exist_link:
            exist_msg = f'{BotMessage.EXIST}{n.join(sorted(exist_link))}' if exist_link else ''
            text: str = right_msg + n + exist_msg + n + invalid_msg
        else:
            text = right_msg + n + invalid_msg
        return safe_message(text)

    async def safe_edit_message(
            self, client: pyrogram.Client,
            message: pyrogram.types.Message,
            last_message_id: int,
            text: Union[str, List[str]],
            reply_markup: Union[pyrogram.types.InlineKeyboardMarkup, None] = None
    ) -> Union[pyrogram.types.Message, str, None]:
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
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                    reply_markup=reply_markup
                )
        except MessageNotModified:
            pass
        except (FloodWait, Exception) as e:
            return str(e)


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

    async def toggle_download_setting_button(
            self,
            user_config: dict
    ):
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
                            text=BotButton.RETURN,
                            callback_data=BotCallbackText.SETTING
                        )
                    ]
                ]
            )
        )

    async def toggle_forward_setting_button(
            self,
            global_config: dict
    ):
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

    @staticmethod
    def toggle_download_chat_type_filter_button(
            download_chat_filter: dict
    ):
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.VIDEO_ON if
                        download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['download_type'][
                            DownloadType.VIDEO] else BotButton.VIDEO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO
                    ),
                    InlineKeyboardButton(
                        text=BotButton.PHOTO_ON if
                        download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['download_type'][
                            DownloadType.PHOTO] else BotButton.PHOTO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.AUDIO_ON if
                        download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['download_type'][
                            DownloadType.AUDIO] else BotButton.AUDIO_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO
                    ),
                    InlineKeyboardButton(
                        text=BotButton.VOICE_ON if
                        download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['download_type'][
                            DownloadType.VOICE] else BotButton.VOICE_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BotButton.ANIMATION_ON if
                        download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['download_type'][
                            DownloadType.ANIMATION] else BotButton.ANIMATION_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION
                    ),
                    InlineKeyboardButton(
                        text=BotButton.DOCUMENT_ON if
                        download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['download_type'][
                            DownloadType.DOCUMENT] else BotButton.DOCUMENT_OFF,
                        callback_data=BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT
                    )
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

    async def task_assign_button(self):
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
    def download_chat_filter_button():
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
                        text=BotButton.EXECUTE_TASK,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_ID
                    ),
                    InlineKeyboardButton(
                        text=BotButton.CANCEL_TASK,
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL
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

        await self.callback_query.message.edit_reply_markup(InlineKeyboardMarkup(keyboard))

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
            adding_keywords=Union[list, None]
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
                        callback_data=BotCallbackText.DOWNLOAD_CHAT_FILTER
                    )
                ]
            ]
        return InlineKeyboardMarkup(keyword_buttons)


class CallbackData:
    def __init__(self, data: Union[dict, None] = None):
        self.data: Union[dict, None] = data

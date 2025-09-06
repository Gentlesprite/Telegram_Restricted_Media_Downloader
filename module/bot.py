# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/1/24 21:27
# File:bot.py
from typing import List, Dict, Union

import pyrogram
from pyrogram.types.messages_and_media import ReplyParameters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.errors.exceptions.flood_420 import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified, AccessTokenInvalid, ButtonDataInvalid
from pyrogram.types.bots_and_keyboards import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from module import log, __version__, __copyright__, __license__, SOFTWARE_FULL_NAME, LINK_PREVIEW_OPTIONS
from module.language import _t
from module.config import GlobalConfig
from module.util import safe_index, safe_message
from module.enums import BotCommandText, BotMessage, BotCallbackText, BotButton, KeyWord


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
        BotCommand(BotCommandText.LISTEN_INFO[0], BotCommandText.LISTEN_INFO[1])
    ]

    def __init__(self):
        self.user = None
        self.bot = None
        self.is_bot_running: bool = False
        self.bot_task_link: set = set()
        self.gc = GlobalConfig()
        self.root: list = []
        self.last_client: Union[pyrogram.Client, None] = None
        self.last_message: Union[pyrogram.types.Message, None] = None
        self.listen_download_chat: dict = {}
        self.listen_forward_chat: dict = {}

    async def process_error_message(self, client: pyrogram.Client, message: pyrogram.types.Message) -> None:
        await self.help(client, message)
        await client.send_message(
            chat_id=message.from_user.id,
            reply_parameters=ReplyParameters(message_id=message.id),
            text='❓❓❓未知命令❓❓❓\n请查看帮助后重试。',
            link_preview_options=LINK_PREVIEW_OPTIONS
        )

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

    async def get_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> Union[Dict[str, Union[set, pyrogram.types.Message]], None]:
        text: str = message.text
        if text == '/download':
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❓❓❓请提供下载链接❓❓❓格式:\n`/download https://t.me/x/x`',
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
                text='⁉️⁉️⁉️链接错误⁉️⁉️⁉️\n请查看帮助后重试。',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
        else:
            link: list = text.split()
            link.remove('/download') if '/download' in link else None
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
                    right_link.add(f'{link[0]}/{i}')
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
            f'📖 Licensed under the terms of the {__license__}.`\n'
            f'🎮️ 可用命令:\n'
            f'🛎️ {BotCommandText.with_description(BotCommandText.HELP)}\n'
            f'📁 {BotCommandText.with_description(BotCommandText.DOWNLOAD)}\n'
            f'📝 {BotCommandText.with_description(BotCommandText.TABLE)}\n'
            f'↗️ {BotCommandText.with_description(BotCommandText.FORWARD)}\n'
            f'❌ {BotCommandText.with_description(BotCommandText.EXIT)}\n'
            f'🕵️ {BotCommandText.with_description(BotCommandText.LISTEN_DOWNLOAD)}\n'
            f'📲 {BotCommandText.with_description(BotCommandText.LISTEN_FORWARD)}\n'
            f'🔍 {BotCommandText.with_description(BotCommandText.LISTEN_INFO)}\n'
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
                        url='https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/releases',
                        callback_data=BotCallbackText.LINK_TABLE
                    ),
                    InlineKeyboardButton(
                        BotButton.COUNT_TABLE, url='https://t.me/RestrictedMediaDownloader',
                        callback_data=BotCallbackText.COUNT_TABLE
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
                text='❌❌❌命令格式无效❌❌❌\n'
                     '⬇️⬇️⬇️格式如下⬇️⬇️⬇️\n'
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
                    text='❌❌❌命令格式无效❌❌❌\n'
                         '⬇️⬇️⬇️格式如下⬇️⬇️⬇️\n'
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
                         '⬇️⬇️⬇️格式如下⬇️⬇️⬇️\n'
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
                         '⬇️⬇️⬇️格式如下⬇️⬇️⬇️\n'
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

    @staticmethod
    async def cancel_listen(
            client: pyrogram.Client,
            message: pyrogram.types,
            link: str,
            command: str
    ):

        try:
            args: list = link.split()
            forward_emoji = ' ➡️ '
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=f'`{link if len(args) == 1 else forward_emoji.join(args)}`\n⚠️⚠️⚠️已经在监听列表中⚠️⚠️⚠️\n请选择是否移除',
                link_preview_options=LINK_PREVIEW_OPTIONS,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            BotButton.OK,
                            callback_data=f'{BotCallbackText.REMOVE_LISTEN_DOWNLOAD} {link}' if command == '/listen_download' else f'{BotCallbackText.REMOVE_LISTEN_FORWARD} {link}'
                        ),
                        InlineKeyboardButton(
                            BotButton.CANCEL,
                            callback_data=BotCallbackText.REMOVE_LISTEN_DOWNLOAD if command == '/listen_download' else BotCallbackText.REMOVE_LISTEN_FORWARD
                        )
                    ]
                ]
                )
            )
        except ButtonDataInvalid:
            len_data: int = len(f'{BotCallbackText.REMOVE_LISTEN_FORWARD} {link}')
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                link_preview_options=LINK_PREVIEW_OPTIONS,
                text='⚠️⚠️⚠️已经在监听列表中⚠️⚠️⚠️\n'
                     f'由于数据位[{len_data}]超过[64]位,当前监听无法移除。'
            )

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

    async def done_notice(
            self,
            link: str
    ):
        if all([self.last_client, self.last_message]):
            if self.gc.get_config(BotCallbackText.NOTICE):
                await self.last_client.send_message(
                    chat_id=self.last_message.from_user.id,
                    text=f'"{link}"已下载完成。',
                    link_preview_options=LINK_PREVIEW_OPTIONS
                )

    async def start_bot(
            self,
            user_client_obj: pyrogram.Client,
            bot_client_obj: pyrogram.Client,
    ) -> str:
        """启动机器人。"""
        try:
            self.bot = bot_client_obj
            self.user = user_client_obj
            root = await self.user.get_me()
            self.root.append(root.id)
            await bot_client_obj.start()
            await self.bot.set_bot_commands(self.COMMANDS)
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
                    self.get_link_from_bot,
                    filters=pyrogram.filters.command(['download']) & pyrogram.filters.user(self.root)
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
                    self.get_link_from_bot,
                    filters=pyrogram.filters.regex(r'^https://t.me.*') & pyrogram.filters.user(self.root)
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
                    filters=pyrogram.filters.user(self.root)
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
        await self.callback_query.message.edit_reply_markup(InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=BotButton.EXPORT_TABLE,
                        callback_data=BotCallbackText.EXPORT_LINK_TABLE if choice == BotCallbackText.EXPORT_LINK_TABLE else BotCallbackText.EXPORT_COUNT_TABLE
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
                prompt: str = '链接' if choice == 'link' else '计数'
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

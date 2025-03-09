# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/1/24 21:27
# File:bot.py
from typing import List, Dict, Union

import pyrogram
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.errors.exceptions.bad_request_400 import MessageNotModified, AccessTokenInvalid
from pyrogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from module import __version__, __copyright__, SOFTWARE_FULL_NAME, __license__
from module.language import _t
from module.config import GlobalConfig
from module.enums import BotCommandText, BotMessage, BotCallbackText, BotButton, KeyWord


class Bot:
    BOT_NAME: str = 'TRMD_BOT'
    COMMANDS: List[BotCommand] = [
        BotCommand(BotCommandText.HELP[0], BotCommandText.HELP[1]),
        BotCommand(BotCommandText.DOWNLOAD[0], BotCommandText.DOWNLOAD[1].replace('`', '')),
        BotCommand(BotCommandText.TABLE[0], BotCommandText.TABLE[1]),
        BotCommand(BotCommandText.FORWARD[0], BotCommandText.FORWARD[1]),
        BotCommand(BotCommandText.EXIT[0], BotCommandText.EXIT[1])
    ]

    def __init__(self):
        self.user = None
        self.bot = None
        self.is_bot_running: bool = False
        self.bot_task_link: set = set()
        self.gc = GlobalConfig()
        self.root: list = []

    async def process_error_message(self, client: pyrogram.Client, message: pyrogram.types.Message) -> None:
        await self.help(client, message)
        await client.send_message(chat_id=message.chat.id,
                                  text='未知命令,请查看帮助后重试。',
                                  disable_web_page_preview=True)

    async def get_link_from_bot(self,
                                client: pyrogram.Client,
                                message: pyrogram.types.Message) -> Dict[str, set] or None:
        text: str = message.text
        if text == '/download':
            await client.send_message(chat_id=message.chat.id,
                                      text='❓❓❓请提供下载链接,格式:\n`/download https://t.me/x/x`',
                                      disable_web_page_preview=True)
        elif text.startswith('https://t.me/'):
            if text[len('https://t.me/'):].count('/') >= 1:
                try:
                    await client.delete_messages(chat_id=message.chat.id, message_ids=message.id)
                    await self.send_message_to_bot(text=f'/download {text}', catch=True)
                except Exception as e:
                    await client.send_message(chat_id=message.chat.id,
                                              text=f'{e}\n🚫🚫🚫请使用以下命令,分配下载任务:\n`/download {text}`',
                                              disable_web_page_preview=True)
            else:
                await client.send_message(chat_id=message.chat.id,
                                          text=f'❗️❗️❗️请使用以下命令,分配下载任务:\n`/download https://t.me/x/x`',
                                          disable_web_page_preview=True)
        elif len(text) <= 25 or text == '/download https://t.me/x/x' or text.endswith('.txt'):
            await self.help(client, message)
            await client.send_message(chat_id=message.chat.id,
                                      text='⁉️⁉️⁉️链接错误,请查看帮助后重试。',
                                      disable_web_page_preview=True)
        else:
            link: list = text.split()
            link.remove('/download') if '/download' in link else None
            right_link: set = set([_ for _ in link if _.startswith('https://t.me/')])
            invalid_link: set = set([_ for _ in link if not _.startswith('https://t.me/')])
            last_bot_message = await client.send_message(chat_id=message.chat.id,
                                                         text=self.update_text(right_link=right_link,
                                                                               invalid_link=invalid_link),
                                                         disable_web_page_preview=True)
            if right_link:
                return {'right_link': right_link,
                        'invalid_link': invalid_link,
                        'last_bot_message': last_bot_message}
            else:
                return None

    async def help(self,
                   client: pyrogram.Client,
                   message: pyrogram.types.Message) -> None:
        func_keyboard = InlineKeyboardMarkup(
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
                        BotButton.CLOSE_NOTICE if self.gc.config.get(BotCallbackText.NOTICE) else BotButton.OPEN_NOTICE,
                        callback_data=BotCallbackText.NOTICE
                    )
                ]
            ]
        )

        msg = (
            f'`\n💎 {SOFTWARE_FULL_NAME} v{__version__} 💎\n'
            f'©️ {__copyright__.replace(" <https://github.com/Gentlesprite>", ".")}\n'
            f'📖 Licensed under the terms of the {__license__}.`\n'
            f'🎮️ 可用命令:\n'
            f'🛎️ {BotCommandText.with_description(BotCommandText.HELP)}\n'
            f'📁 {BotCommandText.with_description(BotCommandText.DOWNLOAD)}\n'
            f'📝 {BotCommandText.with_description(BotCommandText.TABLE)}\n'
            f'❌ {BotCommandText.with_description(BotCommandText.EXIT)}\n'
        )

        await client.send_message(chat_id=message.chat.id,
                                  text=msg,
                                  disable_web_page_preview=True,
                                  reply_markup=func_keyboard)

    @staticmethod
    async def callback_data(client: pyrogram.Client, callback_query: CallbackQuery) -> str or None:
        await callback_query.answer()
        data = callback_query.data
        if not data:
            return None
        if isinstance(data, str):
            support_data: list = [_ for _ in BotCallbackText()]
            for i in support_data:
                if data == i:
                    return i

    @staticmethod
    async def table(client: pyrogram.Client,
                    message: pyrogram.types.Message) -> None:
        choice_keyboard = InlineKeyboardMarkup(
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
        await client.send_message(chat_id=message.chat.id,
                                  text='🧐🧐🧐请选择输出「统计表」的类型:',
                                  disable_web_page_preview=True,
                                  reply_markup=choice_keyboard)

    @staticmethod
    async def get_forward_link_from_bot(client: pyrogram.Client,
                                        message: pyrogram.types.Message) -> Dict[str, list] or None:

        text: str = message.text
        args = text.split(maxsplit=5)
        if text == '/forward' or len(args) <= 1:
            await client.send_message(
                message.from_user.id,
                '❌❌❌命令格式无效,请使用`/forward https://t.me/c/src_chat https://t.me/c/dst_chat 1 100`'
            )
            return None
        try:
            start_id: int = int(args[3])
            end_id: int = int(args[4])
            if end_id:
                if start_id > end_id:
                    raise ValueError('起始ID<结束ID。')
            message_ids: list = [start_id, end_id]
        except Exception as e:
            await client.send_message(
                message.from_user.id,
                f'❌❌❌命令错误,{e}。'
            )
            return None
        return {'origin_link': args[1], 'target_link': args[2], 'message_ids': message_ids}

    async def exit(self, client: pyrogram.Client,
                   message: pyrogram.types.Message) -> None:
        last_message = await client.send_message(chat_id=message.chat.id,
                                                 text='🫡🫡🫡已收到退出命令。',
                                                 disable_web_page_preview=True)
        self.is_bot_running = False
        await self.edit_message_text(client=client,
                                     chat_id=message.chat.id,
                                     last_message_id=last_message.id,
                                     text='👌👌👌退出成功。')
        raise SystemExit(0)

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
                    self.help,
                    filters=pyrogram.filters.command(['help', 'start']) & pyrogram.filters.user(self.root)
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
                    self.get_link_from_bot,
                    filters=pyrogram.filters.regex(r'^https://t.me.*') & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                CallbackQueryHandler(
                    self.callback_data,
                    filters=pyrogram.filters.user(self.root) & pyrogram.filters.user(self.root)
                )
            )
            self.bot.add_handler(
                MessageHandler(
                    self.process_error_message,
                    filters=pyrogram.filters.user(self.root)
                )
            )
            self.is_bot_running: bool = True
            if self.gc.config.get('notice'):
                await self.send_message_to_bot(text='/start')
                notice_status = BotButton.OPEN_NOTICE
            else:
                notice_status = BotButton.CLOSE_NOTICE
            return f'🤖「机器人」启动成功。({notice_status})'
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
                return await self.user.send_message(chat_id=bot_username, text=text, disable_web_page_preview=True)
        except Exception as e:
            if catch:
                raise Exception(str(e))
            else:
                return e

    @staticmethod
    def update_text(right_link: set, invalid_link: set, exist_link: set or None = None):
        n = '\n'
        right_msg = f'{BotMessage.RIGHT}`{n.join(right_link)}`' if right_link else ''
        invalid_msg = f'{BotMessage.INVALID}`{n.join(invalid_link)}`{n}(具体原因请前往终端查看报错信息)' if invalid_link else ''
        if exist_link:
            exist_msg = f'{BotMessage.EXIST}`{n.join(exist_link)}`' if exist_link else ''
            return right_msg + n + exist_msg + n + invalid_msg
        else:
            return right_msg + n + invalid_msg

    @staticmethod
    async def edit_message_text(client: pyrogram.Client,
                                chat_id: Union[int, str],
                                last_message_id: int,
                                text: str,
                                disable_web_page_preview: bool = True):
        try:
            await client.edit_message_text(chat_id=chat_id,
                                           message_id=last_message_id,
                                           text=text,
                                           disable_web_page_preview=disable_web_page_preview)
        except MessageNotModified:
            pass

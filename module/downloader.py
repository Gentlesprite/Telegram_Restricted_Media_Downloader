# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023/10/3 1:00:03
# File:downloader.py
import os
import re
import sys
import asyncio
from functools import partial
from sqlite3 import OperationalError
from typing import Tuple, Union, Callable

import pyrogram
from pyrogram.handlers import MessageHandler
from pyrogram.types.messages_and_media import ReplyParameters
from pyrogram.types.bots_and_keyboards import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.bad_request_400 import ChannelPrivate as ChannelPrivate_400
from pyrogram.errors.exceptions.bad_request_400 import ChatForwardsRestricted as ChatForwardsRestricted_400
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as ChannelPrivate_406
from pyrogram.errors.exceptions.not_acceptable_406 import ChatForwardsRestricted as ChatForwardsRestricted_406
from pyrogram.errors.exceptions.unauthorized_401 import SessionRevoked, AuthKeyUnregistered, SessionExpired, \
    Unauthorized
from pyrogram.errors.exceptions.bad_request_400 import MsgIdInvalid, UsernameInvalid, ChannelInvalid, \
    BotMethodInvalid, MessageNotModified, UsernameNotOccupied

from module import console, log, utils, LINK_PREVIEW_OPTIONS, SLEEP_THRESHOLD
from module.bot import Bot
from module.task import Task
from module.language import _t
from module.util import safe_message
from module.app import Application, MetaData
from module.util import truncate_display_filename
from module.stdio import ProgressBar, Base64Image
from module.enums import LinkType, DownloadStatus, KeyWord, BotCallbackText, BotButton, BotMessage, DownloadType
from module.path_tool import is_file_duplicate, safe_delete, get_file_size, split_path, compare_file_size, \
    move_to_save_directory


class TelegramRestrictedMediaDownloader(Bot):

    def __init__(self):
        super().__init__()
        self.loop = asyncio.get_event_loop()
        self.event = asyncio.Event()
        self.queue = asyncio.Queue()
        self.app = Application()
        self.is_running: bool = False
        self.running_log: set = set()
        self.running_log.add(self.is_running)
        self.pb = ProgressBar()

    async def get_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        link_meta: Union[dict, None] = await super().get_link_from_bot(client, message)
        if link_meta is None:
            return None
        right_link: set = link_meta.get('right_link')
        invalid_link: set = link_meta.get('invalid_link')
        last_bot_message: Union[pyrogram.types.Message, None] = link_meta.get('last_bot_message')
        exist_link: set = set([_ for _ in right_link if _ in self.bot_task_link])
        exist_link.update(right_link & Task.COMPLETE_LINK)
        right_link -= exist_link
        if last_bot_message:
            await self.safe_edit_message(
                client=client,
                message=message,
                last_message_id=last_bot_message.id,
                text=self.update_text(
                    right_link=right_link,
                    exist_link=exist_link,
                    invalid_link=invalid_link
                )
            )
        else:
            log.warning('消息过长编辑频繁,暂时无法通过机器人显示通知。')
        links: Union[set, None] = self.__process_links(link=list(right_link))
        if links is None:
            return None
        for link in links:
            task: dict = await self.__create_download_task(link=link, retry=None)
            invalid_link.add(link) if task.get('status') == DownloadStatus.FAILURE else self.bot_task_link.add(link)
        right_link -= invalid_link
        await self.safe_edit_message(
            client=client,
            message=message,
            last_message_id=last_bot_message.id,
            text=self.update_text(
                right_link=right_link,
                exist_link=exist_link,
                invalid_link=invalid_link
            )
        )

    @staticmethod
    async def __send_pay_qr(client: pyrogram.Client, chat_id, load_name: str) -> dict:
        e_code: dict = {'e_code': None}
        try:
            last_msg = await client.send_message(
                chat_id=chat_id,
                text=f'🙈🙈🙈请稍后🙈🙈🙈{load_name}加载中. . .',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            await client.send_photo(
                chat_id=chat_id,
                photo=Base64Image.base64_to_binary_io(Base64Image.pay),
                disable_notification=True
            )
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=last_msg.id,
                text=f'🐵🐵🐵{load_name}加载成功!🐵🐵🐵'
            )
        except Exception as e:
            e_code['e_code'] = e
        finally:
            return e_code

    async def start(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        self.last_client: pyrogram.Client = client
        self.last_message: pyrogram.types.Message = message
        if self.gc.config.get(BotCallbackText.NOTICE):
            chat_id = message.from_user.id
            res: dict = await self.__send_pay_qr(client=client, chat_id=chat_id, load_name='机器人')
            msg = '😊😊😊欢迎使用😊😊😊' if res.get('e_code') else '😊😊😊欢迎使用😊😊😊您的支持是我持续更新的动力。'
            await client.send_message(chat_id=chat_id, text=msg, link_preview_options=LINK_PREVIEW_OPTIONS)
            await super().start(client, message)

    async def callback_data(self, client: pyrogram.Client, callback_query: pyrogram.types.CallbackQuery):
        callback_data = await super().callback_data(client, callback_query)
        if callback_data is None:
            return None
        elif callback_data == BotCallbackText.NOTICE:
            try:
                self.gc.config[BotCallbackText.NOTICE] = not self.gc.config.get(BotCallbackText.NOTICE)
                self.gc.save_config(self.gc.config)
                new_keyboard = []
                for row in callback_query.message.reply_markup.inline_keyboard:
                    new_row = []
                    for button in row:
                        if getattr(button, 'callback_data', None) == BotCallbackText.NOTICE:
                            new_row.append(
                                InlineKeyboardButton(
                                    text=BotButton.CLOSE_NOTICE if self.gc.config.get(
                                        BotCallbackText.NOTICE) else BotButton.OPEN_NOTICE,
                                    callback_data=button.callback_data
                                )
                            )
                            continue
                        new_row.append(button)
                    new_keyboard.append(new_row)
                await callback_query.message.edit_reply_markup(
                    InlineKeyboardMarkup(new_keyboard)
                )
            except MessageNotModified:
                pass
            except Exception as e:
                await callback_query.message.reply_text('关闭提醒失败\n(具体原因请前往终端查看报错信息)')
                log.error(f'关闭提醒失败,{_t(KeyWord.REASON)}:"{e}"')
        elif callback_data == BotCallbackText.PAY:
            res: dict = await self.__send_pay_qr(
                client=client,
                chat_id=callback_query.message.from_user.id,
                load_name='收款码'
            )
            MetaData.pay()
            if res.get('e_code'):
                msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」十分感谢您的支持!'
            else:
                msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」与「对话框」十分感谢您的支持!'
            await callback_query.message.reply_text(msg)
        elif callback_data == BotCallbackText.LINK_TABLE:
            res: Union[bool, str] = self.app.print_link_table(Task.LINK_INFO)
            if isinstance(res, str):
                await callback_query.message.edit_text(
                    '😵‍💫😵‍💫😵‍💫`链接统计表`打印失败。\n(具体原因请前往终端查看报错信息)')
            elif isinstance(res, bool) and res is True:
                await callback_query.message.edit_text('🫡🫡🫡`链接统计表`已发送至您的「终端」请注意查收。')
            else:
                await callback_query.message.edit_text('😵😵😵没有链接需要统计。')
        elif callback_data == BotCallbackText.COUNT_TABLE:
            self.app.print_count_table(record_dtype=self.app.record_dtype)
            await callback_query.message.edit_text('👌👌👌`计数统计表`已发送至您的「终端」请注意查收。')
        elif callback_data == BotCallbackText.BACK_HELP:
            await callback_query.message.delete()
            await self.help(client, callback_query.message)
        elif callback_data == BotCallbackText.DOWNLOAD:
            command: str = ''
            data: list = callback_data.split()
            callback_data_len: int = len(data)
            if callback_data_len == 1:
                link = data[0]
                command = f'/download {link}'
            elif callback_data_len == 3:
                origin_link, start_id, end_id = data
                command = f'/download {origin_link} {start_id} {end_id}'
            await self.app.client.send_message(
                chat_id=callback_query.message.from_user.id,
                text=command,
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            await callback_query.message.edit_reply_markup(
                InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            text=BotButton.TASK_ASSIGN,
                            callback_data=BotCallbackText.NULL
                        )
                    ]
                ])
            )
        elif callback_data == BotCallbackText.LOOKUP_LISTEN_INFO:
            await self.app.client.send_message(
                chat_id=callback_query.message.from_user.id,
                text='/listen_info',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
        elif callback_data.startswith((BotCallbackText.REMOVE_LISTEN_DOWNLOAD, BotCallbackText.REMOVE_LISTEN_FORWARD)):
            msg: str = ''
            await callback_query.message.edit_reply_markup()
            args: list = callback_data.split()
            if len(args) == 2:
                msg: str = '✅已移除'
                channel: str = args[1]
                self.app.client.remove_handler(self.listen_download_chat.get(channel))
                self.listen_download_chat.pop(channel)
            elif len(args) == 3:
                msg: str = '✅已移除'
                channel: str = f'{args[1]} {args[2]}'
                self.app.client.remove_handler(self.listen_forward_chat.get(channel))
                self.listen_forward_chat.pop(channel)
            await callback_query.message.edit_text(callback_query.message.text.replace('请选择是否移除', msg))

    async def __get_chat(
            self, bot_client: pyrogram.Client,
            bot_message: pyrogram.types.Message,
            chat_id: Union[int, str],
            error_msg: str
    ) -> Union[pyrogram.types.Chat, None]:
        try:
            chat = await self.app.client.get_chat(chat_id)
            return chat
        except UsernameNotOccupied:
            await bot_client.send_message(
                chat_id=bot_message.from_user.id,
                reply_parameters=ReplyParameters(message_id=bot_message.id),
                text=error_msg
            )
            return None

    async def get_forward_link_from_bot(
            self, client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> Union[dict, None]:
        meta: Union[dict, None] = await super().get_forward_link_from_bot(client, message)
        if meta is None:
            return None
        origin_link: str = meta.get('origin_link')
        target_link: str = meta.get('target_link')
        start_id: int = meta.get('message_range')[0]
        end_id: int = meta.get('message_range')[1]
        try:
            origin_meta: Union[dict, None] = await self.__extract_link_content(origin_link, only_chat_id=True)
            target_meta: Union[dict, None] = await self.__extract_link_content(target_link, only_chat_id=True)
            if not all([origin_meta, target_meta]):
                raise Exception('Invalid origin_link or target_link.')
            origin_chat: Union[pyrogram.types.Chat, None] = await self.__get_chat(
                bot_client=client, bot_message=message,
                chat_id=origin_meta.get('chat_id'),
                error_msg=f'⬇️⬇️⬇️原始频道不存在⬇️⬇️⬇️\n{origin_link}'
            )
            target_chat: Union[pyrogram.types.Chat, None] = await self.__get_chat(
                bot_client=client, bot_message=message,
                chat_id=target_meta.get('chat_id'),
                error_msg=f'⬇️⬇️⬇️目标频道不存在⬇️⬇️⬇️\n{target_link}'
            )
            if not all([origin_chat, target_chat]):
                return None
            me = await client.get_me()
            if target_chat.id == me.id:
                await client.send_message(
                    chat_id=message.from_user.id,
                    text='⚠️⚠️⚠️无法转发到此机器人⚠️⚠️⚠️',
                    reply_parameters=ReplyParameters(message_id=message.id),
                )
                return None
            last_message: Union[pyrogram.types.Message, None] = None
            async for i in self.app.client.get_chat_history(
                    chat_id=origin_chat.id,
                    offset_id=start_id,
                    max_id=end_id,
                    reverse=True
            ):
                try:
                    await self.app.client.forward_messages(
                        chat_id=target_chat.id,
                        from_chat_id=origin_chat.id,
                        message_ids=i.id,
                        disable_notification=True,
                        hide_sender_name=True,
                        hide_captions=True,
                        protect_content=False
                    )
                except (ChatForwardsRestricted_400, ChatForwardsRestricted_406):
                    raise
                except Exception as e:
                    if not last_message:
                        last_message = await client.send_message(
                            chat_id=message.from_user.id,
                            reply_parameters=ReplyParameters(message_id=message.id),
                            link_preview_options=LINK_PREVIEW_OPTIONS,
                            text=BotMessage.INVALID
                        )
                    last_message: Union[pyrogram.types.Message, str, None] = await self.safe_edit_message(
                        client=client,
                        message=message,
                        last_message_id=last_message.id,
                        text=safe_message(f'{last_message.text}\n{origin_link}/{i.id}')
                    )
                    log.warning(f'{_t(KeyWord.LINK)}:"{origin_link}/{i.id}"无效,{_t(KeyWord.REASON)}:{e}')
            if isinstance(last_message, str):
                log.warning('消息过长编辑频繁,暂时无法通过机器人显示通知。')
            if not last_message:
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    text='🌟🌟🌟转发任务已完成🌟🌟🌟',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            BotButton.CLICK_VIEW,
                            url=target_link
                        )
                    ]])
                )
            else:
                await self.safe_edit_message(
                    client=client,
                    message=message,
                    last_message_id=last_message.id,
                    text=safe_message(f'{last_message.text}\n🌟🌟🌟转发任务已完成🌟🌟🌟'),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            BotButton.CLICK_VIEW,
                            url=target_link
                        )
                    ]]))
        except (ChatForwardsRestricted_400, ChatForwardsRestricted_406):
            BotCallbackText.DOWNLOAD = f'{origin_link} {start_id} {end_id}'
            await client.send_message(
                chat_id=message.from_user.id,
                text=f'⚠️⚠️⚠️无法转发⚠️⚠️⚠️\n`{origin_link}`存在内容保护限制。',
                reply_parameters=ReplyParameters(message_id=message.id),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        BotButton.CLICK_DOWNLOAD,
                        callback_data=BotCallbackText.DOWNLOAD
                    )
                ]]))
        except AttributeError as e:
            log.exception(f'转发时遇到错误,{_t(KeyWord.REASON)}:"{e}"')
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⬇️⬇️⬇️出错了⬇️⬇️⬇️\n(具体原因请前往终端查看报错信息)'
            )
        except (ValueError, KeyError, UsernameInvalid):
            msg: str = ''
            if any('/c' in link for link in (origin_link, target_link)):
                msg = '(私密频道或话题频道必须让当前账号加入该频道)'
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='❌❌❌没有找到有效链接❌❌❌\n' + msg
            )
        except Exception as e:
            log.exception(f'转发时遇到错误,{_t(KeyWord.REASON)}:"{e}"')
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⬇️⬇️⬇️出错了⬇️⬇️⬇️\n(具体原因请前往终端查看报错信息)'
            )

    async def on_listen(
            self,
            client: pyrogram.Client,
            message: pyrogram.types
    ):
        meta: Union[dict, None] = await super().on_listen(client, message)
        if meta is None:
            return None

        async def add_listen_chat(_link: str, _listen_chat: dict, _callback: callable) -> bool:
            if _link not in _listen_chat:
                try:
                    chat = await self.user.get_chat(_link)
                    handler = MessageHandler(_callback, filters=pyrogram.filters.chat(chat.id))
                    _listen_chat[_link] = handler
                    self.user.add_handler(handler)
                    return True
                except Exception as e:
                    await client.send_message(
                        chat_id=message.from_user.id,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        link_preview_options=LINK_PREVIEW_OPTIONS,
                        text=f'⚠️⚠️⚠️无法读取⚠️⚠️⚠️\n`{_link}`\n(具体原因请前往终端查看报错信息)'
                    )
                    log.error(f'读取频道"{_link}"时遇到错误,{_t(KeyWord.REASON)}:"{e}"')
                    return False
            else:
                await self.cancel_listen(client, message, _link, command)
                return False

        links: list = meta.get('links')
        command: str = meta.get('command')
        if command == '/listen_download':
            last_message: Union[pyrogram.types.Message, None] = None
            for link in links:
                if await add_listen_chat(link, self.listen_download_chat, self.listen_download):
                    if not last_message:
                        last_message: Union[pyrogram.types.Message, str, None] = await client.send_message(
                            chat_id=message.from_user.id,
                            reply_parameters=ReplyParameters(message_id=message.id),
                            link_preview_options=LINK_PREVIEW_OPTIONS,
                            text=f'✅新增`监听下载频道`频道:\n')
                    last_message: Union[pyrogram.types.Message, str, None] = await self.safe_edit_message(
                        client=client,
                        message=message,
                        last_message_id=last_message.id,
                        text=safe_message(f'{last_message.text}\n{link}'),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton(
                                BotButton.LOOKUP_LISTEN_INFO,
                                callback_data=BotCallbackText.LOOKUP_LISTEN_INFO
                            )
                        ]])
                    )
        elif command == '/listen_forward':
            listen_link, target_link = links
            if await add_listen_chat(f'{listen_link} {target_link}', self.listen_forward_chat, self.listen_forward):
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                    text=f'✅新增`监听转发`频道:\n{listen_link} ➡️ {target_link}',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            BotButton.LOOKUP_LISTEN_INFO,
                            callback_data=BotCallbackText.LOOKUP_LISTEN_INFO
                        )
                    ]]))

    async def listen_download(
            self,
            client: pyrogram.Client,
            message: pyrogram.types
    ):
        try:
            await self.__create_download_task(link=message.link, single_link=True)
        except Exception as e:
            log.exception(f'监听下载出现错误,{_t(KeyWord.REASON)}:{e}')

    async def listen_forward(
            self,
            client: pyrogram.Client,
            message: pyrogram.types
    ):
        try:
            link: str = message.link
            meta = await self.__extract_link_content(link=link)
            listen_chat_id = meta.get('chat_id')
            for m in self.listen_forward_chat:
                listen_link, target_link = m.split()
                _listen_link_meta = await self.__extract_link_content(link=listen_link, only_chat_id=True)
                _target_link_meta = await self.__extract_link_content(link=target_link, only_chat_id=True)
                _listen_chat_id = _listen_link_meta.get('chat_id')
                _target_link_id = _target_link_meta.get('chat_id')
                if listen_chat_id == _listen_chat_id:
                    try:
                        await self.app.client.forward_messages(
                            chat_id=_target_link_id,
                            from_chat_id=_listen_chat_id,
                            message_ids=message.id,
                            disable_notification=True,
                            hide_sender_name=True,
                            hide_captions=True,
                            protect_content=False
                        )
                        console.log(
                            f'{_t(KeyWord.LINK)}:"{link}" -> "{target_link}",'
                            f'{_t(KeyWord.STATUS)}:转发成功。'
                        )
                    except (ChatForwardsRestricted_400, ChatForwardsRestricted_406):
                        BotCallbackText.DOWNLOAD = f'https://t.me/{meta.get('chat_id')}/{meta.get('message').id}'
                        await self.bot.send_message(
                            chat_id=message.from_user.id,
                            text=f'⚠️⚠️⚠️无法转发⚠️⚠️⚠️\n`{listen_chat_id}`存在内容保护限制。',
                            reply_parameters=ReplyParameters(message_id=message.id),
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton(
                                    BotButton.CLICK_DOWNLOAD,
                                    callback_data=BotCallbackText.DOWNLOAD
                                )
                            ]]))
        except Exception as e:
            log.exception(f'监听转发出现错误,{_t(KeyWord.REASON)}:{e}')

    async def __extract_link_content(
            self, link: str,
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
        if link.count('/') >= 5:
            if link.startswith('https://t.me/c/'):
                count: int = link.split('https://t.me/c/')[1].count('/')
                record_type.add(LinkType.TOPIC) if count == 2 else None
            elif link.startswith('https://t.me'):
                record_type.add(LinkType.TOPIC)
        # https://github.com/KurimuzonAkuma/pyrogram/blob/dev/pyrogram/methods/messages/get_messages.py#L101
        if only_chat_id:  # todo 话题频道的转发的关键在于解析链接时获取到正确的topic_id。
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
                    async for comment in self.app.client.get_discussion_replies(chat_id, message_id):
                        if not any(getattr(comment, dtype) for dtype in DownloadType()):
                            continue
                        if single_link:  # 处理单链接情况。
                            if '=' in origin_link and int(origin_link.split('=')[-1]) != comment.id:
                                continue
                        comment_message.append(comment)
                message = await self.app.client.get_messages(chat_id=chat_id, message_ids=message_id)
                is_group, group_message = await self.__is_group(message)
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

    async def resume_download(
            self,
            message: Union[pyrogram.types, str],
            file_name: str,
            progress: Callable = None,
            progress_args: tuple = (),
            chunk_size: int = 1024 * 1024,
            compare_size: Union[int, None] = None  # 不为None时,将通过大小比对判断是否为完整文件。
    ) -> str:
        temp_path = f'{file_name}.temp'
        if os.path.exists(file_name) and compare_size:  # 检查是否已完整下载。
            local_file_size: int = get_file_size(file_path=temp_path)
            if compare_file_size(a_size=local_file_size, b_size=compare_size):
                console.log(
                    f'{_t(KeyWord.RESUME)}:"{file_name}",'
                    f'{_t(KeyWord.STATUS)}:{_t(KeyWord.ALREADY_EXIST)}')
                return file_name
        downloaded = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0  # 获取已下载的字节数。
        if downloaded == 0:
            mode = 'wb'
        else:
            mode = 'ab'
            console.log(
                f'{_t(KeyWord.RESUME)}:"{file_name}",'
                f'{_t(KeyWord.ERROR_SIZE)}:{MetaData.suitable_units_display(downloaded)}。')
        with open(file=temp_path, mode=mode) as f:
            skip_chunks: int = downloaded // chunk_size  # 计算要跳过的块数。
            async for chunk in self.app.client.stream_media(message=message, offset=skip_chunks):
                f.write(chunk)
                downloaded += len(chunk)
                progress(downloaded, *progress_args)
        os.rename(temp_path, file_name)  # 下载完成后重命名文件。
        return file_name

    @staticmethod
    async def __is_group(message) -> Tuple[Union[bool, None], Union[list, None]]:
        try:
            return True, await message.get_media_group()
        except ValueError:
            return False, None  # v1.0.4 修改单文件无法下载问题。
        except AttributeError:
            return None, None

    async def __add_task(
            self,
            chat_id: Union[str, int],
            link_type: str,
            link: str,
            message: Union[pyrogram.types.Message, list],
            retry: dict
    ) -> None:
        retry_count = retry.get('count')
        retry_id = retry.get('id')
        if isinstance(message, list):
            for _message in message:
                if retry_count != 0:
                    if _message.id == retry_id:
                        await self.__add_task(chat_id, link_type, link, _message, retry)
                        break
                else:
                    await self.__add_task(chat_id, link_type, link, _message, retry)
        else:
            _task = None
            valid_dtype, is_document_type_valid = self.app.get_valid_dtype(message).values()
            if valid_dtype in self.app.download_type and is_document_type_valid:
                # 如果是匹配到的消息类型就创建任务。
                console.log(
                    f'{_t(KeyWord.CHANNEL)}:"{chat_id}",'  # 频道名。
                    f'{_t(KeyWord.LINK)}:"{link}",'  # 链接。
                    f'{_t(KeyWord.LINK_TYPE)}:{_t(link_type)}。'  # 链接类型。
                )
                while self.app.current_task_num >= self.app.max_download_task:  # v1.0.7 增加下载任务数限制。
                    await self.event.wait()
                    self.event.clear()
                file_id, temp_file_path, sever_file_size, file_name, save_directory, format_file_size = \
                    self.app.get_media_meta(
                        message=message,
                        dtype=valid_dtype).values()
                retry['id'] = file_id
                if is_file_duplicate(
                        save_directory=save_directory,
                        sever_file_size=sever_file_size
                ):  # 检测是否存在。
                    self.__complete_call(
                        sever_file_size=sever_file_size,
                        temp_file_path=temp_file_path,
                        link=link,
                        file_name=file_name,
                        retry_count=retry_count,
                        file_id=file_id,
                        format_file_size=format_file_size,
                        task_id=None,
                        _future=save_directory
                    )
                else:
                    console.log(
                        f'{_t(KeyWord.FILE)}:"{file_name}",'
                        f'{_t(KeyWord.SIZE)}:{format_file_size},'
                        f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.DOWNLOADING))},'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.DOWNLOADING)}。'
                    )
                    task_id = self.pb.progress.add_task(
                        description='',
                        filename=truncate_display_filename(file_name),
                        info=f'0.00B/{format_file_size}',
                        total=sever_file_size
                    )
                    _task = self.loop.create_task(
                        self.resume_download(
                            message=message,
                            file_name=temp_file_path,
                            progress=self.pb.download_bar,
                            progress_args=(sever_file_size, self.pb.progress, task_id),
                            compare_size=sever_file_size
                        )
                    )
                    MetaData.print_current_task_num(self.app.current_task_num)
                    _task.add_done_callback(
                        partial(
                            self.__complete_call, sever_file_size,
                            temp_file_path,
                            link,
                            file_name,
                            retry_count,
                            file_id,
                            format_file_size,
                            task_id)
                    )
            else:
                _error = '不支持或被忽略的类型(已取消)。'
                Task.LINK_INFO.get(link).get('error_msg')['all_member'] = _error.replace('。', '')
                console.log(
                    f'{_t(KeyWord.CHANNEL)}:"{chat_id}",'  # 频道名。
                    f'{_t(KeyWord.LINK)}:"{link}",'  # 链接。
                    f'{_t(KeyWord.LINK_TYPE)}:{_error}'  # 链接类型。
                )
            self.queue.put_nowait(_task) if _task else None

    def __check_download_finish(
            self, sever_file_size: int,
            temp_file_path: str,
            save_directory: str,
            with_move: bool = True
    ) -> bool:
        """检测文件是否下完。"""
        temp_ext: str = '.temp'
        local_file_size: int = get_file_size(file_path=temp_file_path, temp_ext=temp_ext)
        format_local_size: str = MetaData.suitable_units_display(local_file_size)
        format_sever_size: str = MetaData.suitable_units_display(sever_file_size)
        _file_path: str = os.path.join(save_directory, split_path(temp_file_path).get('file_name'))
        file_path: str = _file_path[:-len(temp_ext)] if _file_path.endswith(temp_ext) else _file_path
        if compare_file_size(a_size=local_file_size, b_size=sever_file_size):
            if with_move:
                result: str = move_to_save_directory(
                    temp_file_path=temp_file_path,
                    save_directory=save_directory
                ).get('e_code')
                log.warning(result) if result is not None else None
            console.log(
                f'{_t(KeyWord.FILE)}:"{file_path}",'
                f'{_t(KeyWord.SIZE)}:{format_local_size},'
                f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(temp_file_path, DownloadStatus.SUCCESS))},'
                f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SUCCESS)}。',
            )
            return True
        console.log(
            f'{_t(KeyWord.FILE)}:"{file_path}",'
            f'{_t(KeyWord.ERROR_SIZE)}:{format_local_size},'
            f'{_t(KeyWord.ACTUAL_SIZE)}:{format_sever_size},'
            f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(temp_file_path, DownloadStatus.FAILURE))},'
            f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}。'
        )
        return False

    @Task.on_complete
    def __complete_call(
            self,
            sever_file_size,
            temp_file_path,
            link,
            file_name,
            retry_count,
            file_id,
            format_file_size,
            task_id,
            _future
    ):
        if task_id is None:
            if retry_count == 0:
                console.log(f'{_t(KeyWord.ALREADY_EXIST)}:"{_future}"')
                console.log(
                    f'{_t(KeyWord.FILE)}:"{file_name}",'
                    f'{_t(KeyWord.SIZE)}:{format_file_size},'
                    f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.SKIP))},'
                    f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SKIP)}。', style='#e6db74'
                )
        else:
            self.app.current_task_num -= 1
            self.event.set()  # v1.3.4 修复重试下载被阻塞的问题。
            self.queue.task_done()
            if self.__check_download_finish(
                    sever_file_size=sever_file_size,
                    temp_file_path=temp_file_path,
                    save_directory=self.app.save_directory,
                    with_move=True
            ):
                MetaData.print_current_task_num(self.app.current_task_num)
            else:
                if retry_count < self.app.max_retry_count:
                    retry_count += 1
                    task = self.loop.create_task(
                        self.__create_download_task(link=link, retry={'id': file_id, 'count': retry_count}))
                    task.add_done_callback(
                        partial(
                            self.__retry_call,
                            f'{_t(KeyWord.RELOAD)}:"{file_name}",'
                            f'{_t(KeyWord.RELOAD_TIMES)}:{retry_count}/{self.app.max_retry_count}。'
                        )
                    )
                else:
                    _error = f'(达到最大重试次数:{self.app.max_retry_count}次)。'
                    console.log(
                        f'{_t(KeyWord.FILE)}:"{file_name}",'
                        f'{_t(KeyWord.SIZE)}:{format_file_size},'
                        f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.FAILURE))},'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}'
                        f'{_error}'
                    )
                    Task.LINK_INFO.get(link).get('error_msg')[file_name] = _error.replace('。', '')
                    self.bot_task_link.discard(link)
                link, file_name = None, None
            self.pb.progress.remove_task(task_id=task_id)
        return link, file_name

    @Task.on_create_task
    async def __create_download_task(
            self,
            link: str,
            retry: Union[dict, None] = None,
            single_link: bool = False
    ) -> dict:
        retry = retry if retry else {'id': -1, 'count': 0}
        try:
            meta: dict = await self.__extract_link_content(link=link, single_link=single_link)
            link_type, chat_id, message, member_num = meta.values()
            Task.LINK_INFO.get(link)['link_type'] = link_type
            Task.LINK_INFO.get(link)['member_num'] = member_num
            await self.__add_task(chat_id, link_type, link, message, retry)
            return {
                'chat_id': chat_id,
                'link_type': link_type,
                'member_num': member_num,
                'status': DownloadStatus.DOWNLOADING,
                'e_code': None
            }
        except UnicodeEncodeError as e:
            return {
                'chat_id': None,
                'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg':
                        '频道标题存在特殊字符,请移步终端下载'
                }
            }
        except MsgIdInvalid as e:
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg':
                        '消息不存在,可能已删除'
                }
            }
        except UsernameInvalid as e:
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg':
                        '频道用户名无效,该链接的频道用户名可能已更改或频道已解散'
                }
            }
        except ChannelInvalid as e:
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg':
                        '频道可能为私密频道或话题频道,请让当前账号加入该频道后再重试'
                }
            }
        except ChannelPrivate_400 as e:
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg':
                        '频道可能为私密频道或话题频道,当前账号可能已不在该频道,请让当前账号加入该频道后再重试'
                }
            }
        except ChannelPrivate_406 as e:
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg':
                        '频道为私密频道,无法访问'
                }
            }
        except BotMethodInvalid as e:
            res: bool = safe_delete(file_p_d=os.path.join(self.app.DIRECTORY_NAME, 'sessions'))
            error_msg: str = '已删除旧会话文件' if res else '请手动删除软件目录下的sessions文件夹'
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg':
                        '检测到使用了「bot_token」方式登录了主账号的行为,'
                        f'{error_msg},重启软件以「手机号码」方式重新登录'
                }
            }
        except ValueError as e:
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg': '没有找到有效链接'
                }
            }
        except UsernameNotOccupied as e:
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e), 'error_msg': '频道不存在'
                }
            }
        except Exception as e:
            log.exception(e)
            return {
                'chat_id': None, 'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg': '未收录到的错误'
                }
            }

    def __process_links(self, link: Union[str, list]) -> Union[set, None]:
        """将链接(文本格式或链接)处理成集合。"""
        start_content: str = 'https://t.me/'
        links: set = set()
        if isinstance(link, str):
            if link.endswith('.txt') and os.path.isfile(link):
                with open(file=link, mode='r', encoding='UTF-8') as _:
                    _links: list = [content.strip() for content in _.readlines()]
                for i in _links:
                    if i.startswith(start_content):
                        links.add(i)
                        self.bot_task_link.add(i)
                    elif i == '':
                        continue
                    else:
                        log.warning(f'"{i}"是一个非法链接,{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SKIP)}。')
            elif link.startswith(start_content):
                links.add(link)
        elif isinstance(link, list):
            for i in link:
                _link: Union[set, None] = self.__process_links(link=i)
                if _link is not None:
                    links.update(_link)
        if links:
            return links
        elif not self.app.bot_token:
            console.log('没有找到有效链接,程序已退出。', style='#FF4689')
            sys.exit(0)
        else:
            console.log('没有找到有效链接。', style='#FF4689')
            return None

    @staticmethod
    def __retry_call(notice, _future):
        console.log(notice, style='#FF4689')

    async def __download_media_from_links(self) -> None:
        await self.app.client.start(use_qr=False)
        self.pb.progress.start()  # v1.1.8修复登录输入手机号不显示文本问题。
        if self.app.bot_token is not None:
            result = await self.start_bot(
                self.app.client,
                pyrogram.Client(
                    name=self.BOT_NAME,
                    api_hash=self.app.api_hash,
                    api_id=self.app.api_id,
                    bot_token=self.app.bot_token,
                    workdir=self.app.work_directory,
                    proxy=self.app.enable_proxy,
                    sleep_threshold=SLEEP_THRESHOLD
                )
            )
            console.log(result, style='#B1DB74' if self.is_bot_running else '#FF4689')
        self.is_running = True
        self.running_log.add(self.is_running)
        links: Union[set, None] = self.__process_links(link=self.app.links)
        # 将初始任务添加到队列中。
        [await self.loop.create_task(self.__create_download_task(link=link, retry=None)) for link in
         links] if links else None
        # 处理队列中的任务与机器人事件。
        while not self.queue.empty() or self.is_bot_running:
            result = await self.queue.get()
            try:
                await result
            except PermissionError as e:
                log.error(
                    '临时文件无法移动至下载路径:\n'
                    '1.可能存在使用网络路径、挂载硬盘行为(本软件不支持);\n'
                    '2.可能存在多开软件时,同时操作同一文件或目录导致冲突;\n'
                    '3.由于软件设计缺陷,没有考虑到不同频道文件名相同的情况(若调整将会导致部分用户更新后重复下载已有文件),当保存路径下文件过多时,可能恰巧存在相同文件名的文件,导致相同文件名无法正常移动,故请定期整理归档下载链接与保存路径下的文件。'
                    f'{_t(KeyWord.REASON)}:"{e}"')
        # 等待所有任务完成。
        await self.queue.join()
        await self.app.client.stop() if self.app.client.is_connected else None

    def run(self) -> None:
        record_error: bool = False
        try:
            MetaData.print_meta()
            self.app.print_config_table(
                enable_proxy=self.app.enable_proxy,
                links=self.app.links,
                download_type=self.app.download_type,
                proxy=self.app.proxy
            )
            self.loop.run_until_complete(self.__download_media_from_links())
        except KeyError as e:
            if str(e) == '0':
                log.error('「网络」或「代理问题」,在确保当前网络连接正常情况下检查:\n「VPN」是否可用,「软件代理」是否配置正确。')
                console.print(
                    '[#79FCD4]解决方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\n'
                    '[link=https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0]'
                    'https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki#问题14-error-运行出错原因0-keyerror-0[/link]'
                    '\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4]'
                    '[#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79]'
                    '[#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC]'
                    '[#79FCD4]文件夹下的[/#79FCD4][#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579]'
                    '[#79FCB5]中的[/#79FCB5][#D479FC]【问题14】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6]。[/#FC79A6]'
                )
                raise SystemExit(0)
            log.exception(f'运行出错,{_t(KeyWord.REASON)}:"{e}"')
        except pyrogram.errors.BadMsgNotification as e:
            if str(e) in (str(pyrogram.errors.BadMsgNotification(16)), str(pyrogram.errors.BadMsgNotification(17))):
                console.print(
                    '[#FCFF79]检测到[/#FCFF79][#FF7979]系统时间[/#FF7979][#FC79A5]未同步[/#FC79A5][#79E2FC],[/#79E2FC]'
                    '[#79FCD4]解决方法[/#79FCD4][#FF79D4]请访问:[/#FF79D4]\n'
                    'https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/issues/5#issuecomment-2580677184'
                    '\n[#FCFF79]若[/#FCFF79][#FF4689]无法[/#FF4689][#FF7979]访问[/#FF7979][#79FCD4],[/#79FCD4]'
                    '[#FCFF79]可[/#FCFF79][#d4fc79]查阅[/#d4fc79]'
                    '[#FC79A5]软件压缩包所提供的[/#FC79A5][#79E2FC]"使用手册"[/#79E2FC]'
                    '[#79FCD4]文件夹下的[/#79FCD4][#FFB579]"常见问题及解决方案汇总.pdf"[/#FFB579]'
                    '[#79FCB5]中的[/#79FCB5][#D479FC]【问题4】[/#D479FC][#FCE679]进行操作[/#FCE679][#FC79A6],[/#FC79A6]'
                    '[#79FCD4]并[/#79FCD4][#79FCB5]重启软件[/#79FCB5]。')
                raise SystemExit(0)
            log.exception(f'运行出错,{_t(KeyWord.REASON)}:"{e}"')
        except (SessionRevoked, AuthKeyUnregistered, SessionExpired, Unauthorized, ConnectionError) as e:
            log.error(f'登录时遇到错误,{_t(KeyWord.REASON)}:"{e}"')
            res: bool = safe_delete(file_p_d=os.path.join(self.app.DIRECTORY_NAME, 'sessions'))
            record_error: bool = True
            if res:
                log.warning('账号已失效,已删除旧会话文件,请重启软件。')
            else:
                log.error('账号已失效,请手动删除软件目录下的sessions文件夹后重启软件。')
        except AttributeError as e:
            record_error: bool = True
            log.error(f'登录超时,请重新打开软件尝试登录,{_t(KeyWord.REASON)}:"{e}"')
        except KeyboardInterrupt:
            console.log('用户手动终止下载任务。')
        except OperationalError as e:
            record_error: bool = True
            log.error(
                f'检测到多开软件时,由于在上一个实例中「下载完成」后窗口没有被关闭的行为,请在关闭后重试,{_t(KeyWord.REASON)}:"{e}"')
        except Exception as e:
            record_error: bool = True
            log.exception(msg=f'运行出错,{_t(KeyWord.REASON)}:"{e}"')
        finally:
            self.is_running = False
            self.pb.progress.stop()
            if not record_error:
                self.app.print_link_table(link_info=Task.LINK_INFO)
                self.app.print_count_table(record_dtype=self.app.record_dtype)
                MetaData.pay()
                self.app.process_shutdown(60) if len(self.running_log) == 2 else None  # v1.2.8如果并未打开客户端执行任何下载,则不执行关机。
            self.app.ctrl_c()

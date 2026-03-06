# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023/10/3 1:00:03
# File:downloader.py
import os
import sys
import random
import asyncio
import datetime

from functools import partial
from sqlite3 import OperationalError
from typing import Union, Callable, Optional, Dict, Set

import pyrogram
from pyrogram.enums.parse_mode import ParseMode
from pyrogram.errors import (
    BadMsgNotification,
    FileReferenceExpired,
    FloodWait,
    FloodPremiumWait
)
from pyrogram.errors.exceptions.bad_request_400 import (
    MsgIdInvalid,
    UsernameInvalid,
    ChannelInvalid,
    BotMethodInvalid,
    UsernameNotOccupied,
    PeerIdInvalid,
    MessageNotModified,
    ChannelPrivate as ChannelPrivate_400,
    ChatForwardsRestricted as ChatForwardsRestricted_400
)
from pyrogram.errors.exceptions.not_acceptable_406 import (
    ChannelPrivate as ChannelPrivate_406,
    ChatForwardsRestricted as ChatForwardsRestricted_406
)
from pyrogram.errors.exceptions.unauthorized_401 import (
    SessionRevoked,
    AuthKeyUnregistered,
    SessionExpired,
    Unauthorized
)
from pyrogram.errors.exceptions.forbidden_403 import ChatWriteForbidden
from pyrogram.handlers import MessageHandler
from pyrogram.types.messages_and_media import ReplyParameters
from pyrogram.types.bots_and_keyboards import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from module import (
    console,
    log,
    LINK_PREVIEW_OPTIONS,
    SLEEP_THRESHOLD
)
from module.filter import Filter
from module.app import Application
from module.bot import (
    Bot,
    KeyboardButton,
    CallbackData
)
from module.enums import (
    DownloadStatus,
    LinkType,
    KeyWord,
    BotCallbackText,
    BotButton,
    BotMessage,
    DownloadType,
    CalenderKeyboard,
    SaveDirectoryPrefix
)
from module.language import _t
from module.path_tool import (
    is_file_duplicate,
    safe_delete,
    get_file_size,
    split_path,
    compare_file_size,
    move_to_save_directory,
    safe_replace
)
from module.task import DownloadTask, UploadTask
from module.stdio import ProgressBar, Base64Image, MetaData
from module.uploader import TelegramUploader
from module.util import (
    parse_link,
    format_chat_link,
    get_my_id,
    get_message_by_link,
    get_chat_with_notify,
    safe_message,
    truncate_display_filename,
    Issues
)


class TelegramRestrictedMediaDownloader(Bot):

    def __init__(self):
        super().__init__()
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.event: asyncio.Event = asyncio.Event()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.app: Application = Application()
        self.is_running: bool = False
        self.running_log: Set[bool] = set()
        self.running_log.add(self.is_running)
        self.pb: ProgressBar = ProgressBar()
        self.uploader: Union[TelegramUploader, None] = None
        self.cd: Union[CallbackData, None] = None
        self.my_id: int = 0

    def env_save_directory(
            self,
            message: pyrogram.types.Message
    ) -> str:
        save_directory = self.app.save_directory
        for placeholder in SaveDirectoryPrefix():
            if placeholder in save_directory:
                if placeholder == SaveDirectoryPrefix.CHAT_ID:
                    save_directory = save_directory.replace(
                        placeholder,
                        str(getattr(getattr(message, 'chat'), 'id', 'UNKNOWN_CHAT_ID'))
                    )
                if placeholder == SaveDirectoryPrefix.MIME_TYPE:
                    for dtype in DownloadType():
                        if getattr(message, dtype, None):
                            save_directory = save_directory.replace(
                                placeholder,
                                dtype
                            )
        return save_directory

    async def get_download_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            with_upload: Union[dict, None] = None
    ):
        link_meta: Union[dict, None] = await super().get_download_link_from_bot(client, message)
        if link_meta is None:
            return None
        right_link: set = link_meta.get('right_link')
        invalid_link: set = link_meta.get('invalid_link')
        last_bot_message: Union[pyrogram.types.Message, None] = link_meta.get('last_bot_message')
        exist_link: set = set([_ for _ in right_link if _ in self.bot_task_link])
        exist_link.update(right_link & DownloadTask.COMPLETE_LINK)
        if not with_upload:
            right_link -= exist_link
        if last_bot_message:
            await self.safe_edit_message(
                client=client,
                message=message,
                last_message_id=last_bot_message.id,
                text=self.update_text(
                    right_link=right_link,
                    exist_link=exist_link if not with_upload else None,
                    invalid_link=invalid_link
                )
            )
        else:
            log.warning('消息过长编辑频繁,暂时无法通过机器人显示通知。')
        links: Union[set, None] = self.__process_links(link=list(right_link))

        if links is None:
            return None
        for link in links:
            task: dict = await self.create_download_task(
                message_ids=link,
                retry=None,
                with_upload=with_upload
            )
            invalid_link.add(link) if task.get('status') == DownloadStatus.FAILURE else self.bot_task_link.add(link)
        right_link -= invalid_link
        await self.safe_edit_message(
            client=client,
            message=message,
            last_message_id=last_bot_message.id,
            text=self.update_text(
                right_link=right_link,
                exist_link=exist_link if not with_upload else None,
                invalid_link=invalid_link
            )
        )

    async def get_upload_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            delete: bool = False,
            save_directory: str = None,
            recursion: bool = False,
            valid_link_cache: dict = None
    ):
        link_meta: Union[dict, None] = await super().get_upload_link_from_bot(
            client=client,
            message=message,
            delete=delete,
            save_directory=save_directory,
            recursion=recursion,
            valid_link_cache=valid_link_cache
        )
        if link_meta is None:
            return None
        target_link: str = link_meta.get('target_link')
        valid_link_cache: dict = link_meta.get('valid_link_cache')
        upload_task = link_meta.get('upload_task')
        upload_task.with_delete = self.gc.upload_delete
        await self.uploader.create_upload_task(
            link=valid_link_cache.get(target_link, None) or target_link if valid_link_cache else target_link,
            upload_task=upload_task,
        )

    @staticmethod
    async def __send_pay_qr(
            client: pyrogram.Client,
            chat_id: Union[int, str],
            load_name: str
    ) -> Union[list, str, None]:
        try:
            last_msg = await client.send_message(
                chat_id=chat_id,
                text=f'🚛请稍后{load_name}加载中. . .',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
            tasks = [client.send_photo(
                chat_id=chat_id,
                photo=Base64Image.base64_to_binary_io(Base64Image.pay),
                disable_notification=True
            ),
                client.edit_message_text(
                    chat_id=chat_id,
                    message_id=last_msg.id,
                    text=f'✅{load_name}加载成功!'
                )]
            await asyncio.gather(*tasks)
        except Exception as e:
            return str(e)

    async def start(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        self.last_client: pyrogram.Client = client
        self.last_message: pyrogram.types.Message = message
        if self.gc.config.get(BotCallbackText.NOTICE):
            chat_id = message.from_user.id
            await asyncio.gather(
                self.__send_pay_qr(
                    client=client,
                    chat_id=chat_id,
                    load_name='机器人'
                ),
                super().start(client, message),
                client.send_message(
                    chat_id=chat_id,
                    text='😊欢迎使用,您的支持是我持续更新的动力。',
                    link_preview_options=LINK_PREVIEW_OPTIONS)
            )

    async def callback_data(self, client: pyrogram.Client, callback_query: pyrogram.types.CallbackQuery):
        callback_data = await super().callback_data(client, callback_query)
        kb = KeyboardButton(callback_query)
        if callback_data is None:
            return None
        elif callback_data == BotCallbackText.NOTICE:
            try:
                self.gc.config[BotCallbackText.NOTICE] = not self.gc.config.get(BotCallbackText.NOTICE)
                self.gc.save_config(self.gc.config)
                n_s: str = '启用' if self.gc.config.get(BotCallbackText.NOTICE) else '禁用'
                n_p: str = f'机器人消息通知已{n_s}。'
                log.info(n_p)
                console.log(n_p, style='#FF4689')
                await kb.toggle_setting_button(global_config=self.gc.config, user_config=self.app.config)
            except Exception as e:
                await callback_query.message.reply_text(
                    '启用或禁用机器人消息通知失败\n(具体原因请前往终端查看报错信息)')
                log.error(f'启用或禁用机器人消息通知失败,{_t(KeyWord.REASON)}:"{e}"')
        elif callback_data == BotCallbackText.PAY:
            res: Union[str, None] = await self.__send_pay_qr(
                client=client,
                chat_id=callback_query.from_user.id,  # v1.6.5 修复发送图片时chat_id错误问题。
                load_name='收款码'
            )
            MetaData.pay()
            if res:
                msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」十分感谢您的支持!'
            else:
                msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」与「对话框」十分感谢您的支持!'
            await callback_query.message.reply_text(msg)
        elif callback_data == BotCallbackText.BACK_HELP:
            meta: dict = await self.help()
            await callback_query.message.edit_text(meta.get('text'))
            await callback_query.message.edit_reply_markup(meta.get('keyboard'))
        elif callback_data == BotCallbackText.BACK_TABLE:
            meta: dict = await self.table()
            await callback_query.message.edit_text(meta.get('text'))
            await callback_query.message.edit_reply_markup(meta.get('keyboard'))
        elif callback_data in (BotCallbackText.DOWNLOAD, BotCallbackText.DOWNLOAD_UPLOAD):
            if not isinstance(self.cd.data, dict):
                return None
            meta: Union[dict, None] = self.cd.data.copy()
            self.cd.data = None
            origin_link: str = meta.get('origin_link')
            target_link: str = meta.get('target_link')
            start_id: Union[int, None] = meta.get('start_id')
            end_id: Union[int, None] = meta.get('end_id')
            if callback_data == BotCallbackText.DOWNLOAD:
                self.last_message.text = f'/download {origin_link} {start_id} {end_id}'
                await self.get_download_link_from_bot(
                    client=self.last_client,
                    message=self.last_message
                )
            elif callback_data == BotCallbackText.DOWNLOAD_UPLOAD:
                self.last_message.text = f'/download {origin_link} {start_id} {end_id}'
                await self.get_download_link_from_bot(
                    client=self.last_client,
                    message=self.last_message,
                    with_upload={
                        'link': target_link,
                        'file_name': None,
                        'with_delete': self.gc.upload_delete,
                        'send_as_media_group': True
                    }
                )
            await kb.task_assign_button()
        elif callback_data == BotCallbackText.LOOKUP_LISTEN_INFO:
            await self.app.client.send_message(
                chat_id=callback_query.message.from_user.id,
                text='/listen_info',
                link_preview_options=LINK_PREVIEW_OPTIONS
            )
        elif callback_data == BotCallbackText.SHUTDOWN:
            try:
                self.app.config['is_shutdown'] = not self.app.config.get('is_shutdown')
                self.app.save_config(self.app.config)
                s_s: str = '启用' if self.app.config.get('is_shutdown') else '禁用'
                s_p: str = f'退出后关机已{s_s}。'
                log.info(s_p)
                console.log(s_p, style='#FF4689')
                await kb.toggle_setting_button(global_config=self.gc.config, user_config=self.app.config)
            except Exception as e:
                await callback_query.message.reply_text('启用或禁用自动关机失败\n(具体原因请前往终端查看报错信息)')
                log.error(f'启用或禁用自动关机失败,{_t(KeyWord.REASON)}:"{e}"')
        elif callback_data == BotCallbackText.SETTING:
            await kb.toggle_setting_button(global_config=self.gc.config, user_config=self.app.config)
        elif callback_data == BotCallbackText.EXPORT_TABLE:
            await kb.toggle_table_button(config=self.gc.config)
        elif callback_data == BotCallbackText.DOWNLOAD_SETTING:
            await kb.toggle_download_setting_button(user_config=self.app.config)
        elif callback_data == BotCallbackText.UPLOAD_SETTING:
            await kb.toggle_upload_setting_button(global_config=self.gc.config)
        elif callback_data == BotCallbackText.FORWARD_SETTING:
            await kb.toggle_forward_setting_button(global_config=self.gc.config)
        elif callback_data in (
                BotCallbackText.LINK_TABLE,
                BotCallbackText.COUNT_TABLE,
                BotCallbackText.UPLOAD_TABLE
        ):
            _prompt_string: str = ''
            _false_text: str = ''
            _choice: str = ''
            res: Union[bool, None] = None
            if callback_data == BotCallbackText.LINK_TABLE:
                _prompt_string: str = '链接统计表'
                _false_text: str = '😵😵😵没有链接需要统计。'
                _choice: str = BotCallbackText.EXPORT_LINK_TABLE
                res: Union[bool, None] = self.app.print_link_table(DownloadTask.LINK_INFO)
            elif callback_data == BotCallbackText.COUNT_TABLE:
                _prompt_string: str = '计数统计表'
                _false_text: str = '😵😵😵当前没有任何下载。'
                _choice: str = BotCallbackText.EXPORT_COUNT_TABLE
                res: Union[bool, None] = self.app.print_count_table()
            elif callback_data == BotCallbackText.UPLOAD_TABLE:
                _prompt_string: str = '上传统计表'
                _false_text: str = '😵😵😵当前没有任何上传。'
                _choice: str = BotCallbackText.EXPORT_UPLOAD_TABLE
                res: Union[bool, None] = self.app.print_upload_table(UploadTask.TASKS)
            if res:
                await callback_query.message.edit_text(f'👌👌👌`{_prompt_string}`已发送至您的「终端」请注意查收。')
                await kb.choice_export_table_button(choice=_choice)
                return None
            elif res is False:
                await callback_query.message.edit_text(_false_text)
            else:
                await callback_query.message.edit_text(
                    f'😵‍💫😵‍💫😵‍💫`{_prompt_string}`打印失败。\n(具体原因请前往终端查看报错信息)')
            await kb.back_table_button()
        elif callback_data in (
                BotCallbackText.TOGGLE_LINK_TABLE,
                BotCallbackText.TOGGLE_COUNT_TABLE,
                BotCallbackText.TOGGLE_UPLOAD_TABLE
        ):
            async def _toggle_button(_table_type):
                export_config: dict = self.gc.config.get('export_table')
                export_config[_table_type] = not export_config.get(_table_type)
                if _table_type == 'link':
                    t_t = '链接统计表'
                elif _table_type == 'count':
                    t_t = '计数统计表'
                elif _table_type == 'upload':
                    t_t = '上传统计表'
                else:
                    t_t = '统计表'
                s_t: str = '启用' if export_config.get(_table_type) else '禁用'
                t_p: str = f'退出后导出{t_t}已{s_t}。'
                console.log(t_p, style='#FF4689')
                log.info(t_p)
                self.gc.save_config(self.gc.config)
                await kb.toggle_table_button(
                    config=self.gc.config,
                    choice=_table_type
                )

            if callback_data == BotCallbackText.TOGGLE_LINK_TABLE:
                await _toggle_button('link')
            elif callback_data == BotCallbackText.TOGGLE_COUNT_TABLE:
                await _toggle_button('count')
            elif callback_data == BotCallbackText.TOGGLE_UPLOAD_TABLE:
                await _toggle_button('upload')
        elif callback_data in (
                BotCallbackText.EXPORT_LINK_TABLE,
                BotCallbackText.EXPORT_COUNT_TABLE,
                BotCallbackText.EXPORT_UPLOAD_TABLE
        ):
            _prompt_string: str = ''
            _folder: str = ''
            res: Union[bool, None] = False
            if callback_data == BotCallbackText.EXPORT_LINK_TABLE:
                _prompt_string: str = '链接统计表'
                _folder: str = 'DownloadRecordForm'
                res: Union[bool, None] = self.app.print_link_table(
                    link_info=DownloadTask.LINK_INFO,
                    export=True,
                    only_export=True
                )
            elif callback_data == BotCallbackText.EXPORT_COUNT_TABLE:
                _prompt_string: str = '计数统计表'
                _folder: str = 'DownloadRecordForm'
                res: Union[bool, None] = self.app.print_count_table(
                    export=True,
                    only_export=True
                )
            elif callback_data == BotCallbackText.EXPORT_UPLOAD_TABLE:
                _prompt_string: str = '上传统计表'
                _folder: str = 'UploadRecordForm'
                res: Union[bool, None] = self.app.print_upload_table(
                    upload_tasks=UploadTask.TASKS,
                    export=True,
                    only_export=True
                )
            if res:
                await callback_query.message.edit_text(
                    f'✅✅✅`{_prompt_string}`已发送至您的「终端」并已「导出」为表格请注意查收。\n(请查看软件目录下`{_folder}`文件夹)')
            elif res is False:
                await callback_query.message.edit_text('😵😵😵没有链接需要统计。')
            else:
                await callback_query.message.edit_text(
                    f'😵‍💫😵‍💫😵‍💫`{_prompt_string}`导出失败。\n(具体原因请前往终端查看报错信息)')
            await kb.back_table_button()
        elif callback_data in (BotCallbackText.UPLOAD_DOWNLOAD, BotCallbackText.UPLOAD_DOWNLOAD_DELETE):
            def _toggle_button(_param: str):
                param: bool = self.gc.get_nesting_config(
                    default_nesting=self.gc.default_upload_nesting,
                    param='upload',
                    nesting_param=_param
                )
                self.gc.config.get('upload', self.gc.default_upload_nesting)[_param] = not param
                u_s: str = '禁用' if param else '开启'
                u_p: str = ''
                if _param == 'delete':
                    u_p: str = f'遇到"受限转发"时,下载后上传并"删除上传完成的本地文件"的行为已{u_s}。'
                elif _param == 'download_upload':
                    u_p: str = f'遇到"受限转发"时,下载后上传已{u_s}。'
                console.log(u_p, style='#FF4689')
                log.info(u_p)

            try:
                if callback_data == BotCallbackText.UPLOAD_DOWNLOAD:
                    _toggle_button('download_upload')
                elif callback_data == BotCallbackText.UPLOAD_DOWNLOAD_DELETE:
                    _toggle_button('delete')
                self.gc.save_config(self.gc.config)
                await kb.toggle_upload_setting_button(global_config=self.gc.config)
            except Exception as e:
                await callback_query.message.reply_text(
                    '上传设置失败\n(具体原因请前往终端查看报错信息)')
                log.error(f'上传设置失败,{_t(KeyWord.REASON)}:"{e}"')
        elif callback_data in (
                BotCallbackText.TOGGLE_DOWNLOAD_VIDEO,
                BotCallbackText.TOGGLE_DOWNLOAD_PHOTO,
                BotCallbackText.TOGGLE_DOWNLOAD_AUDIO,
                BotCallbackText.TOGGLE_DOWNLOAD_VOICE,
                BotCallbackText.TOGGLE_DOWNLOAD_ANIMATION,
                BotCallbackText.TOGGLE_DOWNLOAD_DOCUMENT
        ):
            def _toggle_download_type_button(_param: str):
                if _param in self.app.download_type:
                    if len(self.app.download_type) == 1:
                        raise ValueError
                    f_s = '禁用'
                    self.app.download_type.remove(_param)
                else:
                    f_s = '启用'
                    self.app.download_type.append(_param)

                f_p = f'已{f_s}"{_param}"类型的下载。'
                console.log(f_p, style='#FF4689')
                log.info(f_p)

            try:
                if callback_data == BotCallbackText.TOGGLE_DOWNLOAD_VIDEO:
                    _toggle_download_type_button('video')
                elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_PHOTO:
                    _toggle_download_type_button('photo')
                elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_AUDIO:
                    _toggle_download_type_button('audio')
                elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_VOICE:
                    _toggle_download_type_button('voice')
                elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_ANIMATION:
                    _toggle_download_type_button('animation')
                elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_DOCUMENT:
                    _toggle_download_type_button('document')
                self.app.config['download_type'] = self.app.download_type
                self.app.save_config(self.app.config)
                await kb.toggle_download_setting_button(self.app.config)
            except ValueError:
                await callback_query.message.reply_text('⚠️⚠️⚠️至少需要选择一个下载类型⚠️⚠️⚠️')
            except Exception as e:
                await callback_query.message.reply_text(
                    '下载类型设置失败\n(具体原因请前往终端查看报错信息)')
                log.error(f'下载类型设置失败,{_t(KeyWord.REASON)}:"{e}"')
        elif callback_data in (
                BotCallbackText.TOGGLE_FORWARD_VIDEO,
                BotCallbackText.TOGGLE_FORWARD_PHOTO,
                BotCallbackText.TOGGLE_FORWARD_AUDIO,
                BotCallbackText.TOGGLE_FORWARD_VOICE,
                BotCallbackText.TOGGLE_FORWARD_ANIMATION,
                BotCallbackText.TOGGLE_FORWARD_DOCUMENT,
                BotCallbackText.TOGGLE_FORWARD_TEXT
        ):
            def _toggle_forward_type_button(_param: str):
                _forward_type: dict = self.gc.config.get('forward_type', self.gc.default_forward_type_nesting)
                _status: bool = self.gc.get_nesting_config(
                    default_nesting=self.gc.default_forward_type_nesting,
                    param='forward_type',
                    nesting_param=_param
                )
                if list(_forward_type.values()).count(True) == 1 and _status:
                    raise ValueError
                _forward_type[_param] = not _status
                f_s = '禁用' if _status else '启用'
                f_p = f'已{f_s}"{_param}"类型的转发。'
                console.log(f_p, style='#FF4689')
                log.info(f_p)

            try:
                if callback_data == BotCallbackText.TOGGLE_FORWARD_VIDEO:
                    _toggle_forward_type_button('video')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_PHOTO:
                    _toggle_forward_type_button('photo')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_AUDIO:
                    _toggle_forward_type_button('audio')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_VOICE:
                    _toggle_forward_type_button('voice')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_ANIMATION:
                    _toggle_forward_type_button('animation')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_DOCUMENT:
                    _toggle_forward_type_button('document')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_TEXT:
                    _toggle_forward_type_button('text')
                self.gc.save_config(self.gc.config)
                await kb.toggle_forward_setting_button(self.gc.config)
            except ValueError:
                await callback_query.message.reply_text('⚠️⚠️⚠️至少需要选择一个转发类型⚠️⚠️⚠️')
            except Exception as e:
                await callback_query.message.reply_text(
                    '转发设置失败\n(具体原因请前往终端查看报错信息)')
                log.error(f'转发设置失败,{_t(KeyWord.REASON)}:"{e}"')
        elif callback_data == BotCallbackText.REMOVE_LISTEN_FORWARD or callback_data.startswith(
                BotCallbackText.REMOVE_LISTEN_DOWNLOAD):
            if callback_data.startswith(BotCallbackText.REMOVE_LISTEN_DOWNLOAD):
                args: list = callback_data.split()
                link: str = args[1]
                self.app.client.remove_handler(self.listen_download_chat.get(link))
                self.listen_download_chat.pop(link)
                await callback_query.message.edit_text(link)
                await callback_query.message.edit_reply_markup(
                    KeyboardButton.single_button(text=BotButton.ALREADY_REMOVE, callback_data=BotCallbackText.NULL)
                )
                p = f'已删除监听下载,频道链接:"{link}"。'
                console.log(p, style='#FF4689')
                log.info(f'{p}当前的监听下载信息:{self.listen_download_chat}')
                return None
            if not isinstance(self.cd.data, dict):
                return None
            meta: Union[dict, None] = self.cd.data.copy()
            self.cd.data = None
            link: str = meta.get('link')
            self.app.client.remove_handler(self.listen_forward_chat.get(link))
            self.listen_forward_chat.pop(link)
            m: list = link.split()
            _ = ' -> '.join(m)
            p = f'已删除监听转发,转发规则:"{_}"。'
            await callback_query.message.edit_text(
                ' ➡️ '.join(m)
            )
            await callback_query.message.edit_reply_markup(
                KeyboardButton.single_button(text=BotButton.ALREADY_REMOVE, callback_data=BotCallbackText.NULL)
            )
            console.log(p, style='#FF4689')
            log.info(f'{p}当前的监听转发信息:{self.listen_forward_chat}')
        elif callback_data in (
                BotCallbackText.DOWNLOAD_CHAT_FILTER,  # 主页面。
                BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER,  # 下载日期范围设置页面。
                BotCallbackText.DOWNLOAD_CHAT_DTYPE_FILTER,  # 下载类型设置页面。
                BotCallbackText.DOWNLOAD_CHAT_KEYWORD_FILTER,  # 关键词过滤设置页面。
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT,
                BotCallbackText.TOGGLE_DOWNLOAD_CHAT_COMMENT,
                BotCallbackText.DOWNLOAD_CHAT_ID,  # 执行任务。
                BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL,  # 取消任务。
                BotCallbackText.FILTER_START_DATE,  # 设置下载起始日期。
                BotCallbackText.FILTER_END_DATE,  # 设置下载结束日期。
                BotCallbackText.CONFIRM_KEYWORD,  # 确认设置关键词。
                BotCallbackText.CANCEL_KEYWORD_INPUT  # 取消设置关键词。
        ) or callback_data.startswith(
            (
                    'time_inc_',
                    'time_dec_',
                    'set_time_',
                    'set_specific_time_',
                    'adjust_step_',
                    'drop_keyword_',  # 移除特定关键词。
                    'ignore_keyword'  # 忽略特定关键词。
            )  # 切换月份,选择日期。
        ):
            chat_id = BotCallbackText.DOWNLOAD_CHAT_ID

            def _get_update_time():
                _start_timestamp = self.download_chat_filter[chat_id]['date_range'][
                    'start_date']
                _end_timestamp = self.download_chat_filter[chat_id]['date_range']['end_date']
                _start_time = datetime.datetime.fromtimestamp(_start_timestamp) if _start_timestamp else '未定义'
                _end_time = datetime.datetime.fromtimestamp(_end_timestamp) if _end_timestamp else '未定义'
                return _start_time, _end_time

            def _get_format_dtype():
                _download_type = []
                for _dtype, _status in self.download_chat_filter[chat_id]['download_type'].items():
                    if _status:
                        _download_type.append(_t(_dtype))
                return ','.join(_download_type)

            def _get_format_keywords():
                _keywords = self.download_chat_filter[chat_id]['keyword']
                if not _keywords:
                    return '未定义'
                return ','.join(_keywords.keys())

            def _get_format_comment_status():
                _status = self.download_chat_filter[chat_id]['comment']
                return '开' if _status else '关'

            def _remove_chat_id(_chat_id):
                if _chat_id in self.download_chat_filter:
                    self.download_chat_filter.pop(_chat_id)
                    log.info(f'"{_chat_id}"已从{self.download_chat_filter}中移除。')

            def _filter_prompt():
                return (
                    f'💬下载频道:`{chat_id}`\n'
                    f'⏮️当前选择的起始日期为:{_get_update_time()[0]}\n'
                    f'⏭️当前选择的结束日期为:{_get_update_time()[1]}\n'
                    f'📝当前选择的下载类型为:{_get_format_dtype()}\n'
                    f'🔑当前匹配的关键词为:{_get_format_keywords()}\n'
                    f'👥包含评论区:{_get_format_comment_status()}'
                )

            async def _verification_time(_start_time, _end_time) -> bool:
                if isinstance(_start_time, datetime.datetime) and isinstance(_end_time, datetime.datetime):
                    if _start_time > _end_time:
                        await callback_query.message.reply_text(
                            text=f'❌❌❌日期设置失败❌❌❌\n'
                                 f'`起始日期({_start_time})`>`结束日期({_end_time})`\n'
                        )
                        return False
                    elif _start_time == _end_time:
                        await callback_query.message.reply_text(
                            text=f'❌❌❌日期设置失败❌❌❌\n'
                                 f'`起始日期({_start_time})`=`结束日期({_end_time})`\n'
                        )
                        return False
                return True

            if callback_data in (BotCallbackText.DOWNLOAD_CHAT_ID, BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL):  # 执行或取消任务。
                BotCallbackText.DOWNLOAD_CHAT_ID = 'download_chat_id'
                self.adding_keywords.clear()
                self.add_keyword_mode_handler(
                    chat_id=chat_id,
                    callback_query=callback_query,
                    callback_prompt=_filter_prompt,
                    enable=False
                )  # 关闭关键词输入handler。
                if callback_data == chat_id:
                    await self.download_chat(chat_id=chat_id, callback_query=callback_query)
                    _remove_chat_id(chat_id)
                elif callback_data == BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL:
                    _remove_chat_id(chat_id)
                    await callback_query.message.edit_text(
                        text=callback_query.message.text,
                        reply_markup=kb.single_button(
                            text=BotButton.TASK_CANCEL,
                            callback_data=BotCallbackText.NULL
                        )
                    )
            elif callback_data in (
                    BotCallbackText.DOWNLOAD_CHAT_FILTER,
                    BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER
            ):
                if callback_data == BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER:
                    start_time, end_time = _get_update_time()
                    if not await _verification_time(start_time, end_time):
                        return None
                # 返回或点击。
                await callback_query.message.edit_text(
                    text=_filter_prompt(),
                    reply_markup=kb.download_chat_filter_button(
                        self.download_chat_filter[chat_id][
                            'comment']) if callback_data == BotCallbackText.DOWNLOAD_CHAT_FILTER else kb.filter_date_range_button()
                )
            elif callback_data in (BotCallbackText.FILTER_START_DATE, BotCallbackText.FILTER_END_DATE):
                dtype = None
                p_s_d = ''
                if callback_data == BotCallbackText.FILTER_START_DATE:
                    dtype = CalenderKeyboard.START_TIME_BUTTON
                    p_s_d = '起始'
                elif callback_data == BotCallbackText.FILTER_END_DATE:
                    dtype = CalenderKeyboard.END_TIME_BUTTON
                    p_s_d = '结束'
                await callback_query.message.edit_text(
                    text=f'📅选择{p_s_d}日期:\n{_filter_prompt()}'
                )
                await kb.calendar_keyboard(dtype=dtype)
            elif callback_data.startswith('adjust_step_'):
                # 获取当前步进值
                parts = callback_data.split('_')
                dtype = parts[-2]
                current_step = int(parts[-1])
                step_sequence = [1, 2, 5, 10, 15, 20]
                current_index = step_sequence.index(current_step)
                next_index = (current_index + 1) % len(step_sequence)
                new_step = step_sequence[next_index]
                self.download_chat_filter[chat_id]['date_range']['adjust_step'] = new_step
                current_date = datetime.datetime.fromtimestamp(
                    self.download_chat_filter[chat_id]['date_range'][f'{dtype}_date']
                ).strftime('%Y-%m-%d %H:%M:%S')
                await callback_query.message.edit_reply_markup(
                    reply_markup=kb.time_keyboard(
                        dtype=dtype,
                        date=current_date,
                        adjust_step=new_step
                    )
                )
            elif callback_data.startswith(('time_inc_', 'time_dec_')):
                parts = callback_data.split('_')
                dtype = None
                if 'start' in callback_data:
                    dtype = CalenderKeyboard.START_TIME_BUTTON
                elif 'end' in callback_data:
                    dtype = CalenderKeyboard.END_TIME_BUTTON

                if 'month' in callback_data:
                    year = int(parts[-2])
                    month = int(parts[-1])
                    await kb.calendar_keyboard(year=year, month=month, dtype=dtype)
                    log.info(f'日期切换为{year}年,{month}月。')

            elif callback_data.startswith(('set_time_', 'set_specific_time_')):
                parts = callback_data.split('_')
                date = parts[-1]
                dtype = parts[-2]
                date_type = ''
                p_s_d = ''
                timestamp = datetime.datetime.timestamp(datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S'))
                if 'start' in callback_data:
                    date_type = 'start_date'
                    p_s_d = '起始'
                elif 'end' in callback_data:
                    date_type = 'end_date'
                    p_s_d = '结束'
                self.download_chat_filter[chat_id]['date_range'][date_type] = timestamp
                await callback_query.message.edit_text(
                    text=f'📅选择{p_s_d}日期:\n{_filter_prompt()}',
                    reply_markup=kb.time_keyboard(
                        dtype=dtype,
                        date=date,
                        adjust_step=self.download_chat_filter[chat_id]['date_range']['adjust_step']
                    )
                )
                log.info(f'日期设置,起始日期:{_get_update_time()[0]},结束日期:{_get_update_time()[1]}。')
            elif callback_data.startswith(('drop_keyword_', 'ignore_keyword')):
                if callback_data.startswith('drop_keyword_'):
                    parts = callback_data.split('_')
                    keyword = parts[-1]
                    _keyword = self.download_chat_filter.get(chat_id, {}).get('keyword', {})
                    _keyword.pop(keyword)
                    self.adding_keywords.remove(keyword)
                await callback_query.message.edit_text(
                    text=_filter_prompt(),
                    reply_markup=KeyboardButton.keyword_filter_button(self.adding_keywords)
                )

            elif callback_data in (
                    BotCallbackText.DOWNLOAD_CHAT_DTYPE_FILTER,
                    BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO,
                    BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO,
                    BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO,
                    BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE,
                    BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION,
                    BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT
            ):
                def _toggle_dtype_filter_button(_param: str):
                    _dtype: dict = self.download_chat_filter[chat_id]['download_type']
                    _status: bool = _dtype[_param]
                    if list(_dtype.values()).count(True) == 1 and _status:
                        raise ValueError
                    _dtype[_param] = not _status
                    f_s = '禁用' if _status else '启用'
                    f_p = f'已{f_s}"{_param}"类型用于/download_chat命令的下载。'
                    log.info(
                        f'{f_p}当前的/download_chat下载类型设置:{_dtype}')

                try:
                    if callback_data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VIDEO:
                        _toggle_dtype_filter_button('video')
                    elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_PHOTO:
                        _toggle_dtype_filter_button('photo')
                    elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_AUDIO:
                        _toggle_dtype_filter_button('audio')
                    elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_VOICE:
                        _toggle_dtype_filter_button('voice')
                    elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_ANIMATION:
                        _toggle_dtype_filter_button('animation')
                    elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_DTYPE_DOCUMENT:
                        _toggle_dtype_filter_button('document')
                    await callback_query.message.edit_text(
                        text=_filter_prompt(),
                        reply_markup=kb.toggle_download_chat_type_filter_button(self.download_chat_filter)
                    )
                except ValueError:
                    await callback_query.message.reply_text('⚠️⚠️⚠️至少需要选择一个下载类型⚠️⚠️⚠️')
                except Exception as e:
                    await callback_query.message.reply_text(
                        '下载类型设置失败\n(具体原因请前往终端查看报错信息)')
                    log.error(f'下载类型设置失败,{_t(KeyWord.REASON)}:"{e}"', exc_info=True)
            elif callback_data in (
                    BotCallbackText.DOWNLOAD_CHAT_KEYWORD_FILTER,
                    BotCallbackText.CONFIRM_KEYWORD,
                    BotCallbackText.CANCEL_KEYWORD_INPUT
            ):
                if callback_data == BotCallbackText.DOWNLOAD_CHAT_KEYWORD_FILTER:
                    try:
                        await callback_query.message.edit_text(
                            text=_filter_prompt(),
                            reply_markup=kb.keyword_filter_button(self.adding_keywords)
                        )
                    except MessageNotModified:
                        pass
                    self.add_keyword_mode_handler(
                        enable=True,
                        chat_id=chat_id,
                        callback_query=callback_query,
                        callback_prompt=_filter_prompt
                    )  # 进入添加关键词模式。
                elif callback_data == BotCallbackText.CONFIRM_KEYWORD:
                    self.add_keyword_mode_handler(
                        enable=False,
                        chat_id=chat_id,
                        callback_query=callback_query,
                        callback_prompt=_filter_prompt
                    )
                    await callback_query.message.edit_text(
                        text=_filter_prompt(),
                        reply_markup=kb.download_chat_filter_button(self.download_chat_filter[chat_id]['comment'])
                    )
                elif callback_data == BotCallbackText.CANCEL_KEYWORD_INPUT:
                    self.adding_keywords.clear()
                    self.add_keyword_mode_handler(
                        enable=False,
                        chat_id=chat_id,
                        callback_query=callback_query,
                        callback_prompt=_filter_prompt
                    )
                    self.download_chat_filter[chat_id]['keyword'] = {}
                    await callback_query.message.edit_text(
                        text=_filter_prompt(),
                        reply_markup=kb.download_chat_filter_button(self.download_chat_filter[chat_id]['comment'])
                    )
            elif callback_data == BotCallbackText.TOGGLE_DOWNLOAD_CHAT_COMMENT:
                status: bool = self.download_chat_filter[chat_id]['comment']
                self.download_chat_filter[chat_id]['comment'] = not status
                await callback_query.message.edit_text(
                    text=_filter_prompt(),
                    reply_markup=kb.download_chat_filter_button(self.download_chat_filter[chat_id]['comment'])
                )

    async def forward(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            message_id: int,
            origin_chat_id: Union[str, int],
            target_chat_id: Union[str, int],
            target_link: str,
            download_upload: Optional[bool] = False,
            media_group: Optional[list] = None
    ):
        try:
            if not self.check_type(message):
                console.log(
                    f'{_t(KeyWord.CHANNEL)}:"{origin_chat_id}",{_t(KeyWord.MESSAGE_ID)}:"{message_id}"'
                    f' -> '
                    f'{_t(KeyWord.CHANNEL)}:"{target_chat_id}",'
                    f'{_t(KeyWord.STATUS)}:{_t(KeyWord.FORWARD_SKIP)}。'
                )
                await asyncio.create_task(
                    self.done_notice(
                        f'"{origin_chat_id}",{_t(KeyWord.MESSAGE_ID)}:{message_id}'
                        f' ➡️ '
                        f'"{target_chat_id}",{_t(KeyWord.FORWARD_SKIP)}(该类型已过滤)。'
                    )
                )
                return None
            if media_group:
                await self.app.client.copy_media_group(
                    chat_id=target_chat_id,
                    from_chat_id=origin_chat_id,
                    message_id=message_id,
                    disable_notification=True
                )
            elif getattr(message, 'text', False):
                await self.app.client.send_message(
                    chat_id=target_chat_id,
                    text=message.text,
                    disable_notification=True,
                    protect_content=False
                )
            else:
                await self.app.client.forward_messages(
                    chat_id=target_chat_id,
                    from_chat_id=origin_chat_id,
                    message_ids=message_id,
                    disable_notification=True,
                    protect_content=False,
                    hide_sender_name=True
                )
            p_message_id = ','.join(map(str, media_group)) if media_group else message_id
            console.log(
                f'{_t(KeyWord.CHANNEL)}:"{origin_chat_id}",{_t(KeyWord.MESSAGE_ID)}:"{p_message_id}"'
                f' -> '
                f'{_t(KeyWord.CHANNEL)}:"{target_chat_id}",'
                f'{_t(KeyWord.STATUS)}:{_t(KeyWord.FORWARD_SUCCESS)}。'
            )
            await asyncio.create_task(
                self.done_notice(
                    f'"{origin_chat_id}",{_t(KeyWord.MESSAGE_ID)}:{p_message_id}'
                    f' ➡️ '
                    f'"{target_chat_id}",{_t(KeyWord.FORWARD_SUCCESS)}。'
                )
            )
        except (ChatForwardsRestricted_400, ChatForwardsRestricted_406):
            if not download_upload:
                if (
                        getattr(getattr(message, 'chat', None), 'is_creator', False) or
                        getattr(getattr(message, 'chat', None), 'is_admin', False)
                ) and (
                        getattr(getattr(message, 'from_user', None), 'id', -1) ==
                        getattr(getattr(client, 'me', None), 'id', None)
                ):
                    return None
                raise
            link = message.link
            if not self.gc.download_upload:
                await self.bot.send_message(
                    chat_id=client.me.id,
                    text=f'⚠️⚠️⚠️无法转发⚠️⚠️⚠️\n'
                         f'`{link}`\n'
                         f'存在内容保护限制(可在[设置]->[上传设置]中设置转发时遇到受限转发进行下载后上传)。',
                    reply_parameters=ReplyParameters(message_id=message_id),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                        BotButton.SETTING,
                        callback_data=BotCallbackText.SETTING
                    )]]))
                return None
            self.last_message.text = f'/download {link}?single'
            await self.get_download_link_from_bot(
                client=self.last_client,
                message=self.last_message,
                with_upload={
                    'link': target_link,
                    'file_name': None,
                    'with_delete': self.gc.upload_delete,
                    'send_as_media_group': True
                }
            )
            p = f'{_t(KeyWord.DOWNLOAD_AND_UPLOAD_TASK)}{_t(KeyWord.CHANNEL)}:"{target_chat_id}",{_t(KeyWord.LINK)}:"{link}"。'
            console.log(p, style='#FF4689')
            log.info(p)

    async def get_forward_link_from_bot(
            self, client: pyrogram.Client,
            message: pyrogram.types.Message
    ) -> Union[dict, None]:
        meta: Union[dict, None] = await super().get_forward_link_from_bot(client, message)
        if meta is None:
            return None
        self.last_client: pyrogram.Client = client
        self.last_message: pyrogram.types.Message = message
        origin_link: str = meta.get('origin_link')
        target_link: str = meta.get('target_link')
        start_id: int = meta.get('message_range')[0]
        end_id: int = meta.get('message_range')[1]
        last_message: Union[pyrogram.types.Message, None] = None
        loading = '🚛消息转发中,请稍候...'
        try:
            origin_meta: Union[dict, None] = await parse_link(
                client=self.app.client,
                link=origin_link
            )
            target_meta: Union[dict, None] = await parse_link(
                client=self.app.client,
                link=target_link
            )
            if not all([origin_meta, target_meta]):
                raise Exception('Invalid origin_link or target_link.')
            origin_chat_id = origin_meta.get('chat_id')
            target_chat_id = target_meta.get('chat_id')
            origin_chat: Union[pyrogram.types.Chat, None] = await get_chat_with_notify(
                user_client=self.app.client,
                bot_client=client,
                bot_message=message,
                chat_id=origin_chat_id,
                error_msg=f'⬇️⬇️⬇️原始频道不存在⬇️⬇️⬇️\n{origin_link}'
            )
            target_chat: Union[pyrogram.types.Chat, None] = await get_chat_with_notify(
                user_client=self.app.client,
                bot_client=client,
                bot_message=message,
                chat_id=target_chat_id,
                error_msg=f'⬇️⬇️⬇️目标频道不存在⬇️⬇️⬇️\n{target_link}'
            )
            if not all([origin_chat, target_chat]):
                return None
            my_id = await get_my_id(client)
            if target_chat.id == my_id:
                await client.send_message(
                    chat_id=message.from_user.id,
                    text='⚠️⚠️⚠️无法转发到此机器人⚠️⚠️⚠️',
                    reply_parameters=ReplyParameters(message_id=message.id),
                )
                return None
            record_id: list = []
            last_message = await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                link_preview_options=LINK_PREVIEW_OPTIONS,
                text=loading
            )
            async for i in self.app.client.get_chat_history(
                    chat_id=origin_chat.id,
                    offset_id=start_id,
                    max_id=end_id,
                    reverse=True
            ):
                try:
                    message_id = i.id
                    await self.forward(
                        client=client,
                        message=i,
                        message_id=message_id,
                        origin_chat_id=origin_chat_id,
                        target_chat_id=target_chat_id,
                        target_link=target_link
                    )
                    record_id.append(message_id)
                except (ChatForwardsRestricted_400, ChatForwardsRestricted_406):
                    # TODO 存在内容保护限制时，文本类型的消息无需下载，而是直接send_message。
                    # TODO 存在内容保护限制时，下载后上传的消息转发时无法过滤类型。
                    self.cd.data = {
                        'origin_link': origin_link,
                        'target_link': target_link,
                        'start_id': start_id,
                        'end_id': end_id
                    }
                    channel = '@' + origin_chat.username if isinstance(
                        getattr(origin_chat, 'username'),
                        str) else ''
                    if not self.gc.download_upload:
                        await client.send_message(
                            chat_id=message.from_user.id,
                            text=f'⚠️⚠️⚠️无法转发⚠️⚠️⚠️\n`{origin_link}`\n{channel}存在内容保护限制。',
                            parse_mode=ParseMode.MARKDOWN,
                            reply_parameters=ReplyParameters(message_id=message.id),
                            reply_markup=KeyboardButton.restrict_forward_button()
                        )
                        return None
                    await client.send_message(
                        chat_id=message.from_user.id,
                        text=f'`{origin_link}`\n{channel}存在内容保护限制(已自动使用下载后上传)。\n⚠️通过`/forward`命令发送的下载后上传的消息,无法按照`[转发设置]`过滤类型。',
                        parse_mode=ParseMode.MARKDOWN,
                        reply_parameters=ReplyParameters(message_id=message.id)
                    )
                    self.last_message.text = f'/download {origin_link} {start_id} {end_id}'
                    await self.get_download_link_from_bot(
                        client=self.last_client,
                        message=self.last_message,
                        with_upload={
                            'link': target_link,
                            'file_name': None,
                            'with_delete': self.gc.upload_delete,
                            'send_as_media_group': True
                        }
                    )
                    break
                except Exception as e:
                    log.warning(
                        f'{_t(KeyWord.CHANNEL)}:"{origin_chat_id}",{_t(KeyWord.MESSAGE_ID)}:"{i.id}"'
                        f' -> '
                        f'{_t(KeyWord.CHANNEL)}:"{target_chat_id}",'
                        f'{_t(KeyWord.STATUS)}:{_t(KeyWord.FORWARD_FAILURE)},'
                        f'{_t(KeyWord.REASON)}:"{e}"')
                    await asyncio.create_task(
                        self.done_notice(
                            f'"{origin_chat_id}",{_t(KeyWord.MESSAGE_ID)}:{i.id}'
                            f' ➡️ '
                            f'"{target_chat_id}",{_t(KeyWord.FORWARD_FAILURE)}。'
                            f'\n(具体原因请前往终端查看报错信息)'
                        )
                    )
            else:
                if isinstance(last_message, str):
                    log.warning('消息过长编辑频繁,暂时无法通过机器人显示通知。')
                if not record_id:
                    last_message = await self.safe_edit_message(
                        client=client,
                        message=message,
                        last_message_id=last_message.id,
                        text=safe_message(f'😅😅😅没有找到任何有效的消息😅😅😅')
                    )
                    return None
                invalid_id: list = []
                for i in range(start_id, end_id + 1):
                    if i not in record_id:
                        invalid_id.append(i)
                if invalid_id:
                    last_message = await self.safe_edit_message(
                        client=client,
                        message=message,
                        last_message_id=last_message.id,
                        text=safe_message(BotMessage.INVALID)
                    )
                    invalid_chat = await format_chat_link(
                        link=origin_link,
                        client=self.app.client,
                        topic=origin_chat.is_forum
                    )
                    invalid_chat = invalid_chat if invalid_chat else 'Your Saved Messages'
                    for i in invalid_id:
                        last_message: Union[pyrogram.types.Message, str, None] = await self.safe_edit_message(
                            client=client,
                            message=message,
                            last_message_id=last_message.id,
                            text=safe_message(
                                f'{last_message.text}\n{invalid_chat}/{i}'
                            )
                        )
                direct_url: str = await format_chat_link(
                    link=target_link,
                    client=self.app.client,
                    topic=target_chat.is_forum
                )
                last_message = await self.safe_edit_message(
                    client=client,
                    message=message,
                    last_message_id=last_message.id,
                    text=safe_message(
                        f'{last_message.text.strip(loading)}\n🌟🌟🌟转发任务已完成🌟🌟🌟\n(若设置了转发过滤规则,请前往终端查看转发记录,此处不做展示)'),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    BotButton.CLICK_VIEW,
                                    url=direct_url
                                )
                            ]
                        ]
                    ) if direct_url else None
                )
        except AttributeError as e:
            log.exception(f'转发时遇到错误,{_t(KeyWord.REASON)}:"{e}"')
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text='⬇️⬇️⬇️出错了⬇️⬇️⬇️\n(具体原因请前往终端查看报错信息)'
            )
        except (ValueError, KeyError, UsernameInvalid, ChatWriteForbidden):
            msg: str = ''
            if any('/c' in link for link in (origin_link, target_link)):
                msg = '(私密频道或话题频道必须让当前账号加入转发频道,并且目标频道需有上传文件的权限)'
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
        finally:
            if last_message and last_message.text == loading:
                await last_message.delete()

    async def cancel_listen(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            link: str,
            command: str
    ):
        if command == '/listen_forward':
            self.cd.data = {
                'link': link
            }
        args: list = link.split()
        forward_emoji = ' ➡️ '
        await client.send_message(
            chat_id=message.from_user.id,
            reply_parameters=ReplyParameters(message_id=message.id),
            text=f'`{link if len(args) == 1 else forward_emoji.join(args)}`\n🚛已经在监听列表中。',
            link_preview_options=LINK_PREVIEW_OPTIONS,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        BotButton.DROP,
                        callback_data=f'{BotCallbackText.REMOVE_LISTEN_DOWNLOAD} {link}' if command == '/listen_download' else BotCallbackText.REMOVE_LISTEN_FORWARD
                    )
                ]
            ]
            )
        )

    async def on_listen(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        meta: Union[dict, None] = await super().on_listen(client, message)
        if meta is None:
            return None

        async def add_listen_chat(_link: str, _listen_chat: dict, _callback: Callable) -> bool:
            if _link not in _listen_chat:
                try:
                    chat = await self.user.get_chat(_link)
                    if chat.is_forum:
                        raise PeerIdInvalid
                    handler = MessageHandler(_callback, filters=pyrogram.filters.chat(chat.id))
                    _listen_chat[_link] = handler
                    self.user.add_handler(handler)
                    return True
                except PeerIdInvalid:
                    try:
                        link_meta: list = _link.split()
                        link_length: int = len(link_meta)
                        if link_length >= 1:  # v1.6.7 修复内部函数add_listen_chat中,抛出PeerIdInvalid后,在获取链接时抛出ValueError错误。
                            l_link = link_meta[0]
                        else:
                            return False
                        m: dict = await parse_link(client=self.app.client, link=l_link)
                        topic_id = m.get('topic_id')
                        chat_id = m.get('chat_id')
                        if topic_id:
                            filters = pyrogram.filters.chat(
                                chat_id) & pyrogram.filters.topic(topic_id)
                        else:
                            filters = pyrogram.filters.chat(chat_id)
                        handler = MessageHandler(
                            _callback,
                            filters=filters
                        )
                        _listen_chat[_link] = handler
                        self.user.add_handler(handler)
                        return True
                    except ValueError as e:
                        await client.send_message(
                            chat_id=message.from_user.id,
                            reply_parameters=ReplyParameters(message_id=message.id),
                            link_preview_options=LINK_PREVIEW_OPTIONS,
                            text=f'⚠️⚠️⚠️无法读取⚠️⚠️⚠️\n`{_link}`\n(具体原因请前往终端查看报错信息)'
                        )
                        log.error(f'频道"{_link}"解析失败,{_t(KeyWord.REASON)}:"{e}"')
                        return False
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
                    p = f'已新增监听下载,频道链接:"{link}"。'
                    console.log(p, style='#FF4689')
                    log.info(f'{p}当前的监听下载信息:{self.listen_download_chat}')
        elif command == '/listen_forward':
            listen_link, target_link = links
            if await add_listen_chat(f'{listen_link} {target_link}', self.listen_forward_chat, self.listen_forward):
                await client.send_message(
                    chat_id=message.from_user.id,
                    reply_parameters=ReplyParameters(message_id=message.id),
                    link_preview_options=LINK_PREVIEW_OPTIONS,
                    text=f'✅新增`监听转发`频道:\n{listen_link} ➡️ {target_link}',
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    BotButton.LOOKUP_LISTEN_INFO,
                                    callback_data=BotCallbackText.LOOKUP_LISTEN_INFO
                                )
                            ]
                        ]
                    )
                )
                p = f'已新增监听转发,转发规则:"{listen_link} -> {target_link}"。'
                console.log(p, style='#FF4689')
                log.info(f'{p}当前的监听转发信息:{self.listen_forward_chat}')

    async def listen_download(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        try:
            await self.create_download_task(message_ids=message.link, single_link=True)
        except Exception as e:
            log.exception(f'监听下载出现错误,{_t(KeyWord.REASON)}:"{e}"')

    def check_type(self, message: pyrogram.types.Message):
        for dtype, is_forward in self.gc.forward_type.items():
            if is_forward:
                result = getattr(message, dtype)
                if result:
                    return True
        return False

    async def listen_forward(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message
    ):
        try:
            link: str = message.link
            meta = await parse_link(client=self.app.client, link=link)
            listen_chat_id = meta.get('chat_id')
            for m in self.listen_forward_chat:
                listen_link, target_link = m.split()
                _listen_link_meta = await parse_link(
                    client=self.app.client,
                    link=listen_link
                )
                _target_link_meta = await parse_link(
                    client=self.app.client,
                    link=target_link
                )
                _listen_chat_id = _listen_link_meta.get('chat_id')
                _target_chat_id = _target_link_meta.get('chat_id')
                if listen_chat_id == _listen_chat_id:
                    try:
                        media_group_ids = await message.get_media_group()
                        if not media_group_ids:
                            raise ValueError
                        if (
                                not self.gc.forward_type.get('video') or
                                not self.gc.forward_type.get('photo')
                        ):
                            log.warning('由于过滤了图片或视频类型的转发,将不再以媒体组方式发送。')
                            raise ValueError
                        if (
                                getattr(getattr(message, 'chat', None), 'is_creator', False) or
                                getattr(getattr(message, 'chat', None), 'is_admin', False)
                        ) and (
                                getattr(getattr(message, 'from_user', None), 'id', -1) ==
                                getattr(getattr(client, 'me', None), 'id', None)
                        ):
                            pass
                        elif (
                                getattr(getattr(message, 'chat', None), 'has_protected_content', False) or
                                getattr(getattr(message, 'sender_chat', None), 'has_protected_content', False) or
                                getattr(message, 'has_protected_content', False)
                        ):
                            raise ValueError
                        if not self.handle_media_groups.get(listen_chat_id):
                            self.handle_media_groups[listen_chat_id] = set()
                        if listen_chat_id in self.handle_media_groups and message.id not in self.handle_media_groups.get(
                                listen_chat_id):
                            ids: set = set()
                            for peer_message in media_group_ids:
                                peer_id = peer_message.id
                                ids.add(peer_id)
                            if ids:
                                old_ids: Union[None, set] = self.handle_media_groups.get(listen_chat_id)
                                if old_ids and isinstance(old_ids, set):
                                    old_ids.update(ids)
                                    self.handle_media_groups[listen_chat_id] = old_ids
                                else:
                                    self.handle_media_groups[listen_chat_id] = ids
                            await self.forward(
                                client=client,
                                message=message,
                                message_id=message.id,
                                origin_chat_id=_listen_chat_id,
                                target_chat_id=_target_chat_id,
                                target_link=target_link,
                                download_upload=False,
                                media_group=sorted(ids)
                            )
                            break
                        break
                    except ValueError:
                        pass
                    await self.forward(
                        client=client,
                        message=message,
                        message_id=message.id,
                        origin_chat_id=_listen_chat_id,
                        target_chat_id=_target_chat_id,
                        target_link=target_link,
                        download_upload=True
                    )
        except (ValueError, KeyError, UsernameInvalid, ChatWriteForbidden) as e:
            log.error(
                f'监听转发出现错误,{_t(KeyWord.REASON)}:{e}频道性质可能发生改变,包括但不限于(频道解散、频道名改变、频道类型改变、该账户没有在目标频道上传的权限、该账号被当前频道移除)。')
        except Exception as e:
            log.exception(f'监听转发出现错误,{_t(KeyWord.REASON)}:"{e}"')

    async def handle_forwarded_media(
            self,
            user_client: pyrogram.Client,
            user_message: pyrogram.types.Message
    ):
        chat_id = user_message.from_user.id
        message_id = user_message.id
        last_message = await self.bot.send_message(
            chat_id=chat_id,
            text=f'🔄正在处理转发内容`{message_id}`...'
        )
        try:
            task = await self.create_download_task(
                message_ids=user_message,
                diy_download_type=[_ for _ in DownloadType()],
                single_link=True
            )
            if task.get('status') == DownloadStatus.DOWNLOADING:
                await last_message.edit_text(text=f'✅已创建下载任务`{message_id}`。')
            else:
                error_msg = task.get('e_code', {}).get('error_msg', '未知错误。')
                await last_message.edit_text(text=f'❌❌❌无法创建下载任务`{message_id}`❌❌❌\n{error_msg}')
        except Exception as e:
            log.error(f'获取原始消息失败,{_t(KeyWord.REASON)}:"{e}"')
            await last_message.edit_text(text=f'❌❌❌无法创建下载任务`{message_id}`❌❌❌\n{e}')

    async def resume_download(
            self,
            message: Union[pyrogram.types.Message, str],
            file_name: str,
            progress: Callable = None,
            progress_args: tuple = (),
            chunk_size: int = 1024 * 1024,
            compare_size: Union[int, None] = None,  # 不为None时,将通过大小比对判断是否为完整文件。
            retry_count: Optional[int] = 0
    ) -> str:
        temp_path = f'{file_name}.temp'
        if os.path.exists(file_name) and compare_size:
            local_file_size: int = get_file_size(file_path=file_name)
            if compare_file_size(a_size=local_file_size, b_size=compare_size):
                console.log(
                    f'{_t(KeyWord.DOWNLOAD_TASK)}'
                    f'{_t(KeyWord.RESUME)}:"{file_name}",'
                    f'{_t(KeyWord.STATUS)}:{_t(KeyWord.ALREADY_EXIST)}')
                return file_name
            else:
                result: str = safe_replace(origin_file=file_name, overwrite_file=temp_path).get('e_code')
                log.warning(result) if result is not None else None
                log.warning(
                    f'不完整的文件"{file_name}",'
                    f'更改文件名作为缓存:[{file_name}]({get_file_size(file_name)}) -> [{temp_path}]({compare_size})。')
        if os.path.exists(temp_path) and compare_size:
            local_file_size: int = get_file_size(file_path=temp_path)
            if compare_file_size(a_size=local_file_size, b_size=compare_size):
                console.log(
                    f'{_t(KeyWord.DOWNLOAD_TASK)}'
                    f'{_t(KeyWord.RESUME)}:"{temp_path}",'
                    f'{_t(KeyWord.STATUS)}:{_t(KeyWord.ALREADY_EXIST)}')
                result: str = safe_replace(origin_file=temp_path, overwrite_file=file_name).get('e_code')
                log.warning(result) if result is not None else None
                return file_name
            elif local_file_size > compare_size:
                safe_delete(temp_path)
                log.warning(
                    f'错误的缓存文件"{temp_path}",'
                    f'已清除({_t(KeyWord.ERROR_SIZE)}:{local_file_size} > {_t(KeyWord.ACTUAL_SIZE)}:{compare_size})。')
        downloaded = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0  # 获取已下载的字节数。
        if downloaded == 0:
            mode = 'wb'
        else:
            mode = 'r+b'
            console.log(
                f'{_t(KeyWord.DOWNLOAD_TASK)}'
                f'{_t(KeyWord.RESUME)}:"{file_name}",'
                f'{_t(KeyWord.ERROR_SIZE)}:{MetaData.suitable_units_display(downloaded)}。')
        with open(file=temp_path, mode=mode) as f:
            skip_chunks: int = downloaded // chunk_size  # 计算要跳过的块数。
            f.seek(downloaded)
            retry_count: int = 0 if retry_count >= self.app.max_download_retries else retry_count
            while retry_count < self.app.max_download_retries:
                try:
                    async for chunk in self.app.client.stream_media(message=message, offset=skip_chunks):
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress(downloaded, *progress_args)
                    break
                except FileReferenceExpired as e:
                    retry_count += 1
                    if retry_count >= self.app.max_download_retries:
                        log.error(
                            f'文件引用已过期且重试{self.app.max_download_retries}次后仍失败,{_t(KeyWord.REASON)}:"{e}"')
                        break
                    log.warning(
                        f'文件引用已过期,正在重新获取消息以刷新引用(第{retry_count}次重试),{_t(KeyWord.REASON)}:"{e}"')
                    if isinstance(message, pyrogram.types.Message):
                        chat_id = message.chat.id
                        message_id = message.id
                        try:
                            message = await self.app.client.get_messages(chat_id=chat_id, message_ids=message_id)
                            skip_chunks = downloaded // chunk_size
                            f.seek(downloaded)
                        except Exception as refresh_error:
                            log.error(f'重新获取消息失败,{_t(KeyWord.REASON)}:"{refresh_error}"')
                            raise
                except (FloodWait, FloodPremiumWait) as e:
                    amount = e.value
                    console.log(
                        f'[{self.app.client.name}]下载请求频繁,要求等待{amount}秒后继续运行。',
                        style='#FF4689'
                    )
                    await asyncio.sleep(amount)
        if compare_size is None or compare_file_size(a_size=downloaded, b_size=compare_size):
            result: str = safe_replace(origin_file=temp_path, overwrite_file=file_name).get('e_code')
            log.warning(result) if result is not None else None
            log.info(
                f'"{temp_path}"下载完成,更改文件名:[{temp_path}]({get_file_size(temp_path)}) -> [{file_name}]({compare_size})')
        return file_name

    def get_media_meta(self, message: pyrogram.types.Message, dtype) -> Dict[str, Union[int, str]]:
        """获取媒体元数据。"""
        file_id: int = getattr(message, 'id')
        temp_file_path: str = self.app.get_temp_file_path(message, dtype)
        _sever_meta = getattr(message, dtype)
        sever_file_size: int = getattr(_sever_meta, 'file_size')
        file_name: str = split_path(temp_file_path).get('file_name')
        save_directory: str = os.path.join(self.env_save_directory(message), file_name)
        format_file_size: str = MetaData.suitable_units_display(sever_file_size)
        return {
            'file_id': file_id,
            'temp_file_path': temp_file_path,
            'sever_file_size': sever_file_size,
            'file_name': file_name,
            'save_directory': save_directory,
            'format_file_size': format_file_size
        }

    async def __add_task(
            self,
            chat_id: Union[str, int],
            link_type: str,
            link: str,
            message: Union[pyrogram.types.Message, list],
            retry: dict,
            with_upload: Optional[dict] = None,
            diy_download_type: Optional[list] = None
    ) -> None:
        retry_count = retry.get('count')
        retry_id = retry.get('id')
        if isinstance(message, list):
            for _message in message:
                if retry_count != 0:
                    if _message.id == retry_id:
                        await self.__add_task(chat_id, link_type, link, _message, retry, with_upload, diy_download_type)
                        break
                else:
                    await self.__add_task(chat_id, link_type, link, _message, retry, with_upload, diy_download_type)
        else:
            _task = None
            valid_dtype: str = next((_ for _ in DownloadType() if getattr(message, _, None)), None)  # 判断该链接是否为有支持的类型。
            download_type: list = diy_download_type if diy_download_type else self.app.download_type
            if valid_dtype in download_type:
                # 如果是匹配到的消息类型就创建任务。
                console.log(
                    f'{_t(KeyWord.DOWNLOAD_TASK)}'
                    f'{_t(KeyWord.CHANNEL)}:"{chat_id}",'  # 频道名。
                    f'{_t(KeyWord.LINK)}:"{link}",'  # 链接。
                    f'{_t(KeyWord.LINK_TYPE)}:{_t(link_type)}。'  # 链接类型。
                )
                while self.app.current_task_num >= self.app.max_download_task:  # v1.0.7 增加下载任务数限制。
                    await self.event.wait()
                    self.event.clear()
                file_id, temp_file_path, sever_file_size, file_name, save_directory, format_file_size = \
                    self.get_media_meta(
                        message=message,
                        dtype=valid_dtype).values()
                retry['id'] = file_id
                if is_file_duplicate(
                        save_directory=save_directory,
                        sever_file_size=sever_file_size
                ):  # 检测是否存在。
                    self.download_complete_callback(
                        sever_file_size=sever_file_size,
                        temp_file_path=temp_file_path,
                        link=link,
                        message=message,
                        file_name=file_name,
                        retry_count=retry_count,
                        file_id=file_id,
                        format_file_size=format_file_size,
                        task_id=None,
                        with_upload=with_upload,
                        diy_download_type=diy_download_type,
                        _future=save_directory
                    )
                else:
                    console.log(
                        f'{_t(KeyWord.DOWNLOAD_TASK)}'
                        f'{_t(KeyWord.FILE)}:"{file_name}",'
                        f'{_t(KeyWord.SIZE)}:{format_file_size},'
                        f'{_t(KeyWord.TYPE)}:{_t(self.app.get_file_type(message, file_name, DownloadStatus.DOWNLOADING))},'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.DOWNLOADING)}。'
                    )
                    task_id = self.pb.progress.add_task(
                        description='📥',
                        filename=truncate_display_filename(file_name),
                        info=f'0.00B/{format_file_size}',
                        total=sever_file_size
                    )
                    _task = self.loop.create_task(
                        self.resume_download(
                            message=message,
                            file_name=temp_file_path,
                            progress=self.pb.download,
                            progress_args=(
                                sever_file_size,
                                self.pb.progress,
                                task_id
                            ),
                            compare_size=sever_file_size,
                            retry_count=retry_count
                        )
                    )
                    MetaData.print_current_task_num(
                        prompt=_t(KeyWord.CURRENT_DOWNLOAD_TASK),
                        num=self.app.current_task_num
                    )
                    _task.add_done_callback(
                        partial(
                            self.download_complete_callback,
                            sever_file_size,
                            temp_file_path,
                            link,
                            message,
                            file_name,
                            retry_count,
                            file_id,
                            format_file_size,
                            task_id,
                            with_upload,
                            diy_download_type
                        )
                    )
            else:
                _error = '不支持或被忽略的类型(已取消)。'
                try:
                    _, __, ___, file_name, ____, format_file_size = self.get_media_meta(
                        message=message,
                        dtype=valid_dtype
                    ).values()
                    if file_name:
                        console.log(
                            f'{_t(KeyWord.DOWNLOAD_TASK)}'
                            f'{_t(KeyWord.FILE)}:"{file_name}",'
                            f'{_t(KeyWord.SIZE)}:{format_file_size},'
                            f'{_t(KeyWord.TYPE)}:{_t(self.app.get_file_type(message, file_name, DownloadStatus.SKIP))},'
                            f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SKIP)}。'
                        )
                        DownloadTask.set_error(link=link, key=file_name, value=_error.replace('。', ''))
                    else:
                        raise Exception('不支持或被忽略的类型。')
                except Exception as _:
                    DownloadTask.set_error(link=link, value=_error.replace('。', ''))
                    console.log(
                        f'{_t(KeyWord.DOWNLOAD_TASK)}'
                        f'{_t(KeyWord.CHANNEL)}:"{chat_id}",'  # 频道名。
                        f'{_t(KeyWord.LINK)}:"{link}",'  # 链接。
                        f'{_t(KeyWord.LINK_TYPE)}:{_error}'  # 链接类型。
                    )
            self.queue.put_nowait(_task) if _task else None

    def __check_download_finish(
            self,
            message: pyrogram.types.Message,
            sever_file_size: int,
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
                f'{_t(KeyWord.DOWNLOAD_TASK)}'
                f'{_t(KeyWord.FILE)}:"{file_path}",'
                f'{_t(KeyWord.SIZE)}:{format_local_size},'
                f'{_t(KeyWord.TYPE)}:{_t(self.app.get_file_type(message, temp_file_path, DownloadStatus.SUCCESS))},'
                f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SUCCESS)}。',
            )
            return True
        console.log(
            f'{_t(KeyWord.DOWNLOAD_TASK)}'
            f'{_t(KeyWord.FILE)}:"{file_path}",'
            f'{_t(KeyWord.ERROR_SIZE)}:{format_local_size},'
            f'{_t(KeyWord.ACTUAL_SIZE)}:{format_sever_size},'
            f'{_t(KeyWord.TYPE)}:{_t(self.app.get_file_type(message, temp_file_path, DownloadStatus.FAILURE))},'
            f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}。'
        )
        return False

    @DownloadTask.on_complete
    def download_complete_callback(
            self,
            sever_file_size,
            temp_file_path,
            link,
            message,
            file_name,
            retry_count,
            file_id,
            format_file_size,
            task_id,
            with_upload,
            diy_download_type,
            _future
    ):
        if task_id is None:
            if retry_count == 0:
                console.log(
                    f'{_t(KeyWord.DOWNLOAD_TASK)}'
                    f'{_t(KeyWord.ALREADY_EXIST)}:"{_future}"'
                )
                console.log(
                    f'{_t(KeyWord.DOWNLOAD_TASK)}'
                    f'{_t(KeyWord.FILE)}:"{file_name}",'
                    f'{_t(KeyWord.SIZE)}:{format_file_size},'
                    f'{_t(KeyWord.TYPE)}:{_t(self.app.get_file_type(message, file_name, DownloadStatus.SKIP))},'
                    f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SKIP)}。', style='#e6db74'
                )
                DownloadTask.COMPLETE_LINK.add(link)
                if self.uploader:
                    if with_upload and isinstance(with_upload, dict):
                        try:
                            media_group = message.get_media_group()
                        except ValueError:
                            media_group = None
                        with_upload['message_id'] = message.id
                        with_upload['media_group'] = media_group
                        self.uploader.download_upload(
                            with_upload=with_upload,
                            file_path=os.path.join(self.env_save_directory(message), file_name)
                        )
        else:
            self.app.current_task_num -= 1
            self.event.set()  # v1.3.4 修复重试下载被阻塞的问题。
            if self.__check_download_finish(
                    message=message,
                    sever_file_size=sever_file_size,
                    temp_file_path=temp_file_path,
                    save_directory=self.env_save_directory(message),
                    with_move=True
            ):
                MetaData.print_current_task_num(
                    prompt=_t(KeyWord.CURRENT_DOWNLOAD_TASK),
                    num=self.app.current_task_num
                )
                if self.uploader:
                    if with_upload and isinstance(with_upload, dict):
                        try:
                            media_group = message.get_media_group()
                        except ValueError:
                            media_group = None
                        with_upload['message_id'] = message.id
                        with_upload['media_group'] = media_group
                        self.uploader.download_upload(
                            with_upload=with_upload,
                            file_path=os.path.join(self.env_save_directory(message), file_name)
                        )
                self.queue.task_done()
            else:
                if retry_count < self.app.max_download_retries:
                    retry_count += 1
                    task = self.loop.create_task(
                        self.create_download_task(
                            message_ids=link if isinstance(link, str) else message,
                            retry={'id': file_id, 'count': retry_count},
                            with_upload=with_upload,
                            diy_download_type=diy_download_type
                        )
                    )
                    task.add_done_callback(
                        partial(
                            self.__retry_call,
                            f'{_t(KeyWord.RE_DOWNLOAD)}:"{file_name}",'
                            f'{_t(KeyWord.RETRY_TIMES)}:{retry_count}/{self.app.max_download_retries}。'
                        )
                    )
                else:
                    _error = f'(达到最大重试次数:{self.app.max_download_retries}次)。'
                    console.log(
                        f'{_t(KeyWord.DOWNLOAD_TASK)}'
                        f'{_t(KeyWord.FILE)}:"{file_name}",'
                        f'{_t(KeyWord.SIZE)}:{format_file_size},'
                        f'{_t(KeyWord.TYPE)}:{_t(self.app.get_file_type(message, file_name, DownloadStatus.FAILURE))},'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}'
                        f'{_error}'
                    )
                    DownloadTask.set_error(link=link, key=file_name, value=_error.replace('。', ''))
                    self.bot_task_link.discard(link)
                    self.queue.task_done()
                link, file_name = None, None
            self.pb.progress.remove_task(task_id=task_id)
        return link, file_name

    async def download_chat(
            self,
            chat_id: str,
            callback_query: pyrogram.types.CallbackQuery
    ) -> Union[list, None]:
        origin_callback_query_text: str = callback_query.message.text
        cq = await callback_query.message.edit_text(
            text=f'{callback_query.message.text}\n'
                 f'⏳需要检索该频道所有匹配的消息,请耐心等待。\n'
                 f'💡请忽略终端中的请求频繁提示`messages.GetHistory`,因为这并不影响下载。',
            reply_markup=KeyboardButton.single_button(
                text=BotButton.RETRIEVE_MESSAGE,
                callback_data=BotCallbackText.NULL
            )
        )
        callback_query_text: str = cq.text

        try:
            _filter = Filter()
            download_chat_filter: Union[dict, None] = None
            for i in self.download_chat_filter:
                if chat_id == i:
                    download_chat_filter = self.download_chat_filter.get(chat_id)
            if not download_chat_filter:
                return None
            if not isinstance(download_chat_filter, dict):
                return None
            chat_id: Union[str, int] = int(chat_id) if chat_id.startswith('-') else chat_id
            date_filter = download_chat_filter.get('date_range')
            start_date = date_filter.get('start_date')
            end_date = date_filter.get('end_date')
            download_type: dict = download_chat_filter.get('download_type')
            keyword_filter: dict = download_chat_filter.get('keyword', {})
            include_comment: bool = download_chat_filter.get('comment', False)
            active_keywords = [k for k, v in keyword_filter.items() if v]
            links: list = []
            # 第一阶段：收集匹配的消息。
            messages_to_download = []
            media_group_matched = set()  # 记录已匹配的media_group_id。
            async for message in self.app.client.get_chat_history(
                    chat_id=chat_id,
                    reverse=True
            ):
                # 对于媒体组，如果该媒体组已匹配，直接添加。
                if getattr(message, 'media_group_id', None) and message.media_group_id in media_group_matched:
                    messages_to_download.append(message)
                    continue

                if (_filter.date_range(message, start_date, end_date) and
                        _filter.dtype(message, download_type) and
                        _filter.keyword_filter(message, active_keywords)):
                    messages_to_download.append(message)
                    # 如果是媒体组的第一条消息，记录该media_group_id。
                    if message.media_group_id:
                        media_group_matched.add(message.media_group_id)
                    try:
                        await callback_query.message.edit_text(
                            text=f'{callback_query_text}\n'
                                 f'{random.choice(("🔎", "🔍"))}检索消息中,已匹配到{len(messages_to_download)}条消息。',
                            reply_markup=KeyboardButton.single_button(
                                text=BotButton.RETRIEVE_MESSAGE,
                                callback_data=BotCallbackText.NULL)
                        )
                    except MessageNotModified:
                        pass
            if not messages_to_download:
                await callback_query.message.edit_text(
                    text=f'{callback_query.message.text}\n'
                         '❎没有找到任何匹配的消息。',
                    reply_markup=KeyboardButton.single_button(
                        text=BotButton.TASK_CANCEL,
                        callback_data=BotCallbackText.NULL
                    )
                )
                return None
            message_count: int = len(messages_to_download)
            # 第二阶段：对匹配的消息进行处理，获取评论区。
            for message in messages_to_download:
                message_link = message.link if message.link else message
                links.append(message_link)
                if not include_comment:
                    continue
                # 检查并获取评论区。
                try:
                    async for comment in self.app.client.get_discussion_replies(
                            chat_id=chat_id,
                            message_id=message.id
                    ):
                        # 根据用户设置的download_type过滤评论中的媒体，但不过滤具体时间。
                        if not _filter.dtype(comment, download_type):
                            continue
                        comment_link = comment.link if comment.link else comment
                        links.append(comment_link)
                        try:
                            await callback_query.message.edit_text(
                                text=f'{callback_query_text}\n'
                                     f'{random.choice(("🔎", "🔍"))}检索评论区中,已匹配到{len(links) - message_count}条消息。',
                                reply_markup=KeyboardButton.single_button(
                                    text=BotButton.RETRIEVE_COMMENT,
                                    callback_data=BotCallbackText.NULL)
                            )
                        except MessageNotModified:
                            pass
                except (ValueError, AttributeError, MsgIdInvalid):
                    # 消息没有评论区或消息ID无效，跳过。
                    pass
            diy_download_type: list = [_ for _ in DownloadType()]
            comment_count: int = (len(links) - message_count) if include_comment else 0
            total_count: int = message_count + comment_count
            assigned_count: int = 0
            for link in links:
                if assigned_count == total_count:
                    reply_markup = KeyboardButton.single_button(
                        text=BotButton.TASK_ASSIGN,
                        callback_data=BotCallbackText.NULL
                    )
                else:
                    reply_markup = KeyboardButton.single_button(
                        text=BotButton.ASSIGNING_TASK,
                        callback_data=BotCallbackText.NULL
                    )
                try:
                    await callback_query.message.edit_text(
                        text=f'{origin_callback_query_text}\n'
                             f'🔎匹配消息:{message_count}条,评论区消息:{comment_count}条,共{total_count}条。\n'
                             f'⭐️[{assigned_count}/{total_count}]分配下载任务中。\n'
                             f'{random.choice(("⏳", "⌛"))}{self.pb.bot(assigned_count, total_count)}',
                        reply_markup=reply_markup
                    )
                except MessageNotModified:
                    pass
                await self.create_download_task(
                    message_ids=link,
                    single_link=True,
                    diy_download_type=diy_download_type
                )
                assigned_count += 1
            await callback_query.message.edit_text(
                text=origin_callback_query_text,
                reply_markup=KeyboardButton.single_button(
                    text=BotButton.TASK_ASSIGN,
                    callback_data=BotCallbackText.NULL
                )
            )
            return links
        except Exception as e:
            log.error(
                f'{_t(KeyWord.CHANNEL)}:"{chat_id}",无法进行下载,{_t(KeyWord.REASON)}:"{e}"',
                exc_info=True
            )
            asyncio.create_task(callback_query.message.edit_text(
                text=f'{origin_callback_query_text}`\n'
                     f'⚠️由于"{e}"无法执行频道下载任务。',
                reply_markup=KeyboardButton.single_button(
                    text=BotButton.TASK_CANCEL,
                    callback_data=BotCallbackText.NULL
                )
            ))

    @DownloadTask.on_create_task
    async def create_download_task(
            self,
            message_ids: Union[pyrogram.types.Message, str],
            retry: Union[dict, None] = None,
            single_link: bool = False,
            with_upload: Union[dict, None] = None,
            diy_download_type: Optional[list] = None
    ) -> dict:
        retry = retry if retry else {'id': -1, 'count': 0}
        diy_download_type = [_ for _ in DownloadType()] if with_upload else diy_download_type
        try:
            if isinstance(message_ids, pyrogram.types.Message):
                chat_id = message_ids.chat.id
                meta: dict = {
                    'link_type': LinkType.SINGLE,
                    'chat_id': chat_id,
                    'message': message_ids,
                    'member_num': 1
                }
                link = message_ids.link if message_ids.link else message_ids.id
            else:
                meta: dict = await get_message_by_link(
                    client=self.app.client,
                    link=message_ids,
                    single_link=single_link
                )
                link = message_ids

            link_type, chat_id, message, member_num = meta.values()
            DownloadTask.set(link, 'link_type', link_type)
            DownloadTask.set(link, 'member_num', member_num)
            await self.__add_task(chat_id, link_type, link, message, retry, with_upload, diy_download_type)
            return {
                'chat_id': chat_id,
                'member_num': member_num,
                'link_type': link_type,
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
                'chat_id': None,
                'member_num': 0,
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
                'chat_id': None,
                'member_num': 0,
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
                'chat_id': None,
                'member_num': 0,
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
                'chat_id': None,
                'member_num': 0,
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
                'chat_id': None,
                'member_num': 0,
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
                'chat_id': None,
                'member_num': 0,
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
                'chat_id': None,
                'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e),
                    'error_msg': '没有找到有效链接'
                }
            }
        except UsernameNotOccupied as e:
            return {
                'chat_id': None,
                'member_num': 0,
                'link_type': None,
                'status': DownloadStatus.FAILURE,
                'e_code': {
                    'all_member': str(e), 'error_msg': '频道不存在'
                }
            }
        except Exception as e:
            log.exception(e)
            return {
                'chat_id': None,
                'member_num': 0,
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
                    elif i == '' or '#':
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
            console.log('🔗 没有找到有效链接,程序已退出。', style='#FF4689')
            sys.exit(0)
        else:
            console.log('🔗 没有找到有效链接。', style='#FF4689')
            return None

    def __retry_call(self, notice, _future):
        self.queue.task_done()
        console.log(notice, style='#FF4689')

    async def __download_media_from_links(self) -> None:
        await self.app.client.start(use_qr=False)
        self.my_id = await get_my_id(self.app.client)
        self.pb.progress.start()  # v1.1.8修复登录输入手机号不显示文本问题。
        if self.app.bot_token is not None:
            result = await self.start_bot(
                self.app,
                self.app.client,
                pyrogram.Client(
                    name=self.BOT_NAME,
                    api_hash=self.app.api_hash,
                    api_id=self.app.api_id,
                    bot_token=self.app.bot_token,
                    workdir=self.app.work_directory,
                    proxy=self.app.proxy if self.app.enable_proxy else None,
                    sleep_threshold=SLEEP_THRESHOLD
                )
            )
            console.log(result, style='#B1DB74' if self.is_bot_running else '#FF4689')
            if self.is_bot_running:
                self.uploader = TelegramUploader(download_object=self)
                self.cd = CallbackData()
                if self.gc.upload_delete:
                    console.log(
                        f'在使用转发(/forward)、监听转发(/listen_forward)、上传(/upload)、递归上传(/upload_r)时:\n'
                        f'当检测到"受限转发"时,自动采用"下载后上传"的方式,并在完成后删除本地文件。\n'
                        f'如需关闭,前往机器人[帮助页面]->[设置]->[上传设置]进行修改。\n',
                        style='#FF4689'
                    )
        self.is_running = True
        self.running_log.add(self.is_running)
        links: Union[set, None] = self.__process_links(link=self.app.links)
        # 将初始任务添加到队列中。
        [await self.loop.create_task(self.create_download_task(message_ids=link, retry=None)) for link in
         sorted(links)] if links else None
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
            MetaData.print_helper()
            MetaData.print_meta()
            self.app.print_env_table(self.app)
            self.app.print_config_table(self.app)
            self.loop.run_until_complete(self.__download_media_from_links())
        except KeyError as e:
            record_error: bool = True
            if str(e) == '0':
                log.error('「网络」或「代理问题」,在确保当前网络连接正常情况下检查:\n「VPN」是否可用,「软件代理」是否配置正确。')
                console.print(Issues.PROXY_NOT_CONFIGURED)
                raise SystemExit(0)
            log.exception(f'运行出错,{_t(KeyWord.REASON)}:"{e}"')
        except BadMsgNotification as e:
            record_error: bool = True
            if str(e) in (str(BadMsgNotification(16)), str(BadMsgNotification(17))):
                console.print(Issues.SYSTEM_TIME_NOT_SYNCHRONIZED)
                raise SystemExit(0)
            log.exception(f'运行出错,{_t(KeyWord.REASON)}:"{e}"')
        except (SessionRevoked, AuthKeyUnregistered, SessionExpired, Unauthorized) as e:
            log.error(f'登录时遇到错误,{_t(KeyWord.REASON)}:"{e}"')
            res: bool = safe_delete(file_p_d=os.path.join(self.app.DIRECTORY_NAME, 'sessions'))
            record_error: bool = True
            if res:
                log.warning('账号已失效,已删除旧会话文件,请重启软件。')
            else:
                log.error('账号已失效,请手动删除软件目录下的sessions文件夹后重启软件。')
        except (ConnectionError, TimeoutError) as e:
            record_error: bool = True
            if not self.app.enable_proxy:
                log.error(f'网络连接失败,请尝试配置代理,{_t(KeyWord.REASON)}:"{e}"')
                console.print(Issues.PROXY_NOT_CONFIGURED)
            else:
                log.error(f'网络连接失败,请检查VPN是否可用,{_t(KeyWord.REASON)}:"{e}"')
        except AttributeError as e:
            record_error: bool = True
            log.error(f'登录超时,请重新打开软件尝试登录,{_t(KeyWord.REASON)}:"{e}"')
        except KeyboardInterrupt:
            console.log('⌨️ 用户键盘中断。')
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
                self.app.print_link_table(
                    link_info=DownloadTask.LINK_INFO,
                    export=self.gc.get_config('export_table').get('link')
                )
                self.app.print_count_table(
                    export=self.gc.get_config('export_table').get('count')
                )
                self.app.print_upload_table(
                    upload_tasks=UploadTask.TASKS,
                    export=self.gc.get_config('export_table').get('upload')
                )
                MetaData.pay()
                self.app.process_shutdown(60) if len(self.running_log) == 2 else None  # v1.2.8如果并未打开客户端执行任何下载,则不执行关机。
            self.app.ctrl_c()

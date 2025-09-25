# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023/10/3 1:00:03
# File:downloader.py
import os
import sys
import asyncio
import datetime

from functools import partial
from sqlite3 import OperationalError
from typing import Union, Callable, Optional, Dict

import pyrogram
from pyrogram.enums.parse_mode import ParseMode
from pyrogram.errors.exceptions.bad_request_400 import (
    MsgIdInvalid,
    UsernameInvalid,
    ChannelInvalid,
    BotMethodInvalid,
    UsernameNotOccupied,
    PeerIdInvalid,
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
from module.bot import Bot, KeyboardButton, CallbackData
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
from module.task import DownloadTask
from module.stdio import ProgressBar, Base64Image, MetaData
from module.uploader import TelegramUploader
from module.util import (
    parse_link,
    format_chat_link,
    get_message_by_link,
    get_chat_with_notify,
    safe_message,
    truncate_display_filename
)


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
        self.uploader: Union[TelegramUploader, None] = None
        self.cd: Union[CallbackData, None] = None

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
            task: dict = await self.create_download_task(message_ids=link, retry=None, with_upload=with_upload)
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

    async def get_upload_link_from_bot(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            delete: bool = False,
            save_directory: str = None
    ):
        link_meta: Union[dict, None] = await super().get_upload_link_from_bot(client, message)
        if link_meta is None:
            return None
        file_path: str = link_meta.get('file_path')
        target_link: str = link_meta.get('target_link')
        try:
            await self.uploader.create_upload_task(
                link=target_link,
                file_path=file_path
            )
        except ValueError:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_parameters=ReplyParameters(message_id=message.id),
                text=f'⬇️⬇️⬇️目标频道不存在⬇️⬇️⬇️\n{target_link}'
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
                text=f'🙈🙈🙈请稍后🙈🙈🙈{load_name}加载中. . .',
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
                    text=f'🐵🐵🐵{load_name}加载成功!🐵🐵🐵'
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
                    text='😊😊😊欢迎使用😊😊😊您的支持是我持续更新的动力。',
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
                        'with_delete': False
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
        elif callback_data == BotCallbackText.UPLOAD_SETTING:
            await kb.toggle_upload_setting_button(global_config=self.gc.config)
        elif callback_data == BotCallbackText.FORWARD_SETTING:
            await kb.toggle_forward_setting_button(global_config=self.gc.config)
        elif callback_data in (BotCallbackText.LINK_TABLE, BotCallbackText.COUNT_TABLE):
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
        elif callback_data in (BotCallbackText.TOGGLE_LINK_TABLE, BotCallbackText.TOGGLE_COUNT_TABLE):
            async def _toggle_button(_table_type):
                export_config: dict = self.gc.config.get('export_table')
                export_config[_table_type] = not export_config.get(_table_type)
                t_t: str = '链接统计表' if _table_type == 'link' else '计数统计表'
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
        elif callback_data in (BotCallbackText.EXPORT_LINK_TABLE, BotCallbackText.EXPORT_COUNT_TABLE):
            _prompt_string: str = ''
            res: Union[bool, None] = False
            if callback_data == BotCallbackText.EXPORT_LINK_TABLE:
                _prompt_string: str = '链接统计表'
                res: Union[bool, None] = self.app.print_link_table(
                    link_info=DownloadTask.LINK_INFO,
                    export=True,
                    only_export=True
                )
            elif callback_data == BotCallbackText.EXPORT_COUNT_TABLE:
                _prompt_string: str = '计数统计表'
                res: Union[bool, None] = self.app.print_count_table(
                    export=True,
                    only_export=True
                )
            if res:
                await callback_query.message.edit_text(
                    f'✅✅✅`{_prompt_string}`已发送至您的「终端」并已「导出」为表格请注意查收。\n(请查看软件目录下`DownloadRecordForm`文件夹)')
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
                BotCallbackText.TOGGLE_FORWARD_VIDEO,
                BotCallbackText.TOGGLE_FORWARD_PHOTO,
                BotCallbackText.TOGGLE_FORWARD_AUDIO,
                BotCallbackText.TOGGLE_FORWARD_VOICE,
                BotCallbackText.TOGGLE_FORWARD_ANIMATION,
                BotCallbackText.TOGGLE_FORWARD_DOCUMENT,
                BotCallbackText.TOGGLE_FORWARD_TEXT
        ):
            def _toggle_button(_param: str):
                param: bool = self.gc.get_nesting_config(
                    default_nesting=self.gc.default_forward_type_nesting,
                    param='forward_type',
                    nesting_param=_param
                )
                self.gc.config.get('forward_type', self.gc.default_forward_type_nesting)[_param] = not param
                f_s = '禁用' if param else '启用'
                f_p = f'已{f_s}"{_param}"类型的转发。'
                console.log(f_p, style='#FF4689')
                log.info(f_p)

            try:
                if callback_data == BotCallbackText.TOGGLE_FORWARD_VIDEO:
                    _toggle_button('video')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_PHOTO:
                    _toggle_button('photo')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_AUDIO:
                    _toggle_button('audio')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_VOICE:
                    _toggle_button('voice')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_ANIMATION:
                    _toggle_button('animation')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_DOCUMENT:
                    _toggle_button('document')
                elif callback_data == BotCallbackText.TOGGLE_FORWARD_TEXT:
                    _toggle_button('text')
                self.gc.save_config(self.gc.config)
                await kb.toggle_forward_setting_button(self.gc.config)
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
                BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER,  # 设置下载日期范围设置页面。
                BotCallbackText.DOWNLOAD_CHAT_ID,  # 执行任务。
                BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL,  # 取消任务。
                BotCallbackText.FILTER_START_DATE,  # 设置下载起始日期。
                BotCallbackText.FILTER_END_DATE  # 设置下载结束日期。
        ) or callback_data.startswith(
            ('cal_last_', 'cal_next_', 'cal_select_')  # 切换月份,选择日期。
        ):
            def _get_update_time():
                _start_timestamp = self.download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['date_range'][
                    'start_date']
                _end_timestamp = self.download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['date_range']['end_date']
                _start_time = datetime.datetime.fromtimestamp(_start_timestamp) if _start_timestamp else '未定义'
                _end_time = datetime.datetime.fromtimestamp(_end_timestamp) if _end_timestamp else '未定义'
                return _start_time, _end_time

            def _remove_chat_id(_chat_id):
                if _chat_id in self.download_chat_filter:
                    self.download_chat_filter.pop(_chat_id)
                    log.info(f'"{_chat_id}"已从{self.download_chat_filter}中移除。')

            async def _verification_time(_start_time, _end_time) -> bool:
                if isinstance(_start_time, datetime.datetime) and isinstance(_end_time, datetime.datetime):
                    if _start_time > _end_time:
                        await callback_query.message.reply_text(
                            text=f'❌❌❌日期设置失败❌❌❌\n'
                                 f'`起始日期({_start_time})`>`结束日期({_end_time})`\n'
                        )
                        return False
                return True

            if callback_data in (BotCallbackText.DOWNLOAD_CHAT_ID, BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL):  # 执行或取消任务。
                chat_id = BotCallbackText.DOWNLOAD_CHAT_ID
                BotCallbackText.DOWNLOAD_CHAT_ID = 'download_chat_id'
                if callback_data == chat_id:
                    await callback_query.message.edit_text(
                        text=f'下载频道:`{chat_id}`\n{callback_query.message.text}',
                        reply_markup=kb.single_button(
                            text=BotButton.TASK_ASSIGN,
                            callback_data=BotCallbackText.NULL
                        )
                    )
                    await self.download_chat(
                        chat_id=chat_id
                    )
                    _remove_chat_id(chat_id)
                elif callback_data == BotCallbackText.DOWNLOAD_CHAT_ID_CANCEL:
                    _remove_chat_id(chat_id)
                    await callback_query.message.edit_text(
                        text=f'下载频道:`{chat_id}`\n{callback_query.message.text}',
                        reply_markup=kb.single_button(
                            text=BotButton.TASK_CANCEL,
                            callback_data=BotCallbackText.NULL
                        )
                    )
            elif callback_data in (
                    BotCallbackText.DOWNLOAD_CHAT_FILTER,
                    BotCallbackText.DOWNLOAD_CHAT_DATE_FILTER
            ):
                # 返回或点击。
                await callback_query.message.edit_text(
                    text=f'⏮️当前选择的起始日期为:{_get_update_time()[0]}\n'
                         f'⏭️当前选择的结束日期为:{_get_update_time()[1]}',
                    reply_markup=kb.download_chat_filter_button() if callback_data == BotCallbackText.DOWNLOAD_CHAT_FILTER else kb.filter_date_range_button()
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
                    text=f'📅选择{p_s_d}日期:\n{callback_query.message.text}'
                )
                await kb.calendar_keyboard(dtype=dtype)
            elif callback_data.startswith(('cal_last_', 'cal_next_')):
                parts = callback_data.split('_')
                dtype = None
                if 'start' in callback_data:
                    dtype = CalenderKeyboard.START_TIME_BUTTON
                elif 'end' in callback_data:
                    dtype = CalenderKeyboard.END_TIME_BUTTON
                year = int(parts[-2])
                month = int(parts[-1])
                await kb.calendar_keyboard(year=year, month=month, dtype=dtype)
                log.info(f'日期切换为{year}年,{month}月。')
            elif callback_data.startswith('cal_select_'):
                async def _set_time(_dtype, _timestamp) -> bool:
                    _last_timestamp = self.download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['date_range'][_dtype]
                    self.download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['date_range'][_dtype] = _timestamp
                    _start_time, _end_time = _get_update_time()
                    if not await _verification_time(_start_time, _end_time):
                        self.download_chat_filter[BotCallbackText.DOWNLOAD_CHAT_ID]['date_range'][
                            _dtype] = _last_timestamp
                        return False
                    return True

                parts = callback_data.split('_')
                date = parts[-1]
                dtype = ''
                p_s_d = ''
                timestamp = datetime.datetime.timestamp(datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S'))
                if callback_data.startswith('cal_select_start_'):
                    dtype = 'start_date'
                    if not await _set_time(_dtype='start_date', _timestamp=timestamp):
                        return None
                    p_s_d = '起始'
                elif callback_data.startswith('cal_select_end_'):
                    dtype = 'end_date'
                    p_s_d = '结束'
                if not await _set_time(_dtype=dtype, _timestamp=timestamp):
                    return None
                start_time, end_time = _get_update_time()
                await callback_query.message.edit_text(
                    text=f'📅选择{p_s_d}日期:\n'
                         f'⏮️当前选择的起始日期为:{start_time}\n'
                         f'⏭️当前选择的结束日期为:{end_time}',
                    reply_markup=callback_query.message.reply_markup
                )
                log.info(f'日期设置,起始日期:{start_time},结束日期:{end_time}。')

    async def forward(
            self,
            client: pyrogram.Client,
            message: pyrogram.types.Message,
            message_id: int,
            origin_chat_id: int,
            target_chat_id: int,
            target_link: str,
            download_upload: Optional[bool] = False,
            media_group: Optional[list] = None
    ):
        try:
            if not self.check_type(message):
                console.log(
                    f'{_t(KeyWord.CHANNEL)}:"{target_chat_id}",{_t(KeyWord.MESSAGE_ID)}:"{message_id}"'
                    f' -> '
                    f'{_t(KeyWord.CHANNEL)}:"{origin_chat_id}",'
                    f'{_t(KeyWord.STATUS)}:{_t(KeyWord.FORWARD_SKIP)}。'
                )
                return None
            if media_group:
                await self.app.client.copy_media_group(
                    chat_id=target_chat_id,
                    from_chat_id=origin_chat_id,
                    message_id=message_id,
                    disable_notification=True
                )
            else:
                await self.app.client.copy_message(
                    chat_id=target_chat_id,
                    from_chat_id=origin_chat_id,
                    message_id=message_id,
                    disable_notification=True,
                    protect_content=False
                )
            p_message_id = ','.join(map(str, media_group)) if media_group else message_id
            console.log(
                f'{_t(KeyWord.CHANNEL)}:"{target_chat_id}",{_t(KeyWord.MESSAGE_ID)}:"{p_message_id}"'
                f' -> '
                f'{_t(KeyWord.CHANNEL)}:"{origin_chat_id}",'
                f'{_t(KeyWord.STATUS)}:{_t(KeyWord.FORWARD_SUCCESS)}。'
            )
        except (ChatForwardsRestricted_400, ChatForwardsRestricted_406):
            if not download_upload:
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
                    'with_delete': self.gc.upload_delete
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
            origin_chat: Union[pyrogram.types.Chat, None] = await get_chat_with_notify(
                user_client=self.app.client,
                bot_client=client,
                bot_message=message,
                chat_id=origin_meta.get('chat_id'),
                error_msg=f'⬇️⬇️⬇️原始频道不存在⬇️⬇️⬇️\n{origin_link}'
            )
            target_chat: Union[pyrogram.types.Chat, None] = await get_chat_with_notify(
                user_client=self.app.client,
                bot_client=client,
                bot_message=message,
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
            origin_chat_id = origin_chat.id
            target_chat_id = target_chat.id
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
                    self.cd.data = {
                        'origin_link': origin_link,
                        'target_link': target_link,
                        'start_id': start_id,
                        'end_id': end_id
                    }
                    channel = '@' + origin_chat.username if isinstance(
                        getattr(origin_chat, 'username'),
                        str) else ''
                    await client.send_message(
                        chat_id=message.from_user.id,
                        text=f'⚠️⚠️⚠️无法转发⚠️⚠️⚠️\n`{origin_link}`\n{channel}存在内容保护限制。',
                        parse_mode=ParseMode.MARKDOWN,
                        reply_parameters=ReplyParameters(message_id=message.id),
                        reply_markup=KeyboardButton.restrict_forward_button()
                    )
                    return None
                except Exception as e:
                    log.warning(
                        f'{_t(KeyWord.CHANNEL)}:"{origin_chat_id}",{_t(KeyWord.MESSAGE_ID)}:"{i.id}"'
                        f' -> '
                        f'{_t(KeyWord.CHANNEL)}:"{target_chat_id}",'
                        f'{_t(KeyWord.STATUS)}:{_t(KeyWord.FORWARD_FAILURE)},'
                        f'{_t(KeyWord.REASON)}:"{e}"')
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
                    for i in invalid_id:
                        last_message: Union[pyrogram.types.Message, str, None] = await self.safe_edit_message(
                            client=client,
                            message=message,
                            last_message_id=last_message.id,
                            text=safe_message(
                                f'{last_message.text}\n{format_chat_link(origin_link, topic=origin_chat.is_forum)}/{i}'
                            )
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
                                    url=format_chat_link(target_link, topic=target_chat.is_forum)
                                )
                            ]
                        ]
                    )
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
            message: pyrogram.types,
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
            text=f'`{link if len(args) == 1 else forward_emoji.join(args)}`\n⚠️⚠️⚠️已经在监听列表中⚠️⚠️⚠️\n请选择是否移除',
            link_preview_options=LINK_PREVIEW_OPTIONS,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        BotButton.OK,
                        callback_data=f'{BotCallbackText.REMOVE_LISTEN_DOWNLOAD} {link}' if command == '/listen_download' else BotCallbackText.REMOVE_LISTEN_FORWARD
                    ),
                    InlineKeyboardButton(
                        BotButton.CANCEL,
                        callback_data=BotCallbackText.NULL
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

        async def add_listen_chat(_link: str, _listen_chat: dict, _callback: callable) -> bool:
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
            log.exception(f'监听下载出现错误,{_t(KeyWord.REASON)}:{e}')

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
            log.exception(f'监听转发出现错误,{_t(KeyWord.REASON)}:{e}')

    async def resume_download(
            self,
            message: Union[pyrogram.types.Message, str],
            file_name: str,
            progress: Callable = None,
            progress_args: tuple = (),
            chunk_size: int = 1024 * 1024,
            compare_size: Union[int, None] = None  # 不为None时,将通过大小比对判断是否为完整文件。
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
            mode = 'ab'
            console.log(
                f'{_t(KeyWord.DOWNLOAD_TASK)}'
                f'{_t(KeyWord.RESUME)}:"{file_name}",'
                f'{_t(KeyWord.ERROR_SIZE)}:{MetaData.suitable_units_display(downloaded)}。')
        with open(file=temp_path, mode=mode) as f:
            skip_chunks: int = downloaded // chunk_size  # 计算要跳过的块数。
            async for chunk in self.app.client.stream_media(message=message, offset=skip_chunks):
                f.write(chunk)
                downloaded += len(chunk)
                progress(downloaded, *progress_args)
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
            with_upload: Union[dict, None] = None
    ) -> None:
        retry_count = retry.get('count')
        retry_id = retry.get('id')
        if isinstance(message, list):
            for _message in message:
                if retry_count != 0:
                    if _message.id == retry_id:
                        await self.__add_task(chat_id, link_type, link, _message, retry, with_upload)
                        break
                else:
                    await self.__add_task(chat_id, link_type, link, _message, retry, with_upload)
        else:
            _task = None
            valid_dtype: str = next((_ for _ in DownloadType() if getattr(message, _, None)), None)  # 判断该链接是否为有支持的类型。
            if valid_dtype in self.app.download_type:
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
                        _future=save_directory
                    )
                else:
                    console.log(
                        f'{_t(KeyWord.DOWNLOAD_TASK)}'
                        f'{_t(KeyWord.FILE)}:"{file_name}",'
                        f'{_t(KeyWord.SIZE)}:{format_file_size},'
                        f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.DOWNLOADING))},'
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
                            progress=self.pb.bar,
                            progress_args=(
                                sever_file_size,
                                self.pb.progress,
                                task_id
                            ),
                            compare_size=sever_file_size
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
                            with_upload
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
                            f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.SKIP))},'
                            f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SKIP)}。'
                        )
                        self.app.guess_file_type(file_name, DownloadStatus.SKIP)
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
                f'{_t(KeyWord.DOWNLOAD_TASK)}'
                f'{_t(KeyWord.FILE)}:"{file_path}",'
                f'{_t(KeyWord.SIZE)}:{format_local_size},'
                f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(temp_file_path, DownloadStatus.SUCCESS))},'
                f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SUCCESS)}。',
            )
            return True
        console.log(
            f'{_t(KeyWord.DOWNLOAD_TASK)}'
            f'{_t(KeyWord.FILE)}:"{file_path}",'
            f'{_t(KeyWord.ERROR_SIZE)}:{format_local_size},'
            f'{_t(KeyWord.ACTUAL_SIZE)}:{format_sever_size},'
            f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(temp_file_path, DownloadStatus.FAILURE))},'
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
                    f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.SKIP))},'
                    f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SKIP)}。', style='#e6db74'
                )
                if self.uploader:
                    self.uploader.download_upload(
                        with_upload=with_upload,
                        file_path=os.path.join(self.env_save_directory(message), file_name)
                    )
        else:
            self.app.current_task_num -= 1
            self.event.set()  # v1.3.4 修复重试下载被阻塞的问题。
            self.queue.task_done()
            if self.__check_download_finish(
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
                    self.uploader.download_upload(
                        with_upload=with_upload,
                        file_path=os.path.join(self.env_save_directory(message), file_name)
                    )
            else:
                if retry_count < self.app.max_download_retries:
                    retry_count += 1
                    task = self.loop.create_task(
                        self.create_download_task(
                            message_ids=link if isinstance(link, str) else message,
                            retry={'id': file_id, 'count': retry_count})
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
                        f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.FAILURE))},'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}'
                        f'{_error}'
                    )
                    DownloadTask.set_error(link=link, key=file_name, value=_error.replace('。', ''))
                    self.bot_task_link.discard(link)
                link, file_name = None, None
            self.pb.progress.remove_task(task_id=task_id)
        return link, file_name

    async def download_chat(
            self,
            chat_id: str
    ):
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
        links: list = []
        async for message in self.app.client.get_chat_history(
                chat_id=chat_id,
                reverse=True
        ):
            if _filter.date_filter(message, start_date, end_date):
                links.append(message.link if message.link else message)
        for link in links:
            await self.create_download_task(message_ids=link, single_link=True)

    @DownloadTask.on_create_task
    async def create_download_task(
            self,
            message_ids: Union[pyrogram.types.Message, str],
            retry: Union[dict, None] = None,
            single_link: bool = False,
            with_upload: Union[dict, None] = None
    ) -> dict:
        retry = retry if retry else {'id': -1, 'count': 0}
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
            await self.__add_task(chat_id, link_type, link, message, retry, with_upload)
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
            if self.is_bot_running:
                self.uploader = TelegramUploader(
                    client=self.app.client,
                    loop=self.loop,
                    is_premium=self.app.client.me.is_premium,
                    progress=self.pb,
                    max_upload_task=self.app.max_upload_task,
                    max_retry_count=self.app.max_upload_retries,
                    notify=self.done_notice
                )
                self.cd = CallbackData()
                if self.gc.upload_delete:
                    console.log(
                        f'在使用监听转发(/listen_forward)时:\n'
                        f'当检测到"受限转发"时,自动采用"下载后上传"的方式,并在完成后删除本地文件。\n'
                        f'如需关闭,前往机器人[帮助页面]->[设置]->[上传设置]进行修改。\n',
                        style='#FF4689'
                    )
        self.is_running = True
        self.running_log.add(self.is_running)
        links: Union[set, None] = self.__process_links(link=self.app.links)
        # 将初始任务添加到队列中。
        [await self.loop.create_task(self.create_download_task(message_ids=link, retry=None)) for link in
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
                self.app.print_link_table(
                    link_info=DownloadTask.LINK_INFO,
                    export=self.gc.get_config('export_table').get('link')
                )
                self.app.print_count_table(
                    export=self.gc.get_config('export_table').get('count')
                )
                MetaData.pay()
                self.app.process_shutdown(60) if len(self.running_log) == 2 else None  # v1.2.8如果并未打开客户端执行任何下载,则不执行关机。
            self.app.ctrl_c()

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
from typing import Tuple, Union

import pyrogram
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate, ChatForwardsRestricted
from pyrogram.errors.exceptions.unauthorized_401 import SessionRevoked, AuthKeyUnregistered, SessionExpired
from pyrogram.errors.exceptions.bad_request_400 import MsgIdInvalid, UsernameInvalid, ChannelInvalid, \
    BotMethodInvalid, MessageNotModified, UsernameNotOccupied

from module import console, log, utils
from module.bot import Bot
from module.task import Task
from module.language import _t
from module.app import Application, MetaData
from module.util import truncate_display_filename
from module.stdio import ProgressBar, Base64Image
from module.enums import LinkType, DownloadStatus, KeyWord, BotCallbackText, BotButton, BotMessage
from module.path_tool import is_file_duplicate, safe_delete, get_file_size, split_path, compare_file_size, \
    move_to_save_directory


class TelegramRestrictedMediaDownloader(Bot):

    def __init__(self):
        super().__init__()
        MetaData.print_helper()
        self.loop = asyncio.get_event_loop()
        self.event = asyncio.Event()
        self.queue = asyncio.Queue()
        self.app = Application()
        self.is_running: bool = False
        self.running_log: set = set()
        self.running_log.add(self.is_running)
        self.pb = ProgressBar()

    async def get_link_from_bot(self,
                                client: pyrogram.Client,
                                message: pyrogram.types.Message):
        link_meta: dict | None = await super().get_link_from_bot(client, message)
        if link_meta is None:
            return
        else:
            right_link: set = link_meta.get('right_link')
            invalid_link: set = link_meta.get('invalid_link')
            last_bot_message_id: int | None = link_meta.get('last_bot_message_id')
        chat_id: Union[int, str] = message.from_user.id
        exist_link: set = set([_ for _ in right_link if _ in self.bot_task_link])
        exist_link.update(right_link & Task.COMPLETE_LINK)
        right_link -= exist_link
        await self.edit_message_text(
            client=client,
            message=message,
            chat_id=chat_id,
            last_message_id=last_bot_message_id,
            text=self.update_text(
                right_link=right_link,
                exist_link=exist_link,
                invalid_link=invalid_link
            )
        )
        links: set | None = self.__process_links(link=list(right_link))
        if links is None:
            return
        else:
            for link in links:
                task: dict = await self.__create_download_task(link=link, retry=None)
                invalid_link.add(link) if task.get('status') == DownloadStatus.FAILURE else self.bot_task_link.add(link)
            right_link -= invalid_link
            await self.edit_message_text(
                client=client,
                message=message,
                chat_id=chat_id,
                last_message_id=last_bot_message_id,
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
            last_msg = await client.send_message(chat_id=chat_id,
                                                 text=f'🙈🙈🙈请稍后🙈🙈🙈{load_name}加载中. . .',
                                                 disable_web_page_preview=True
                                                 )
            await client.send_photo(chat_id=chat_id,
                                    photo=Base64Image.base64_to_binary_io(Base64Image.pay),
                                    disable_notification=True
                                    )
            await client.edit_message_text(chat_id=chat_id,
                                           message_id=last_msg.id,
                                           text=f'🐵🐵🐵{load_name}加载成功!🐵🐵🐵')
        except Exception as e:
            e_code['e_code'] = e
        finally:
            return e_code

    async def help(self,
                   client: pyrogram.Client,
                   message: pyrogram.types.Message) -> None:
        chat_id = message.from_user.id
        if message.text == '/start':
            res: dict = await self.__send_pay_qr(client=client, chat_id=chat_id, load_name='机器人')
            if res.get('e_code'):
                msg = '😊😊😊欢迎使用😊😊😊'
            else:
                msg = '😊😊😊欢迎使用😊😊😊您的支持是我持续更新的动力。'
            await client.send_message(chat_id=chat_id, text=msg, disable_web_page_preview=True)
        await super().help(client, message)

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
                            new_row.append(InlineKeyboardButton(
                                text=BotButton.CLOSE_NOTICE if self.gc.config.get(
                                    BotCallbackText.NOTICE) else BotButton.OPEN_NOTICE,
                                callback_data=button.callback_data
                            ))
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
            res: dict = await self.__send_pay_qr(client=client,
                                                 chat_id=callback_query.message.from_user.id,
                                                 load_name='收款码')
            MetaData.pay()
            if res.get('e_code'):
                msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」十分感谢您的支持!'
            else:
                msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」与「对话框」十分感谢您的支持!'
            await callback_query.message.reply_text(msg)
        elif callback_data == BotCallbackText.LINK_TABLE:
            res: bool | str = self.app.print_link_table(Task.LINK_INFO)
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
            origin_link, start_id, end_id = callback_data.split()
            await self.app.client.send_message(chat_id=callback_query.message.from_user.id,
                                               text=f'/download {origin_link} {start_id} {end_id}',
                                               disable_web_page_preview=True)

    async def __get_chat(self, bot_client: pyrogram.Client,
                         bot_message: pyrogram.types.Message,
                         chat_id: Union[int, str],
                         error_msg: str) -> pyrogram.types.Chat | None:
        try:
            chat = await self.app.client.get_chat(chat_id)
            return chat
        except UsernameNotOccupied:
            await bot_client.send_message(
                chat_id=bot_message.from_user.id,
                reply_to_message_id=bot_message.id,
                text=error_msg
            )
            return None

    async def get_forward_link_from_bot(self, client: pyrogram.Client,
                                        message: pyrogram.types.Message) -> dict | None:
        meta: dict | None = await super().get_forward_link_from_bot(client, message)
        if meta is None:
            return None
        origin_link: str = meta.get('origin_link')
        target_link: str = meta.get('target_link')
        start_id: int = meta.get('message_range')[0]
        end_id: int = meta.get('message_range')[1]
        try:
            origin_meta: dict = await self.__extract_link_content(origin_link, only_chat_id=True)
            target_meta: dict = await self.__extract_link_content(target_link, only_chat_id=True)
            origin_chat: pyrogram.types.Chat | None = await self.__get_chat(
                bot_client=client, bot_message=message,
                chat_id=origin_meta.get('chat_id'),
                error_msg=f'⬇️⬇️⬇️原始频道不存在⬇️⬇️⬇️\n{origin_link}'
            )
            target_chat: pyrogram.types.Chat | None = await self.__get_chat(
                bot_client=client, bot_message=message,
                chat_id=target_meta.get('chat_id'),
                error_msg=f'⬇️⬇️⬇️目标频道不存在⬇️⬇️⬇️\n{target_link}'
            )
            if not all([origin_chat, target_chat]):
                return None
            me = await self.app.client.get_me()
            if target_chat.id == me.id:
                await client.send_message(
                    chat_id=message.from_user.id,
                    text='⚠️⚠️⚠️无法转发到此机器人⚠️⚠️⚠️',
                    reply_to_message_id=message.id,
                )
                return None
            last_message = None
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
                        hide_captions=True
                    )
                except ChatForwardsRestricted:
                    raise ChatForwardsRestricted
                except Exception as e:
                    if not last_message:
                        last_message = await client.send_message(
                            chat_id=message.from_user.id,
                            reply_to_message_id=message.id,
                            text=BotMessage.INVALID
                        )
                    last_message = await client.edit_message_text(
                        chat_id=message.from_user.id,
                        message_id=last_message.id,
                        text=f'{last_message.text}\n{origin_link}/{i.id}'
                    )
                    log.warning(f'{_t(KeyWord.LINK)}:"{origin_link}/{i.id}"无效,{_t(KeyWord.REASON)}:{e}')
            await client.edit_message_text(
                message.from_user.id,
                message_id=last_message.id,
                text=f'{last_message.text}\n🌟🌟🌟转发任务已完成🌟🌟🌟',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        BotButton.CLICK_VIEW,
                        url=target_link
                    )
                ]]))
        except ChatForwardsRestricted:
            BotCallbackText.DOWNLOAD = f'{origin_link} {start_id} {end_id}'
            await client.send_message(
                chat_id=message.from_user.id,
                text=f'⚠️⚠️⚠️无法转发⚠️⚠️⚠️\n`{origin_link}`存在内容保护限制。',
                reply_to_message_id=message.id,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        BotButton.CLICK_DOWNLOAD,
                        callback_data=BotCallbackText.DOWNLOAD
                    )
                ]]))
        except ValueError:
            msg: str = ''
            if any('/c' in link for link in (origin_link, target_link)):
                msg = '(私密频道或话题频道必须让当前账号加入该频道)'
            await client.send_message(
                chat_id=message.from_user.id,
                reply_to_message_id=message.id,
                text='❌❌❌没有找到有效链接❌❌❌\n' + msg
            )
        except Exception as e:
            await client.send_message(
                chat_id=message.from_user.id,
                reply_to_message_id=message.id,
                text='⬇️⬇️⬇️出错了⬇️⬇️⬇️\n(具体原因请前往终端查看报错信息)'
            )
            log.exception(e)
            log.error(f'转发时遇到错误,{_t(KeyWord.REASON)}:"{e}"')
            # todo 测试话题频道无法转发。

    async def __extract_link_content(self, link: str, only_chat_id=False) -> dict | None:
        record_type: set = set()
        link: str = link[:-1] if link.endswith('/') else link
        record_type.add(LinkType.COMMENT) if '?single&comment' in link else None  # v1.1.0修复讨论组中附带?single时不下载的问题。
        link: str = link.split('?single')[0] if '?single' in link else link
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
        if only_chat_id:
            match = re.match(r'^(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.(?:org|me|dog)/(?:c/)?)([\w]+)(?:/(\d+))?$',
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
                        comment_message.append(comment)
                message = await self.app.client.get_messages(chat_id=chat_id, message_ids=message_id)
                is_group, group_message = await self.__is_group(message)
                if is_group or comment_message:  # 组或评论区。
                    try:  # v1.1.2解决当group返回None时出现comment无法下载的问题。
                        group_message.extend(comment_message) if comment_message else None
                    except AttributeError:
                        if comment_message and group_message is None:
                            group_message: list = []
                            group_message.extend(comment_message)
                    if comment_message:
                        return {'link_type': LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.COMMENT,
                                'chat_id': chat_id,
                                'message_id': group_message,
                                'member_num': len(group_message)}
                    else:
                        return {'link_type': LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.GROUP,
                                'chat_id': chat_id,
                                'message_id': group_message,
                                'member_num': len(group_message)}
                elif is_group is False and group_message is None:  # 单文件。
                    return {'link_type': LinkType.TOPIC if LinkType.TOPIC in record_type else LinkType.SINGLE,
                            'chat_id': chat_id,
                            'message_id': message,
                            'member_num': 1}
                elif is_group is None and group_message is None:
                    raise MsgIdInvalid(
                        'The message does not exist, the channel has been disbanded or is not in the channel.')
                elif is_group is None and group_message == 0:
                    raise Exception('Link parsing error.')
                else:
                    raise Exception('Unknown error.')
            else:
                raise ValueError('Invalid message link.')

    @staticmethod
    async def __is_group(message) -> Tuple[bool | None, bool | None]:
        try:
            return True, await message.get_media_group()
        except ValueError:
            return False, None  # v1.0.4 修改单文件无法下载问题。
        except AttributeError:
            return None, None

    async def __add_task(self, link, message: pyrogram.types.Message | list, retry: dict) -> None:
        retry_count = retry.get('count')
        retry_id = retry.get('id')
        if isinstance(message, list):
            for _message in message:
                if retry_count != 0:
                    if _message.id == retry_id:
                        await self.__add_task(link, _message, retry)
                        break
                else:
                    await self.__add_task(link, _message, retry)
        else:
            _task = None
            valid_dtype, is_document_type_valid = self.app.get_valid_dtype(message).values()
            if valid_dtype in self.app.download_type and is_document_type_valid:
                # 如果是匹配到的消息类型就创建任务。
                while self.app.current_task_num >= self.app.max_download_task:  # v1.0.7 增加下载任务数限制。
                    await self.event.wait()
                    self.event.clear()
                file_id, temp_file_path, sever_file_size, file_name, save_directory, format_file_size = \
                    self.app.get_media_meta(
                        message=message,
                        dtype=valid_dtype).values()
                retry['id'] = file_id
                if is_file_duplicate(save_directory=save_directory,
                                     sever_file_size=sever_file_size):  # 检测是否存在。
                    self.__complete_call(sever_file_size=sever_file_size,
                                         temp_file_path=temp_file_path,
                                         link=link,
                                         file_name=file_name,
                                         retry_count=retry_count,
                                         file_id=file_id,
                                         format_file_size=format_file_size,
                                         task_id=None,
                                         _future=save_directory)
                else:
                    console.log(
                        f'{_t(KeyWord.FILE)}:"{file_name}",'
                        f'{_t(KeyWord.SIZE)}:{format_file_size},'
                        f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.DOWNLOADING))},'
                        f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.DOWNLOADING)}。')
                    task_id = self.pb.progress.add_task(description='',
                                                        filename=truncate_display_filename(file_name),
                                                        info=f'0.00B/{format_file_size}',
                                                        total=sever_file_size)
                    _task = self.loop.create_task(
                        self.app.client.download_media(message=message,
                                                       progress_args=(self.pb.progress, task_id),
                                                       progress=self.pb.download_bar,
                                                       file_name=temp_file_path))
                    MetaData.print_current_task_num(self.app.current_task_num)
                    _task.add_done_callback(
                        partial(self.__complete_call, sever_file_size,
                                temp_file_path,
                                link,
                                file_name,
                                retry_count,
                                file_id,
                                format_file_size,
                                task_id))
            self.queue.put_nowait(_task) if _task else None

    def __check_download_finish(self, sever_file_size: int,
                                temp_file_path: str,
                                save_directory: str,
                                with_move: bool = True) -> bool:
        """检测文件是否下完。"""
        temp_ext: str = '.temp'
        local_file_size: int = get_file_size(file_path=temp_file_path, temp_ext=temp_ext)
        format_local_size: str = MetaData.suitable_units_display(local_file_size)
        format_sever_size: str = MetaData.suitable_units_display(sever_file_size)
        _file_path: str = os.path.join(save_directory, split_path(temp_file_path).get('file_name'))
        file_path: str = _file_path[:-len(temp_ext)] if _file_path.endswith(temp_ext) else _file_path
        if compare_file_size(a_size=local_file_size, b_size=sever_file_size):
            if with_move:
                result: str = move_to_save_directory(temp_file_path=temp_file_path,
                                                     save_directory=save_directory).get('e_code')
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
            f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}。')
        safe_delete(file_p_d=temp_file_path)  # v1.2.9 修复临时文件删除失败的问题。
        return False

    @Task.on_complete
    def __complete_call(self, sever_file_size,
                        temp_file_path,
                        link, file_name,
                        retry_count, file_id,
                        format_file_size,
                        task_id, _future):
        if task_id is None:
            if retry_count == 0:
                console.log(f'{_t(KeyWord.ALREADY_EXIST)}:"{_future}"')
                console.log(
                    f'{_t(KeyWord.FILE)}:"{file_name}",'
                    f'{_t(KeyWord.SIZE)}:{format_file_size},'
                    f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.SKIP))},'
                    f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.SKIP)}。', style='#e6db74')
        else:
            self.app.current_task_num -= 1
            self.event.set()  # v1.3.4 修复重试下载被阻塞的问题。
            self.queue.task_done()
            if self.__check_download_finish(sever_file_size=sever_file_size,
                                            temp_file_path=temp_file_path,
                                            save_directory=self.app.save_directory,
                                            with_move=True):
                MetaData.print_current_task_num(self.app.current_task_num)
            else:
                if retry_count < self.app.max_retry_count:
                    retry_count += 1
                    task = self.loop.create_task(
                        self.__create_download_task(link=link, retry={'id': file_id, 'count': retry_count}))
                    task.add_done_callback(
                        partial(self.__retry_call,
                                f'{_t(KeyWord.RELOAD)}:"{file_name}",'
                                f'{_t(KeyWord.RELOAD_TIMES)}:{retry_count}/{self.app.max_retry_count}。'
                                ))
                else:
                    _error = f'(达到最大重试次数:{self.app.max_retry_count}次)。'
                    console.log(f'{_t(KeyWord.FILE)}:"{file_name}",'
                                f'{_t(KeyWord.SIZE)}:{format_file_size},'
                                f'{_t(KeyWord.TYPE)}:{_t(self.app.guess_file_type(file_name, DownloadStatus.FAILURE))},'
                                f'{_t(KeyWord.STATUS)}:{_t(DownloadStatus.FAILURE)}'
                                f'{_error}')
                    Task.LINK_INFO.get(link).get('error_msg')[file_name] = _error.replace('。', '')
                    self.bot_task_link.discard(link)
            self.pb.progress.remove_task(task_id=task_id)
        return link, file_name

    @Task.on_create_task
    async def __create_download_task(self,
                                     link: str,
                                     retry: dict | None = None) -> dict:
        retry = retry if retry else {'id': -1, 'count': 0}
        try:
            meta: dict = await self.__extract_link_content(link)
            link_type, chat_id, message_id, member_num = meta.values()
            await self.__add_task(link, message_id, retry)
            return {'chat_id': chat_id,
                    'link_type': link_type,
                    'member_num': member_num,
                    'status': DownloadStatus.DOWNLOADING,
                    'e_code': None}
        except UnicodeEncodeError as e:
            return {'chat_id': None,
                    'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {'all_member': str(e), 'error_msg': '频道标题存在特殊字符,请移步终端下载'}}
        except MsgIdInvalid as e:
            return {'chat_id': None, 'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {'all_member': str(e), 'error_msg': '消息不存在,可能已删除'}}
        except UsernameInvalid as e:
            return {'chat_id': None, 'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {'all_member': str(e),
                               'error_msg': '频道用户名无效,该链接的频道用户名可能已更改或频道已解散'}}
        except ChannelInvalid as e:
            return {'chat_id': None, 'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {'all_member': str(e),
                               'error_msg': '频道可能为私密频道或话题频道,请让当前账号加入该频道后再重试'}}
        except ChannelPrivate as e:
            return {'chat_id': None, 'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {
                        'all_member': str(e),
                        'error_msg': '频道可能为私密频道或话题频道,当前账号可能已不在该频道,请让当前账号加入该频道后再重试'}}
        except BotMethodInvalid as e:
            res: bool = safe_delete(file_p_d=os.path.join(self.app.DIRECTORY_NAME, 'sessions'))
            return {'chat_id': None, 'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {
                        'all_member': str(e),
                        'error_msg': f'检测到使用了「bot_token」方式登录了主账号的行为,'
                                     f'{"已删除旧会话文件" if res else "请手动删除软件目录下的sessions文件夹"},'
                                     f'请重启软件以「手机号码」方式重新登录'}}
        except ValueError as e:
            return {'chat_id': None, 'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {'all_member': str(e), 'error_msg': '没有找到有效链接'}}
        except UsernameNotOccupied as e:
            return {'chat_id': None, 'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {'all_member': str(e), 'error_msg': '频道不存在'}}
        except Exception as e:
            log.exception(e)
            return {'chat_id': None, 'member_num': 0,
                    'link_type': None,
                    'status': DownloadStatus.FAILURE,
                    'e_code': {'all_member': str(e), 'error_msg': '未收录到的错误'}}

    def __process_links(self, link: str | list) -> set | None:
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
                _link: set | None = self.__process_links(link=i)
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
        await self.app.client.start()
        self.pb.progress.start()  # v1.1.8修复登录输入手机号不显示文本问题。
        if self.app.bot_token is not None:
            result = await self.start_bot(self.app.client,
                                          pyrogram.Client(
                                              name=self.BOT_NAME,
                                              api_hash=self.app.api_hash,
                                              api_id=self.app.api_id,
                                              bot_token=self.app.bot_token,
                                              workdir=self.app.work_directory,
                                              proxy=self.app.enable_proxy
                                          ))
            console.log(result, style='#B1DB74' if self.is_bot_running else '#FF4689')
        self.is_running = True
        self.running_log.add(self.is_running)
        links: set | None = self.__process_links(link=self.app.links)
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
                    f'临时文件无法移动至下载路径,检测到多开软件时,由于在上一个实例中「下载完成」后窗口没有被关闭的行为,请在关闭后重试,{_t(KeyWord.REASON)}:"{e}"')
        # 等待所有任务完成。
        await self.queue.join()
        await self.app.client.stop() if self.app.client.is_connected else None

    def run(self) -> None:
        record_error: bool = False
        try:
            MetaData.print_meta()
            self.app.print_config_table(enable_proxy=self.app.enable_proxy, links=self.app.links,
                                        download_type=self.app.download_type, proxy=self.app.proxy)
            self.loop.run_until_complete(self.__download_media_from_links())
        except (SessionRevoked, AuthKeyUnregistered, SessionExpired, ConnectionError) as e:
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
            log.exception(msg=f'运行出错,{_t(KeyWord.REASON)}:"{e}"', exc_info=True)
        finally:
            self.is_running = False
            self.pb.progress.stop()
            if not record_error:
                self.app.print_link_table(link_info=Task.LINK_INFO)
                self.app.print_count_table(record_dtype=self.app.record_dtype)
                MetaData.pay()
                self.app.process_shutdown(60) if len(self.running_log) == 2 else None  # v1.2.8如果并未打开客户端执行任何下载,则不执行关机。
            self.app.ctrl_c()

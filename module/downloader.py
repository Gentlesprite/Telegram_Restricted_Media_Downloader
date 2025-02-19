# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023/10/3 1:00:03
# File:downloader.py
import os
import sys
import asyncio
from functools import partial
from sqlite3 import OperationalError
from typing import Tuple, Union

import pyrogram
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate
from pyrogram.errors.exceptions.bad_request_400 import MsgIdInvalid, UsernameInvalid, ChannelInvalid, BotMethodInvalid
from pyrogram.errors.exceptions.unauthorized_401 import SessionRevoked, AuthKeyUnregistered, SessionExpired

from module import console, log
from module.bot import Bot
from module.app import Application, MetaData
from module.process_path import is_file_duplicate, safe_delete
from module.enum_define import LinkType, DownloadStatus, DownloadType, KeyWord, Status, BotCallbackText, Base64Image


class TelegramRestrictedMediaDownloader(Bot):

    def __init__(self):
        super().__init__()
        MetaData.print_helper()
        self.loop = asyncio.get_event_loop()
        self.event = asyncio.Event()
        self.queue = asyncio.Queue()
        self.app = Application()
        self.client = self.app.build_client()
        self.is_running: bool = False
        self.running_log: set = set()
        self.running_log.add(self.is_running)

    async def get_link_from_bot(self,
                                client: pyrogram.Client,
                                message: pyrogram.types.Message):
        res: dict or None = await super().get_link_from_bot(client, message)
        if res is None:
            return
        else:
            right_link: set = res.get('right_link')
            invalid_link: set = res.get('invalid_link')
            last_bot_message = res.get('last_bot_message')
        chat_id: Union[int, str] = message.chat.id
        last_message_id: int = last_bot_message.id
        exist_link: set = set([_ for _ in right_link if _ in self.bot_task_link])
        exist_link.update(right_link & self.app.complete_link)
        right_link -= exist_link
        await self.edit_message_text(client=client,
                                     chat_id=chat_id,
                                     last_message_id=last_message_id,
                                     text=self.update_text(right_link=right_link,
                                                           exist_link=exist_link,
                                                           invalid_link=invalid_link))
        links: set or None = self.__process_links(link=list(right_link))
        if links is None:
            return
        else:
            for link in links:
                res = await self.__create_download_task(link=link)
                if res is False:
                    invalid_link.add(link)
                else:
                    self.bot_task_link.add(link)
            right_link -= invalid_link
            await self.edit_message_text(client=client,
                                         chat_id=chat_id,
                                         last_message_id=last_message_id,
                                         text=self.update_text(right_link=right_link,
                                                               exist_link=exist_link,
                                                               invalid_link=invalid_link))

    @staticmethod
    async def __send_pay_qr(client: pyrogram.Client, chat_id, load_name: str) -> dict:
        e_code: dict = {'e_code': None}
        try:
            last_msg = await client.send_message(chat_id=chat_id,
                                                 text=f'🙈🙈🙈请稍后🙈🙈🙈{load_name}加载中. . .',
                                                 disable_web_page_preview=True
                                                 )
            await client.send_photo(chat_id=chat_id,
                                    photo=Base64Image.base64_to_binaryio(Base64Image.pay),
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
        chat_id = message.chat.id
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
            return
        elif callback_data == BotCallbackText.pay:
            res: dict = await self.__send_pay_qr(client=client,
                                                 chat_id=callback_query.message.chat.id,
                                                 load_name='收款码')
            MetaData.pay()
            if res.get('e_code'):
                msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」十分感谢您的支持!'
            else:
                msg = '🥰🥰🥰\n收款「二维码」已发送至您的「终端」与「对话框」十分感谢您的支持!'
            await callback_query.message.reply_text(msg)
        elif callback_data == BotCallbackText.link_table:
            res: bool or str = self.app.print_link_table()
            if isinstance(res, str):
                await callback_query.message.edit_text(
                    '😵‍💫😵‍💫😵‍💫`链接统计表`打印失败。\n(具体原因请前往终端查看报错信息)')
            elif isinstance(res, bool) and res is True:
                await callback_query.message.edit_text('🫡🫡🫡`链接统计表`已发送至您的「终端」请注意查收。')
            else:
                await callback_query.message.edit_text('😵😵😵没有链接需要统计。')
        elif callback_data == BotCallbackText.count_table:
            self.app.print_count_table()
            await callback_query.message.edit_text('👌👌👌`计数统计表`已发送至您的「终端」请注意查收。')
        elif callback_data == BotCallbackText.back_help:
            await callback_query.message.delete()
            await self.help(client, callback_query.message)

    async def __extract_link_content(self, link) -> Tuple[str, int, list]:
        comment_message = []
        is_comment = False
        if '?single&comment' in link:  # v1.1.0修复讨论组中附带?single时不下载的问题，
            is_comment = True
        if '?single' in link:  # todo 如果只想下载组中的其一。
            link = link.split('?single')[0]
        if '?comment' in link:  # 链接中包含?comment表示用户需要同时下载评论中的媒体。
            link = link.split('?comment')[0]
            is_comment = True
        message_id = int(link.split('/')[-1])
        if 't.me/c/' in link:
            if 't.me/b/' in link:
                chat_id = str(link.split('/')[-2])
            else:
                chat_id = int('-100' + str(link.split('/')[-2]))  # 得到频道的id。
        else:
            chat_id = link.split('/')[-2]  # 频道的名字。

        if is_comment:
            # 如果用户需要同时下载媒体下面的评论,把评论中的所有信息放入列表一起返回。
            async for comment in self.client.get_discussion_replies(chat_id, message_id):
                comment_message.append(comment)
        return chat_id, message_id, comment_message

    @staticmethod
    async def __is_group(message) -> Tuple[bool or None, bool or None]:
        try:
            return True, await message.get_media_group()
        except ValueError:
            return False, None  # v1.0.4 修改单文件无法下载问题。
        except AttributeError:
            return None, None

    def __listen_link_complete(self, link, file_name) -> bool:
        self.app.link_info.get(link).get('file_name').add(file_name)
        for i in self.app.link_info.items():
            compare_link: str = i[0]
            info: dict = i[1]
            if compare_link == link:
                info['complete_num'] = len(info.get('file_name'))
        all_num: int = self.app.link_info.get(link).get('member_num')
        complete_num: int = self.app.link_info.get(link).get('complete_num')
        if all_num == complete_num:
            console.log(f'{KeyWord.LINK}:"{link}",'
                        f'{KeyWord.STATUS}:{Status.SUCCESS}。')
            self.app.link_info.get(link)['error_msg'] = {}
            self.app.complete_link.add(link)
            return True
        else:
            return False

    async def __add_task(self, link, message: pyrogram.types.Message or list, retry: dict) -> None:
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
                    if retry_count == 0:  # v1.2.9 下载失败时,不再重复打印已存在的文件信息。
                        console.log(f'{KeyWord.ALREADY_EXIST}:"{save_directory}"')
                        console.log(f'{KeyWord.FILE}:"{file_name}",'
                                    f'{KeyWord.SIZE}:{format_file_size},'
                                    f'{KeyWord.TYPE}:{DownloadType.t(self.app.guess_file_type(file_name=file_name, status=DownloadStatus.skip)[0].text)},'
                                    f'{KeyWord.STATUS}:{Status.SKIP}。', style='#e6db74')
                    self.__listen_link_complete(link=link, file_name=file_name)
                else:
                    console.log(f'{KeyWord.FILE}:"{file_name}",'
                                f'{KeyWord.SIZE}:{format_file_size},'
                                f'{KeyWord.TYPE}:{DownloadType.t(self.app.guess_file_type(file_name=file_name, status=DownloadStatus.downloading)[0].text)},'
                                f'{KeyWord.STATUS}:{Status.DOWNLOADING}。')
                    task_id = self.app.progress.add_task(description='',
                                                         filename=file_name,
                                                         info=f'0.00B/{format_file_size}',
                                                         total=sever_file_size)
                    _task = self.loop.create_task(
                        self.client.download_media(message=message,
                                                   progress_args=(self.app.progress, task_id),
                                                   progress=self.app.download_bar,
                                                   file_name=temp_file_path))
                    console.log(f'[当前任务数]:{self.app.current_task_num}。', justify='right')
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

    def __complete_call(self, sever_file_size,
                        temp_file_path,
                        link, file_name,
                        retry_count, file_id,
                        format_file_size,
                        task_id, _future):
        self.app.current_task_num -= 1
        self.event.set()  # v1.3.4 修复重试下载被阻塞的问题。
        self.queue.task_done()
        if self.app.check_download_finish(sever_file_size=sever_file_size,
                                          temp_file_path=temp_file_path,
                                          save_directory=self.app.save_directory,
                                          with_move=True):
            self.__listen_link_complete(link=link, file_name=file_name)
            console.log(f'[当前任务数]:{self.app.current_task_num}。', justify='right')
        else:
            if retry_count < self.app.max_retry_count:
                retry_count += 1
                self.app.global_retry_task += 1
                notice = f'[重新下载]:"{file_name}",[重试次数]:{retry_count}/{self.app.max_retry_count}。'
                self.queue.put_nowait((link, {'id': file_id, 'count': retry_count}, notice))
            else:
                _error = f'(达到最大重试次数:{self.app.max_retry_count}次)。'
                console.log(f'{KeyWord.FILE}:"{file_name}",'
                            f'{KeyWord.SIZE}:{format_file_size},'
                            f'{KeyWord.TYPE}:{DownloadType.t(self.app.guess_file_type(file_name=file_name, status=DownloadStatus.failure)[0].text)},'
                            f'{KeyWord.STATUS}:{Status.FAILURE}'
                            f'{_error}')
                self.app.link_info.get(link).get('error_msg')[file_name] = _error.replace('。', '')
                self.bot_task_link.discard(link)
        self.app.progress.remove_task(task_id=task_id)

    async def __create_download_task(self,
                                     link: str,
                                     retry: dict or None = None) -> bool:
        retry = retry if retry else {'id': -1, 'count': 0}
        self.app.link_info[link] = {'link_type': None,
                                    'member_num': 0,
                                    'complete_num': 0,
                                    'file_name': set(),
                                    'error_msg': {}}
        try:
            chat_id, message_id, comment_message = await self.__extract_link_content(link)
            msg = await self.client.get_messages(chat_id=chat_id, message_ids=message_id)  # 该消息的信息。
            res, group = await self.__is_group(msg)
            if res or comment_message:  # 组或评论区。
                try:  # v1.1.2解决当group返回None时出现comment无法下载的问题。
                    group.extend(comment_message) if comment_message else None
                except AttributeError:
                    if comment_message and group is None:
                        group = []
                        group.extend(comment_message)
                link_type = LinkType.comment if comment_message else LinkType.group
                self.app.link_info[link] = {'link_type': link_type,
                                            'member_num': len(group),
                                            'complete_num': 0,
                                            'file_name': set(),
                                            'error_msg': {}}
                console.log(
                    f'{KeyWord.CHANNEL}:"{chat_id}",'  # 频道名。
                    f'{KeyWord.LINK}:"{link}",'  # 链接。
                    f'{KeyWord.LINK_TYPE}:{LinkType.t(link_type)}。')  # 链接类型。
                await self.__add_task(link, group, retry)
                return True
            elif res is False and group is None:  # 单文件。
                link_type = LinkType.single
                self.app.link_info[link] = {'link_type': link_type,
                                            'member_num': 1,
                                            'complete_num': 0,
                                            'file_name': set(),
                                            'error_msg': {}}
                console.log(
                    f'{KeyWord.CHANNEL}:"{chat_id}",'  # 频道名。
                    f'{KeyWord.LINK}:"{link}",'  # 链接。
                    f'{KeyWord.LINK_TYPE}:{LinkType.t(link_type)}。')  # 链接类型。
                await self.__add_task(link, msg, retry)
                return True
            elif res is None and group is None:
                error = '消息不存在,频道已解散或未在频道中'
                self.app.link_info.get(link)['error_msg'] = {'all_member': error}
                log.warning(
                    f'{KeyWord.LINK}:"{link}"{error},{Status.FAILURE}。')
                return False
            elif res is None and group == 0:
                error = '未收录到的错误'
                self.app.link_info.get(link)['error_msg'] = {'all_member': error}
                log.error(f'{KeyWord.LINK}:"{link}"{error},'
                          f'{KeyWord.STATUS}:{Status.FAILURE}。')
                return False
        except UnicodeEncodeError as e:
            error = '频道标题存在特殊字符,请移步终端下载'
            self.app.link_info.get(link)['error_msg'] = {'all_member': e}
            log.error(f'{KeyWord.LINK}:"{link}"{error},'
                      f'{KeyWord.REASON}:"{e}",'
                      f'{KeyWord.STATUS}:{Status.FAILURE}。')
            return False
        except MsgIdInvalid as e:
            self.app.link_info.get(link)['error_msg'] = {'all_member': e}
            log.error(f'{KeyWord.LINK}:"{link}"消息不存在,可能已删除,'
                      f'{KeyWord.REASON}:"{e}",'
                      f'{KeyWord.STATUS}:{Status.FAILURE}。')
            return False
        except UsernameInvalid as e:
            self.app.link_info.get(link)['error_msg'] = {'all_member': e}
            log.error(
                f'{KeyWord.LINK}:"{link}"频道用户名无效,该链接的频道用户名可能已更改或频道已解散,'
                f'{KeyWord.REASON}:"{e}",'
                f'{KeyWord.STATUS}:{Status.FAILURE}。')
            return False
        except ChannelInvalid as e:
            self.app.link_info.get(link)['error_msg'] = {'all_member': e}
            log.error(
                f'{KeyWord.LINK}:"{link}"频道可能为私密频道,请让当前账号加入该频道后再重试,'
                f'{KeyWord.REASON}:"{e}",'
                f'{KeyWord.STATUS}:{Status.FAILURE}。')
            return False
        except ChannelPrivate as e:
            self.app.link_info.get(link)['error_msg'] = {'all_member': e}
            log.error(
                f'{KeyWord.LINK}:"{link}"频道可能为私密频道,当前账号可能已不在该频道,请让当前账号加入该频道后再重试,'
                f'{KeyWord.REASON}:"{e}",'
                f'{KeyWord.STATUS}:{Status.FAILURE}。')
            return False
        except BotMethodInvalid as e:
            self.app.link_info.get(link)['error_msg'] = {'all_member': e}
            res: bool = safe_delete(file_p_d=os.path.join(self.app.DIRECTORY_NAME, 'sessions'))
            msg = '已删除旧会话文件' if res else '请手动删除软件目录下的sessions文件夹'
            log.error(
                f'{KeyWord.LINK}:"{link}"检测到使用了「bot_token」方式登录了主账号的行为,{msg},请重启软件以「手机号码」方式重新登录,'
                f'{KeyWord.REASON}:"{e}",'
                f'{KeyWord.STATUS}:{Status.FAILURE}。')
            return False
        except Exception as e:
            self.app.link_info.get(link)['error_msg'] = {'all_member': e}
            log.error(
                f'{KeyWord.LINK}:"{link}"未收录到的错误,'
                f'{KeyWord.REASON}:"{e}",'
                f'{KeyWord.STATUS}:{Status.FAILURE}。')
            log.exception(e)
            return False

    def __process_links(self, link: str or list) -> set or None:
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
                    else:
                        log.warning(f'"{i}"是一个非法链接,{KeyWord.STATUS}:{Status.SKIP}。')
            elif link.startswith(start_content):
                links.add(link)
        elif isinstance(link, list):
            for i in link:
                res = self.__process_links(link=i)
                if res is not None:
                    links.update(res)
        if links:
            return links
        elif not self.app.bot_token:
            console.log('没有找到有效链接,程序已退出。')
            sys.exit(0)
        else:
            console.log('没有找到有效链接。', style='#FF4689')
            return None

    def __retry_call(self, notice, _future):
        console.log(notice)
        self.app.global_retry_task -= 1
        self.queue.task_done()

    async def __download_media_from_links(self) -> None:
        await self.client.start()
        self.app.progress.start()  # v1.1.8修复登录输入手机号不显示文本问题。
        if self.app.bot_token is not None:
            result = await self.start_bot(self.client,
                                          pyrogram.Client(
                                              name=self.app.BOT_NAME,
                                              api_hash=self.app.api_hash,
                                              api_id=self.app.api_id,
                                              bot_token=self.app.bot_token,
                                              workdir=self.app.work_directory,
                                              proxy=self.app.enable_proxy
                                          ))
            console.log(result, style='#B1DB74' if self.is_bot_running else '#FF4689')
        self.is_running = True
        self.running_log.add(self.is_running)
        txt_links = self.__process_links(link=self.app.links)
        # 将初始任务添加到队列中。
        if txt_links:
            for _link in txt_links:
                await self.__create_download_task(link=_link)

        # 处理队列中的任务,与机器人事件。
        while not self.queue.empty() or self.is_bot_running:
            result = await self.queue.get()
            if isinstance(result, tuple):
                link, retry, notice = result
                task = self.loop.create_task(self.__create_download_task(link=link, retry=retry))
                task.add_done_callback(partial(self.__retry_call, notice))
                await task
            else:
                if self.app.global_retry_task != 0 and self.app.current_task_num < self.app.max_download_task:
                    continue  # v1.3.8 修复:正常下载任务未达上限时,重试任务需等待当前任务完成后再创建。
                else:
                    await result
        # 等待所有任务完成。
        await self.queue.join()

    def run(self) -> None:
        record_error: bool = False
        try:

            MetaData.print_meta()
            self.app.print_config_table()
            self.loop.run_until_complete(self.__download_media_from_links())
        except (SessionRevoked, AuthKeyUnregistered, SessionExpired, ConnectionError) as e:
            log.error(f'登录时遇到错误,{KeyWord.REASON}:"{e}"')
            res: bool = safe_delete(file_p_d=os.path.join(self.app.DIRECTORY_NAME, 'sessions'))
            record_error: bool = True
            if res:
                log.warning('账号已失效,已删除旧会话文件,请重启软件。')
            else:
                log.error('账号已失效,请手动删除软件目录下的sessions文件夹后重启软件。')
        except AttributeError as e:
            record_error: bool = True
            log.error(f'登录超时,请重新打开软件尝试登录,{KeyWord.REASON}:"{e}"')
        except KeyboardInterrupt:
            console.log('用户手动终止下载任务。')
        except OperationalError as e:
            record_error: bool = True
            log.error(f'检测到多开软件时,由于在上一个实例中「下载完成」后窗口没有被关闭的行为,请在关闭后重试,{KeyWord.REASON}:"{e}"')
        except Exception as e:
            record_error: bool = True
            log.exception(msg=f'运行出错,{KeyWord.REASON}:"{e}"', exc_info=True)
        finally:
            self.is_running = False
            self.client.stop() if self.client.is_connected else None
            self.app.progress.stop()
            if not record_error:
                self.app.print_link_table()
                self.app.print_count_table()
                MetaData.pay()
                self.app.process_shutdown(60) if len(self.running_log) == 2 else None  # v1.2.8如果并未打开客户端执行任何下载,则不执行关机。
            self.app.ctrl_c()

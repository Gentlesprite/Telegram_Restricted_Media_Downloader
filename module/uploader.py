# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/9/6 23:00
# File:uploader.py
import os
import hashlib
import asyncio
import inspect

from functools import partial
from typing import (
    List,
    Dict,
    Union,
    Callable
)

import pyrogram
from pyrogram import raw, utils
from pyrogram.errors.exceptions import (
    FilePartMissing,
    ChatAdminRequired,
    PhotoInvalidDimensions,
    PhotoSaveFileInvalid
)
from pyrogram.errors.exceptions.bad_request_400 import ChannelPrivate as ChannelPrivate_400
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as ChannelPrivate_406
from pymediainfo import MediaInfo

from module import console, log
from module.language import _t

from module.task import UploadTask
from module.path_tool import get_mime_from_extension

from module.stdio import (
    MetaData,
    ProgressBar
)
from module.path_tool import (
    split_path,
    safe_delete
)
from module.enums import (
    KeyWord,
    UploadStatus
)
from module.util import (
    parse_link,
    truncate_display_filename,
    get_chat_with_notify,
    is_allow_upload
)


class TelegramUploader:
    def __init__(
            self,
            download_object
    ):
        self.app = download_object.app
        self.client: pyrogram.Client = self.app.client
        self.loop: asyncio.AbstractEventLoop = download_object.loop
        self.event: asyncio.Event = asyncio.Event()
        self.pb: ProgressBar = download_object.pb
        self.is_premium: bool = self.client.me.is_premium
        self.current_task_num: int = 0
        self.max_upload_task: int = self.app.max_upload_task
        self.max_upload_retries: int = self.app.max_upload_retries
        self.is_bot_running = download_object.is_bot_running
        self.upload_queue: asyncio.Queue = asyncio.Queue()
        self.valid_link_cache = {}
        UploadTask.NOTIFY = download_object.done_notice
        UploadTask.DIRECTORY_NAME = os.path.join(UploadTask.DIRECTORY_NAME, str(download_object.my_id))
        asyncio.create_task(self.send_media_worker())

    async def resume_upload(
            self,
            upload_task: UploadTask,
            progress: Callable = None,
            progress_args: tuple = ()
    ):
        missing_parts = upload_task.get_missing_parts()
        chat_id = upload_task.chat_id
        path = upload_task.file_path
        file_id = upload_task.file_id
        file_size: int = upload_task.file_size
        file_total_parts: int = upload_task.file_total_parts
        if not missing_parts:
            # 所有分片都已上传,准备发送消息。
            log.info(f'所有分片已上传完成,正在发送消息...')
        else:
            log.info(f'需要上传的分片:{len(missing_parts)}/{file_total_parts}')
        # 上传缺失的分片。
        for part_index in missing_parts:
            try:
                # 上传单个分片。
                part_size = 512 * 1024
                await self.client.save_file(
                    path=path,
                    file_id=file_id,
                    file_part=part_index
                )
                # 更新上传记录。
                upload_task.update_file_part(part_index)
                # 调用进度回调。
                if progress:
                    current_size = min((part_index + 1) * part_size, file_size)
                    func = partial(
                        progress,
                        current_size,
                        file_size,
                        *progress_args
                    )

                    if inspect.iscoroutinefunction(progress):
                        await func()
                    else:
                        await self.loop.run_in_executor(self.client.executor, func)

            except Exception as e:
                log.error(
                    f'{_t(KeyWord.UPLOAD_FILE_PART)}:{part_index},'
                    f'{_t(KeyWord.STATUS)}:{_t(UploadStatus.FAILURE)},'
                    f'{_t(KeyWord.REASON)}:"{e}"'
                )
                raise  # 重新抛出异常,由重试机制处理。

        # 检查是否所有分片都上传完成。
        if len(upload_task.file_part) != file_total_parts:
            raise Exception(f'分片上传不完整:{len(upload_task.file_part)}/{file_total_parts}')

        is_big = file_size > 10 * 1024 * 1024
        if is_big:
            file = raw.types.InputFileBig(
                id=file_id,
                parts=file_total_parts,
                name=os.path.basename(path)
            )
        else:
            md5_hash = hashlib.md5()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    md5_hash.update(chunk)
            md5_sum = ''.join([hex(i)[2:].zfill(2) for i in md5_hash.digest()])

            file = raw.types.InputFile(
                id=file_id,
                parts=file_total_parts,
                name=os.path.basename(path),
                md5_checksum=md5_sum
            )

        file_path: Union[str, None] = getattr(file, 'name', '')
        if not file_path:
            file_path = str(path) if isinstance(path, str) else ''

        mime_type = self.client.guess_mime_type(file_path) or get_mime_from_extension(file_path)
        file_name = split_path(file_path).get('file_name', 'file')

        if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            try:
                media = raw.types.InputMediaUploadedPhoto(
                    file=file,
                    spoiler=False
                )
                media = await self.client.invoke(
                    raw.functions.messages.UploadMedia(
                        peer=await self.client.resolve_peer(chat_id),
                        media=media
                    )
                )
                media = raw.types.InputMediaPhoto(
                    id=raw.types.InputPhoto(
                        id=media.photo.id,
                        access_hash=media.photo.access_hash,
                        file_reference=media.photo.file_reference
                    ),
                    spoiler=False
                )
            except (PhotoInvalidDimensions, PhotoSaveFileInvalid) as e:
                obj: str = ''
                if isinstance(e, PhotoInvalidDimensions):
                    obj: str = '尺寸'
                elif isinstance(e, PhotoSaveFileInvalid):
                    obj: str = '大小'
                p = f'[图片]:"{file_path}"因来自Telegram的{obj}限制,回退为文档格式进行上传,{_t(KeyWord.REASON)}:"{e}"'
                log.info(p)
                console.log(p, style='#FF4689')
                attributes = [raw.types.DocumentAttributeFilename(file_name=file_name)]
                media = await self.get_input_media_document(
                    chat_id=chat_id,
                    file=file,
                    attributes=attributes,
                    mime_type=mime_type
                )
        else:
            attributes = [raw.types.DocumentAttributeFilename(file_name=file_name)]
            if file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                video_meta: Union[dict, None] = self.get_video_info(path)
                if video_meta:
                    attributes.append(raw.types.DocumentAttributeVideo(
                        supports_streaming=True,
                        duration=video_meta.get('duration'),
                        w=video_meta.get('width'),
                        h=video_meta.get('height')
                    ))
                    log.info(f'视频"{file_path}"将以原本格式进行上传。')
                else:
                    p = f'[视频]:"{file_path}"获取视频元数据失败,回退为文档格式进行上传。'
                    log.info(p)
                    console.log(p, style='#FF4689')
            media = await self.get_input_media_document(
                chat_id=chat_id,
                file=file,
                attributes=attributes,
                mime_type=mime_type
            )
        self.upload_queue.put_nowait((media, upload_task))

    async def send_media_worker(self):
        # 在函数内部使用本地缓存。
        media_group_cache = {}  # media_group_id -> {message_id: media, ...}
        media_group_poll_tasks = {}  # media_group_id -> polling_task

        while self.is_bot_running:
            try:
                media, upload_task = await self.upload_queue.get()

                log.info(
                    f'[Upload Worker]获取到上传任务,'
                    f'chat_id={upload_task.chat_id}, '
                    f'is_media_group={upload_task.is_media_group}, '
                    f'message_id={upload_task.message_id}'
                )

                if upload_task.is_media_group and upload_task.send_as_media_group:
                    try:
                        media_group = await upload_task.get_media_group()
                        if not media_group:
                            log.info(f'[Upload Worker]警告:media_group为空。')
                            continue

                        media_group_id = media_group[0].media_group_id
                        if not media_group_id:
                            log.info(f'[Upload Worker]警告:media_group_id为空。')
                            # 如果不是媒体组，则作为单条消息发送。
                            await self.send_media(media, upload_task)
                            continue

                        chat_id = upload_task.chat_id
                        message_id = upload_task.message_id

                        if media_group_id not in media_group_cache:
                            # 使用字典来存储，键为message_id，值为InputSingleMedia。
                            media_group_cache[media_group_id] = {}

                        # 以message_id为键存储。
                        media_group_cache[media_group_id][message_id] = raw.types.InputSingleMedia(
                            media=media,
                            random_id=self.client.rnd_id(),
                            **await utils.parse_text_entities(
                                self.client,
                                text='',
                                parse_mode=None,
                                entities=None
                            )
                        )
                        prompt = f'[媒体组]:"{media_group_id}"已收集{len(media_group_cache[media_group_id])}个媒体,等待所有媒体上传完成。'
                        console.log(
                            f'{_t(KeyWord.UPLOAD_TASK)}{prompt}')
                        upload_task.prompt = prompt

                        # 如果该媒体组还没有轮询任务，启动一个。
                        if media_group_id not in media_group_poll_tasks:
                            # 获取media_group中所有需要上传的message_id。
                            message_ids = {m.id for m in media_group}
                            poll_task = asyncio.create_task(
                                self.send_media_group(
                                    chat_id=chat_id,
                                    media_group=media_group,
                                    media_group_id=media_group_id,
                                    message_ids=message_ids,
                                    media_group_cache=media_group_cache,
                                    media_group_poll_tasks=media_group_poll_tasks)
                            )
                            media_group_poll_tasks[media_group_id] = poll_task
                            log.info(
                                f'[Upload Worker]启动媒体组"{media_group_id}"的轮询任务,预期{len(message_ids)}个文件。')

                    except Exception as e:
                        log.info(f'[Upload Worker]处理媒体组时出错,回退到单条发送,{_t(KeyWord.REASON)}:"{e}"')
                        # 出错时回退到单条发送。
                        await self.send_media(media, upload_task)

                else:
                    await self.send_media(media, upload_task)

            except Exception as e:
                log.error(f'[Upload Worker]错误,{_t(KeyWord.REASON)}:"{e}"', exc_info=True)
            finally:
                self.upload_queue.task_done()

    async def send_media_group(
            self,
            chat_id: int,
            media_group: list,
            media_group_id: int,
            message_ids: set,
            media_group_cache: dict,
            media_group_poll_tasks: dict
    ):
        try:
            while self.is_bot_running:
                await asyncio.sleep(1)  # 每1秒检查一次。

                # 检查两个条件：
                # 1. 所有需要上传的文件都已创建UploadTask（没有文件还在下载中）。
                # 2. 没有待处理的媒体组任务。
                created_count = UploadTask.get_media_group_task_count(message_ids)
                no_pending = not UploadTask.has_pending_media_group_tasks()
                collected_count = len(media_group_cache.get(media_group_id, {}))

                log.debug(
                    f'[Upload Worker]发送媒体组"{media_group_id}"创建的任务数:{created_count},当前是否有任务:{not no_pending},媒体组收集的媒体数:{collected_count}。')
                if created_count == collected_count and no_pending:
                    # 所有需要上传的文件都已创建且没有待处理任务，发送已收集的媒体。
                    if media_group_id in media_group_cache:
                        # 按照原始message_id的顺序排序。
                        sorted_media_group = []
                        for message in media_group:
                            msg_id = message.id
                            # 只发送在message_ids中的（用户选择的范围）。
                            if msg_id in message_ids and msg_id in media_group_cache[media_group_id]:
                                sorted_media_group.append(media_group_cache[media_group_id][msg_id])

                        if sorted_media_group:
                            log.info(
                                f'[Upload Worker]发送媒体组"{media_group_id}",包含{len(sorted_media_group)}个媒体（共预期{len(message_ids)}个）。')
                            try:
                                await self.client.invoke(
                                    raw.functions.messages.SendMultiMedia(
                                        peer=await self.client.resolve_peer(chat_id),
                                        multi_media=sorted_media_group
                                    ),
                                    sleep_threshold=60
                                )
                                prompt = f'[媒体组]:"{media_group_id}"上传完成,包含{len(sorted_media_group)}个媒体。'
                                console.log(f'{_t(KeyWord.UPLOAD_TASK)}{prompt}')
                                # 将已发送的媒体组任务状态更新为SENT。
                                for task in UploadTask.TASKS:
                                    if task.message_id in message_ids and task.status == UploadStatus.SUCCESS:
                                        task.status = UploadStatus.SENT
                                self.valid_link_cache = {k: v for k, v in self.valid_link_cache.items() if v != chat_id}
                            except Exception as send_error:
                                log.error(f'[Upload Worker]发送媒体组失败,{_t(KeyWord.REASON)}:"{send_error}"',
                                          exc_info=True)
                        else:
                            log.warning(f'[Upload Worker]发送媒体组"{media_group_id}"没有可发送的媒体。')

                    # 清理缓存和轮询任务。
                    if media_group_id in media_group_cache:
                        del media_group_cache[media_group_id]
                    if media_group_id in media_group_poll_tasks:
                        del media_group_poll_tasks[media_group_id]
                    break  # 轮询结束。
                else:
                    # 还有文件在下载中或还在上传，继续等待。
                    if created_count < len(message_ids):
                        log.debug(
                            f'[Upload Worker]发送媒体组"{media_group_id}"已创建{created_count}/{len(message_ids)}个任务，等待下载...')
        except asyncio.CancelledError:
            log.info(f'[Upload Worker]发送媒体组"{media_group_id}"轮询任务被取消。')
            if media_group_id in media_group_poll_tasks:
                del media_group_poll_tasks[media_group_id]
        except Exception as e:
            log.error(
                f'[Upload Worker]发送媒体组"{media_group_id}"轮询任务出错,{_t(KeyWord.REASON)}:"{e}"',
                exc_info=True
            )
            if media_group_id in media_group_cache:
                del media_group_cache[media_group_id]
            if media_group_id in media_group_poll_tasks:
                del media_group_poll_tasks[media_group_id]

    async def send_media(
            self,
            media: raw.types.InputMediaDocument,
            upload_task: UploadTask
    ):
        """发送单条媒体消息。"""
        try:
            chat_id = upload_task.chat_id
            await self.client.invoke(
                raw.functions.messages.SendMedia(
                    peer=await self.client.resolve_peer(chat_id),
                    media=media,
                    random_id=self.client.rnd_id(),
                    **await utils.parse_text_entities(
                        self.client,
                        text='',
                        parse_mode=None,
                        entities=None
                    )
                )
            )
            upload_task.status = UploadStatus.SENT
            self.valid_link_cache = {k: v for k, v in self.valid_link_cache.items() if v != chat_id}
            log.info(f'[Upload Worker]单条消息发送完成,{_t(KeyWord.CHANNEL)}:"{chat_id}"')
        except Exception as e:
            log.error(f'"[Upload Worker]发送单条消息失败,{_t(KeyWord.REASON)}:"{e}"', exc_info=True)

    @staticmethod
    def get_video_info(video_path: str) -> Union[Dict[str, int], None]:
        try:
            media_info = MediaInfo.parse(video_path)
            video_track = media_info.video_tracks[0]
            meta = {
                'width': video_track.width,
                'height': video_track.height,
                'duration': round(video_track.duration / 1000)
            }
            if all(meta.values()):
                return meta
        except Exception as e:
            log.error(f'获取视频元数据失败,{_t(KeyWord.REASON)}:"{e}"')

    async def get_input_media_document(
            self,
            chat_id: Union[int, str],
            file: Union[raw.types.InputFile, raw.types.InputFileBig],
            attributes: List[raw.types.DocumentAttributeFilename],
            mime_type: str,
    ) -> raw.types.InputMediaDocument:
        media = raw.types.InputMediaUploadedDocument(
            mime_type=mime_type,
            file=file,
            attributes=attributes,
            force_file=False,
            thumb=None
        )
        media = await self.client.invoke(
            raw.functions.messages.UploadMedia(
                peer=await self.client.resolve_peer(chat_id),
                media=media
            )
        )
        return raw.types.InputMediaDocument(
            id=raw.types.InputDocument(
                id=media.document.id,
                access_hash=media.document.access_hash,
                file_reference=media.document.file_reference
            )
        )

    async def create_upload_task(
            self,
            link: Union[str, int],
            upload_task: UploadTask
    ) -> None:
        if isinstance(link, str):
            if link.startswith('https://t.me/'):
                if link in self.valid_link_cache:
                    chat_id: Union[int, str] = self.valid_link_cache[link]
                else:
                    target_meta: Union[dict, None] = await parse_link(
                        client=self.client,
                        link=link
                    )
                    chat_id: Union[int, str] = target_meta.get('chat_id')
                    target_chat = await get_chat_with_notify(
                        user_client=self.client,
                        chat_id=chat_id
                    )
                    if not target_chat:
                        raise ValueError
                    self.valid_link_cache[link] = chat_id
            else:
                chat_id: Union[int, str] = link
        else:
            chat_id: Union[int, str] = link
        file_path = upload_task.file_path
        file_size: int = os.path.getsize(file_path)
        upload_task.chat_id = chat_id
        if not is_allow_upload(file_size, self.is_premium):
            upload_task.error_msg = '上传大小超过限制(普通用户2000MiB,会员用户4000MiB)'
            upload_task.status = UploadStatus.FAILURE
            return None
        elif file_size == 0:
            upload_task.error_msg = '上传文件大小为0'
            upload_task.status = UploadStatus.FAILURE
            return None

        retry = 0
        while retry < self.max_upload_retries:
            try:
                await self.__add_task(
                    upload_task=upload_task
                )
                return None
            except FilePartMissing as e:
                missing_part = getattr(e, 'value')
                console.log(
                    f'{_t(KeyWord.UPLOAD_FILE_PART)}:{missing_part},'
                    f'{_t(KeyWord.STATUS)}:{_t(UploadStatus.UPLOADING)}。'
                )
                fp = upload_task.file_part
                if missing_part in fp:
                    fp.remove(missing_part)
                continue
            except (ChatAdminRequired, ChannelPrivate_400, ChannelPrivate_406) as e:
                upload_task.error_msg = str(e)
                upload_task.status = UploadStatus.FAILURE
                return None
            except Exception as e:
                console.log(
                    f'{_t(KeyWord.UPLOAD_TASK)}'
                    f'{_t(KeyWord.RE_UPLOAD)}:"{file_path}",'
                    f'{_t(KeyWord.RETRY_TIMES)}:{retry + 1}/{self.max_upload_retries},'
                    f'{_t(KeyWord.REASON)}:"{e}"'
                )
                retry += 1  # 只有非FilePartMissing异常才递增重试计数。
                if retry == self.max_upload_retries:
                    upload_task.error_msg = str(e)
                    upload_task.status = UploadStatus.FAILURE

    async def __add_task(
            self,
            upload_task: UploadTask
    ):
        file_path = upload_task.file_path
        file_size = upload_task.file_size
        while self.current_task_num >= self.max_upload_task:  # v1.0.7 增加下载任务数限制。
            await self.event.wait()
            self.event.clear()
        upload_task.status = UploadStatus.UPLOADING
        console.log(f'{_t(KeyWord.UPLOAD_TASK)}{_t(KeyWord.RESUME)}:"{file_path}"。') if upload_task.file_part else None
        format_file_size: str = MetaData.suitable_units_display(file_size)
        task_id = self.pb.progress.add_task(
            description='📤',
            filename=truncate_display_filename(split_path(file_path).get('file_name')),
            info=f'0.00B/{format_file_size}',
            total=file_size
        )
        _task = self.loop.create_task(
            self.resume_upload(
                upload_task=upload_task,
                progress=self.pb.upload,
                progress_args=(
                    self.pb.progress,
                    task_id,
                    upload_task
                )
            )
        )
        _task.add_done_callback(
            partial(
                self.upload_complete_callback,
                upload_task,
                task_id
            )
        )

        if _task:
            self.current_task_num += 1
            MetaData.print_current_task_num(
                prompt=_t(KeyWord.CURRENT_UPLOAD_TASK),
                num=self.current_task_num
            )
            await _task

    def upload_complete_callback(
            self,
            upload_task,
            task_id,
            _future
    ):
        try:
            _ = _future.result()
        except Exception as e:
            self.current_task_num -= 1
            self.pb.progress.remove_task(task_id=task_id)
            self.event.set()
            log.info(e)
            return
        file_path: str = upload_task.file_path
        self.current_task_num -= 1
        self.pb.progress.remove_task(task_id=task_id)
        if upload_task.file_size < 10 * 1024 * 1024:
            if not safe_delete(os.path.join(UploadTask.DIRECTORY_NAME, f'{upload_task.sha256}.json')):
                log.warning(f'无法删除"{os.path.basename(file_path)}"的上传缓存管理文件。')
            else:
                log.info(f'成功删除"{os.path.basename(file_path)}"的上传缓存管理文件。')
        self.event.set()
        safe_delete(file_path) if upload_task.with_delete else None
        upload_task.status = UploadStatus.SUCCESS
        MetaData.print_current_task_num(
            prompt=_t(KeyWord.CURRENT_UPLOAD_TASK),
            num=self.current_task_num
        )

    def download_upload(self, with_upload: dict, file_path: str):
        if isinstance(with_upload, dict):
            asyncio.create_task(
                self.create_upload_task(
                    link=with_upload.get('link'),
                    upload_task=UploadTask(
                        chat_id=None,
                        file_path=file_path,
                        file_id=self.client.rnd_id(),
                        file_size=os.path.getsize(file_path),
                        file_part=[],
                        status=UploadStatus.PENDING,
                        with_delete=with_upload.get('with_delete'),
                        media_group=with_upload.get('media_group'),
                        message_id=with_upload.get('message_id'),
                        send_as_media_group=with_upload.get('send_as_media_group', False)
                    )
                )
            )

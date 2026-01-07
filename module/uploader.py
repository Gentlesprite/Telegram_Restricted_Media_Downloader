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
    Dict,
    Union,
    Optional,
    Callable
)

import pyrogram
from pyrogram import raw, utils
from pyrogram.errors.exceptions import (
    FilePartMissing,
    ChatAdminRequired
)
from pyrogram.errors.exceptions.bad_request_400 import ChannelPrivate as ChannelPrivate_400
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as ChannelPrivate_406
from pymediainfo import MediaInfo

from module import console, log
from module.language import _t

from module.stdio import MetaData
from module.task import UploadTask
from module.path_tool import get_mime_from_extension

from module.path_tool import (
    split_path,
    safe_delete,
    truncate_filename
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
            client: pyrogram.Client,
            loop,
            is_premium: bool,
            progress,
            max_upload_task: int = 3,
            max_retry_count: int = 3,
            notify: Optional[Callable] = None
    ):
        self.client: pyrogram.Client = client
        self.loop = loop
        self.event = asyncio.Event()
        self.pb = progress
        self.current_task_num = 0
        self.max_upload_task = max_upload_task
        self.max_retry_count = max_retry_count
        self.is_premium: bool = is_premium
        self.notify: Callable = notify

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
            media = raw.types.InputMediaUploadedPhoto(
                file=file,
                spoiler=False
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
                    p = f'获取视频元数据失败,视频"{file_path}"将以文档格式进行上传。'
                    console.log(p)
                    log.info(p)
            media = raw.types.InputMediaUploadedDocument(
                mime_type=mime_type,
                file=file,
                attributes=attributes,
                force_file=False,  # 不要强制作为文件发送。
                thumb=None  # 缩略图。
            )
        peer = await self.client.resolve_peer(chat_id)
        r = await self.client.invoke(
            raw.functions.messages.SendMedia(
                peer=peer,
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
        return await utils.parse_messages(self.client, r)

    @staticmethod
    def get_video_info(video_path: str) -> Dict[str, int]:
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

    async def create_upload_task(
            self,
            link: str,
            upload_task: UploadTask
    ) -> None:
        file_path = upload_task.file_path
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
        file_part_retry = 0
        while retry < self.max_retry_count:
            try:
                if retry != 0 or upload_task.file_part:
                    console.log(f'{_t(KeyWord.RESUME)}:"{file_path}"。')
                upload_task.status = UploadStatus.UPLOADING
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
                file_part_retry += 1
                if file_part_retry >= upload_task.file_total_parts:
                    upload_task.error_msg = f'缺失分片重传次数大于分片总数{upload_task.file_total_parts},可能存在网络问题'
                    upload_task.status = UploadStatus.FAILURE
                continue
            except (ChatAdminRequired, ChannelPrivate_400, ChannelPrivate_406) as e:
                upload_task.error_msg = str(e)
                upload_task.status = UploadStatus.FAILURE
            except Exception as e:
                console.log(
                    f'{_t(KeyWord.UPLOAD_TASK)}'
                    f'{_t(KeyWord.RE_UPLOAD)}:"{file_path}",'
                    f'{_t(KeyWord.RETRY_TIMES)}:{retry + 1}/{self.max_retry_count},'
                    f'{_t(KeyWord.REASON)}:"{e}"'
                )
                retry += 1  # 只有非FilePartMissing异常才递增重试计数。
                if retry == self.max_retry_count:
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
                num=self.current_task_num,
                complete=upload_task.complete_task,
                total=upload_task.TASK_COUNTER
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
        chat_id: Union[str, int] = upload_task.chat_id
        file_size: int = upload_task.file_size
        file_path: str = upload_task.file_path
        with_delete: bool = upload_task.with_delete
        self.current_task_num -= 1
        self.pb.progress.remove_task(task_id=task_id)
        if not safe_delete(
                os.path.join(
                    UploadTask.DIRECTORY_NAME,
                    str(chat_id),
                    f'{truncate_filename(f"{file_size} - {os.path.basename(file_path)}")}.json'
                )
        ):
            log.warning(f'无法删除"{os.path.basename(file_path)}"的上传缓存管理文件。')
        else:
            log.info(f'成功删除"{os.path.basename(file_path)}"的上传缓存管理文件。')
        asyncio.create_task(self.notify(f'"{file_path}"已上传完成。')) if isinstance(self.notify, Callable) else None
        self.event.set()
        safe_delete(file_path) if with_delete else None
        upload_task.status = UploadStatus.SUCCESS
        MetaData.print_current_task_num(
            prompt=_t(KeyWord.CURRENT_UPLOAD_TASK),
            num=self.current_task_num,
            complete=upload_task.complete_task,
            total=upload_task.TASK_COUNTER
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
                        status=UploadStatus.IDLE,
                        with_delete=with_upload.get('with_delete')
                    )
                )
            )

# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/9/6 23:00
# File:uploader.py
import os
import asyncio

from functools import partial
from typing import (
    Callable,
    Union,
    BinaryIO
)

import pyrogram
from pyrogram import raw, utils

from module import console
from module.language import _t

from module.stdio import MetaData
from module.task import UploadTask
from module.path_tool import (
    split_path,
    safe_delete
)
from module.enums import (
    KeyWord,
    UploadStatus
)
from module.util import (
    truncate_display_filename,
    extract_link_content,
    get_chat_with_notify,
    is_allow_upload
)


class TelegramUploader:
    def __init__(
            self,
            client: pyrogram.Client,
            loop,
            progress,
            queue,
            is_premium,
            max_upload_task: int = 3,
            max_retry_count: int = 3,

    ):
        self.client: pyrogram.Client = client
        self.loop = loop
        self.event = asyncio.Event()
        self.queue = queue
        self.pb = progress
        self.current_task_num = 0
        self.max_upload_task = max_upload_task
        self.max_retry_count = max_retry_count
        self.is_premium: bool = is_premium

    async def send_media(
            self,
            chat_id: Union[int, str],
            path: Union[str, BinaryIO],
            file_id: int = None,
            file_part: int = 0,
            progress: Callable = None,
            progress_args: tuple = ()
    ):
        file = await self.client.save_file(
            path=path,
            file_id=file_id,
            file_part=file_part,
            progress=progress,
            progress_args=progress_args
        )
        file_path: Union[str, None] = getattr(file, 'name')
        if file_path:
            media = raw.types.InputMediaUploadedDocument(
                mime_type=self.client.guess_mime_type(file_path) or 'application/octet-stream',
                file=file,
                attributes=[raw.types.DocumentAttributeFilename(file_name=split_path(file_path).get('file_name'))]
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

    @UploadTask.on_create_task
    async def create_upload_task(
            self,
            link: str,
            file_path: str,
            with_delete: bool = False
    ):
        target_meta: Union[dict, None] = await extract_link_content(
            client=self.client,
            link=link,
            only_chat_id=True
        )
        chat_id: Union[int, str] = target_meta.get('chat_id')
        target_chat = await get_chat_with_notify(
            user_client=self.client,
            chat_id=chat_id
        )
        if not target_chat:
            raise ValueError
        file_size: int = os.path.getsize(file_path)
        UploadTask(chat_id=chat_id, file_path=file_path, size=file_size, error_msg=None)
        if not is_allow_upload(file_size, self.is_premium):
            return {
                'chat_id': chat_id,
                'file_name': file_path,
                'size': os.path.getsize(file_path),
                'status': UploadStatus.FAILURE,
                'error_msg': '上传大小超过限制(普通用户2000MiB,会员用户4000MiB)'
            }
        elif file_size == 0:
            return {
                'chat_id': chat_id,
                'file_name': file_path,
                'size': os.path.getsize(file_path),
                'status': UploadStatus.FAILURE,
                'error_msg': '上传文件大小为0'
            }
        for retry in range(self.max_retry_count):
            try:
                console.log(
                    f'{_t(KeyWord.UPLOAD_TASK)}'
                    f'{_t(KeyWord.CHANNEL)}:"{chat_id}",'
                    f'{_t(KeyWord.FILE)}:"{file_path}",'
                    f'{_t(KeyWord.SIZE)}:{MetaData.suitable_units_display(file_size)},'
                    f'{_t(KeyWord.STATUS)}:{_t(UploadStatus.UPLOADING)}。'
                )
                await self.__add_task(
                    chat_id=chat_id,
                    file_path=file_path,
                    size=file_size,
                    with_delete=with_delete
                )
                return {
                    'chat_id': chat_id,
                    'file_name': file_path,
                    'size': os.path.getsize(file_path),
                    'status': UploadStatus.SUCCESS,
                    'error_msg': None
                }
            except Exception as e:
                console.log(
                    f'{_t(KeyWord.UPLOAD_TASK)}'
                    f'{_t(KeyWord.RE_UPLOAD)}:"{file_path}",'
                    f'{_t(KeyWord.RETRY_TIMES)}:{retry + 1}/{self.max_retry_count},'
                    f'{_t(KeyWord.REASON)}:"{e}"'
                )
                if retry == self.max_retry_count - 1:
                    return {
                        'chat_id': chat_id,
                        'file_name': file_path,
                        'size': os.path.getsize(file_path),
                        'status': UploadStatus.FAILURE,
                        'error_msg': str(e)
                    }

    async def __add_task(
            self,
            chat_id: Union[str, int],
            file_path: str,
            size: int,
            with_delete: bool = False
    ):
        while self.current_task_num >= self.max_upload_task:  # v1.0.7 增加下载任务数限制。
            await self.event.wait()
            self.event.clear()
        format_file_size: str = MetaData.suitable_units_display(size)
        task_id = self.pb.progress.add_task(
            description='📤',
            filename=truncate_display_filename(split_path(file_path).get('file_name')),
            info=f'0.00B/{format_file_size}',
            total=size
        )
        _task = self.loop.create_task(
            self.send_media(
                chat_id=chat_id,
                path=file_path,
                progress=self.pb.bar,
                progress_args=(
                    self.pb.progress,
                    task_id
                )
            )
        )
        _task.add_done_callback(
            partial(
                self.upload_complete_callback,
                size,
                file_path,
                task_id,
                with_delete
            )
        )

        if _task:
            self.current_task_num += 1
            MetaData.print_current_task_num(
                prompt=_t(KeyWord.CURRENT_UPLOAD_TASK),
                num=self.current_task_num
            )
            self.queue.put_nowait(_task)

    def upload_complete_callback(
            self,
            local_file_size,
            file_path,
            task_id,
            with_delete,
            _future
    ):
        more = ''
        if with_delete:
            safe_delete(file_path)
            more = '(本地文件已删除)'
        console.log(
            f'{_t(KeyWord.UPLOAD_TASK)}'
            f'{_t(KeyWord.FILE)}:"{file_path}",'
            f'{_t(KeyWord.SIZE)}:{MetaData.suitable_units_display(local_file_size)},'
            f'{_t(KeyWord.STATUS)}:{_t(UploadStatus.SUCCESS)}{more}。',
        )
        self.current_task_num -= 1
        self.pb.progress.remove_task(task_id=task_id)
        self.event.set()
        self.queue.task_done()
        MetaData.print_current_task_num(
            prompt=_t(KeyWord.CURRENT_UPLOAD_TASK),
            num=self.current_task_num
        )

    def download_upload(self, with_upload: dict, file_path: str):
        if isinstance(with_upload, dict):
            asyncio.create_task(
                self.create_upload_task(
                    link=with_upload.get('link'),
                    file_path=file_path,
                    with_delete=with_upload.get('with_delete')
                )
            )

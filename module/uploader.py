# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/9/6 23:00
# File:uploader.py
import os
from typing import (
    Callable,
    Union,
    BinaryIO
)
from functools import partial

import pyrogram
from pyrogram import raw, utils

from module.stdio import MetaData
from module.path_tool import split_path
from module.util import (
    truncate_display_filename,
    extract_link_content,
    get_chat_with_notify
)


class TelegramUploader:
    def __init__(
            self,
            client: pyrogram.Client,
            loop,
            progress,
            queue
    ):
        self.client: pyrogram.Client = client
        self.loop = loop
        self.queue = queue
        self.pb = progress

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
        file_name = getattr(file, 'name')
        if file_name:
            media = raw.types.InputMediaUploadedDocument(
                mime_type=self.client.guess_mime_type(file_name) or 'application/octet-stream',
                file=file,
                attributes=[raw.types.DocumentAttributeFilename(file_name=split_path(file_name).get('file_name'))]
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

    async def create_upload_task(
            self,
            link: str,
            file_name: str
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

        await self.__add_task(
            chat_id=chat_id,
            link=link,
            file_name=file_name
        )

    async def __add_task(
            self,
            chat_id,
            link,
            file_name
    ):
        local_file_size: int = os.path.getsize(file_name)
        format_file_size: str = MetaData.suitable_units_display(local_file_size)
        task_id = self.pb.progress.add_task(
            description='',
            filename=truncate_display_filename(file_name),
            info=f'0.00B/{format_file_size}',
            total=local_file_size
        )
        _task = self.loop.create_task(
            self.send_media(
                chat_id=chat_id,
                path=file_name,
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
                local_file_size,
                file_name,
                task_id
            )
        )
        self.queue.put_nowait(_task) if _task else None

    def upload_complete_callback(
            self,
            local_file_size,
            file_path,
            task_id,
            _future
    ):
        self.pb.progress.remove_task(task_id=task_id)

# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/9/6 23:00
# File:uploader.py

from typing import (
    Callable,
    Union,
    BinaryIO
)

import pyrogram
from pyrogram import raw, utils

from module.path_tool import split_path


class TelegramUploader:
    def __init__(self, client: pyrogram.Client):
        self.client: pyrogram.Client = client

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

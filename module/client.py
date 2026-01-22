# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/2/25 1:26
# File:client.py
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Optional, Union, List

import pyrogram
from pyrogram.qrlogin import QRLogin
from pyrogram import raw, types, utils
from pyrogram.errors.exceptions import PhoneNumberInvalid
from pyrogram.raw.core import TLObject
from pyrogram.session.session import Result
from pyrogram.session import (
    Auth,
    Session
)
from pyrogram.crypto import mtproto
from pyrogram.errors import (
    FloodPremiumWait,
    FloodWait,
    InternalServerError,
    ServiceUnavailable,
    AuthBytesInvalid,
    BadMsgNotification,
    RPCError
)

from module import (
    console,
    SOFTWARE_FULL_NAME,
    log,
    __version__
)
from module.enums import KeyWord
from module.language import _t


class TelegramRestrictedMediaDownloaderClient(pyrogram.Client):

    async def authorize(self) -> pyrogram.types.User:
        console.print(
            f'Pyrogram is free software and comes with ABSOLUTELY NO WARRANTY. Licensed\n'
            f'under the terms of the {pyrogram.__license__}.')
        console.print(
            f'欢迎使用[#b4009e]{SOFTWARE_FULL_NAME}[/#b4009e](版本 {__version__})'
            f'基于Pyrogram(版本 {pyrogram.__version__})。')
        while True:
            try:
                while True:
                    value = console.input('请输入「电话号码」([#6a2c70]电话号码[/#6a2c70]需以[#b83b5e]「+地区」[/#b83b5e]开头!'
                                          '如:[#f08a5d]+86[/#f08a5d][#f9ed69]15000000000[/#f9ed69]):').strip()
                    if not value.startswith('+'):
                        log.warning(f'意外的参数:"{value}",电话号码需以「+地区」开头!')
                        continue
                    if len(value) < 8 or len(value) > 16:
                        log.warning(f'意外的参数:"{value}",电话号码无效!')
                        continue
                    if not value:
                        continue

                    confirm = console.input(
                        f'所输入的「{value}」是否[#B1DB74]正确[/#B1DB74]? - 「y|n」(默认y):').strip().lower()
                    if confirm in ('y', ''):
                        break
                    elif confirm == 'n':
                        continue
                    else:
                        log.warning(f'意外的参数:"{confirm}",支持的参数 - 「y|n」')
                self.phone_number = value
                sent_code = await self.send_code(self.phone_number)
            except pyrogram.errors.BadRequest as e:
                console.print(e.MESSAGE)
                self.phone_number = None
            except (pyrogram.errors.PhoneNumberInvalid, AttributeError) as e:
                self.phone_number = None
                log.error(f'「电话号码」错误,请重新输入!{_t(KeyWord.REASON)}:"{e.MESSAGE}"')
            else:
                break
        if sent_code.type == pyrogram.enums.SentCodeType.SETUP_EMAIL_REQUIRED:
            console.print('需要「设置邮箱」以完成授权。')

            while True:
                try:
                    while True:
                        email = console.input('请输入「邮箱」:')
                        if not email:
                            continue
                        confirm = console.input(f'所输入的「{email}」是否正确? - 「y|n」(默认y):').strip().lower()
                        if confirm in ('y', ''):
                            break
                        elif confirm == 'n':
                            continue
                        else:
                            log.warning(f'意外的参数:"{confirm}",支持的参数 - 「y|n」')
                    await self.invoke(
                        raw.functions.account.SendVerifyEmailCode(
                            purpose=raw.types.EmailVerifyPurposeLoginSetup(
                                phone_number=self.phone_number,
                                phone_code_hash=sent_code.phone_code_hash,
                            ),
                            email=email,
                        )
                    )

                    email_code = console.input('请输入「验证码」:')

                    email_sent_code = await self.invoke(
                        raw.functions.account.VerifyEmail(
                            purpose=raw.types.EmailVerifyPurposeLoginSetup(
                                phone_number=self.phone_number,
                                phone_code_hash=sent_code.phone_code_hash,
                            ),
                            verification=raw.types.EmailVerificationCode(code=email_code),
                        )
                    )

                    if isinstance(email_sent_code, raw.types.account.EmailVerifiedLogin):
                        if isinstance(email_sent_code.sent_code, raw.types.auth.SentCodePaymentRequired):
                            raise pyrogram.errors.Unauthorized(
                                'You need to pay for or purchase premium to continue authorization '
                                'process, which is currently not supported by Pyrogram.'
                            )
                except pyrogram.errors.BadRequest as e:
                    console.print(e.MESSAGE)
                else:
                    break

        else:
            sent_code_descriptions = {
                pyrogram.enums.SentCodeType.APP: 'Telegram app',
                pyrogram.enums.SentCodeType.SMS: 'SMS',
                pyrogram.enums.SentCodeType.CALL: 'phone call',
                pyrogram.enums.SentCodeType.FLASH_CALL: 'phone flash call',
                pyrogram.enums.SentCodeType.FRAGMENT_SMS: 'Fragment SMS',
                pyrogram.enums.SentCodeType.EMAIL_CODE: 'email code'
            }

            console.print(
                f'[#f08a5d]「验证码」[/#f08a5d]已通过[#f9ed69]「{sent_code_descriptions[sent_code.type]}」[/#f9ed69]发送。')

        while True:
            if not self.phone_code:
                self.phone_code = console.input('请输入收到的[#f08a5d]「验证码」[/#f08a5d]:').strip()

            try:
                signed_in = await self.sign_in(self.phone_number, sent_code.phone_code_hash, self.phone_code)
            except pyrogram.errors.BadRequest as e:
                console.print(e.MESSAGE)
                self.phone_code = None
            except pyrogram.errors.SessionPasswordNeeded as _:
                console.print(
                    '当前登录账号设置了[#f08a5d]「两步验证」[/#f08a5d],需要提供两步验证的[#f9ed69]「密码」[/#f9ed69]。')

                while True:
                    console.print('密码提示:{}'.format(await self.get_password_hint()))

                    if not self.password:
                        self.password = console.input(
                            '输入[#f08a5d]「两步验证」[/#f08a5d]的[#f9ed69]「密码」[/#f9ed69](为空代表[#FF4689]忘记密码[/#FF4689]):',
                            password=self.hide_password).strip()

                    try:
                        if not self.password:
                            confirm = console.input(
                                '所输入的[#f08a5d]「恢复密码」[/#f08a5d]是否正确? - 「y|n」(默认y):').strip().lower()
                            if confirm in ('y', ''):
                                email_pattern = await self.send_recovery_code()
                                console.print(
                                    f'[#f08a5d]「恢复代码」[/#f08a5d]已发送到邮箱[#f9ed69]「{email_pattern}」[/#f9ed69]。')

                                while True:
                                    recovery_code = console.input('请输入[#f08a5d]「恢复代码」[/#f08a5d]:').strip()

                                    try:
                                        return await self.recover_password(recovery_code)
                                    except pyrogram.errors.BadRequest as e:
                                        console.print(e.MESSAGE)
                                    except Exception as _:
                                        console.print_exception()
                                        raise
                            else:
                                self.password = None
                        else:
                            return await self.check_password(self.password)
                    except pyrogram.errors.BadRequest as e:
                        console.print(e.MESSAGE)
                        self.password = None
            else:
                break

        if isinstance(signed_in, pyrogram.types.User):
            return signed_in

        while True:
            first_name = console.input('输入[#f08a5d]「名字」[/#f08a5d]:').strip()
            last_name = console.input('输入[#f9ed69]「姓氏」[/#f9ed69](为空代表跳过): ').strip()

            try:
                signed_up = await self.sign_up(
                    self.phone_number,
                    sent_code.phone_code_hash,
                    first_name,
                    last_name
                )
            except pyrogram.errors.BadRequest as e:
                console.print(e.MESSAGE)
            else:
                break

        if isinstance(signed_in, pyrogram.types.TermsOfService):
            console.print('\n' + signed_in.text + '\n')
            await self.accept_terms_of_service(signed_in.id)

        return signed_up

    async def authorize_qr(self, except_ids: List[int] = []) -> "User":
        import qrcode
        qr_login = QRLogin(self, except_ids)
        await qr_login.recreate()

        qr = qrcode.QRCode(version=1)

        while True:
            try:
                console.print(
                    'Pyrogram is free software and comes with ABSOLUTELY NO WARRANTY. Licensed\n'
                    f'under the terms of the {pyrogram.__license__}.\n'
                    f'欢迎使用[#b4009e]{SOFTWARE_FULL_NAME}[/#b4009e](版本 {__version__})'
                    f'基于Pyrogram(版本 {pyrogram.__version__})。\n'
                    '请扫描[#6a2c70]「二维码」[/#6a2c70]登录\n'
                    '[#b83b5e]Settings(设置)[/#b83b5e] -> [#f08a5d]Devices(设备)[/#f08a5d] -> [#f9ed69]Link Desktop Device(关联桌面设备)[/#f9ed69]'
                )

                qr.clear()
                qr.add_data(qr_login.url)
                qr.print_ascii(tty=True)
                log.info('Waiting for QR code being scanned.')

                signed_in = await qr_login.wait()

                if signed_in:
                    log.info(f'Logged in successfully as {signed_in.full_name}')
                    return signed_in
            except asyncio.TimeoutError:
                log.info('Recreating QR code.')
                await qr_login.recreate()
            except pyrogram.errors.SessionPasswordNeeded as e:
                console.print(e.MESSAGE)

                while True:
                    console.print('密码提示:{}'.format(await self.get_password_hint()))

                    if not self.password:
                        self.password = console.input(
                            '输入[#f08a5d]「两步验证」[/#f08a5d]的[#f9ed69]「密码」[/#f9ed69](为空代表[#FF4689]忘记密码[/#FF4689]):',
                            password=self.hide_password).strip()

                    try:
                        if not self.password:
                            confirm = console.input(
                                '所输入的[#f08a5d]「恢复密码」[/#f08a5d]是否正确? - 「y|n」(默认y):').strip().lower()

                            if confirm in ('y', ''):
                                email_pattern = await self.send_recovery_code()
                                console.print(
                                    f'[#f08a5d]「恢复代码」[/#f08a5d]已发送到邮箱[#f9ed69]「{email_pattern}」[/#f9ed69]。')

                                while True:
                                    recovery_code = console.input('请输入[#f08a5d]「恢复代码」[/#f08a5d]:').strip()

                                    try:
                                        return await self.recover_password(recovery_code)
                                    except pyrogram.errors.BadRequest as e:
                                        console.print(e.MESSAGE)
                                    except Exception as e:
                                        log.exception(e)
                                        raise
                            else:
                                self.password = None
                        else:
                            return await self.check_password(self.password)
                    except pyrogram.errors.BadRequest as e:
                        console.print(e.MESSAGE)
                        self.password = None
            else:
                break

    async def get_chat_history(
            self: pyrogram.Client,
            chat_id: Union[int, str],
            limit: int = 0,
            min_id: int = 0,
            max_id: int = 0,
            offset: int = 0,
            offset_id: int = 0,
            offset_date: datetime = utils.zero_datetime(),
            reverse: bool = False,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        # https://github.com/tangyoha/telegram_media_downloader/blob/master/module/get_chat_history_v2.py
        current = 0
        total = limit or (1 << 31) - 1
        limit = min(100, total)

        while True:
            messages = await get_chunk(
                client=self,
                chat_id=chat_id,
                limit=limit,
                offset=offset,
                min_id=min_id,
                max_id=max_id + 1 if max_id else 0,
                from_message_id=offset_id,
                from_date=offset_date,
                reverse=reverse,
            )

            if not messages:
                return

            offset_id = messages[-1].id + (1 if reverse else 0)

            for message in messages:
                yield message

                current += 1

                if current >= total:
                    return

    async def get_session(
            self,
            dc_id: Optional[int] = None,
            is_media: Optional[bool] = False,
            is_cdn: Optional[bool] = False,
            business_connection_id: Optional[str] = None,
            export_authorization: Optional[bool] = True,
            server_address: Optional[str] = None,
            port: Optional[int] = None,
            temporary: Optional[bool] = False
    ) -> "Session":
        if not dc_id:
            dc_id = await self.storage.dc_id()

        if business_connection_id:
            dc_id = self.business_connections.get(business_connection_id)

            if dc_id is None:
                connection = await self.session.invoke(
                    raw.functions.account.GetBotBusinessConnection(
                        connection_id=business_connection_id
                    )
                )

                dc_id = self.business_connections[business_connection_id] = connection.updates[0].connection.dc_id

        is_current_dc = await self.storage.dc_id() == dc_id

        if not temporary and is_current_dc and not is_media:
            return self.session

        sessions = self.media_sessions if is_media else self.sessions

        if not temporary and sessions.get(dc_id):
            return sessions[dc_id]

        if not server_address or not port:
            dc_option = await self.get_dc_option(dc_id, is_media=is_media, ipv6=self.ipv6, is_cdn=is_cdn)

            server_address = server_address or dc_option.ip_address
            port = port or dc_option.port

        if is_media:
            auth_key = (await self.get_session(dc_id)).auth_key
        else:
            if not is_current_dc:
                auth_key = await Auth(
                    self,
                    dc_id,
                    server_address,
                    port,
                    await self.storage.test_mode()
                ).create()
            else:
                auth_key = await self.storage.auth_key()

        session = TelegramRestrictedMediaDownloaderSession(
            self,
            dc_id,
            server_address,
            port,
            auth_key,
            await self.storage.test_mode(),
            is_media=is_media
        )

        if not temporary:
            sessions[dc_id] = session

        await session.start()

        if not is_current_dc and export_authorization:
            for _ in range(3):
                exported_auth = await self.invoke(
                    raw.functions.auth.ExportAuthorization(
                        dc_id=dc_id
                    )
                )

                try:
                    await session.invoke(
                        raw.functions.auth.ImportAuthorization(
                            id=exported_auth.id,
                            bytes=exported_auth.bytes
                        )
                    )
                except AuthBytesInvalid:
                    continue
                else:
                    break
            else:
                await session.stop()
                raise AuthBytesInvalid

        return session


async def get_chunk(
        *,
        client: pyrogram.Client,
        chat_id: Union[int, str],
        limit: int = 0,
        offset: int = 0,
        min_id: int = 0,
        max_id: int = 0,
        from_message_id: int = 0,
        from_date: datetime = utils.zero_datetime(),
        reverse: bool = False
):
    from_message_id = from_message_id or (1 if reverse else 0)
    messages = await utils.parse_messages(
        client,
        await client.invoke(
            raw.functions.messages.GetHistory(
                peer=await client.resolve_peer(chat_id),
                offset_id=from_message_id,
                offset_date=utils.datetime_to_timestamp(from_date),
                add_offset=offset * (-1 if reverse else 1) - (limit if reverse else 0),
                limit=limit,
                max_id=max_id,
                min_id=min_id,
                hash=0,
            ),
            sleep_threshold=60,
        ),
        replies=0,
    )

    if reverse:
        messages.reverse()

    return messages


class TelegramRestrictedMediaDownloaderSession(Session):
    WAIT_TIMEOUT = 20
    START_TIMEOUT = 10
    MAX_RETRIES = 15

    async def invoke(
            self,
            query: TLObject,
            retries: int = MAX_RETRIES,
            timeout: float = WAIT_TIMEOUT,
            sleep_threshold: float = Session.SLEEP_THRESHOLD,
            retry_delay: float = Session.RETRY_DELAY
    ):
        try:
            await asyncio.wait_for(self.is_started.wait(), self.WAIT_TIMEOUT)
        except asyncio.TimeoutError:
            pass

        if isinstance(
                query, (raw.functions.InvokeWithoutUpdates, raw.functions.InvokeWithTakeout)
        ):
            inner_query = query.query
        else:
            inner_query = query

        query_name = '.'.join(inner_query.QUALNAME.split('.')[1:])

        for attempt in range(1, retries + 1):
            try:
                return await self.send(query, timeout=timeout)
            except (FloodWait, FloodPremiumWait) as e:
                amount = e.value

                if amount > sleep_threshold >= 0:
                    raise
                log.info(
                    '[%s] Waiting for %s seconds before continuing (required by "%s")',
                    self.client.name,
                    amount,
                    query_name,
                )
                console.log(f'[{self.client.name}]请求频繁,"{query_name}"要求等待{amount}秒后继续运行。')

                await asyncio.sleep(amount)
            except (OSError, InternalServerError, ServiceUnavailable) as e:
                log.info(
                    '[%s] Retrying "%s" due to: %s', attempt, query_name, str(e) or repr(e)
                )
                console.log(f'[{attempt}/{retries}]尝试重连,重新调用"{query_name}",{_t(KeyWord.REASON)}:"{str(e) or repr(e)}"')

                await asyncio.sleep(retry_delay)

        raise TimeoutError(f'经{retries}次尝试后仍无法调用"{query_name}"')

    async def send(
            self,
            data: TLObject,
            wait_response: bool = True,
            timeout: float = WAIT_TIMEOUT
    ):
        message = await self.msg_factory.create(data)
        msg_id = message.msg_id

        if wait_response:
            self.results[msg_id] = Result()

        log.debug('Sent: %s', message)

        payload = await self.client.loop.run_in_executor(
            self.connection.protocol.crypto_executor,
            mtproto.pack,
            message,
            self.salt,
            self.session_id,
            self.auth_key,
            self.auth_key_id
        )

        try:
            await self.connection.send(payload)
        except OSError as e:
            self.results.pop(msg_id, None)
            raise e

        if wait_response:
            try:
                await asyncio.wait_for(self.results[msg_id].event.wait(), timeout)
            except asyncio.TimeoutError:
                pass

            result = self.results.pop(msg_id).value

            if result is None:
                raise TimeoutError('Request timed out')

            if isinstance(result, raw.types.RpcError):
                if isinstance(
                        data, (raw.functions.InvokeWithoutUpdates, raw.functions.InvokeWithTakeout)
                ):
                    data = data.query

                RPCError.raise_it(result, type(data))

            if isinstance(result, raw.types.BadMsgNotification):
                e_code: int = result.error_code

                if e_code in (16, 17):
                    log.error(
                        '%s: %s', BadMsgNotification.__name__, BadMsgNotification(e_code)
                    )
                    raise BadMsgNotification(e_code)

                log.warning(
                    '%s: %s', BadMsgNotification.__name__, BadMsgNotification(e_code)
                )
            if isinstance(result, raw.types.BadServerSalt):
                self.salt = result.new_server_salt
                return await self.send(data, wait_response, timeout)

            return result

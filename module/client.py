# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/2/25 1:26
# File:client.py
import pyrogram
from pyrogram.errors import PhoneNumberInvalid

from module import console, SOFTWARE_FULL_NAME, log, __version__
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
                        f'所输入的「{value}」是否[#B1DB74]正确[/#B1DB74]? - 「y|n」(默认y): ').strip().lower()
                    if confirm in ('y', ''):
                        break
                    else:
                        log.warning(f'意外的参数:"{confirm}",支持的参数 - 「y|n」')
                self.phone_number = value
                sent_code = await self.send_code(self.phone_number)
            except pyrogram.errors.BadRequest as e:
                console.print(e.MESSAGE)
                self.phone_number = None
            except (PhoneNumberInvalid, AttributeError) as e:
                self.phone_number = None
                log.error(f'「电话号码」错误,请重新输入!{_t(KeyWord.REASON)}:"{e.MESSAGE}"')
            else:
                break

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
                                '确认[#f08a5d]「恢复密码」[/#f08a5d]? - 「y|n」(默认y):').strip().lower()
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

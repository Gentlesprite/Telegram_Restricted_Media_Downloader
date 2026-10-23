# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026-10-22 12:00:00
# File:notice.py
import datetime

from typing import Union

from module.enums import NoticeType


class NoticeHub:
    """通知中心:汇集下载、上传、转发的完成通知,供网页面板的「通知」板块展示。"""

    NOTICES: list = []  # 全部通知,新通知插入到最前面,网页面板按时间倒序展示。
    MAX_NOTICES_PER_TYPE: int = 500  # 每种通知类型独立保留的条数(三类合计最多1500条),超出后丢弃该类型最旧的,避免长时间运行后内存无限增长。
    OWNER_NAMES: dict = {}  # 创建者ID -> 显示名,任务创建时登记,通知展示时直接读取,避免每次通知都重复解析用户信息。

    @staticmethod
    def add_owner(owner: Union[int, str, None], user) -> None:
        """登记任务创建者的显示名,供通知展示"谁创建的任务"。"""
        if owner is None or user is None:
            return
        first_name: str = str(getattr(user, 'first_name', '') or '')
        last_name: str = str(getattr(user, 'last_name', '') or '')
        name: str = f'{first_name} {last_name}'.strip() or str(getattr(user, 'username', '') or '')
        if name:
            NoticeHub.OWNER_NAMES[str(owner)] = name

    @staticmethod
    def get_owner_name(owner: Union[int, str, None]) -> str:
        """读取创建者的显示名,未登记时回退为创建者ID,供通知展示。"""
        if owner is None:
            return ''
        return NoticeHub.OWNER_NAMES.get(str(owner), str(owner))

    @staticmethod
    def trim() -> None:
        """按类型裁剪通知:每种类型只保留最新的MAX_NOTICES_PER_TYPE条,类型之间互不挤占。"""
        counts: dict = {}
        kept: list = []
        for notice in NoticeHub.NOTICES:  # 列表本身最新在前,故每种类型先遇到的即最新,超限的后遇到的为更旧,丢弃。
            notice_type = notice.get('type')
            counts[notice_type] = counts.get(notice_type, 0) + 1
            if counts[notice_type] <= NoticeHub.MAX_NOTICES_PER_TYPE:
                kept.append(notice)
        NoticeHub.NOTICES[:] = kept

    @staticmethod
    def push(notice_type: str, text: str, owner: Union[int, None] = None) -> None:
        """登记一条通知,notice_type为通知类型,text为通知内容,owner为任务创建者。"""
        if not text:
            return
        NoticeHub.NOTICES.insert(0, {
            'type': notice_type,
            'text': str(text),
            'owner': owner,
            'owner_name': NoticeHub.get_owner_name(owner),
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        NoticeHub.trim()

    @staticmethod
    def snapshot() -> dict:
        """按通知类型分组返回通知副本,供网页面板「通知」板块使用。"""
        result: dict = {notice_type: [] for notice_type in NoticeType()}
        for notice in list(NoticeHub.NOTICES):
            notice_type = notice.get('type')
            if notice_type in result:
                result[notice_type].append(notice)
        return result

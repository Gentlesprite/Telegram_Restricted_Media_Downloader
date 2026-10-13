# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/10/13 12:05
# File:database.py
import os
import time
import sqlite3

from abc import (
    ABC,
    abstractmethod
)
from dataclasses import dataclass
from typing import (
    Union,
    List
)

from module import log
from module.language import _t
from module.path_tool import safe_delete
from module.enums import KeyWord


class RecordType:
    """网页记录的类型。"""
    DOWNLOAD: str = 'download'  # 下载记录。
    UPLOAD: str = 'upload'  # 上传记录。


@dataclass
class WebRecord:
    """网页面板的下载/上传记录,字段与数据库列一一对应。"""
    record_type: str = RecordType.DOWNLOAD  # 记录类型,download为下载记录,upload为上传记录。
    chat_id: Union[str, int, None] = None  # 频道ID,下载记录为来源频道,上传记录为目标频道。
    chat_name: str = ''  # 频道标题,为空时由展示方回退为频道ID。
    message_id: Union[int, None] = None  # 消息ID,上传记录可为空。
    file_name: str = ''  # 文件名。
    file_path: str = ''  # 文件的保存路径,读取记录时会实时校验该路径是否还存在。
    file_size: int = 0  # 文件大小,单位为字节。
    file_type: str = ''  # 媒体类型,如video、photo。
    status: str = ''  # 终态,success为成功,skip为跳过,failure为失败。
    error_msg: str = ''  # 失败原因,非失败记录为空。
    link: str = ''  # 下载链接,上传记录可为空。
    create_time: int = 0  # 创建时间,unix时间戳,单位为秒。
    finish_time: int = 0  # 完成时间,unix时间戳,单位为秒。
    record_id: Union[int, None] = None  # 数据库自增ID,写入成功后回填。


class RecordDatabase(ABC):
    """网页下载/上传记录数据库的抽象类。

    仿照pyrogram的Storage:只规范本项目实际用到的操作,不引入用不到的功能。
    后续更换数据库时新增一个实现类并调整build_record_database的返回值即可,
    下载器、上传器与网页面板无需任何改动。
    """

    @abstractmethod
    async def open(self) -> bool:
        """打开数据库并建表。

        Returns:
            bool: 成功返回True;失败时只记日志,记录功能不可用,但不影响下载与上传。
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """关闭数据库。"""
        raise NotImplementedError

    @abstractmethod
    async def add_record(self, record: WebRecord) -> bool:
        """写入一条记录。

        Args:
            record: 待写入的记录,写入成功后回填record_id。

        Returns:
            bool: 成功返回True;失败只记日志,不影响主流程。
        """
        raise NotImplementedError

    @abstractmethod
    async def remove_record(self, record_id: int) -> bool:
        """按记录ID删除一条记录。

        Args:
            record_id: 记录ID。

        Returns:
            bool: 成功返回True。
        """
        raise NotImplementedError

    @abstractmethod
    async def get_records(self, record_type: Union[str, None] = None) -> List[WebRecord]:
        """读取记录,实时校验文件是否还存在,不存在的条目直接丢弃。

        Args:
            record_type: 记录类型,为空时返回全部记录。

        Returns:
            List[WebRecord]: 文件仍存在的记录,按写入时间从新到旧排列。
        """
        raise NotImplementedError


class SqliteRecordDatabase(RecordDatabase):
    """基于sqlite3的网页记录数据库实现,仿照pyrogram的SQLiteStorage组织代码。"""

    DATABASE_NAME: str = 'TRMDWebRecord'  # 记录库文件名(不含扩展名),保存在会话目录。
    FILE_EXTENSION: str = '.record'  # 记录库文件的扩展名,与telegram的.session会话文件区分。
    TABLE_NAME: str = 'web_records'  # 记录表名。
    COLUMNS: tuple = (
        'record_id',
        'record_type',
        'chat_id',
        'chat_name',
        'message_id',
        'file_name',
        'file_path',
        'file_size',
        'file_type',
        'status',
        'error_msg',
        'link',
        'create_time',
        'finish_time'
    )  # 记录表的全部列,查询按此顺序取值,与建表语句保持一致。
    # language=SQLite
    RECORD_SCHEMA: str = '''
        CREATE TABLE IF NOT EXISTS web_records
        (
            record_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT    NOT NULL,
            chat_id     TEXT,
            chat_name   TEXT,
            message_id  INTEGER,
            file_name   TEXT,
            file_path   TEXT    NOT NULL,
            file_size   INTEGER NOT NULL DEFAULT 0,
            file_type   TEXT,
            status      TEXT,
            error_msg   TEXT,
            link        TEXT,
            create_time INTEGER NOT NULL DEFAULT 0,
            finish_time INTEGER NOT NULL DEFAULT 0
        );
    '''

    def __init__(self, work_directory: str):
        self.name: str = SqliteRecordDatabase.DATABASE_NAME
        self.work_directory: str = work_directory
        self.database: str = os.path.join(
            self.work_directory,
            self.name + self.FILE_EXTENSION
        )
        self._conn: Union[sqlite3.Connection, None] = None

    @property
    def conn(self) -> sqlite3.Connection:
        # 仿照pyrogram:open()之前访问连接直接报错,避免在每个方法里重复判空。
        if self._conn is None:
            msg = '`SqliteRecordDatabase.conn` accessed before `open()`'
            raise RuntimeError(msg)

        return self._conn

    @conn.setter
    def conn(self, value: Union[sqlite3.Connection, None]) -> None:
        self._conn = value

    async def open(self) -> bool:
        """打开记录库并建表;文件损坏时删除重建,避免网页记录功能整体不可用。"""
        try:
            os.makedirs(self.work_directory, exist_ok=True)
        except Exception as e:
            log.error(f'创建会话目录"{self.work_directory}"失败,{_t(KeyWord.REASON)}:"{e}"')
            return False
        recreated: bool = False
        while True:
            try:
                self.conn = sqlite3.connect(self.database, timeout=1, check_same_thread=False)
                self.conn.execute('PRAGMA journal_mode=DELETE')
                await self.create()
                break
            except sqlite3.DatabaseError as e:
                await self.close()
                if recreated:
                    log.error(f'打开网页记录数据库"{self.database}"失败,{_t(KeyWord.REASON)}:"{e}"')
                    return False
                # 记录库文件损坏(如被其它工具改动)时删除重建,重建后仍失败则放弃记录功能。
                recreated = True
                log.warning(f'网页记录数据库"{self.database}"损坏,即将删除重建,{_t(KeyWord.REASON)}:"{e}"')
                safe_delete(self.database)
            except Exception as e:
                log.error(f'打开网页记录数据库失败,{_t(KeyWord.REASON)}:"{e}"')
                await self.close()
                return False
        log.info(f'网页记录数据库已打开:"{self.database}"。')
        return True

    async def close(self) -> None:
        """关闭记录库。"""
        conn: Union[sqlite3.Connection, None] = self._conn
        self._conn = None
        if conn is None:
            return
        try:
            conn.close()
        except Exception as e:
            log.warning(f'关闭网页记录数据库失败,{_t(KeyWord.REASON)}:"{e}"')

    async def create(self) -> None:
        """建表,表已存在时无副作用,重复打开安全。"""
        with self.conn:
            self.conn.executescript(self.RECORD_SCHEMA)

    async def add_record(self, record: WebRecord) -> bool:
        """写入一条记录,成功时回填record_id,未提供时间戳时按当前时间填充。"""
        if not record.file_path:
            log.warning(f'网页记录缺少文件路径,已拒绝写入:"{record.file_name}"。')
            return False
        now: int = int(time.time())
        record.create_time = record.create_time or now
        record.finish_time = record.finish_time or now
        try:
            with self.conn:
                cursor = self.conn.execute(
                    f'INSERT INTO {self.TABLE_NAME} '
                    '(record_type, chat_id, chat_name, message_id, file_name, file_path, '
                    'file_size, file_type, status, error_msg, link, create_time, finish_time) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        record.record_type,
                        str(record.chat_id) if record.chat_id is not None else None,
                        record.chat_name,
                        record.message_id,
                        record.file_name,
                        record.file_path,
                        record.file_size,
                        record.file_type,
                        record.status,
                        record.error_msg,
                        record.link,
                        record.create_time,
                        record.finish_time
                    )
                )
                record.record_id = cursor.lastrowid
            return True
        except Exception as e:
            log.warning(f'写入网页记录失败,{_t(KeyWord.REASON)}:"{e}"')
            return False

    async def remove_record(self, record_id: int) -> bool:
        """按记录ID删除一条记录。"""
        return await self.__remove_records(record_ids=[record_id])

    async def get_records(self, record_type: Union[str, None] = None) -> List[WebRecord]:
        """读取记录,实时校验文件是否还存在,不存在的条目从数据库丢弃。"""
        try:
            query: str = f'SELECT {", ".join(self.COLUMNS)} FROM {self.TABLE_NAME}'
            params: tuple = ()
            if record_type:
                query += ' WHERE record_type = ?'
                params = (record_type,)
            query += ' ORDER BY record_id DESC'
            rows: list = self.conn.execute(query, params).fetchall()
        except Exception as e:
            log.warning(f'读取网页记录失败,{_t(KeyWord.REASON)}:"{e}"')
            return []
        records: List[WebRecord] = [self.__build_record(row) for row in rows]
        return await self.__filter_existing(records)

    async def __remove_records(self, record_ids: List[int]) -> bool:
        """按记录ID批量删除记录,仿照pyrogram处理id列表的占位符写法。"""
        placeholders: str = ', '.join('?' for _ in record_ids)
        try:
            with self.conn:
                self.conn.execute(
                    f'DELETE FROM {self.TABLE_NAME} WHERE record_id IN ({placeholders})',
                    tuple(record_ids)
                )
            return True
        except Exception as e:
            log.warning(f'删除网页记录失败,{_t(KeyWord.REASON)}:"{e}"')
            return False

    @staticmethod
    def __build_record(row: tuple) -> WebRecord:
        """把数据库行转换为记录对象。"""
        data: dict = dict(zip(SqliteRecordDatabase.COLUMNS, row))
        return WebRecord(
            record_type=data.get('record_type') or '',
            chat_id=data.get('chat_id'),
            chat_name=data.get('chat_name') or '',
            message_id=data.get('message_id'),
            file_name=data.get('file_name') or '',
            file_path=data.get('file_path') or '',
            file_size=int(data.get('file_size') or 0),
            file_type=data.get('file_type') or '',
            status=data.get('status') or '',
            error_msg=data.get('error_msg') or '',
            link=data.get('link') or '',
            create_time=int(data.get('create_time') or 0),
            finish_time=int(data.get('finish_time') or 0),
            record_id=data.get('record_id')
        )

    async def __filter_existing(self, records: List[WebRecord]) -> List[WebRecord]:
        """实时校验记录对应的文件是否还存在,不存在的条目从数据库丢弃。"""
        existing: List[WebRecord] = []
        missing_ids: List[int] = []
        for record in records:
            if record.file_path and os.path.isfile(record.file_path):
                existing.append(record)
            else:
                missing_ids.append(record.record_id)
        if missing_ids:
            # 批量删除:整目录被删时可能一次性出现大量失效记录,逐条提交会带来多次fsync。
            await self.__remove_records(record_ids=missing_ids)
            log.info(f'已丢弃{len(missing_ids)}条文件已不存在的网页记录。')
        return existing


def build_record_database(work_directory: str) -> RecordDatabase:
    """构造网页记录数据库。

    Args:
        work_directory: 记录库文件的保存目录,使用telegram的会话目录。

    Returns:
        RecordDatabase: 默认返回基于sqlite3的实现,存储风格仿照pyrogram的SQLiteStorage。
    """
    return SqliteRecordDatabase(work_directory=work_directory)

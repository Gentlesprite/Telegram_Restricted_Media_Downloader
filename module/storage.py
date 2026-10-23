# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026-10-13 12:05:00
# File:storage.py
import os
import time
import sqlite3
import asyncio

from abc import (
    ABC,
    abstractmethod
)
from dataclasses import dataclass
from typing import (
    Union,
    List,
    Dict,
    Tuple
)

from module import log
from module.language import _t
from module.path_tool import safe_delete
from module.enums import (
    DownloadStatus,
    KeyWord
)


class StorageType:
    """数据库记录的类型。"""
    DOWNLOAD: str = 'download'  # 下载记录。
    UPLOAD: str = 'upload'  # 上传记录。


@dataclass
class TRMDStorage:
    """网页面板的下载/上传记录,字段与数据库列一一对应。"""
    storage_type: str = StorageType.DOWNLOAD  # 记录类型,download为下载记录,upload为上传记录。
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
    storage_id: Union[int, None] = None  # 数据库自增ID,写入成功后回填。


class StorageDatabase(ABC):
    """网页下载/上传记录数据库的抽象类。

    后续更换数据库时新增一个实现类并调整build_storage_database的返回值即可,
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
    async def add_storage(self, storage: TRMDStorage) -> bool:
        """写入一条记录。

        Args:
            storage: 待写入的记录,写入成功后回填storage_id。

        Returns:
            bool: 成功返回True;失败只记日志,不影响主流程。
        """
        raise NotImplementedError

    @abstractmethod
    async def get_storages(
            self,
            storage_type: Union[str, None] = None
    ) -> List[TRMDStorage]:
        """读取记录,并按需先做一次文件存在性校验。

        校验由实现内部完成:只stat各父目录,mtime没变的目录不再逐个stat其中的文件,
        阻塞的stat全部放到线程池执行,事件循环不卡;目录极度分散时按内部闸门限流。
        因此读取成本不随记录数线性增长,磁盘IO被压到最低。
        返回全部仍存在的记录;按频道分组的分页由前端完成,故此处不做条数截断。

        Args:
            storage_type: 记录类型,为空时返回全部记录。

        Returns:
            List[TRMDStorage]: 文件仍存在的记录,按写入时间从新到旧排列。
        """
        raise NotImplementedError

    @abstractmethod
    async def update_chat_names(self, chat_names: Dict[str, str]) -> bool:
        """按频道ID批量补全频道标题,返回是否成功。

        读取记录时若ChatInfo缓存已被其他流程补齐,把标题写回库,
        避免写入时缓存未命中的历史记录永远只显示频道ID。

        Args:
            chat_names: 频道ID -> 频道标题,只补全库中标题为空的记录。
        """
        raise NotImplementedError


class SqliteStorageDatabase(StorageDatabase):
    """基于sqlite3的数据库实现,仿照pyrogram的SQLiteStorage组织代码。"""

    STORAGE_NAME: str = 'TRMDStorage'  # 存储库文件名(不含扩展名),保存在会话目录。
    FILE_EXTENSION: str = '.db'  # 记录库文件的扩展名,与telegram的.session会话文件区分。
    TABLE_NAME: str = 'web_storages'  # 记录表名。
    COLUMNS: tuple = (
        'storage_id',
        'storage_type',
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
    STORAGE_SCHEMA: str = '''
        CREATE TABLE IF NOT EXISTS web_storages
        (
            storage_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            storage_type TEXT    NOT NULL,
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
    SWEEP_BATCH_SIZE: int = 500  # 存在性校验的单批文件数,批间通过await让出事件循环。
    SWEEP_TTL: float = 15.0  # 目录极度分散时两次校验的最小间隔,单位为秒。
    SWEEP_TTL_THRESHOLD: int = 200  # 父目录数超过该值时启用SWEEP_TTL限流。
    DIR_CONFIRM_TIMES: int = 2  # 目录级缺失需连续确认几次才丢弃,防止网络盘瞬断误删。
    FULL_CHECK_INTERVAL: float = 1800.0  # 目录mtime没变也至少隔这么久全量校验一次,兜底时间戳粒度问题。
    DELETE_CHUNK_SIZE: int = 900  # 单条DELETE语句的记录ID个数,避开SQLite变量数上限。

    def __init__(self, work_directory: str):
        self.name: str = SqliteStorageDatabase.STORAGE_NAME
        self.work_directory: str = work_directory
        self.storage_path: str = os.path.join(
            self.work_directory,
            self.name + self.FILE_EXTENSION
        )
        self._conn: Union[sqlite3.Connection, None] = None
        self._dir_mtime: Dict[str, float] = {}  # 父目录 -> 上次校验到的mtime,没变则跳过其中的文件。
        self._dir_checked_at: Dict[str, float] = {}  # 父目录 -> 上次全量校验文件的单调时间。
        self._dir_missing: Dict[str, int] = {}  # 父目录 -> 连续确认缺失的次数。
        self._last_sweep_at: float = 0.0  # 上次校验的单调时间,供自适应闸门限流。

    @property
    def conn(self) -> sqlite3.Connection:
        # 仿照pyrogram:open()之前访问连接直接报错,避免在每个方法里重复判空。
        if self._conn is None:
            msg = '`SqliteStorageDatabase.conn` accessed before `open()`'
            raise RuntimeError(msg)

        return self._conn

    @conn.setter
    def conn(self, value: Union[sqlite3.Connection, None]) -> None:
        self._conn = value

    async def open(self) -> bool:
        """打开记录库并建表;文件损坏时删除重建,避免数据库功能整体不可用。"""
        try:
            os.makedirs(self.work_directory, exist_ok=True)
        except Exception as e:
            log.error(f'创建会话目录"{self.work_directory}"失败,{_t(KeyWord.REASON)}:"{e}"')
            return False
        recreated: bool = False
        while True:
            try:
                self.conn = sqlite3.connect(self.storage_path, timeout=1, check_same_thread=False)
                self.conn.execute('PRAGMA journal_mode=DELETE')
                await self.create()
                break
            except sqlite3.DatabaseError as e:
                await self.close()
                if recreated:
                    log.error(f'打开数据库"{self.storage_path}"失败,{_t(KeyWord.REASON)}:"{e}"')
                    return False
                # 记录库文件损坏(如被其它工具改动)时删除重建,重建后仍失败则放弃记录功能。
                recreated = True
                log.warning(f'数据库"{self.storage_path}"损坏,即将删除重建,{_t(KeyWord.REASON)}:"{e}"')
                safe_delete(self.storage_path)
            except Exception as e:
                log.error(f'打开数据库失败,{_t(KeyWord.REASON)}:"{e}"')
                await self.close()
                return False
        log.info(f'数据库路径:"{self.storage_path}"。')
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
            log.warning(f'关闭数据库失败,{_t(KeyWord.REASON)}:"{e}"')

    async def create(self) -> None:
        """建表,表已存在时无副作用,重复打开安全。"""
        with self.conn:
            self.conn.executescript(self.STORAGE_SCHEMA)

    async def add_storage(self, storage: TRMDStorage) -> bool:
        """写入一条记录,成功时回填storage_id,未提供时间戳时按当前时间填充。

        同一文件(记录类型+文件路径)只保留一条:重复下载、重试成功或重新扫描时
        更新原记录而不是再插一行,避免记录表出现同一文件多条重复条目。
        """
        if not storage.file_path:
            log.warning(f'数据库缺少文件路径,已拒绝写入:"{storage.file_name}"。')
            return False
        now: int = int(time.time())
        storage.create_time = storage.create_time or now
        storage.finish_time = storage.finish_time or now
        try:
            with self.conn:
                cursor = self.conn.execute(
                    f'SELECT storage_id, status FROM {self.TABLE_NAME} '
                    'WHERE storage_type = ? AND file_path = ? '
                    'ORDER BY storage_id DESC LIMIT 1',
                    (
                        storage.storage_type,
                        storage.file_path
                    )
                )
                row: Union[tuple, None] = cursor.fetchone()
                if row is not None:
                    storage.storage_id = row[0]
                    # 已有同文件记录时只做更新:状态实质变化(如失败后重试成功)才改写状态;
                    # 状态相同、或因文件已存在而跳过(skip)时不动原记录,
                    # 避免重新扫描把成功记录降级或改写历史时间。
                    if storage.status != DownloadStatus.SKIP and row[1] != storage.status:
                        self.conn.execute(
                            f'UPDATE {self.TABLE_NAME} '
                            'SET status = ?, error_msg = ?, finish_time = ? WHERE storage_id = ?',
                            (
                                storage.status,
                                storage.error_msg,
                                storage.finish_time,
                                storage.storage_id
                            )
                        )
                    return True
                cursor = self.conn.execute(
                    f'INSERT INTO {self.TABLE_NAME} '
                    '(storage_type, chat_id, chat_name, message_id, file_name, file_path, '
                    'file_size, file_type, status, error_msg, link, create_time, finish_time) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        storage.storage_type,
                        str(storage.chat_id) if storage.chat_id is not None else None,
                        storage.chat_name,
                        storage.message_id,
                        storage.file_name,
                        storage.file_path,
                        storage.file_size,
                        storage.file_type,
                        storage.status,
                        storage.error_msg,
                        storage.link,
                        storage.create_time,
                        storage.finish_time
                    )
                )
                storage.storage_id = cursor.lastrowid
            return True
        except Exception as e:
            log.warning(f'写入数据库失败,{_t(KeyWord.REASON)}:"{e}"')
            return False

    async def get_storages(
            self,
            storage_type: Union[str, None] = None
    ) -> List[TRMDStorage]:
        """读取记录,先按需做一次存在性校验,保证返回的是校验后的结果。

        返回全部仍存在的记录;分页与按频道分组由前端完成,故此处不截断。
        """
        await self.__sweep_missing()
        try:
            query: str = f'SELECT {", ".join(self.COLUMNS)} FROM {self.TABLE_NAME}'
            params: tuple = ()
            if storage_type:
                query += ' WHERE storage_type = ?'
                params = (storage_type,)
            query += ' ORDER BY storage_id DESC'
            rows: list = self.conn.execute(query, params).fetchall()
        except Exception as e:
            log.warning(f'读取数据库失败,{_t(KeyWord.REASON)}:"{e}"')
            return []
        return [self.__build_storage(row) for row in rows]

    async def __sweep_missing(self) -> int:
        """校验记录对应的文件是否还存在,丢弃失效记录,返回丢弃条数。

        目录mtime捷径:文件的增删与改名必然更新父目录mtime,故每次只stat各父目录,
        mtime没变的目录不再逐个stat其中的文件;阻塞的stat全部放到线程池执行。
        目录极度分散(父目录数超过阈值)时按SWEEP_TTL限流,避免退化到逐文件校验过频。
        """
        if self._conn is None:
            return 0
        try:
            rows: List[tuple] = self.conn.execute(
                f'SELECT storage_id, file_path FROM {self.TABLE_NAME}'
            ).fetchall()
        except Exception as e:
            log.warning(f'读取数据库失败,{_t(KeyWord.REASON)}:"{e}"')
            return 0
        dirs: Dict[str, List[tuple]] = {}  # 父目录 -> [(storage_id, file_path), ...]
        missing_ids: List[int] = []  # 直接判定失效的记录ID(没有路径的记录本就不该存在)。
        for storage_id, file_path in rows:
            if not file_path:
                missing_ids.append(storage_id)
                continue
            dirs.setdefault(os.path.dirname(file_path), []).append((storage_id, file_path))
        # 自适应闸门:目录少时每次读取都校验(成本仅各目录一次stat);目录极度分散时限流。
        if len(dirs) > self.SWEEP_TTL_THRESHOLD:
            if time.monotonic() - self._last_sweep_at < self.SWEEP_TTL:
                return 0
        self._last_sweep_at = time.monotonic()
        loop = asyncio.get_running_loop()
        for parent, items in dirs.items():
            stat_result: Union[Tuple[float, bool], None] = await loop.run_in_executor(
                None, self.__stat_dir, parent)
            if stat_result is None:
                # 目录级缺失不当场删:连续确认DIR_CONFIRM_TIMES次才丢弃,防网络盘瞬断误删。
                confirmed: int = self._dir_missing.get(parent, 0) + 1
                if confirmed >= self.DIR_CONFIRM_TIMES:
                    self._dir_missing.pop(parent, None)
                    self._dir_mtime.pop(parent, None)
                    self._dir_checked_at.pop(parent, None)
                    missing_ids.extend(storage_id for storage_id, _ in items)
                else:
                    self._dir_missing[parent] = confirmed
                continue
            self._dir_missing.pop(parent, None)
            mtime, full_check_due = stat_result
            if not full_check_due and self._dir_mtime.get(parent) == mtime:
                continue  # 目录没变过,其中的文件无需逐个校验。
            self._dir_mtime[parent] = mtime
            self._dir_checked_at[parent] = time.monotonic()
            # 目录变过(或到了全量校验时间):分批校验其中的文件,批间让出事件循环。
            for start in range(0, len(items), self.SWEEP_BATCH_SIZE):
                batch: List[tuple] = items[start:start + self.SWEEP_BATCH_SIZE]
                missing_ids.extend(
                    await loop.run_in_executor(None, self.__stat_files, batch)
                )
        if missing_ids:
            self.__remove_storages(storage_ids=missing_ids)
            log.info(f'已丢弃{len(missing_ids)}条文件已不存在的数据记录。')
        return len(missing_ids)

    def __stat_dir(self, parent: str) -> Union[Tuple[float, bool], None]:
        """stat父目录,返回(mtime, 是否到了全量校验时间);目录不可访问时返回None。"""
        try:
            mtime: float = os.stat(parent).st_mtime
        except OSError:
            return None
        checked_at: float = self._dir_checked_at.get(parent, 0.0)
        due: bool = (time.monotonic() - checked_at) >= self.FULL_CHECK_INTERVAL
        return mtime, due

    @staticmethod
    def __stat_files(batch: List[tuple]) -> List[int]:
        """批量校验文件是否存在,返回其中不存在的记录ID。"""
        return [storage_id for storage_id, file_path in batch if not os.path.isfile(file_path)]

    async def update_chat_names(self, chat_names: Dict[str, str]) -> bool:
        """按频道ID批量补全频道标题,只补全库中标题为空的记录,已有标题不被覆盖。"""
        if not chat_names:
            return True
        try:
            with self.conn:
                self.conn.executemany(
                    f'UPDATE {self.TABLE_NAME} SET chat_name = ? '
                    f'WHERE chat_id = ? AND (chat_name IS NULL OR chat_name = \'\')',
                    [(title, chat_id) for chat_id, title in chat_names.items()]
                )
            return True
        except Exception as e:
            log.warning(f'在数据库中补全频道标题失败,{_t(KeyWord.REASON)}:"{e}"')
            return False

    def __remove_storages(self, storage_ids: List[int]) -> bool:
        """按记录ID批量删除记录,按块切分以避开SQLite的变量数上限。"""
        try:
            for start in range(0, len(storage_ids), self.DELETE_CHUNK_SIZE):
                chunk: List[int] = storage_ids[start:start + self.DELETE_CHUNK_SIZE]
                placeholders: str = ', '.join('?' for _ in chunk)
                with self.conn:
                    self.conn.execute(
                        f'DELETE FROM {self.TABLE_NAME} WHERE storage_id IN ({placeholders})',
                        tuple(chunk)
                    )
            return True
        except Exception as e:
            log.warning(f'删除数据库记录失败,{_t(KeyWord.REASON)}:"{e}"')
            return False

    @staticmethod
    def __build_storage(row: tuple) -> TRMDStorage:
        """把数据库行转换为记录对象。"""
        data: dict = dict(zip(SqliteStorageDatabase.COLUMNS, row))
        return TRMDStorage(
            storage_type=data.get('storage_type') or '',
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
            storage_id=data.get('storage_id')
        )


def build_storage_database(work_directory: str) -> StorageDatabase:
    """构造数据库。

    Args:
        work_directory: 记录库文件的保存目录,使用telegram的会话目录。

    Returns:
        StorageDatabase: 默认返回基于sqlite3的实现,存储风格仿照pyrogram的SQLiteStorage。
    """
    return SqliteStorageDatabase(work_directory=work_directory)

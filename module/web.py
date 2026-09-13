# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/9/10 12:00
# File:web.py
import os
import sys
import json
import base64
import socket
import mimetypes
import threading

from typing import Union
from urllib.parse import unquote
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer
)

from module import log
from module.stdio import (
    MetaData,
    PanelTable
)
from module.path_tool import split_path
from module.task import (
    DownloadTask,
    UploadTask,
    ChatInfo
)
from module.language import _t
from module.parser import PARSE_ARGS
from module.util import (
    is_frozen,
    gen_random_credential,
    get_work_directory,
    get_message_dtype
)
from module.enums import (
    WebMeta,
    KeyWord,
    QueueStatus,
    UploadStatus,
    DownloadStatus
)


class WebHandler(BaseHTTPRequestHandler):
    """处理网页面板的请求。"""
    server_version: str = 'TRMDWeb'

    def do_GET(self) -> None:
        if self.__check_auth() is False:
            return
        if self.path.startswith('/api/progress'):
            self.__response_progress()
        else:
            self.__response_static()

    def log_message(self, fmt, *args) -> None:
        """屏蔽默认的请求日志,避免污染终端输出。"""

    def __check_auth(self) -> bool:
        """校验Basic认证。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        if web is None or not web.username:
            return True
        authorization: str = self.headers.get('Authorization', '')
        if not authorization.startswith('Basic '):
            self.__response_unauthorized()
            return False
        try:
            credential: str = base64.b64decode(authorization.split(' ', 1)[1]).decode('UTF-8')
        except Exception:
            self.__response_unauthorized()
            return False
        if credential != f'{web.username}:{web.password}':
            self.__response_unauthorized()
            return False
        return True

    def __response_unauthorized(self) -> None:
        """返回需要认证的响应。"""
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="TRMD"')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def __response_body(self, body: bytes, content_type: str) -> None:
        """返回指定内容的响应。"""
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')  # 禁用缓存,避免浏览器沿用旧页面。
        self.end_headers()
        self.wfile.write(body)

    def __response_progress(self) -> None:
        """返回进度数据的JSON。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        data: dict = web.snapshot() if web else {}
        self.__response_body(
            body=json.dumps(data, ensure_ascii=False).encode('UTF-8'),
            content_type='application/json; charset=utf-8'
        )

    def __response_static(self) -> None:
        """返回网页模板与静态目录下的文件。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        if web is None:
            self.send_error(404)
            return
        name: str = unquote(self.path.split('?')[0].lstrip('/'))
        if not name or name in Web.TEMPLATE_FILES:  # 根路径返回首页,登记的模板名称从模板目录取。
            root: str = os.path.abspath(web.template_directory)
            file_path: str = os.path.join(root, name or Web.INDEX_FILE)
        else:
            root = os.path.abspath(web.static_directory)
            file_path = os.path.abspath(os.path.join(root, name))
        if os.path.commonpath([root, file_path]) != root:  # 禁止访问网页目录之外的文件。
            self.send_error(403)
            return
        if not os.path.isfile(file_path):
            self.send_error(404)
            return
        try:
            with open(file=file_path, mode='rb') as f:
                body: bytes = f.read()
        except OSError as e:
            log.warning(f'读取网页文件"{file_path}"失败,{_t(KeyWord.REASON)}:"{e}"')
            self.send_error(404)
            return
        content_type: str = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        if content_type.startswith('text/'):
            content_type: str = f'{content_type}; charset=utf-8'
        self.__response_body(body=body, content_type=content_type)


class Web:
    # 网页面板资源的目录约定。
    # templates:存放HTML页面,新增页面时需在此登记模板名称以便路由。
    # static:存放静态资源,按类型分子目录(css、js、img、fonts、vendor),
    # 页面里用相对于站点根的路径引用,如"css/style.css"。
    TEMPLATE_DIRECTORY: str = os.path.join('module', 'templates')
    STATIC_DIRECTORY: str = os.path.join('module', 'static')
    INDEX_FILE: str = 'index.html'
    TEMPLATE_FILES: tuple = ('index.html',)  # 模板目录提供的页面,其余请求一律按静态资源处理。
    UNGROUPED: str = '未分组'
    UNFINISHED_STATE: tuple = (
        QueueStatus.PENDING,
        QueueStatus.WAITING,
        QueueStatus.DOWNLOADING,
        QueueStatus.CANCELLED
    )  # 尚未出结果的消息状态。

    def __init__(self, progress, app=None):
        self.progress = progress
        self.app = app
        self.credential: dict = gen_random_credential()
        self.protocol: str = 'http'
        self.ip: str = '0.0.0.0'
        self.port: int = self.get_free_port(PARSE_ARGS.web)
        self.username: str = self.credential.get(WebMeta.USERNAME)
        self.password: str = self.credential.get(WebMeta.PASSWORD)
        self.template_directory, self.static_directory = self.get_web_directory()
        self.server: Union[ThreadingHTTPServer, None] = None
        self.thread: Union[threading.Thread, None] = None

    @staticmethod
    def __bind_port(port: int) -> int:
        """绑定指定端口,返回实际占用的端口。"""
        # 不设置SO_REUSEADDR,否则Windows下会绑到已被占用的端口,导致连接被其它进程接管。
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
            return s.getsockname()[1]

    @staticmethod
    def get_free_port(port: int) -> int:
        """获取可用端口,指定端口被占用时自动分配。"""
        try:
            return Web.__bind_port(port)
        except OSError as e:
            log.warning(f'无法使用{port}端口,已自动分配新的端口,{_t(KeyWord.REASON)}:"{e}"')
            return Web.__bind_port(0)

    @staticmethod
    def get_web_directory() -> tuple:
        """获取网页模板目录与静态资源目录,打包环境取资源解压目录。"""
        base_directory: str = get_work_directory()
        if is_frozen():
            base_directory = getattr(sys, '_MEIPASS', sys.prefix)
        template_directory: str = os.path.join(base_directory, Web.TEMPLATE_DIRECTORY)
        static_directory: str = os.path.join(base_directory, Web.STATIC_DIRECTORY)
        log.info(f'获取网页模板目录:"{template_directory}",静态资源目录:"{static_directory}"。')
        return template_directory, static_directory

    @staticmethod
    def format_seconds(seconds: Union[int, float, None]) -> str:
        """将秒数格式化为易于阅读的剩余时间。"""
        if seconds is None:
            return ''
        seconds: int = int(seconds)
        if seconds < 60:
            return f'{seconds}秒'
        if seconds < 3600:
            return f'{seconds // 60}分{seconds % 60}秒'
        return f'{seconds // 3600}时{seconds % 3600 // 60}分{seconds % 60}秒'

    def start(self) -> bool:
        """在后台线程启动网页面板。"""
        for directory in (self.template_directory, self.static_directory):
            if not os.path.isdir(directory):
                log.error(f'网页面板启动失败,未找到网页目录:"{directory}"。')
                return False
        try:
            self.server = ThreadingHTTPServer((self.ip, self.port), WebHandler)
        except OSError as e:
            log.error(f'网页面板启动失败,{_t(KeyWord.REASON)}:"{e}"')
            return False
        self.server.web = self
        self.thread = threading.Thread(target=self.server.serve_forever, name='TRMDWeb', daemon=True)
        self.thread.start()
        log.info(f'网页面板已启动,访问链接:"{self.protocol}://127.0.0.1:{self.port}"。')
        self.print_meta()
        return True

    def stop(self) -> None:
        """停止网页面板。"""
        if self.server is None:
            return
        self.server.shutdown()
        self.server.server_close()
        log.info('网页面板已停止。')

    def print_meta(self) -> None:
        """打印网页面板的访问信息。"""
        PanelTable(
            title='Web配置',
            header=('属性', '内容'),
            data=[
                [_t(WebMeta.PORT), self.port],
                [_t(WebMeta.USERNAME), self.username],
                [_t(WebMeta.PASSWORD), self.password],
                ['访问链接', f'{self.protocol}://127.0.0.1:{self.port}']
            ],
            show_lines=True
        ).print_meta()

    def get_count(self) -> dict:
        """聚合下载任务的成功、失败、跳过数量。"""
        count: dict = {'success': 0, 'failure': 0, 'skip': 0}
        if self.app is None:
            return count
        for name, value in list(vars(self.app).items()):
            if not isinstance(value, set):
                continue
            if name.startswith('success_'):
                count['success'] += len(value)
            elif name.startswith('failure_'):
                count['failure'] += len(value)
            elif name.startswith('skip_'):
                count['skip'] += len(value)
        return count

    def get_link_progress(self) -> list:
        """获取每个下载链接的进度与该链接下所有消息成员(含已完成、跳过、失败)。"""
        result: list = []
        try:
            for link, task in list(DownloadTask.TASKS.items()):
                member_num: int = int(task.member_num or 0)
                complete_num: int = int(task.complete_num or 0)
                fail_num: int = int(task.fail_num or 0)
                members: list = self.get_members(task=task)
                unfinished: int = len(
                    [i for i in members if i.get('state') in Web.UNFINISHED_STATE]
                )
                result.append({
                    'link': str(link),
                    'channel': str(task.chat_id or ''),
                    'channel_name': Web.format_channel(str(task.chat_id or '')),
                    'complete': complete_num,
                    'member': member_num,
                    'failed': fail_num,
                    'remaining': max(member_num - complete_num - fail_num, 0),
                    'queue': members,
                    'queue_total': unfinished,
                    'total': len(members),
                    'percent': round(complete_num / member_num * 100, 1) if member_num else 0.0
                })
        except Exception as e:
            log.debug(f'获取链接进度时出错,{_t(KeyWord.REASON)}:"{e}"')
        return result

    def get_members(self, task: DownloadTask) -> list:
        """获取链接下所有消息成员的展示信息。

        仍在队列中的消息可以取到原始消息,用于补全文件名与大小;
        已完成或失败的消息已被移出队列,使用登记时保存的信息。
        """
        result: list = []
        for message_id, member in list(task.member_info.items()):
            item: dict = task.items.get(message_id) or {}
            meta: dict = self.format_queue_message(item, member.get('state')) if item else {}
            result.append({
                'name': member.get('name') or meta.get('name') or f'消息 {message_id}',
                'size': member.get('size') or meta.get('size') or '',
                'size_byte': int(member.get('size_byte') or 0),
                'date': member.get('date') or meta.get('date') or '',
                'state': member.get('state') or QueueStatus.PENDING,
                'task_id': member.get('task_id')
            })
        return result

    def format_queue_message(self, item: dict, state: Union[str, None] = None) -> dict:
        """解析排队消息的展示信息,首次解析后缓存,避免每次轮询重复解析。"""
        meta: Union[dict, None] = item.get('meta')
        if meta is None:
            meta = self.parse_queue_message(item)
            item['meta'] = meta
        meta['state'] = str(state or '')  # 排队状态会变化,不写入缓存。
        return meta

    def parse_queue_message(self, item: dict) -> dict:
        """解析排队消息的名称、大小与日期。"""
        message = item.get('message')
        result: dict = {'name': '消息 ' + str(getattr(message, 'id', '')), 'size': '', 'date': ''}
        try:
            result['date'] = str(getattr(message, 'date', '') or '')[:10]
            if self.app is None:
                return result
            dtype: Union[str, None] = get_message_dtype(message, self.app.download_type)
            if dtype:
                result['name'] = str(split_path(self.app.get_temp_file_path(message, dtype)).get('file_name'))
                result['size'] = MetaData.suitable_units_display(getattr(getattr(message, dtype), 'file_size', 0))
        except Exception as e:
            log.debug(f'解析排队消息时出错,{_t(KeyWord.REASON)}:"{e}"')
        return result

    def get_upload_tasks(self, tasks: Union[list, None] = None) -> list:
        """获取上传任务的概要信息,并按进度条任务ID补全上传进度。"""
        result: list = []
        live: dict = {}
        for item in tasks if tasks is not None else self.get_tasks():
            live[item.get('id')] = item
        try:
            for task in list(UploadTask.TASKS):
                status = getattr(task.status, 'value', task.status)
                done: bool = status in (UploadStatus.SUCCESS, UploadStatus.SENT)
                progress: dict = live.get(getattr(task, 'task_id', None)) or {}
                size: str = MetaData.suitable_units_display(task.file_size)
                info: str = progress.get('info', '')
                if not info and done:
                    info = f'{size}/{size}'  # 进度条任务已在完成时移除,用文件自身大小回填。
                result.append({
                    'file': task.file_name,
                    'path': task.file_path,
                    'chat': Web.format_channel(str(task.chat_id)) if task.chat_id else Web.UNGROUPED,
                    'channel': str(task.chat_id) if task.chat_id else Web.UNGROUPED,
                    'size': size,
                    'size_byte': int(task.file_size),
                    'status': _t(str(status)),
                    'state': str(status),  # 原始状态,供网页面板区分上传中、已完成、失败。
                    'task_id': getattr(task, 'task_id', None),
                    'completed': progress.get('completed', task.file_size if done else 0),
                    'percent': progress.get('percent', 100.0 if done else 0.0),
                    'info': info,
                    'speed': progress.get('speed', ''),
                    'speed_value': progress.get('speed_value', 0),
                    'remaining': progress.get('remaining', ''),
                    'error': task.error_msg if task.error_msg else ''
                })
        except Exception as e:
            log.debug(f'获取上传任务时出错,{_t(KeyWord.REASON)}:"{e}"')
        return result

    @staticmethod
    def get_summary(links: list, tasks: list) -> dict:
        """汇总所有任务的总体进度。

        总量取所有链接成员的大小之和(包含排队、已完成、跳过、失败),
        而不是只统计正在下载的任务,避免总进度随着任务开始下载而不断变大。

        Args:
            links: get_link_progress返回的链接进度。
            tasks: 进度条中正在下载的任务。

        Returns:
            dict: 总体进度。
        """
        live: dict = {task.get('id'): task for task in tasks}
        completed: int = 0
        total: int = 0
        speed: float = 0.0
        for link in links:
            for member in link.get('queue') or []:
                size: int = int(member.get('size_byte') or 0)
                total += size
                state: str = str(member.get('state') or '')
                if state in (DownloadStatus.SUCCESS, DownloadStatus.SKIP):
                    completed += size
                    continue
                if state == QueueStatus.DOWNLOADING:
                    completed += int(live.get(member.get('task_id'), {}).get('completed') or 0)
        for task in tasks:
            speed += task.get('speed_value', 0)
        remaining: Union[float, None] = None
        if speed and total > completed:
            remaining: Union[float, None] = (total - completed) / speed
        return {
            'completed': completed,
            'total': total,
            'percent': round(completed / total * 100, 1) if total else 0.0,
            'info': f'{MetaData.suitable_units_display(completed)}/{MetaData.suitable_units_display(total)}',
            'speed': f'{MetaData.suitable_units_display(speed)}/s' if speed else '',
            'remaining': Web.format_seconds(remaining)
        }

    @staticmethod
    def format_channel(channel: str) -> str:
        """格式化频道的显示名称,有标题时显示为"标题(ID)"。"""
        if not channel or channel == Web.UNGROUPED:
            return Web.UNGROUPED
        title: str = ChatInfo.get(channel)
        return f'{title}({channel})' if title else channel

    def get_tasks(self) -> list:
        """读取进度条中正在下载的任务。"""
        tasks: list = []
        for task in self.progress.tasks:
            item: dict = {
                'id': task.id,
                'type': str(task.description),
                'channel': str(task.fields.get('channel', '')) or Web.UNGROUPED,
                'channel_name': Web.format_channel(str(task.fields.get('channel', ''))),
                'filename': str(task.fields.get('filename', '')),
                'info': str(task.fields.get('info', '')),
                'completed': int(task.completed),
                'total': int(task.total) if task.total else 0,
                'percent': round(task.percentage, 1),
                'speed': f'{MetaData.suitable_units_display(task.speed)}/s' if task.speed else '',
                'speed_value': task.speed if task.speed else 0,
                'remaining': self.format_seconds(task.time_remaining)
            }
            tasks.append(item)
        return tasks

    def snapshot(self) -> dict:
        """生成供网页面板展示的进度数据。"""
        try:
            all_tasks: list = self.get_tasks()
            uploads: list = self.get_upload_tasks(tasks=all_tasks)
            upload_ids: set = {item.get('task_id') for item in uploads if item.get('task_id') is not None}
            tasks: list = [item for item in all_tasks if item.get('id') not in upload_ids]  # 上传进度条任务不纳入下载统计。
            links: list = self.get_link_progress()
            return {
                'count': self.get_count(),
                'summary': self.get_summary(links=links, tasks=tasks),
                'queue': sum(link.get('remaining', 0) for link in links),  # 所有链接待下载的消息总数。
                'tasks': tasks,
                'links': links,
                'uploads': uploads
            }
        except Exception as e:
            log.debug(f'生成进度数据时出错,{_t(KeyWord.REASON)}:"{e}"')
            return {
                'count': {'success': 0, 'failure': 0, 'skip': 0},
                'summary': self.get_summary(links=[], tasks=[]),
                'queue': 0,
                'tasks': [],
                'links': [],
                'uploads': []
            }

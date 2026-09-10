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
    get_work_directory
)
from module.enums import (
    WebMeta,
    KeyWord
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
        """返回网页目录下的静态文件。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        if web is None:
            self.send_error(404)
            return
        root: str = os.path.abspath(web.web_directory)
        name: str = unquote(self.path.split('?')[0].lstrip('/'))
        file_path: str = os.path.abspath(os.path.join(root, name or Web.INDEX_FILE))
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
    WEB_DIRECTORY: str = os.path.join('res', 'web')
    INDEX_FILE: str = 'index.html'
    MAX_DONE_TASK: int = 20
    UNGROUPED: str = '未分组'

    def __init__(self, progress, app=None):
        self.progress = progress
        self.app = app
        self.credential: dict = gen_random_credential()
        self.protocol: str = 'http'
        self.ip: str = '0.0.0.0'
        self.port: int = self.get_free_port(PARSE_ARGS.web)
        self.username: str = self.credential.get(WebMeta.USERNAME)
        self.password: str = self.credential.get(WebMeta.PASSWORD)
        self.web_directory: str = self.get_web_directory()
        self.server: Union[ThreadingHTTPServer, None] = None
        self.thread: Union[threading.Thread, None] = None
        self.last_tasks: dict = {}
        self.done_tasks: list = []

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
    def get_web_directory() -> str:
        """获取网页静态资源的目录,打包环境取资源解压目录。"""
        if is_frozen():
            resource_directory: str = getattr(sys, '_MEIPASS', sys.prefix)
            path: str = os.path.join(resource_directory, Web.WEB_DIRECTORY)
            log.info(f'在打包环境获取网页目录:"{path}"。')
            return path
        path: str = os.path.join(get_work_directory(), Web.WEB_DIRECTORY)
        log.info(f'在生产环境获取网页目录:"{path}"。')
        return path

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
        if not os.path.isdir(self.web_directory):
            log.error(f'网页面板启动失败,未找到网页目录:"{self.web_directory}"。')
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
        """获取每个下载链接的完成进度。"""
        result: list = []
        try:
            for link, info in list(DownloadTask.LINK_INFO.items()):
                member_num: int = int(info.get('member_num') or 0)
                complete_num: int = int(info.get('complete_num') or 0)
                result.append({
                    'link': str(link),
                    'complete': complete_num,
                    'member': member_num,
                    'percent': round(complete_num / member_num * 100, 1) if member_num else 0.0
                })
        except Exception as e:
            log.debug(f'获取链接进度时出错,{_t(KeyWord.REASON)}:"{e}"')
        return result

    def get_upload_tasks(self) -> list:
        """获取上传任务的概要信息。"""
        result: list = []
        try:
            for task in list(UploadTask.TASKS):
                status = getattr(task.status, 'value', task.status)
                result.append({
                    'file': task.file_name,
                    'chat': Web.format_channel(str(task.chat_id)) if task.chat_id else '',
                    'size': MetaData.suitable_units_display(task.file_size),
                    'status': _t(str(status)),
                    'error': task.error_msg if task.error_msg else ''
                })
        except Exception as e:
            log.debug(f'获取上传任务时出错,{_t(KeyWord.REASON)}:"{e}"')
        return result

    @staticmethod
    def get_summary(tasks: list) -> dict:
        """汇总所有进行中任务的总体进度。"""
        completed: int = 0
        total: int = 0
        speed: float = 0.0
        for task in tasks:
            completed += task.get('completed', 0)
            total += task.get('total', 0)
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

    @staticmethod
    def get_groups(tasks: list) -> list:
        """按频道对任务分组,并汇总每组的进度。"""
        groups: dict = {}
        order: list = []
        for task in tasks:
            channel: str = task.get('channel') or Web.UNGROUPED
            if channel not in groups:
                groups[channel] = []
                order.append(channel)  # 保持频道首次出现的顺序。
            groups[channel].append(task)
        result: list = []
        for channel in order:
            group_tasks: list = groups[channel]
            result.append({
                'channel': channel,
                'name': Web.format_channel(channel),
                'count': len(group_tasks),
                'summary': Web.get_summary(group_tasks),
                'tasks': group_tasks
            })
        return result

    def get_tasks(self) -> list:
        """读取进度条的任务,并将已移除的完成任务转入完成记录。"""
        tasks: list = []
        current: dict = {}
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
            current[task.id] = item
            tasks.append(item)
        for task_id, item in self.last_tasks.items():
            if task_id not in current and item.get('percent', 0) >= 100:
                self.done_tasks.append(item)
        self.done_tasks = self.done_tasks[-Web.MAX_DONE_TASK:]
        self.last_tasks = current
        return tasks

    def snapshot(self) -> dict:
        """生成供网页面板展示的进度数据。"""
        try:
            tasks: list = self.get_tasks()
            return {
                'count': self.get_count(),
                'summary': self.get_summary(tasks),
                'groups': self.get_groups(tasks),
                'tasks': tasks,
                'done': list(reversed(self.done_tasks)),
                'links': self.get_link_progress(),
                'uploads': self.get_upload_tasks()
            }
        except Exception as e:
            log.debug(f'生成进度数据时出错,{_t(KeyWord.REASON)}:"{e}"')
            return {
                'count': {'success': 0, 'failure': 0, 'skip': 0},
                'summary': self.get_summary([]),
                'groups': [],
                'tasks': [],
                'done': [],
                'links': [],
                'uploads': []
            }

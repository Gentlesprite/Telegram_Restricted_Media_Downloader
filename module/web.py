# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/9/10 12:00
# File:web.py
import os
import re
import sys
import json
import time
import copy
import base64
import shutil
import socket
import asyncio
import datetime
import mimetypes
import threading

from typing import Union
from asyncio import AbstractEventLoop
from urllib.parse import (
    unquote,
    urlparse,
    parse_qs
)
from http.server import (
    ThreadingHTTPServer,
    BaseHTTPRequestHandler
)

from pyrogram import __version__ as pyrogram_version  # noqa.

from module import (
    log,
    console,
    VERSION_WITH_COMMIT
)
from module.remote import rc
from module.language import _t
from module.parser import PARSE_ARGS
from module.path_tool import split_path
from module.storage import TRMDStorage
from module.stdio import (
    MetaData,
    PanelTable
)
from module.task import (
    UploadTask,
    DownloadTask
)
from module.util import (
    ChatInfo,
    is_frozen,
    is_docker,
    get_local_ip,
    parse_chat_id,
    get_web_session,
    reset_web_session,
    get_message_dtype,
    get_work_directory,
    gen_random_credential
)
from module.enums import (
    Issues,
    WebMeta,
    KeyWord,
    UploadStatus,
    DownloadStatus,
    SaveDirectoryPrefix
)


class WebHandler(BaseHTTPRequestHandler):
    """处理网页面板的请求。"""
    server_version: str = 'TRMDWeb'
    remember_session: bool = False  # 本次响应是否需要下发Cookie。
    expire_session: bool = False  # 本次响应是否需要清除Cookie(退出登录)。
    first_login: bool = False  # 本次请求是否属于未携带有效Cookie的首次登录。
    # 首页<body>起始标签,用正则匹配,模板给<body>新增属性后替换依然生效。
    BODY_TAG_PATTERN: bytes = rb'<body\b[^>]*>'
    # data-auth 表示已启用密码认证,前端据此显示"退出登录"入口。
    FIRST_LOGIN_BODY: bytes = b'<body data-auth="1" data-first-login="1" data-bot="__HAS_BOT__" data-storage="__HAS_STORAGE__">'  # 首次登录时写入首页的标记,供页面自动展示卡片。
    # 已设置账号密码时注入:首屏先隐藏页面内容,避免F5刷新时闪现一瞬间的已登录界面。
    LOGIN_BODY: bytes = b'<body data-auth="1" class="logged-out" data-bot="__HAS_BOT__" data-storage="__HAS_STORAGE__">'
    VERSION_PLACEHOLDER: bytes = b'__VERSION__'  # 首页模板中的TRMD版本占位符,返回页面时替换为实际版本号。
    # 首页模板中的Pyrogram版本占位符,返回页面时替换为实际版本号。
    PYROGRAM_PLACEHOLDER: bytes = b'__PYROGRAM_VERSION__'
    HAS_BOT_PLACEHOLDER: bytes = b'__HAS_BOT__'  # 是否配置了机器人(bot_token),前端据此隐藏上传与监听侧边栏。
    HAS_STORAGE_PLACEHOLDER: bytes = b'__HAS_STORAGE__'  # 记录数据库是否可用,前端据此展示记录侧边栏。

    def do_GET(self) -> None:  # noqa.
        if self.path.startswith('/api/'):
            # 接口需要认证;页面与静态资源放行,否则登录卡片自身无法加载。
            if self.__check_auth() is False:  # noqa.
                return
            if self.path.startswith('/api/progress'):
                self.__response_progress()
            elif self.path.startswith('/api/storage/disk'):
                self.__response_disk_usage()
            elif self.path.startswith('/api/storage'):
                self.__response_storages()
            else:
                self.send_error(404)
            return
        self.__response_static()

    def do_POST(self) -> None:  # noqa.
        if self.path.startswith('/api/login'):
            self.__response_login()  # 登录接口本身不能被认证拦截。
            return
        if self.path.startswith('/api/logout'):
            self.__response_logout()  # 退出登录同样不能被认证拦截。
            return
        if self.__check_auth() is False:  # noqa.
            return
        if self.path.startswith('/api/listener/remove'):
            self.__response_remove_listener()
        elif (self.path.startswith('/api/config/save_directory')
              or self.path.startswith('/api/config/max_tasks')
              or self.path.startswith('/api/config/max_retries')):
            self.__response_set_config()
        elif self.path.startswith('/api/pause'):
            self.__response_set_pause()  # 三个历史路径等价:统一入口,多项改动只落盘一次。
        else:
            self.send_error(404)

    @staticmethod
    def replace_body_tag(body: bytes, tag: bytes) -> bytes:
        """替换首页的<body>起始标签,注入认证标记与机器人标记。
        模板的<body>可能携带属性,直接按固定字符串替换会漏掉,故用正则匹配起始标签本身。"""
        return re.sub(WebHandler.BODY_TAG_PATTERN, tag, body, count=1)

    def log_message(self, fmt, *args) -> None:
        """屏蔽默认的请求日志,避免污染终端输出。"""

    def __check_auth(self) -> bool:
        """校验认证:优先Cookie免密,其次前端持有的临时令牌,最后回退到Basic认证。"""
        self.remember_session = False
        self.first_login = False
        web: Union[Web, None] = getattr(self.server, 'web', None)
        if web is None or not web.username:
            return True
        if web.check_session(self.__get_cookie()):
            return True  # 浏览器已被记住,无需重复输入密码。
        authorization: str = self.headers.get('Authorization', '')
        if authorization.startswith('Bearer '):
            # 未勾选"30天内免登录"时不发Cookie,前端把令牌存sessionStorage并随请求带来,关闭标签页即失效。
            if web.check_session(authorization.split(' ', 1)[1].strip()):
                return True
        if not authorization.startswith('Basic '):
            self.__response_unauthorized()
            return False
        try:
            credential: str = base64.b64decode(authorization.split(' ', 1)[1]).decode('UTF-8')
        except Exception:  # noqa.
            self.__response_unauthorized()
            return False
        if credential != f'{web.username}:{web.password}':
            self.__response_unauthorized()
            return False
        self.remember_session = True  # 首次认证成功,响应时下发Cookie。
        self.first_login = True  # 走到这里说明请求未携带有效Cookie,即本次为首次登录。
        return True

    def __get_cookie(self) -> str:
        """读取请求头中指定名称的Cookie。"""
        for item in self.headers.get('Cookie', '').split(';'):
            name, _, value = item.strip().partition('=')
            if name == WebMeta.COOKIE_NAME:
                return value
        return ''

    def __response_unauthorized(self) -> None:
        """返回需要认证的响应。
        不下发 WWW-Authenticate:否则浏览器会弹出系统自带的账号密码框,
        无法套用页面风格;改由前端展示毛玻璃登录卡片。"""
        self.send_response(401)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def __response_login(self) -> None:
        """校验登录卡片提交的账号密码。
        勾选"30天内免登录"才下发长期Cookie;未勾选时不下发Cookie,
        改为把令牌返回给前端存放在sessionStorage,关闭标签页即需重新登录。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        payload: dict = self.__read_json()
        ok: bool = False
        if web is not None:
            if not web.username:  # 未设置账号密码时直接放行。
                ok = True
            else:
                username: str = str(payload.get('username') or '')
                password: str = str(payload.get('password') or '')
                ok = username == web.username and password == web.password
        if ok:
            # 未勾选时不置 remember_session,即不下发任何Cookie。
            self.remember_session = bool(payload.get('remember'))
            self.first_login = bool(web and web.username)
        self.__response_body(
            body=json.dumps(
                {
                    'status': ok,
                    'first_login': bool(ok and web and web.username),
                    'token': web.token if (ok and web is not None) else ''
                },
                ensure_ascii=False
            ).encode('UTF-8'),
            content_type='application/json; charset=utf-8',
            status=200 if ok else 401
        )

    def __response_session_cookie(self) -> None:
        """下发或清除Cookie。
        登录勾选"30天内免登录"时下发长期Cookie;退出登录时下发一个立即过期的Cookie以清除它。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        if web is None:
            return
        if self.remember_session:
            cookie: str = (
                f'{WebMeta.COOKIE_NAME}={web.token}; '
                f'Max-Age={Web.REMEMBER_COOKIE_MAX_AGE}; Path=/; HttpOnly; SameSite=Lax'
            )
        elif self.expire_session:
            # Max-Age=0 让浏览器立即丢弃该Cookie(HttpOnly 无法由前端 JS 删除)。
            cookie = f'{WebMeta.COOKIE_NAME}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax'
        else:
            return
        self.send_header('Set-Cookie', cookie)

    def __response_logout(self) -> None:
        """退出登录:轮换令牌使所有已下发的Cookie失效,并清除本浏览器的Cookie。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        if web is not None:
            web.logout()
        self.expire_session = True
        self.__response_body(
            body=json.dumps({'status': True}, ensure_ascii=False).encode('UTF-8'),
            content_type='application/json; charset=utf-8'
        )

    def __response_body(self, body: bytes, content_type: str, status: int = 200) -> None:
        """返回指定内容的响应,status 用于登录失败时返回401。"""
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')  # 禁用缓存,避免浏览器沿用旧页面。
        self.__response_session_cookie()
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

    def __response_storages(self) -> None:
        """返回网页下载/上传存储的JSON,读取时实时校验文件是否存在,不存在的条目直接丢弃。

        返回该类型的全部记录;分页与按频道分组由前端完成。
        """
        web: Union[Web, None] = getattr(self.server, 'web', None)
        query: dict = parse_qs(urlparse(self.path).query)
        storage_type: str = (query.get('type') or [''])[0]
        storages: list = web.get_storage(storage_type=storage_type) if web else []
        self.__response_body(
            body=json.dumps({'storage': storages}, ensure_ascii=False).encode('UTF-8'),
            content_type='application/json; charset=utf-8'
        )

    def __response_disk_usage(self) -> None:
        """返回下载保存目录所在磁盘空间信息的JSON。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        data: dict = web.disk_usage() if web else {}
        self.__response_body(
            body=json.dumps(data, ensure_ascii=False).encode('UTF-8'),
            content_type='application/json; charset=utf-8'
        )

    def __read_json(self) -> dict:
        """读取请求体中的JSON数据,解析失败时返回空字典。"""
        try:
            length: int = int(self.headers.get('Content-Length') or 0)
        except (TypeError, ValueError):
            return {}
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode('UTF-8'))
        except Exception as e:
            log.debug(f'解析请求数据失败,{_t(KeyWord.REASON)}:"{e}"')
            return {}

    def __response_remove_listener(self) -> None:
        """处理移除监听下载与监听转发的请求。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        payload: dict = self.__read_json()
        if web is None:
            body: dict = {'status': False, 'e_code': '网页面板未就绪。'}
        else:
            body: dict = web.remove_listener(
                kind=str(payload.get('kind') or ''),
                link=str(payload.get('link') or '')
            )
        self.__response_body(
            body=json.dumps(body, ensure_ascii=False).encode('UTF-8'),
            content_type='application/json; charset=utf-8'
        )

    def __response_set_config(self) -> None:
        """处理网页面板修改配置的请求。

        save_directory / max_tasks / max_retries三个历史路径在这里等价:一次性读取请求体中的全部字段交由Web.set_config处理,多项改动因此只会写一次配置文件。
        """
        web: Union[Web, None] = getattr(self.server, 'web', None)
        payload: dict = self.__read_json()
        if web is None:
            body: dict = {'status': False, 'e_code': '网页面板未就绪'}  # 末尾句号由前端统一补。
        else:
            body: dict = web.set_config(
                directory=payload.get('save_directory'),
                max_tasks=payload.get('max_tasks'),
                max_retries=payload.get('max_retries'),
                confirm_directory=bool(payload.get('confirm_directory'))
            )
        self.__response_body(
            body=json.dumps(body, ensure_ascii=False).encode('UTF-8'),
            content_type='application/json; charset=utf-8'
        )

    def __response_set_pause(self) -> None:
        """处理全局暂停/恢复的请求。"""
        web: Union[Web, None] = getattr(self.server, 'web', None)
        payload: dict = self.__read_json()
        if web is None:
            body: dict = {'status': False, 'e_code': '网页面板未就绪。'}
        else:
            body: dict = web.set_pause(bool(payload.get('paused')))
        self.__response_body(
            body=json.dumps(body, ensure_ascii=False).encode('UTF-8'),
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
        body: bytes = b''
        try:
            with open(file=file_path, mode='rb') as f:
                body = f.read()
        except OSError as e:
            log.warning(f'读取网页文件"{file_path}"失败,{_t(KeyWord.REASON)}:"{e}"')
            self.send_error(404)
            return
        if os.path.basename(file_path) == Web.INDEX_FILE:  # 首页需要替换标记与版本号。
            # body 在此处已确定赋值(正常路径来自文件读取,异常路径已在上方 return)。
            # 先取出基准内容到 page,后续替换均基于 page,避免在分支内回头读取 try 赋值的 body。
            page: bytes = body  # type: ignore[reportPossiblyUnboundVariable]
            if self.first_login:
                page = WebHandler.replace_body_tag(page, WebHandler.FIRST_LOGIN_BODY)
            elif web and web.username:
                page = WebHandler.replace_body_tag(
                    page,
                    WebHandler.LOGIN_BODY
                )  # 需要认证:首屏即隐藏页面内容,认证通过后由前端移除该类,避免刷新时闪现已登录界面。
            page = page.replace(
                WebHandler.VERSION_PLACEHOLDER,
                f'{VERSION_WITH_COMMIT}'.encode('UTF-8')
            )
            page = page.replace(
                WebHandler.PYROGRAM_PLACEHOLDER,
                f'{pyrogram_version}'.encode('UTF-8')
            )
            page = page.replace(  # 注入是否配置机器人,前端据此隐藏上传与监听侧边栏。
                WebHandler.HAS_BOT_PLACEHOLDER,
                b'1' if (web and web.has_bot) else b'0'
            )
            page = page.replace(  # 注入记录数据库是否可用,前端据此展示记录侧边栏。
                WebHandler.HAS_STORAGE_PLACEHOLDER,
                b'1' if (web and web.has_storage) else b'0'
            )
            body = page
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
    REMOVE_LISTEN_TIMEOUT: int = 10  # 等待事件循环移除监听的超时时间,单位为秒。
    REMEMBER_COOKIE_MAX_AGE: int = 30 * 24 * 3600  # Cookie的有效期,单位为秒(30天)。
    STORAGE_TIMEOUT: int = 3  # 等待事件循环返回网页记录的超时时间,单位为秒。
    CACHE_SIZE_INTERVAL: int = 30  # 缓存目录大小的最短重算间隔,单位为秒:全盘遍历开销大,不能跟着3秒轮询跑。
    UNFINISHED_STATE: tuple = (
        DownloadStatus.PENDING,
        DownloadStatus.DOWNLOADING
    )  # 尚未出结果的消息状态。
    LOCAL_IP: str = get_local_ip()

    def __init__(self, progress, app=None, downloader=None):
        self.progress = progress
        self.app = app
        self.downloader = downloader  # 下载器实例,用于读取已注册的监听信息。
        self.cache_size_stamp: float = 0.0  # 上次统计缓存目录大小的时刻,用于节流。
        self.cache_size_value: int = 0  # 上次统计出的缓存目录字节数。
        self.filled_chat_ids: set = set()  # 已补全过标题的频道ID,避免重复扫描与重复回写。
        self.has_bot = bool(app and getattr(app, 'bot_token', None))  # 是否配置了机器人,决定前端是否展示上传与监听侧边栏(无机器人时只有下载可用)。
        self.credential: dict = gen_random_credential()
        self.protocol: str = 'http'
        self.ip: str = '0.0.0.0'
        self.port: int = self.get_free_port(PARSE_ARGS.port)
        self.username: str = self.credential.get(WebMeta.USERNAME)
        self.password: str = self.credential.get(WebMeta.PASSWORD)
        self.token: str = get_web_session()  # 令牌,使浏览器在软件重启后依然免密。
        self.template_directory, self.static_directory = self.get_web_directory()
        self.server: Union[ThreadingHTTPServer, None] = None
        self.thread: Union[threading.Thread, None] = None

    @property
    def has_storage(self) -> bool:
        """记录数据库是否可用,决定前端是否展示记录入口。

        数据库在登录成功后才会打开,故不能像has_bot那样在初始化时确定,必须实时判断。
        """
        return bool(getattr(self.downloader, 'storage_database', None))

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
            base_directory = getattr(sys, '_MEIPASS', sys.prefix)  # noqa.
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
            self.server = ThreadingHTTPServer((self.ip, self.port), WebHandler)  # type: ignore[arg-type]
        except OSError as e:
            log.error(f'网页面板启动失败,{_t(KeyWord.REASON)}:"{e}"')
            return False
        self.server.web = self
        self.thread = threading.Thread(target=self.server.serve_forever, name='TRMDWeb', daemon=True)
        self.thread.start()
        log.info(f'网页面板已启动,链接:"{self.protocol}://{self.LOCAL_IP}:{self.port}"。')
        self.print_meta()
        console.log(Issues.DOCKER_HOST_IP_TIP, style='#5AC8FA') if is_docker() else None
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
                ['链接', f'{self.protocol}://{Web.LOCAL_IP}:{self.port}']
            ],
            show_lines=True
        ).print_meta()

    def check_session(self, token: str) -> bool:
        """校验浏览器提交的令牌是否有效,用于免密登录。"""
        return bool(token) and token == self.token

    def logout(self) -> None:
        """退出登录:重新生成令牌并持久化,使所有已下发的Cookie失效。"""
        self.token = reset_web_session()

    @staticmethod
    def get_outer_links() -> dict:
        """读取顶栏菜单使用的外部链接,远程配置缺失时回退到内置默认值。"""
        config: dict = rc.cached_config()
        return {
            'github': config.get('github', rc.DEFAULT_GITHUB) + '/releases',
            'subscribe_channel': config.get('subscribe_channel', rc.DEFAULT_SUBSCRIBE_CHANNEL),
            'video_tutorial': config.get('video_tutorial', rc.DEFAULT_VIDEO_TUTORIAL)
        }

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
        # 链接级解析失败(如频道不存在)仅登记在 task.fail_id 的 -1 哨兵上,不写入 app 级 failure_* 集合。
        # 这里单独把这类失败计入失败总数,使网页"失败"卡片数字与实际可见的失败链接一致,且不污染 app 级统计。
        for _task in list(DownloadTask.TASKS.values()):
            if -1 in _task.fail_id:
                count['failure'] += 1
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
                base_num: int = max(member_num - fail_num, 0)  # 彻底失败的成员退出进度基数,避免进度永远到不了100%。
                result.append({
                    'link': str(link),
                    'channel': str(task.chat_id or ''),
                    'channel_name': Web.format_channel(str(task.chat_id or ''), parse_chat_id(task.link)),
                    'complete': complete_num,
                    'member': member_num,
                    'failed': fail_num,
                    'remaining': max(member_num - complete_num - fail_num, 0),
                    'queue': members,
                    'queue_total': unfinished,
                    'total': len(members),
                    'percent': round(complete_num / base_num * 100, 1) if base_num else 0.0
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
                'state': member.get('state') or DownloadStatus.PENDING,
                'task_id': member.get('task_id'),
                'note': member.get('note') or ''
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

    def get_listeners(self) -> dict:
        """获取已注册的监听下载与监听转发信息。

        Returns:
            dict: download为监听下载的频道链接;forward为监听转发的监听频道与转发频道。
        """
        result: dict = {'download': [], 'forward': []}
        if self.downloader is None:
            return result
        try:
            result['download'] = [str(link) for link in list(self.downloader.listen_download_chat)]
            for rule in list(self.downloader.listen_forward_chat):
                args: list = str(rule).split()
                if len(args) != 2:
                    continue  # 转发规则固定为"监听频道 转发频道"两段,异常规则直接跳过。
                result['forward'].append({'source': args[0], 'target': args[1]})
        except Exception as e:
            log.debug(f'获取监听信息时出错,{_t(KeyWord.REASON)}:"{e}"')
        return result

    def get_storage(self, storage_type: str = '') -> list:
        """读取网页下载/上传存储。

        读取动作需要投递到下载器的事件循环中执行(数据库连接由循环线程持有),
        与移除监听一致:通过run_coroutine_threadsafe投递并等待结果。
        数据库内部会先按目录mtime捷径做一次存在性校验,不存在的条目直接丢弃。
        返回该类型的全部记录;分页与按频道分组由前端完成。

        Args:
            storage_type: 记录类型,download为下载存储,upload为上传存储,为空时返回全部记录。

        Returns:
            list: 记录的展示信息。
        """
        if self.downloader is None:
            return []
        storage_db = getattr(self.downloader, 'storage_database', None)
        if storage_db is None:
            return []
        loop: Union[AbstractEventLoop, None] = getattr(self.downloader, 'loop', None)
        if loop is None or not loop.is_running():
            return []
        try:
            future = asyncio.run_coroutine_threadsafe(
                storage_db.get_storages(storage_type=storage_type or None),
                loop
            )
            storages: list = future.result(timeout=Web.STORAGE_TIMEOUT)
        except Exception as e:
            log.debug(f'获取网页记录失败,{_t(KeyWord.REASON)}:"{e}"')
            return []
        self.__fill_storage_chat_names(storages)  # 先把缓存里已有的标题补进记录,展示即为"标题(ID)"。
        return [Web.format_storage(storage) for storage in storages]

    def disk_usage(self) -> dict:
        """返回保存目录所在磁盘的空间信息与缓存目录占用,供存储页展示。

        Windows按盘符根查询:盘符即文件系统边界,与路径中的通配符和中间层级无关。
        类UNIX只有一个根"/",而它可能跨多个挂载点(Docker的bind mount尤甚),
        故裁到保存目录最近的真实目录再查,才能命中真正的文件系统。
        Windows、Linux、macOS 统一由 shutil.disk_usage 读取(内部按平台调用
        GetDiskFreeSpaceEx 或 statvfs),因此读取本身无需按系统分支。

        Returns:
            dict: 磁盘的 directory、total、used、free、percent 及展示文本,
                  外加缓存目录的 cache_directory、cache_size、cache_text。
        """
        directory: str = self.app.save_directory if self.app else ''
        root: str = ''
        if directory:
            if sys.platform == 'win32':
                # Windows:盘符根即目标文件系统,无需解析%CHAT_NAME%等占位符。
                drive, _ = os.path.splitdrive(os.path.abspath(directory))
                root = drive + os.sep if drive else os.sep
            else:
                # 类UNIX:根目录可能跨挂载点,改裁到最近的真实目录再查。
                root = os.path.abspath(directory)
                drive, _ = os.path.splitdrive(root)
                volume: str = drive + os.sep if drive else os.sep
                while root and not os.path.isdir(root):
                    parent = os.path.dirname(root.rstrip(os.sep))
                    if not parent or parent == root:
                        root = ''
                        break
                    root = parent
                if root == volume:
                    root = ''  # 整条路径都不存在,不能拿根目录冒充。
        data: dict = {'directory': directory}
        try:
            usage = shutil.disk_usage(root or os.getcwd())
        except Exception as e:
            log.debug(f'读取磁盘空间失败,{_t(KeyWord.REASON)}:"{e}"')
            data.update({'total': 0, 'used': 0, 'free': 0, 'percent': 0.0})
        else:
            total: int = int(usage.total)
            used: int = int(usage.used)
            free: int = int(usage.free)
            data.update({
                'total': total,
                'used': used,
                'free': free,
                'percent': round(used * 100 / total, 1) if total else 0.0,
                'used_text': '已用{0}'.format(MetaData.suitable_units_display(used)),
                'free_text': '可用{0}'.format(MetaData.suitable_units_display(free)),
                'total_text': '共{0}'.format(MetaData.suitable_units_display(total))
            })
        data.update(self.cache_size())
        return data

    def cache_size(self) -> dict:
        """统计缓存目录占用的磁盘空间,并按时间节流避免每次轮询都全盘遍历。

        缓存目录同样支持通配符,故逐级向上裁剪到最近的真实目录再遍历:
        占位符只是其下更深一层的子目录,同属一份缓存。

        Returns:
            dict: cache_directory、cache_size(字节)、cache_text(展示文本)。
        """
        directory: str = self.app.temp_directory if self.app else ''
        result: dict = {
            'cache_directory': directory,
            'cache_size': 0,
            'cache_text': '0.00B'
        }
        if not directory:
            return result
        now: float = time.monotonic()
        if now - self.cache_size_stamp >= Web.CACHE_SIZE_INTERVAL:
            # 先占位再遍历:遍历期间到来的请求直接复用上次结果,避免多线程叠加遍历同一目录。
            self.cache_size_stamp = now
            total: int = 0
            real: str = os.path.abspath(directory)
            drive, _ = os.path.splitdrive(real)
            volume: str = drive + os.sep if drive else os.sep
            while real and not os.path.isdir(real):
                parent: str = os.path.dirname(real.rstrip(os.sep))
                if not parent or parent == real:
                    real = ''
                    break
                real = parent
            if real == volume:
                # 缓存目录整条路径都不存在:不能把整个卷当成缓存统计,否则数字失去意义且遍历极慢。
                real = ''
            if real:
                for walk_root, _, files in os.walk(real):
                    for name in files:
                        try:
                            total += os.path.getsize(os.path.join(walk_root, name))
                        except OSError:
                            continue  # 文件正被下载占用或已删除,跳过即可。
            self.cache_size_value = total
        result['cache_size'] = self.cache_size_value
        result['cache_text'] = MetaData.suitable_units_display(self.cache_size_value)
        return result

    @staticmethod
    def format_storage(storage: TRMDStorage) -> dict:
        """格式化网页记录的展示信息,频道列优先取记录里的标题,与下载板块的"标题(ID)"样式一致。"""
        chat_id: str = str(storage.chat_id) if storage.chat_id is not None else ''
        display_id: str = parse_chat_id(storage.link, chat_id)
        chat_name: str = storage.chat_name or ChatInfo.get(display_id)
        return {
            'storage_id': storage.storage_id,
            'storage_type': storage.storage_type,
            'channel': chat_id,
            'chat': f'{chat_name}({display_id})' if chat_name and display_id else (display_id or Web.UNGROUPED),
            'message_id': storage.message_id if storage.message_id is not None else '',
            'file': storage.file_name,
            'path': storage.file_path,
            'size': MetaData.suitable_units_display(storage.file_size),
            'size_byte': storage.file_size,
            'type': storage.file_type,
            'status': _t(storage.status),
            'state': storage.status,
            'error': storage.error_msg,
            'link': storage.link,
            'time': datetime.datetime.fromtimestamp(storage.finish_time).strftime(
                '%Y-%m-%d %H:%M:%S') if storage.finish_time else ''
        }

    def __fill_storage_chat_names(self, storages: list) -> None:
        """把ChatInfo缓存中已有的标题补到记录上,并异步回写数据库。

        写入记录时若缓存未命中,chat_name为空,之后该频道被任何下载或上传流程
        缓存过标题;此处读取时补全,让历史记录也显示"标题(ID)"而非裸ID。
        回写只投递不等待,失败不影响本次展示;同一频道只补一次。
        """
        storage_db = getattr(self.downloader, 'storage_database', None)
        loop: Union[AbstractEventLoop, None] = getattr(self.downloader, 'loop', None)
        if storage_db is None or loop is None or not loop.is_running():
            return
        pending: dict = {}
        for storage in storages:
            chat_id: str = str(storage.chat_id or '')
            if not chat_id or storage.chat_name or chat_id in self.filled_chat_ids:
                continue
            title: str = ChatInfo.get(chat_id)
            if title:
                storage.chat_name = title
                pending[chat_id] = title
        if not pending:
            return
        self.filled_chat_ids.update(pending.keys())
        try:
            asyncio.run_coroutine_threadsafe(storage_db.update_chat_names(pending), loop)
        except Exception as e:
            log.debug(f'回写网页记录频道标题失败,{_t(KeyWord.REASON)}:"{e}"')

    def remove_listener(self, kind: str, link: str) -> dict:
        """按网页面板的请求移除已注册的监听下载或监听转发。

        移除动作需要在下载器的事件循环中执行,才能安全地让用户端向机器人发送命令,
        而网页面板运行在独立的HTTP服务线程中,因此把协程投递到事件循环并等待结果。

        Args:
            kind: 监听类型,download为监听下载,forward为监听转发。
            link: 监听下载为频道链接;监听转发为"监听频道 转发频道"。

        Returns:
            dict: status为是否移除成功,失败时e_code为失败原因。
        """
        if self.downloader is None:
            return {'status': False, 'e_code': '网页面板未关联下载器。'}
        loop: Union[AbstractEventLoop, None] = self.downloader.loop
        if loop is None or not loop.is_running():
            return {'status': False, 'e_code': '下载器未运行，无法移除监听。'}
        future = asyncio.run_coroutine_threadsafe(
            self.downloader.cancel_listen_from_web(kind=kind, link=link),
            loop
        )
        try:
            return future.result(timeout=Web.REMOVE_LISTEN_TIMEOUT)
        except Exception as e:
            log.debug(f'移除监听失败,{_t(KeyWord.REASON)}:"{e}"')
            return {'status': False, 'e_code': '移除监听超时，请稍后重试。'}

    def set_pause(self, paused: bool) -> dict:
        """按网页面板的请求切换全局暂停状态。

        切换标志与暂停事件必须在下载器的事件循环线程内完成,
        网页面板运行在独立的HTTP服务线程中,因此通过call_soon_threadsafe把动作投递到事件循环执行。

        Args:
            paused: True为暂停,False为恢复。

        Returns:
            dict: status为是否切换成功,失败时e_code为失败原因。
        """
        if self.app is None:
            return {'status': False, 'e_code': '配置未加载，无法暂停。'}
        if self.downloader is None:
            return {'status': False, 'e_code': '网页面板未关联下载器。'}
        loop: Union[AbstractEventLoop, None] = self.downloader.loop
        if loop is None or not loop.is_running():
            return {'status': False, 'e_code': '下载器未运行，无法暂停。'}

        def apply(_paused: bool) -> None:
            # 同一闭包内顺序切换标志与事件,避免HTTP线程读到不一致的中间状态。
            self.app.is_paused = _paused
            if _paused:
                self.downloader.pause_event.clear()
            else:
                self.downloader.pause_event.set()

        loop.call_soon_threadsafe(apply, paused)  # 投递到事件循环线程执行,无需等待即可确认已入队。
        return {'status': True}

    @staticmethod
    def __check_number_pair(
            values: Union[dict, None],
            lower: int,
            upper: Union[int, None],
            name: str,
            range_text: str,
            error_parts: list
    ) -> Union[dict, None]:
        """校验一组下载/上传数值是否合法,不合法时把失败原因追加到error_parts。

        Args:
            values: 形如{'download': int, 'upload': int}的取值;None表示本次不修改。
            lower: 允许的下限(含)。
            upper: 允许的上限(含);None表示不限制上限。
            name: 配置项名称,用于拼装失败原因。
            range_text: 超出范围时的提示语。
            error_parts: 失败原因收集列表。

        Returns:
            dict | None: 校验通过时的规范化取值;本次不修改或校验失败时为None。
        """
        if values is None:
            return None
        try:
            result: dict = {'download': int(values.get('download')), 'upload': int(values.get('upload'))}
        except (AttributeError, TypeError, ValueError):
            error_parts.append(f'{name}必须是整数')
            return None
        if result['download'] < lower or result['upload'] < lower:
            error_parts.append(f'{name}{range_text}')
            return None
        if upper is not None and (result['download'] > upper or result['upload'] > upper):
            error_parts.append(f'{name}{range_text}')
            return None
        return result

    @staticmethod
    def __check_save_directory(path: str, allow_create: bool = True) -> dict:
        """非交互地校验保存目录。

        剥离通配符占位符后判断目录,不存在时按allow_create决定是否直接创建。

        Args:
            path: 新的保存目录,允许包含通配符占位符。
            allow_create: 目录不存在时是否直接创建;False时不创建,并在结果中标记need_confirm,
                由网页面板先向用户二次确认,避免静默创建拼错的目录。

        Returns:
            dict: status为校验是否通过;不通过时e_code为失败原因;
                need_confirm为True表示目录不存在且尚未创建。
        """
        if not path:
            return {'status': False, 'e_code': '保存目录不能为空'}
        clean_path: str = path
        for placeholder in SaveDirectoryPrefix():
            if placeholder in clean_path:
                clean_path = clean_path.replace(placeholder, '')
        clean_path = os.path.normpath(clean_path)
        drive, tail = os.path.splitdrive(clean_path)
        invalid: list = [c for c in '<>:"|?*' if c in tail]
        if invalid:
            return {'status': False, 'e_code': f'路径包含非法字符：{"、".join(sorted(set(invalid)))}'}
        if os.path.isdir(clean_path):
            return {'status': True}
        if not allow_create:
            return {'status': False, 'need_confirm': True}  # 目录不存在,交由网页面板二次确认后再创建。
        try:
            os.makedirs(clean_path, exist_ok=True)
        except Exception as e:
            return {'status': False, 'e_code': f'目录无效或无法创建,{_t(KeyWord.REASON)}:"{e}"'}
        if not os.path.isdir(clean_path):
            return {'status': False, 'e_code': '保存目录不是一个有效的目录'}
        return {'status': True}

    def __adjust_client_semaphores(self, download: int, upload: int) -> None:
        """按新的并发数调整客户端传输信号量的额度。

        只调整额度而不是新建信号量:新建会丢弃正在传输所占用的名额,导致"旧的活跃数 + 新的额度"
        叠加超限。调整额度时正在进行的传输仍在同一个闸门内,降低并发后新的传输会排队等待。

        Args:
            download: 最大下载并发数。
            upload: 最大上传并发数。
        """
        client = getattr(self.app, 'client', None)
        if client is None:
            return
        try:
            loop = getattr(client, 'loop', None)

            def adjust() -> None:
                client.get_file_semaphore.set_limit(download)
                client.save_file_semaphore.set_limit(upload)

            if loop is not None and hasattr(loop, 'call_soon_threadsafe'):
                loop.call_soon_threadsafe(adjust)
            else:
                adjust()
        except Exception as e:
            log.warning(f'实时更新并发信号量失败,原因:"{e}"')

    def __wake_upload_waiters(self) -> None:
        """唤醒排队等待上传名额的任务,让它们按新的并发上限重新检查。

        上传任务用uploader.event.wait()阻塞等待名额,该事件只在一次上传结束(成功或失败)时被set;
        因此只修改max_upload_task并不会唤醒它们,队列里已排队的任务会一直睡着,直到下次有上传结束
        或新命令进来才开始——表现为"改了并发但当前上传数不变"。
        """
        uploader = getattr(self.downloader, 'uploader', None)
        if uploader is None:
            return
        loop = getattr(self.downloader, 'loop', None)
        if loop is None or not loop.is_running():
            return  # 没有运行中的事件循环就不会有任务在等待,且跨线程操作asyncio对象并不安全。
        try:
            loop.call_soon_threadsafe(lambda: uploader.notify_waiters())
        except Exception as e:
            log.warning(f'唤醒排队上传任务失败,原因:"{e}"')

    def set_config(self, directory=None, max_tasks=None, max_retries=None, confirm_directory: bool = False) -> dict:
        """按网页面板的请求一次性修改多项配置。

        Args:
            directory: 新的保存目录;None表示本次不修改。
            max_tasks: 形如{'download': int, 'upload': int}的并发数;None表示本次不修改。
            max_retries: 形如{'download': int, 'upload': int}的重试次数;None表示本次不修改。
            confirm_directory: 目录不存在时是否已确认创建(False则先返回need_confirm由前端二次确认)。

        Returns:
            dict: status为是否成功,失败时e_code为失败原因(多项问题时以全角分号分隔);
                目录待确认时额外返回need_confirm为True。
        """
        if self.app is None:
            return {'status': False, 'e_code': '配置未加载，无法修改'}  # 末尾句号由前端统一补。
        error_parts: list = []
        need_confirm: bool = False  # 目录不存在;待其它错误都排除后再请求前端二次确认。
        tasks = self.__check_number_pair(max_tasks, 1, 10, '并发数', '必须为1到10之间的整数', error_parts)
        retries = self.__check_number_pair(max_retries, 1, None, '重试次数', '必须大于0', error_parts)
        if directory is not None:
            checked: dict = self.__check_save_directory(directory, allow_create=confirm_directory)
            if checked.get('need_confirm'):
                need_confirm = True  # 目录不存在不是错误,先不与其它错误一起返回。
            elif not checked.get('status'):
                error_parts.append(checked.get('e_code') or '保存目录无效')
        if error_parts:
            # 存在不合法的项:先让用户改正,此时不提示创建目录(有一项不合法就一项都不改)。
            return {'status': False, 'e_code': '；'.join(error_parts)}
        if need_confirm:
            # 其它项均合法,仅目录不存在:此时不落盘、不创建,交回前端二次确认后再提交。
            return {'status': False, 'need_confirm': True, 'e_code': f'目录"{directory}"不存在，是否创建'}
        save_config: dict = copy.deepcopy(self.app.config)  # 先在副本上改动:落盘失败时原配置不受影响。
        if directory is not None:
            save_config['save_directory'] = directory
        if tasks is not None:
            save_config['max_tasks'] = tasks
        if retries is not None:
            save_config['max_retries'] = retries
        if not self.app.save_config(save_config):  # 多项改动合并后,整个请求只在这里写一次配置文件。
            return {'status': False, 'e_code': '配置文件保存失败，请稍后重试'}  # 末尾句号由前端统一补。
        self.app.config = save_config
        if directory is not None:
            self.app.save_directory = directory
        if tasks is not None:
            self.app.max_download_task = tasks['download']
            self.app.max_upload_task = tasks['upload']
            self.__adjust_client_semaphores(tasks['download'], tasks['upload'])
            self.__wake_upload_waiters()  # 提高上传并发后,排队中的任务才会重新检查额度并开始上传。
        if retries is not None:
            self.app.max_download_retries = retries['download']
            self.app.max_upload_retries = retries['upload']
        return {'status': True}

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

        总量取未失败成员的字节之和(包含排队、已完成、跳过),
        而不是只统计正在下载的任务,避免总进度随着任务开始下载而不断变大;
        彻底失败(重试耗尽)的成员不再计入总量,避免进度被永久拉低。

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
                state: str = str(member.get('state') or '')
                note: str = str(member.get('note') or '')
                if state == DownloadStatus.FAILURE:
                    continue  # 彻底失败的成员不再计入总量与速度,避免进度被拉低或无法归零。
                if state == DownloadStatus.SKIP and note:
                    continue  # 不支持或被忽略的类型(已取消)的跳过成员不再计入总量,因为它们本就不会被下载;文件已存在(已下载)的跳过不带note,仍计入总量。
                size: int = int(member.get('size_byte') or 0)
                total += size
                if state in (DownloadStatus.SUCCESS, DownloadStatus.SKIP):
                    completed += size
                    continue
                if state == DownloadStatus.DOWNLOADING:
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
    def format_channel(channel: str, display: str = '') -> str:
        """格式化频道的显示名称,有标题时显示为"标题(显示值)"。

        channel为标题缓存键(下载流程以小写口径写入缓存),display为括号内的显示值,
        默认同channel;传入时用于保留链接中的原始大小写,与网页面板存储记录一致。
        """
        if not channel or channel == Web.UNGROUPED:
            return Web.UNGROUPED
        title: str = ChatInfo.get(channel)
        _display: str = display or channel
        return f'{title}({_display})' if title else _display

    def get_tasks(self) -> list:
        """读取进度条中正在进行的任务。"""
        tasks: list = []
        for task in self.progress.tasks:
            item: dict = {
                'id': task.id,
                'type': str(task.description),
                'channel': str(task.fields.get('channel', '')) or Web.UNGROUPED,
                'channel_name': Web.format_channel(str(task.fields.get('channel', ''))),
                'filename': str(task.fields.get('fullname') or task.fields.get('filename', '')),
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
                'uploads': uploads,
                'listeners': self.get_listeners(),
                'is_paused': bool(self.app.is_paused) if self.app else False,  # 全局暂停状态,供前端展示与切换。
                'outer_links': self.get_outer_links(),  # 顶栏菜单使用的外部链接。
                'save_directory': self.app.save_directory if self.app else '',
                'max_tasks': {
                    'download': self.app.max_download_task if self.app else 3,
                    'upload': self.app.max_upload_task if self.app else 3
                },
                'max_retries': {
                    'download': self.app.max_download_retries if self.app else 5,
                    'upload': self.app.max_upload_retries if self.app else 3
                }
            }
        except Exception as e:
            log.debug(f'生成进度数据时出错,{_t(KeyWord.REASON)}:"{e}"')
            return {
                'count': {'success': 0, 'failure': 0, 'skip': 0},
                'summary': self.get_summary(links=[], tasks=[]),
                'queue': 0,
                'tasks': [],
                'links': [],
                'uploads': [],
                'listeners': {'download': [], 'forward': []},
                'is_paused': bool(self.app.is_paused) if self.app else False,  # 全局暂停状态,供前端展示与切换。
                'outer_links': self.get_outer_links(),
                'save_directory': self.app.save_directory if self.app else '',
                'max_tasks': {
                    'download': self.app.max_download_task if self.app else 3,
                    'upload': self.app.max_upload_task if self.app else 3
                },
                'max_retries': {
                    'download': self.app.max_download_retries if self.app else 5,
                    'upload': self.app.max_upload_retries if self.app else 3
                }
            }

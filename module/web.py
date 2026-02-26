# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/2/19 18:50
# File:web.py
import os
import socket
import tempfile
import platform
import subprocess

from module import (
    log,
    file_handler
)
from module.ttyd import TTYD
from module.tmux import TMUX
from module.stdio import PanelTable
from module.language import _t
from module.enums import (
    WebMeta,
    ENVIRON,
    KeyWord
)
from module.util import (
    gen_random_credential,
    get_subprocess_args
)


class Web(TTYD, TMUX):
    def __init__(self, *args, **kwargs):
        TTYD.__init__(self, *args, **kwargs)
        TMUX.__init__(self, *args, **kwargs)
        self.credential: dict = gen_random_credential()
        self.protocol: str = 'http'
        self.ip: str = '127.0.0.1'
        self.port: int = self.get_free_port()
        self.username: str = self.credential.get(WebMeta.USERNAME)
        self.password: str = self.credential.get(WebMeta.PASSWORD)
        self.platform: str = platform.system()

    @staticmethod
    def get_free_port():

        def _get_port(_port: int):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', _port))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                return s.getsockname()[1]

        port: int = int(os.environ.get(ENVIRON.TRMD_WEB_PORT, '0'))
        try:
            return _get_port(port)
        except OSError as e:
            log.warning(f'无法使用{port}端口,已自动分配新的端口,{_t(KeyWord.REASON)}:"{e}"')
            return _get_port(0)

    def run_once(self):
        env: dict = os.environ.copy()
        env[ENVIRON.TRMD_WEB_PID] = str(os.getpid())
        env[ENVIRON.TRMD_WEB_PORT] = str(self.port)
        log.info(f'通过浏览器运行,父进程pid:{env.get(ENVIRON.TRMD_WEB_PID)},未写入系统环境变量。')
        cmd: list = [
                        self.ttyd_path,
                        '--writable',
                        '--port', str(self.port),
                        '--ipv6',
                        '--credential', f'{self.username}:{self.password}',
                        '--once',
                        '--browser'
                    ] + get_subprocess_args(self.main_file)
        if self.platform == 'Windows':
            cmd.remove('--writable')
        log.info(f'通过浏览器运行,命令:"{cmd}"。')
        process = subprocess.Popen(cmd, env=env, stdout=file_handler.stream, stderr=file_handler.stream)
        os.environ[ENVIRON.TRMD_WEB_PID] = str(process.pid)
        PanelTable(
            title='Web配置',
            header=('属性', '内容'),
            data=[
                [_t(WebMeta.IP), self.ip],
                [_t(WebMeta.PORT), self.port],
                [_t(WebMeta.USERNAME), self.username],
                [_t(WebMeta.PASSWORD), self.password],
                ['访问链接', f'{self.protocol}://{self.ip}:{self.port}']
            ],
            show_lines=True
        ).print_meta()
        log.info(f'通过浏览器运行,子进程pid:{os.environ.get(ENVIRON.TRMD_WEB_PID)},已写入系统环境变量。')

    def run_session(self):
        env: dict = os.environ.copy()
        env[ENVIRON.TRMD_WEB_PID] = str(os.getpid())
        env[ENVIRON.TRMD_WEB_PORT] = str(self.port)
        log.info(f'通过浏览器运行,父进程pid:{env.get(ENVIRON.TRMD_WEB_PID)},未写入系统环境变量。')
        cmd: list = [
            self.ttyd_path,
            '--writable',
            '--port', str(self.port),
            '--ipv6',
            '--credential', f'{self.username}:{self.password}',
            '--browser'
        ]
        session_name: str = 'ttyd_session'
        args: str = ' '.join(get_subprocess_args(main_file=self.main_file))
        if self.platform == 'Windows':
            cmd.remove('--writable')
            # Windows (tmux): 检查会话是否存在。
            result = subprocess.run(
                [self.tmux_path, 'has-session', '-t', session_name],
                capture_output=True
            )
            if result.returncode != 0:
                # 会话不存在，先创建会话并执行程序（使用-d在后台创建）。
                # 显式设置环境变量，确保子进程能访问到。
                # 创建一个bat文件来设置环境变量并执行程序，然后保持cmd打开。
                bat_content = f'@echo off\r\nset {ENVIRON.TRMD_WEB_PID}={env[ENVIRON.TRMD_WEB_PID]}\r\nset {ENVIRON.TRMD_WEB_PORT}={env[ENVIRON.TRMD_WEB_PORT]}\r\n{args}\r\n'
                bat_path = os.path.join(tempfile.gettempdir(), 'trmd_tmux_session.bat')
                with open(bat_path, 'w', encoding='UTF-8') as f:
                    f.write(bat_content)
                # 使用cmd /k执行bat文件并保持打开。
                subprocess.run(
                    [self.tmux_path, 'new-session', '-d', '-s', session_name, 'cmd', '/k', bat_path],
                    capture_output=True
                )
                # 设置psmux选项（设置终端类型，禁用鼠标）。
                # 注意：需要tmux>v0.3.7或更高版本才能正确禁用鼠标。
                subprocess.run(
                    [self.tmux_path, 'set-option', '-t', session_name, '-g', 'mouse', 'off'],
                    capture_output=True
                )
                subprocess.run(
                    [self.tmux_path, 'set-option', '-t', session_name, '-g', 'default-terminal', 'xterm-256color'],
                    capture_output=True
                )
                log.info(f'在后台创建新会话并执行程序:"{session_name}"。')
            # 再次检查会话是否创建成功。
            result = subprocess.run(
                [self.tmux_path, 'has-session', '-t', session_name],
                capture_output=True
            )
            if result.returncode == 0:
                # 会话存在，直接启动psmux（不带任何参数）。
                # 根据psmux文档，不带命令时会自动附加到会话或创建新会话。
                # 设置环境变量指定默认会话名。
                cmd_env = env.copy()
                cmd_env[ENVIRON.PSMUX_SESSION_NAME] = session_name
                cmd.extend([self.tmux_path])
                log.info(f'tmux使用会话:"{session_name}"。')
            else:
                # 会话不存在，创建一个简单的会话。
                cmd.extend([self.tmux_path, 'new-session', '-s', session_name, 'cmd', '/k'])
                log.warning(f'无法创建tmux会话,使用简单的cmd会话。')
        else:
            shell_cmd = rf'''
            {self.tmux_path} new -A -s {session_name} -e TERM=xterm-256color \; \
                set-option -g mouse on \; \
                set-option -g default-terminal "xterm-256color" \; \
                send-keys "{args}" C-m
            '''
            cmd.extend(
                ['sh', '-c', shell_cmd]
            )
        log.info(f'通过浏览器运行,命令:"{cmd}"。')
        process = None
        try:
            # 根据平台使用不同的环境变量。
            use_env = cmd_env if self.platform == 'Windows' and 'cmd_env' in locals() else env
            process = subprocess.Popen(cmd, env=use_env, stdout=file_handler.stream, stderr=file_handler.stream)
            os.environ[ENVIRON.TRMD_WEB_PID] = str(process.pid)
            PanelTable(
                title='Web配置',
                header=('属性', '内容'),
                data=[
                    [_t(WebMeta.IP), self.ip],
                    [_t(WebMeta.PORT), self.port],
                    [_t(WebMeta.USERNAME), self.username],
                    [_t(WebMeta.PASSWORD), self.password],
                    ['访问链接', f'{self.protocol}://{self.ip}:{self.port}']
                ],
                show_lines=True
            ).print_meta()
            log.info(f'通过浏览器运行,子进程pid:{os.environ.get(ENVIRON.TRMD_WEB_PID)},已写入系统环境变量。')
            process.wait()
        except KeyboardInterrupt:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            result = subprocess.run(
                [self.tmux_path, 'has-session', '-t', session_name],
                capture_output=True
            )
            if result.returncode == 0:
                session_killer = subprocess.Popen(
                    [self.tmux_path, 'kill-session', '-t', session_name]
                )
                session_killer.wait()
                log.info(f'已清理tmux会话:"{session_name}"。')
            else:
                log.info(f'没有产生tmux会话:"{session_name}"。')

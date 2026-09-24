# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/9/24 20:33
# File:build.py
import os
import sys
import datetime
import subprocess

from pathlib import Path
from shutil import which

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # Python < 3.11回退。

with open(Path(__file__).resolve().parent / 'pyproject.toml', 'rb') as f:
    pyproject = tomllib.load(f)
PROJECT = pyproject['project']
AUTHOR = PROJECT['authors'][0]['name']
__version__ = PROJECT['version']
SOFTWARE_SHORT_NAME = ''.join(part[0].upper() for part in PROJECT['name'].split('_') if part)

VERSION_INFO = sys.version_info
PLATFORM: str = sys.platform
UV: str = 'uv ' if which('uv') and os.path.exists('uv.lock') else ''
try:
    TERMINAL_COLUMNS: int = os.get_terminal_size().columns
    GRID_CONTENT: str = '='
except OSError:
    TERMINAL_COLUMNS: int = 1
    GRID_CONTENT: str = ''
GRID: str = GRID_CONTENT * TERMINAL_COLUMNS


def ready_zstandard():
    try:
        import zstandard
    except (ImportError, ModuleNotFoundError, NameError):
        subprocess.run(f'{UV}pip install zstandard', shell=True)


def ready_nuitka():
    try:
        import nuitka
    except (ImportError, ModuleNotFoundError, NameError):
        subprocess.run(f'{UV}pip install nuitka==4.2.1', shell=True)


def ready_web() -> list:
    web_directories: list = []
    for relative_directory in ('module/templates', 'module/static'):
        path = str(Path(relative_directory).resolve())
        if not os.path.isdir(path):
            print(f'未找到网页面板的资源目录:"{path}"。')
            sys.exit(1)
        web_directories.append((path, relative_directory))
    return web_directories


def build(command):
    print(f'Command:\n{command}\n{GRID}')
    print('Build in progress:')
    subprocess.run(command, shell=True)


def check_python_version():
    current_version = (VERSION_INFO.major, VERSION_INFO.minor, VERSION_INFO.micro)

    min_version = (3, 9, 0)
    max_version = (3, 15, 0)

    version_valid = (
            VERSION_INFO.major == 3
            and min_version <= current_version < max_version
    )

    if not version_valid:
        print(
            f'Python版本不满足要求\n当前版本:{sys.version}\n要求范围:{".".join(map(str, min_version))} ≤ Python 版本 < {".".join(map(str, max_version))}\n请安装符合要求的Python版本后重试。')
        sys.exit(1)

    print(f'{GRID}\nPython:\n{sys.version}\n{GRID}')


if __name__ == '__main__':
    check_python_version()
    try:
        ready_nuitka()
        ready_zstandard()
        web_directories: list = ready_web()
        extension = '.exe' if PLATFORM == 'win32' else ''
        ico_path = 'res/icon.ico'
        output = 'output'
        main = 'main.py'
        years = str(datetime.datetime.now().year)
        copy_right = f'Copyright (C) 2024-{years} {AUTHOR}.All rights reserved.'
        command = f'nuitka --standalone --onefile '
        command += f'--no-deployment-flag=self-execution '
        command += f'--msvc=latest --windows-icon-from-ico="{ico_path}" --assume-yes-for-downloads ' if PLATFORM == 'win32' else ''
        command += f'--include-package-data=pyrogram '
        command += f'--include-module=pygments.lexers.data '
        command += ''.join(map(lambda d: f'--include-data-dir="{d[0]}"="{d[1]}" ', web_directories))
        command += f'--output-dir={output} --output-filename="{SOFTWARE_SHORT_NAME}{extension}" --file-version={__version__} --product-version={__version__} --copyright="{copy_right}" '
        command += f'--script-name={main}'
        build(command)
    except KeyboardInterrupt:
        print('键盘中断。')

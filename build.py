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
    import tomli as tomllib  # noqa, Python < 3.11回退。

with open(Path(__file__).resolve().parent / 'pyproject.toml', 'rb') as f:
    pyproject: dict = tomllib.load(f)

PROJECT: dict = pyproject['project']
AUTHOR: str = PROJECT['authors'][0]['name']
__version__: str = PROJECT['version']
SOFTWARE_SHORT_NAME: str = ''.join(part[0].upper() for part in PROJECT['name'].split('_') if part)
VERSION_INFO = sys.version_info
PLATFORM: str = sys.platform
UV: str = 'uv ' if which('uv') and os.path.exists('uv.lock') else ''  # noqa.
MIN_PYTHON_VERSION: tuple = (3, 9, 0)
MAX_PYTHON_VERSION: tuple = (3, 15, 0)
MIN_NUITKA_VERSION: tuple = (4, 3, 0)

try:
    TERMINAL_COLUMNS: int = os.get_terminal_size().columns
    GRID_CONTENT: str = '='
except OSError:
    TERMINAL_COLUMNS: int = 1
    GRID_CONTENT: str = ''
GRID: str = GRID_CONTENT * TERMINAL_COLUMNS


def ready_nuitka():
    subprocess.run(
        f'{UV}pip install --upgrade --no-cache-dir "nuitka[app] @ https://github.com/Nuitka/Nuitka/archive/factory.zip"',
        shell=True)


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

    version_valid = (
            VERSION_INFO.major == 3
            and MIN_PYTHON_VERSION <= current_version < MAX_PYTHON_VERSION
    )

    if not version_valid:
        print(
            f'Python版本不满足要求\n当前版本:{sys.version}\n要求范围:{".".join(map(str, MIN_PYTHON_VERSION))} ≤ Python 版本 < {".".join(map(str, MAX_PYTHON_VERSION))}\n请安装符合要求的Python版本后重试。')
        sys.exit(1)

    print(f'{GRID}\nPython:\n{sys.version}\n{GRID}')


if __name__ == '__main__':
    check_python_version()
    try:
        ready_nuitka()
        extension = '.exe' if PLATFORM == 'win32' else ''
        ico_path = 'res/icon.ico'
        output = 'output'
        main = 'main.py'
        years = str(datetime.datetime.now().year)
        copy_right = f'Copyright (C) 2024-{years} {AUTHOR}.All rights reserved.'
        build_command = f'{sys.executable} -m '
        build_command += f'nuitka --standalone --onefile '
        build_command += f'--zig '
        build_command += f'--no-deployment-flag=self-execution '
        build_command += f'--windows-icon-from-ico="{ico_path}" --assume-yes-for-downloads ' if PLATFORM == 'win32' else ''
        build_command += f'--include-package-data=pyrogram '
        build_command += f'--include-module=pygments.lexers.data '
        build_command += ''.join(map(lambda d: f'--include-data-dir="{d[0]}"="{d[1]}" ', ready_web()))
        build_command += f'--output-dir={output} --output-filename="{SOFTWARE_SHORT_NAME}{extension}" --file-version={__version__} --product-version={__version__} --copyright="{copy_right}" '
        build_command += f'--low-memory ' if '--low-memory' in sys.argv else ''
        build_command += f'--remove-output ' if '--remove-output' in sys.argv else ''
        build_command += f'--script-name={main}'
        build(build_command)
    except KeyboardInterrupt:
        print('键盘中断。')

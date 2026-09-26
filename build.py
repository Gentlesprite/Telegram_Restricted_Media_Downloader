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


def ready_meta() -> dict:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # noqa, Python < 3.11回退。
    pyroject_path: Path = Path(__file__).resolve().parent / 'pyproject.toml'
    if pyroject_path.exists():
        with open(pyroject_path, 'rb') as f:
            pyproject: dict = tomllib.load(f)
        return pyproject
    import logging
    logging.disable(logging.CRITICAL)  # 导入module前禁用日志,避免其初始化日志写入文件。
    from module import (
        AUTHOR,
        SOFTWARE_FULL_NAME,
        __version__
    )
    logging.disable(logging.NOTSET)  # 恢复日志输出。
    # 构建日志仅输出到控制台,移除module配置的文件处理器。
    for handler in logging.getLogger().handlers[:]:
        if getattr(handler, 'baseFilename', None):
            logging.getLogger().removeHandler(handler)
    # pyproject.toml不存在时,从module模块读取元数据,构建结构一致的字典作为回退。
    return {
        'project': {
            'authors': [{'name': AUTHOR}],
            'name': SOFTWARE_FULL_NAME.replace(' ', '_'),
            'version': __version__,
        }
    }


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


PROJECT: dict = ready_meta()['project']
AUTHOR: str = PROJECT['authors'][0]['name']
VERSION: str = PROJECT['version']
SOFTWARE_SHORT_NAME: str = ''.join(part[0].upper() for part in PROJECT['name'].split('_') if part)
VERSION_INFO = sys.version_info
PLATFORM: str = sys.platform
UV: str = 'uv ' if which('uv') and os.path.exists('uv.lock') else ''  # noqa.
MIN_PYTHON_VERSION: tuple = (3, 9, 0)
MAX_PYTHON_VERSION: tuple = (3, 15, 0)
MIN_NUITKA_VERSION: tuple = (4, 3, 0)

EXTENSION: str = '.exe' if PLATFORM == 'win32' else ''
ICO_PATH: str = 'res/icon.ico'
OUTPUT: str = 'output'
SCRIPT_NAME: str = 'main.py'
YEARS: str = str(datetime.datetime.now().year)
COPYRIGHT: str = f'Copyright (C) 2024-{YEARS} {AUTHOR}.All rights reserved.'

try:
    TERMINAL_COLUMNS: int = os.get_terminal_size().columns
    GRID_CONTENT: str = '='
except OSError:
    TERMINAL_COLUMNS: int = 1
    GRID_CONTENT: str = ''
GRID: str = GRID_CONTENT * TERMINAL_COLUMNS

if __name__ == '__main__':
    check_python_version()
    try:
        ready_nuitka()
        build_command = f'{sys.executable} -m '
        build_command += f'nuitka --standalone --onefile '
        build_command += f'--assume-yes-for-downloads '
        build_command += f'--no-deployment-flag=self-execution '
        build_command += f'--clang --windows-icon-from-ico="{ICO_PATH}" ' if PLATFORM == 'win32' else ''
        build_command += f'--include-package-data=pyrogram '
        build_command += f'--include-module=pygments.lexers.data '
        build_command += ''.join(map(lambda d: f'--include-data-dir="{d[0]}"="{d[1]}" ', ready_web()))
        build_command += f'--output-dir={OUTPUT} --output-filename="{SOFTWARE_SHORT_NAME}{EXTENSION}" --file-version={VERSION} --product-version={VERSION} --copyright="{COPYRIGHT}" '
        build_command += f'--low-memory ' if '--low-memory' in sys.argv else ''
        build_command += f'--remove-output ' if '--remove-output' in sys.argv else ''
        build_command += f'--disable-cache=all ' if '--disable-cache=all' in sys.argv else ''
        build_command += f'--script-name={SCRIPT_NAME}'
        build(build_command)
    except KeyboardInterrupt:
        print('键盘中断。')

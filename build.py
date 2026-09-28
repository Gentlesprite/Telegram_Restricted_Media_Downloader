# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/9/24 20:33
# File:build.py
import os
import sys
import datetime
import subprocess

from typing import Union
from pathlib import Path
from shutil import which

from module import (
    __version__,
    AUTHOR,
    SOFTWARE_SHORT_NAME
)


def ready_nuitka() -> None:
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


def ready_commit_hash() -> Union[str, None]:
    repo_root: Path = Path(__file__).resolve().parent
    try:
        completed = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip()
    except Exception:  # noqa.
        pass
    return None


def build(command):
    print(f'Command:\n{command}\n{GRID}', flush=True)
    print('Build in progress:', flush=True)
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

    print(f'{GRID}\nPython:\n{sys.version}\n{GRID}', flush=True)


VERSION_INFO = sys.version_info
PLATFORM: str = sys.platform
UV: str = 'uv ' if which('uv') and os.path.exists('uv.lock') else ''  # noqa.
MIN_PYTHON_VERSION: tuple = (3, 10, 0)
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
        commit_hash: Union[str, None] = ready_commit_hash()
        build_command = f'{sys.executable} -m '
        build_command += f'nuitka --standalone --onefile '
        build_command += f'--assume-yes-for-downloads '
        build_command += f'--no-deployment-flag=self-execution '
        build_command += f'--force-runtime-environment-variable=TRMD_COMMIT_HASH={commit_hash} ' if commit_hash else ''
        build_command += f'--force-runtime-environment-variable=TRMD_BUILD_TIME={datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")} '
        build_command += f'--clang --windows-icon-from-ico="{ICO_PATH}" ' if PLATFORM == 'win32' else ''
        build_command += f'--include-package-data=pyrogram '
        build_command += ''.join(map(lambda d: f'--include-data-dir="{d[0]}"="{d[1]}" ', ready_web()))
        build_command += f'--output-dir={OUTPUT} --output-filename="{SOFTWARE_SHORT_NAME}{EXTENSION}" --file-version={__version__} --product-version={__version__} --copyright="{COPYRIGHT}" '
        build_command += f'--low-memory ' if '--low-memory' in sys.argv else ''
        build_command += f'--remove-output ' if '--remove-output' in sys.argv else ''
        build_command += ''.join(f'{arg} ' for arg in sys.argv if arg.startswith('--disable-cache='))
        build_command += f'--script-name={SCRIPT_NAME}'
        build(build_command)
    except KeyboardInterrupt:
        pass

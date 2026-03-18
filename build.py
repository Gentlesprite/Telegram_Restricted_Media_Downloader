# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/7/22 22:37
# File:build.py
import os
import sys
import subprocess

from pathlib import Path
from shutil import which

from module import AUTHOR, __version__, __update_date__, SOFTWARE_SHORT_NAME
from module.ttyd import TTYD
from module.tmux import TMUX

platform: str = sys.platform
uv: str = 'uv ' if which('uv') and os.path.exists('uv.lock') else ''


def ready_zstandard():
    try:
        import zstandard
    except (ImportError, ModuleNotFoundError, NameError):
        subprocess.run(f'{uv}pip install zstandard', shell=True)


def ready_nuitka():
    try:
        import nuitka
    except (ImportError, ModuleNotFoundError, NameError):
        if sys.version_info >= (3, 13):
            subprocess.run(f'{uv}pip install nuitka==2.6.7', shell=True)
        else:
            subprocess.run(f'{uv}pip install nuitka', shell=True)


def ready_pymediainfo() -> tuple:
    try:
        import pymediainfo
        mediainfo_lib_meta = None
        mediainfo_lib_directory = os.path.dirname(pymediainfo.__file__)
        if platform == 'win32':
            file_name = 'MediaInfo.dll'
            file_path = os.path.join(mediainfo_lib_directory, file_name)
            if os.path.isfile(file_path):
                mediainfo_lib_meta = {
                    'file_name': file_name,
                    'file_path': file_path
                }
        else:
            file = 'libmediainfo.so'
            milf = []
            for i in os.listdir(mediainfo_lib_directory):
                if i.startswith(file):
                    milf.append(i)
            if milf:
                file_name = milf[0]
                file_path = os.path.join(mediainfo_lib_directory, file_name)
                if os.path.isfile(file_path):
                    mediainfo_lib_meta = {
                        'file_name': file_name,
                        'file_path': file_path
                    }
        if mediainfo_lib_meta:
            return mediainfo_lib_meta.get('file_name'), mediainfo_lib_meta.get('file_path')
        file_name = 'MediaInfo.dll' if platform == 'win32' else 'libmediainfo.so.0'
        path = str(Path(f'res/bin/{file_name}').resolve())
        if os.path.isfile(path):
            return file_name, path
        print(f'缺少依赖,请使用pip install pymediainfo安装依赖后重试。')
        sys.exit(1)
    except (ImportError, ModuleNotFoundError, NameError):
        if sys.version_info >= (3, 9):
            subprocess.run(f'{uv}pip install pymediainfo==7.0.1', shell=True)
            subprocess.run([sys.executable] + sys.argv)
        else:
            print('python版本过低,请至少升级至3.9.x后重试。')
        sys.exit(1)


def ready_ttyd():
    file_name = TTYD.get_ttyd_executable()
    path = str(Path(f'res/bin/{file_name}').resolve())
    if os.path.isfile(path):
        return file_name, path
    print(f'未找到ttyd。')
    sys.exit(1)


def ready_tmux():
    file_name = TMUX.get_tmux_executable()
    path = str(Path(f'res/bin/{file_name}').resolve())
    if os.path.isfile(path):
        return file_name, path
    print('未找到tmux。')
    sys.exit(1)


def build(command):
    print(command)
    subprocess.run(command, shell=True)


if __name__ == '__main__':
    try:
        ready_nuitka()
        ready_zstandard()
        media_info_lib_filename, media_info_lib_path = ready_pymediainfo()
        ttyd_filename, ttyd_path = ready_ttyd()
        tmux_filename, tmux_path = ready_tmux()
        extension = '.exe' if platform == 'win32' else ''
        ico_path = 'res/icon.ico'
        output = 'output'
        main = 'main.py'
        years = __update_date__[:4]
        include_module = '--include-module=pygments.lexers.data'
        copy_right = f'Copyright (C) 2024-{years} {AUTHOR}.All rights reserved.'
        build_command = f'nuitka --standalone --onefile {include_module} '
        build_command += f'--output-dir={output} --file-version={__version__} --product-version={__version__} '
        build_command += f'--windows-icon-from-ico="{ico_path}" --assume-yes-for-downloads '
        build_command += f'--output-filename="{SOFTWARE_SHORT_NAME}{extension}" --copyright="{copy_right}" --msvc=latest '
        build_command += f'--include-data-file="{media_info_lib_path}"={media_info_lib_filename} '
        build_command += f'--include-data-file="{ttyd_path}"={ttyd_filename} '
        build_command += f'--include-data-file="{tmux_path}"={tmux_filename} '
        build_command += f'--remove-output '
        build_command += f'--no-deployment-flag=self-execution '
        build_command += f'--script-name={main}'
        build(build_command)
    except KeyboardInterrupt:
        print('键盘中断。')

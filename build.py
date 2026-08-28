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

from module import (
    AUTHOR,
    __version__,
    __update_date__,
    SOFTWARE_SHORT_NAME
)
from module.ttyd import TTYD
from module.tmux import TMUX

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


def ready_pyinstaller():
    try:
        import PyInstaller
        return PyInstaller.__version__
    except (ImportError, ModuleNotFoundError, NameError):
        subprocess.run(f'{UV}pip install pyinstaller', shell=True)
        print('缺少PyInstaller依赖已自动安装,正在重启...')
        subprocess.run([sys.executable] + sys.argv)
        sys.exit(1)


def ready_pymediainfo() -> tuple:
    try:
        import pymediainfo
        mediainfo_lib_meta = None
        mediainfo_lib_directory = os.path.dirname(pymediainfo.__file__)
        if PLATFORM == 'win32':
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
        file_name = 'MediaInfo.dll' if PLATFORM == 'win32' else 'libmediainfo.so.0'
        path = str(Path(f'res/bin/{file_name}').resolve())
        if os.path.isfile(path):
            return file_name, path
        print(f'缺少依赖,请使用pip install pymediainfo安装依赖后重试。')
        sys.exit(1)
    except (ImportError, ModuleNotFoundError, NameError):
        if sys.version_info >= (3, 9):
            subprocess.run(f'{UV}pip install pymediainfo==7.0.1', shell=True)
            print(f'缺少pymediainfo依赖已自动安装,正在重启...')
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


def check_python_version():
    """检查Python版本是否满足：3.9.0 ≤ Python版本 < 3.14.0"""

    current_version = (VERSION_INFO.major, VERSION_INFO.minor, VERSION_INFO.micro)

    min_version = (3, 9, 0)
    max_version = (3, 14, 0)

    version_valid = (
            VERSION_INFO.major == 3
            and min_version <= current_version < max_version
    )

    if not version_valid:
        print(
            f'Python版本不满足要求\n当前版本:{sys.version}\n要求范围:3.9.0 ≤ Python 版本 < 3.14.0\n请安装符合要求的Python版本后重试。')
        sys.exit(1)

    print(f'{GRID}\nPython:\n{sys.version}\n{GRID}')


def gen_version_file(output_directory: str) -> str:
    """生成PyInstaller所需的Windows版本资源信息文件。"""
    years: str = __update_date__[:4]
    version_parts: list = __version__.split('.')
    filevers: tuple = tuple(int(part) for part in version_parts[:4])
    filevers: tuple = filevers + (0,) * (4 - len(filevers))
    version_info: str = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({', '.join(map(str, filevers))}),
    prodvers=({', '.join(map(str, filevers))}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', '{AUTHOR}'),
        StringStruct('FileDescription', '{SOFTWARE_SHORT_NAME}'),
        StringStruct('FileVersion', '{__version__}'),
        StringStruct('InternalName', '{SOFTWARE_SHORT_NAME}'),
        StringStruct('LegalCopyright', 'Copyright (C) 2024-{years} {AUTHOR}.All rights reserved.'),
        StringStruct('OriginalFilename', '{SOFTWARE_SHORT_NAME}.exe'),
        StringStruct('ProductName', '{SOFTWARE_SHORT_NAME}'),
        StringStruct('ProductVersion', '{__version__}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
    os.makedirs(output_directory, exist_ok=True)
    version_file: str = os.path.join(output_directory, 'version_info.txt')
    with open(version_file, 'w', encoding='UTF-8') as f:
        f.write(version_info)
    return version_file


def ready_upx() -> str:
    """定位UPX可执行文件,返回其所在目录,未找到则返回空字符串。"""
    upx_executable: str = 'upx.exe' if PLATFORM == 'win32' else 'upx'
    candidates: list = [which(upx_executable)]
    if os.environ.get('UPX_DIR'):
        candidates.append(os.path.join(os.environ.get('UPX_DIR'), upx_executable))
    candidates.append(str(Path(f'res/bin/{upx_executable}').resolve()))
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.dirname(os.path.abspath(candidate))
    return ''


def build(command):
    print(f'Command:\n{command}\n{GRID}')
    print('Build in progress:')
    subprocess.run(command, shell=True)


def main():
    check_python_version()
    pyinstaller_version: str = ready_pyinstaller()
    media_info_lib_filename, media_info_lib_path = ready_pymediainfo()
    ttyd_filename, ttyd_path = ready_ttyd()
    tmux_filename, tmux_path = ready_tmux()

    # 使用绝对路径,避免PyInstaller执行spec文件时相对路径解析错误(如output/output/version_info.txt)。
    ico_path: str = os.path.abspath('res/icon.ico')
    output_directory: str = os.path.abspath('output')
    dist_directory: str = os.path.join(output_directory, 'dist')
    work_directory: str = os.path.join(output_directory, 'build')
    separator: str = ';' if PLATFORM == 'win32' else ':'  # --add-data路径分隔符。

    command: str = (
        # 使用sys.executable -m PyInstaller,避免依赖venv激活状态。
        f'"{sys.executable}" -m PyInstaller --noconfirm --clean --onefile '
        f'--name {SOFTWARE_SHORT_NAME} '
        f'--distpath "{dist_directory}" --workpath "{work_directory}" --specpath "{output_directory}" '
        f'--icon "{ico_path}" '
        # pyrogram/kurigram存在大量动态导入与raw数据,pygments、pymediainfo需完整收集。
        f'--collect-all pyrogram --collect-all pygments --collect-all pymediainfo '
    )
    upx_directory: str = ready_upx()
    if upx_directory:
        command += f'--upx-dir "{upx_directory}" '
        print(f'UPX已启用,目录:{upx_directory}')
    else:
        print('未找到UPX,将不使用UPX压缩。如需启用,请将upx可执行文件放入res/bin目录、加入PATH或设置UPX_DIR环境变量。')
    if PLATFORM == 'win32':
        # Windows下readline由pyreadline3提供,需显式包含;附带版本资源信息。
        command += '--hidden-import readline '
        command += f'--version-file "{gen_version_file(output_directory)}" '
    # 资源文件打包到解压目录根目录,运行时通过sys._MEIPASS定位。
    for resource in (media_info_lib_path, ttyd_path, tmux_path):
        command += f'--add-data "{resource}{separator}." '
    command += 'main.py'

    print(f'{GRID}\nPyInstaller版本:{pyinstaller_version}\n{GRID}')
    build(command)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('键盘中断。')

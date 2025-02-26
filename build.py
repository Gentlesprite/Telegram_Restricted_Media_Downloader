# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/7/22 22:37
# File:build.py
import os
import sys

from module import AUTHOR, __version__, __update_date__, SOFTWARE_SHORT_NAME

ico_path = 'res/icon.ico'
output = 'output'
main = 'main.py'
years = __update_date__[:4]
include_module = '--include-module=pygments.lexers.data'
copy_right = f'Copyright (C) 2024-{years} {AUTHOR}.All rights reserved.'
build_command = f'nuitka --standalone --onefile {include_module} '
build_command += f'--output-dir={output} --file-version={__version__} --product-version={__version__} '
build_command += f'--windows-icon-from-ico="{ico_path}" --assume-yes-for-downloads '
build_command += f'--output-filename="{SOFTWARE_SHORT_NAME}.exe" --copyright="{copy_right}" --msvc=latest '
build_command += f'--remove-output '
build_command += f'--script-name={main}'


def build(command):
    print(command)
    try:
        import nuitka
        os.system(command)
    except ImportError:
        os.system('pip install nuitka==2.6.7') if sys.version_info >= (3, 13) else os.system('pip install nuitka')
        build(command)
    except KeyboardInterrupt:
        print('键盘中断。')


if __name__ == '__main__':
    build(build_command)

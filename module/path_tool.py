# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2023/11/13 20:34:13
# File:path_tool.py
import os
import re
import struct
import shutil
import datetime
import mimetypes
import unicodedata

from io import BytesIO
from typing import Optional, Union, List

from pyrogram.file_id import (
    FILE_REFERENCE_FLAG,
    PHOTO_TYPES,
    WEB_LOCATION_FLAG,
    FileType,
    b64_decode,
    rle_decode,
)

from module.enums import Extension

_mimetypes = mimetypes.MimeTypes()


def split_path(path: str) -> dict:
    """将传入路径拆分为目录名和文件名并以字典形式返回。"""
    directory, file_name = os.path.split(path)
    return {
        'directory': directory,
        'file_name': file_name
    }


def __is_exist(file_path: str) -> bool:
    """判断文件路径是否存在。"""
    return not os.path.isdir(file_path) and os.path.exists(file_path)


def compare_file_size(a_size: int, b_size: int) -> bool:
    """比较文件的大小是否一致。"""
    return a_size == b_size


def is_file_duplicate(save_directory: str, sever_file_size: int) -> bool:
    """判断文件是否重复。"""
    return __is_exist(save_directory) and compare_file_size(os.path.getsize(save_directory), sever_file_size)


def validate_title(title: str) -> str:
    """验证并修改(如果不合法)标题的合法性。"""
    r_str = r"[/\\:*?\"<>|\n]"  # '/ \ : * ? " < > |'
    new_title = re.sub(r_str, "_", title)
    return new_title


def truncate_filename(path: str, limit: int = 230) -> str:
    # https://github.com/tangyoha/telegram_media_downloader/blob/a3a9c2bed89ea8fd4db0b6616f055dfa11208362/utils/format.py#L195
    """将文件名截断到最大长度。
    Parameters
    ----------
    path: str
        文件名路径

    limit: int
        文件名长度限制（以UTF-8 字节为单位）

    Returns
    -------
    str
        如果文件名的长度超过限制，则返回截断后的文件名;否则返回原始文件名。
    """
    p, f = os.path.split(os.path.normpath(path))
    f, e = os.path.splitext(f)
    f_max = limit - len(e.encode('utf-8'))
    f = unicodedata.normalize('NFC', f)
    f_trunc = f.encode()[:f_max].decode('utf-8', errors='ignore')
    return os.path.join(p, f_trunc + e)


def gen_backup_config(old_path: str, absolute_backup_dir: str, error_config: bool = False) -> str:
    """备份配置文件。"""
    time_format: str = '%Y-%m-%d_%H-%M-%S'
    os.makedirs(absolute_backup_dir, exist_ok=True)
    error_flag: str = 'error_' if error_config else ''
    new_path = os.path.join(
        absolute_backup_dir,
        f'{error_flag}history_{datetime.datetime.now().strftime(time_format)}_config.yaml'
    )
    os.rename(old_path, new_path)
    return new_path


def safe_delete(file_p_d: str) -> bool:
    """删除文件或目录。"""
    try:
        if os.path.isdir(file_p_d):
            shutil.rmtree(file_p_d)
            return True
        elif os.path.isfile(file_p_d):
            os.remove(file_p_d)
            return True
    except FileNotFoundError:
        return True
    except PermissionError:
        return False
    except Exception as _:
        return False


def safe_scan_directory_file(
        directory: str
) -> List[str]:
    """扫描目录下的文件并返回文件名的列表。"""
    with os.scandir(directory) as entries:
        return [entry.name for entry in entries if entry.is_file()]


def safe_replace(origin_file: str, overwrite_file: str) -> dict:
    e_code = None
    if not os.path.isfile(origin_file):
        e_code = f'"{origin_file}"不存在或不是一个文件。'
        return {'e_code': e_code}

    try:
        os.replace(origin_file, overwrite_file)
    except OSError as e:
        if 'Invalid cross-device link' in str(e):
            try:
                shutil.move(origin_file, overwrite_file)
            except Exception as e2:
                e_code = f'移动文件失败,原因:"{e2}"'
        else:
            e_code = f'覆盖文件失败,原因:"{e}"'

    return {'e_code': e_code}


def move_to_save_directory(temp_file_path: str, save_directory: str) -> dict:
    """移动文件到指定路径。"""
    try:
        os.makedirs(save_directory, exist_ok=True)
        if os.path.isdir(save_directory):
            file_name: str = split_path(temp_file_path).get('file_name')
            if os.path.exists(os.path.join(save_directory, file_name)):
                return {'e_code': f'"{file_name}"已存在于保存路径无法移动,请手动解决冲突。'}
            shutil.move(temp_file_path, save_directory)
            return {'e_code': None}
        else:
            save_directory: str = os.path.join(os.getcwd(), 'downloads')
            os.makedirs(save_directory, exist_ok=True)
            shutil.move(temp_file_path, save_directory)
            return {'e_code': f'"{save_directory}"不是一个目录,已将文件下载到默认目录。'}
    except FileExistsError as e:
        return {'e_code': f'"{save_directory}"已存在,不能重复保存,原因:"{e}'}
    except PermissionError as e:
        return {'e_code': f'"{save_directory}"进程无法访问,可能是任务重复分配问题,原因:"{e}"'}
    except Exception as e:
        return {'e_code': f'意外的错误,原因:"{e}"'}


def get_extension(file_id: str, mime_type: str, dot: bool = True) -> str:
    """获取文件的扩展名。
    更多扩展名见: https://www.iana.org/assignments/media-types/media-types.xhtml
    """

    if not file_id:
        if dot:
            return '.unknown'
        return 'unknown'

    file_type = __get_file_type(file_id)

    guessed_extension = __guess_extension(mime_type)

    if file_type in PHOTO_TYPES:
        extension = Extension.PHOTO.get(mime_type, 'jpg')
    elif file_type == FileType.VOICE:
        extension = guessed_extension or 'ogg'
    elif file_type in (FileType.VIDEO, FileType.ANIMATION, FileType.VIDEO_NOTE):
        extension = guessed_extension or Extension.VIDEO.get(mime_type, 'mp4')
    elif file_type == FileType.DOCUMENT:
        if 'video' in mime_type:
            extension = guessed_extension or Extension.VIDEO.get(mime_type, 'mp4')
        elif 'image' in mime_type:
            extension = guessed_extension or Extension.PHOTO.get(mime_type, 'jpg')  # v1.2.8 修复获取图片格式时,实际指向为视频字典的错误。
        else:
            extension = guessed_extension or 'zip'
    elif file_type == FileType.STICKER:
        extension = guessed_extension or 'webp'
    elif file_type == FileType.AUDIO:
        extension = guessed_extension or 'mp3'
    else:
        extension = 'unknown'

    if dot:
        extension = '.' + extension
    return extension


def __guess_extension(mime_type: str) -> Optional[str]:
    """如果扩展名不是None，则从没有点的MIME类型返回中猜测文件扩展名。"""
    extension = _mimetypes.guess_extension(mime_type, strict=True)
    return extension[1:] if extension and extension.startswith('.') else extension


def __get_file_type(file_id: str) -> FileType:
    """获取文件类型。"""
    decoded = rle_decode(b64_decode(file_id))

    # File id versioning. Major versions lower than 4 don't have a minor version
    major = decoded[-1]

    if major < 4:
        buffer = BytesIO(decoded[:-1])
    else:
        buffer = BytesIO(decoded[:-2])

    file_type, _ = struct.unpack('<ii', buffer.read(8))

    file_type &= ~WEB_LOCATION_FLAG
    file_type &= ~FILE_REFERENCE_FLAG

    try:
        file_type = FileType(file_type)
    except ValueError as exc:
        raise ValueError(f'文件ID:"{file_id}",未知的文件类型:"{file_type}"。') from exc
    return file_type


def get_file_size(file_path: str, temp_ext: str = '.temp') -> int:
    """获取文件大小，支持临时扩展名。"""
    if os.path.exists(file_path):
        return os.path.getsize(file_path)
    elif os.path.exists(file_path + temp_ext):
        return os.path.getsize(file_path + temp_ext)
    else:
        return 0


def get_mime_from_extension(file_path: str) -> str:
    ext = file_path.split('.')[-1].lower()
    return Extension.ALL_REVERSE.get(ext, 'application/octet-stream')


def extract_full_extension(filename: Union[str, None]):
    """
    提取完整的文件扩展名，支持多段扩展名。
    """
    if not filename or not isinstance(filename, str):
        return None

    filename = filename.strip()
    if not filename:
        return None

    multi_ext_patterns = [
        r'\.(7z|rar|zip|r\d+|z\d+|s\d+|t\d+)\.\d+$',  # 压缩文件分卷格式。
        r'\.(tar|zip|7z|rar)(\.(gz|bz2|xz|zip|7z|rar))+$',  # 多段压缩格式
        r'\.(tar\.(gz|bz2|xz)|[a-z0-9]+\.\d+)$'  # 常见的多段扩展名
    ]

    for pattern in multi_ext_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            full_ext = match.group(0).lstrip('.')
            return full_ext

    # 普通文件,返回最后一个扩展名。
    base_ext = os.path.splitext(filename)[-1]
    if base_ext:
        return base_ext.lstrip('.')

    return None


def is_compressed_file(filename: Union[str, None]) -> bool:
    """
    判断是否为压缩包文件。
    """
    if not filename:
        return False

    # 压缩文件扩展名模式。
    compressed_patterns = [
        # 单扩展名压缩格式。
        r'\.(7z|rar|zip|tar|gz|bz2|xz|arj|cab|lzh|lzma|tgz|tbz2|txz|z|Z)$',
        # 多段扩展名压缩格式。
        r'\.(tar\.(gz|bz2|xz)|7z\.\d+|rar\.\d+|zip\.\d+)$',
        # 旧格式分卷。
        r'\.(r\d+|z\d+|s\d+|t\d+)$'
    ]

    for pattern in compressed_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return True

    return False

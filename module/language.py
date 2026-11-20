# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025-03-01 01:15:00
# File:language.py
import yaml
from functools import lru_cache

from module import GLOBAL_CONFIG_PATH

translations: dict = {
    'single': ['单文件', 'Single'],
    'group': ['组文件', 'Group'],
    'comment': ['评论文件', 'Comment'],
    'topic': ['话题文件', 'Topic'],
    'video': ['视频', 'Video'],
    'photo': ['图片', 'Photo'],
    'document': ['文档', 'Document'],
    'audio': ['音频', 'Audio'],
    'voice': ['语音', 'Voice'],
    'animation': ['GIF', 'GIF'],
    'video_note': ['视频笔记', 'Video note'],
    'live_photo': ['实况图片', 'Live photo'],
    'media': ['媒体', 'Media'],
    'pending': ['队列中', 'Pending'],
    'downloading': ['下载中', 'Downloading'],
    'uploading': ['上传中', 'Uploading'],
    'success': ['成功', 'Success'],
    'failure': ['失败', 'Failure'],
    'sent': ['已发送', 'Sent'],
    'skip': ['跳过', 'Skipped'],
    'retry': ['重试', 'Retry'],
    'link': ['[链接]', '[Link]'],
    'link type': ['[链接类型]', '[Link type]'],
    'size': ['[大小]', '[Size]'],
    'status': ['[状态]', '[Status]'],
    'file': ['[文件]', '[File]'],
    'error size': ['[错误大小]', '[Error size]'],
    'actual size': ['[实际大小]', '[Actual size]'],
    'already exist': ['[已存在]', '[Already exists]'],
    'channel': ['[频道]', '[Channel]'],
    'message id': ['[消息ID]', '[Message ID]'],
    'type': ['[类型]', '[Type]'],
    're-download': ['[重新下载]', '[Re-download]'],
    're-upload': ['[重新上传]', '[Re-upload]'],
    'retry times': ['[重试次数]', '[Retry times]'],
    'current download task': ['[当前下载任务数]', '[Current download tasks]'],
    'current upload task': ['[当前上传任务数]', '[Current upload tasks]'],
    'reason': ['原因', 'Reason'],
    'resume': ['[断点续传]', '[Resume]'],
    'download task': ['「📥下载任务」', '「📥Download task」'],
    'upload task': ['「📤上传任务」', '「📤Upload task」'],
    'download and upload task': ['「📥📤下载后上传任务」', '「📥📤Download and upload task」'],
    'forward success': ['转发成功', 'Forward success'],
    'forward failure': ['转发失败', 'Forward failure'],
    'skip forward': ['跳过转发', 'Skip forward'],
    'upload file part': ['[上传缺失分片]', '[Upload missing part]'],
    'IP': ['IP地址', 'IP address'],
    'port': ['端口', 'Port'],
    'username': ['账号', 'Username'],
    'password': ['密码', 'Password'],
    'earliest': ['最早', 'Earliest'],
    'latest': ['最新', 'Latest'],
    'not set': ['未设置', 'Not set'],
    'on': ['开', 'On'],
    'off': ['关', 'Off'],
    'chinese path warning': ['如果无法正常下载,请尝试不使用中文路径后重试。',
                             'If download fails, try not using a Chinese path.'],
    'invalid api id': ['意外的参数:"{value}",不是「纯数字」请重新输入!',
                       'Unexpected parameter "{value}", not a pure number, please re-enter!'],
    'api id too long': ['意外的参数,填写的"{value}"可能是「api_hash」,请填入正确的「api_id」!',
                        'Unexpected parameter "{value}" may be an api_hash, please enter the correct api_id!'],
    'api id need quotes': ['手动编辑config.yaml时,api_id需要有引号!',
                           'When manually editing config.yaml, api_id must be quoted!'],
    'directory not exist': ['目录:"{value}"不存在,是否创建? - 「y|n」(默认y):',
                            'Directory "{value}" does not exist, create it? - 「y|n」(default y):'],
    'directory created': ['成功创建目录:"{value}"', 'Directory "{value}" created successfully'],
    'invalid yes no': ['意外的参数:"{value}",支持的参数 - 「y|n」',
                       'Unexpected parameter "{value}", supported values - 「y|n」'],
    'unsupported dtype': ['"{value}"不在支持的下载类型中,已移除。',
                          '"{value}" is not a supported download type, removed.'],
    'system proxy found': ['获取到系统代理"{value}",是否自动填入? - 「y|n」(默认y):',
                           'System proxy "{value}" detected, auto-fill? - 「y|n」(default y):'],
    'auto proxy value': ['已从系统代理自动获取「{name}」为:「{value}」',
                         'Auto-filled 「{name}」 from system proxy as:「{value}」'],
    'proxy not config': ['请配置代理!', 'Please configure the proxy!'],
    'proxy auth empty': ['代理账号或密码未输入!', 'Proxy username or password not entered!'],
    'unknown': ['未知', 'Unknown']
}


@lru_cache(maxsize=1)
def get_language() -> str:
    """获取全局配置文件中的界面语言。"""
    try:
        with open(file=GLOBAL_CONFIG_PATH, mode='r', encoding='UTF-8') as f:
            config: dict = yaml.safe_load(f)
        language: str = (config or {}).get('language', '')
    except Exception:  # noqa.
        language: str = ''
    return language


def _t(text: str):
    try:
        from module.enums import Language
        language_index: dict = Language().index
        index: int = language_index.get(get_language(), language_index[Language.EN_US])
        if text in translations:
            return translations[text][index]
        else:
            return text
    except Exception:  # noqa.
        return text

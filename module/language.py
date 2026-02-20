# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/3/1 1:15
# File:language.py
translations: dict = {
    'single': ['单文件'],
    'group': ['组文件'],
    'comment': ['评论文件'],
    'topic': ['话题文件'],
    'video': ['视频'],
    'photo': ['图片'],
    'document': ['文档'],
    'audio': ['音频'],
    'voice': ['语音'],
    'animation': ['GIF'],
    'media': ['媒体'],
    'pending': ['队列中'],
    'downloading': ['下载中'],
    'uploading': ['上传中'],
    'success': ['成功'],
    'failure': ['失败'],
    'sent': ['已发送'],
    'skip': ['跳过'],
    'retry': ['重试'],
    'link': ['[链接]'],
    'link type': ['[链接类型]'],
    'size': ['[大小]'],
    'status': ['[状态]'],
    'file': ['[文件]'],
    'error size': ['[错误大小]'],
    'actual size': ['[实际大小]'],
    'already exist': ['[已存在]'],
    'channel': ['[频道]'],
    'message id': ['[消息ID]'],
    'type': ['[类型]'],
    're-download': ['[重新下载]'],
    're-upload': ['[重新上传]'],
    'retry times': ['[重试次数]'],
    'current download task': ['[当前下载任务数]'],
    'current upload task': ['[当前上传任务数]'],
    'reason': ['原因'],
    'resume': ['[断点续传]'],
    'download task': ['「📥下载任务」'],
    'upload task': ['「📤上传任务」'],
    'download and upload task': ['「📥📤下载后上传任务」'],
    'forward success': ['转发成功'],
    'forward failure': ['转发失败'],
    'skip forward': ['跳过转发'],
    'upload file part': ['[上传缺失分片]'],
    'IP': ['IP地址'],
    'port': ['端口'],
    'username': ['账号'],
    'password': ['密码']
}


def _t(text: str):
    try:
        if text in translations:
            return translations[text][0]
        else:
            return text
    except Exception:
        return text

# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/3/1 1:15
# File:language.py


translations: dict = {'single': ['单文件'],
                      'group': ['组文件'],
                      'comment': ['评论区文件'],
                      'video': ['视频'],
                      'photo': ['图片'],
                      'document': ['文档'],
                      'downloading': ['下载中'],
                      'success': ['成功'],
                      'failure': ['失败'],
                      'skip': ['跳过'],
                      'retry': ['重试'],
                      '[link]': ['[链接]'],
                      '[link type]': ['[链接类型]'],
                      '[size]': ['[大小]'],
                      '[status]': ['[状态]'],
                      '[file]': ['[文件]'],
                      '[error_size]': ['[错误大小]'],
                      '[actual size]': ['[实际大小]'],
                      '[already exist]': ['[已存在]'],
                      '[channel]': ['[频道]'],
                      '[type]': ['[类型]'],
                      '[reload]': ['重新下载'],
                      '[reload times]': ['重试次数'],
                      '[current task]': ['当前任务数'],
                      'reason': ['原因']}


def _t(text: str):
    try:
        if text in translations:
            return translations[text][0]
        else:
            return text
    except Exception as _:
        return text

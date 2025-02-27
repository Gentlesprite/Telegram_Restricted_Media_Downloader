# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/2/25 1:11
# File:stdio.py
import qrcode
from rich.style import Style
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, TransferSpeedColumn

from module import log, console, README, SOFTWARE_FULL_NAME, __version__, __copyright__, __license__
from module.path_tool import get_terminal_width
from module.enums import DownloadType, KeyWord, GradientColor, ProcessConfig, Banner, QrcodeRender


class StatisticalTable:
    def __init__(self):
        self.skip_video, self.skip_photo = set(), set()
        self.success_video, self.success_photo = set(), set()
        self.failure_video, self.failure_photo = set(), set()

    def print_count_table(self, download_type: list, record_dtype: set) -> None:
        """打印统计的下载信息的表格。"""
        header: tuple = ('种类&状态', '成功下载', '失败下载', '跳过下载', '合计')
        download_type.remove(
            DownloadType.DOCUMENT.text) if DownloadType.DOCUMENT.text in download_type else None
        success_video: int = len(self.success_video)
        failure_video: int = len(self.failure_video)
        skip_video: int = len(self.skip_video)
        success_photo: int = len(self.success_photo)
        failure_photo: int = len(self.failure_photo)
        skip_photo: int = len(self.skip_photo)
        total_video: int = sum([success_video, failure_video, skip_video])
        total_photo: int = sum([success_photo, failure_photo, skip_photo])
        rdt_length: int = len(record_dtype)
        if rdt_length == 1:
            _compare_dtype: list = list(record_dtype)[0]
            if _compare_dtype == DownloadType.VIDEO.text:  # 只有视频的情况。
                video_table = PanelTable(title='视频下载统计',
                                         header=header,
                                         data=[
                                             [DownloadType.t(DownloadType.VIDEO.text),
                                              success_video,
                                              failure_video,
                                              skip_video,
                                              total_video],
                                             ['合计', success_video,
                                              failure_video,
                                              skip_video,
                                              total_video]
                                         ]
                                         )
                video_table.print_meta()
            if _compare_dtype == DownloadType.PHOTO.text:  # 只有图片的情况。
                photo_table = PanelTable(title='图片下载统计',
                                         header=header,
                                         data=[
                                             [DownloadType.t(DownloadType.PHOTO.text),
                                              success_photo,
                                              failure_photo,
                                              skip_photo,
                                              total_photo],
                                             ['合计', success_photo,
                                              failure_photo,
                                              skip_photo,
                                              total_photo]
                                         ]
                                         )
                photo_table.print_meta()
        elif rdt_length == 2:
            media_table = PanelTable(title='媒体下载统计',
                                     header=header,
                                     data=[
                                         [DownloadType.t(DownloadType.VIDEO.text),
                                          success_video,
                                          failure_video,
                                          skip_video,
                                          total_video],
                                         [DownloadType.t(DownloadType.PHOTO.text),
                                          success_photo,
                                          failure_photo,
                                          skip_photo,
                                          total_photo],
                                         ['合计', sum([success_video, success_photo]),
                                          sum([failure_video, failure_photo]),
                                          sum([skip_video, skip_photo]),
                                          sum([total_video, total_photo])]
                                     ]
                                     )
            media_table.print_meta()

    @staticmethod
    def print_link_table(link_info: dict) -> bool or str:
        """打印统计的下载链接信息的表格。"""
        try:
            data: list = []
            for index, (link, info) in enumerate(link_info.items(), start=1):
                complete_num = int(info.get('complete_num'))
                member_num = int(info.get('member_num'))
                try:
                    rate = round(complete_num / member_num * 100, 2)
                except ZeroDivisionError:
                    rate = 0
                complete_rate = f'{complete_num}/{member_num}[{rate}%]'
                file_names = '\n'.join(info.get('file_name'))
                error_msg = info.get('error_msg')
                if not error_msg:
                    error_info = ''
                elif 'all_member' in error_msg:
                    error_info = str(error_msg.get('all_member'))
                else:
                    error_info = '\n'.join([f'{fn}: {err}' for fn, err in error_msg.items()])
                data.append([index, link, file_names, complete_rate, error_info])
            if data:
                panel_table = PanelTable(title='下载链接统计',
                                         header=('编号', '链接', '文件名', '完成率', '错误信息'),
                                         data=data,
                                         show_lines=True)
                panel_table.print_meta()
                return True
            else:
                return False
        except Exception as e:
            log.error(f'打印下载链接统计表时出错,{KeyWord.REASON}:"{e}"')
            return e

    @staticmethod
    def print_config_table(enable_proxy: dict or None, links: str, download_type: list, proxy: dict) -> None:
        """打印用户所填写配置文件的表格。"""
        try:
            if enable_proxy:
                console.log(GradientColor.gen_gradient_text(
                    text='当前正在使用代理!',
                    gradient_color=GradientColor.GREEN2BLUE_10))
                proxy_key: list = []
                proxy_value: list = []
                for i in proxy.items():
                    if i[0] not in ['username', 'password']:
                        key, value = i
                        proxy_key.append(key)
                        proxy_value.append(value)
                proxy_table = PanelTable(title='代理配置', header=tuple(proxy_key), data=[proxy_value])
                proxy_table.print_meta()
            else:
                console.log(GradientColor.gen_gradient_text(text='当前没有使用代理!',
                                                            gradient_color=GradientColor.new_life))
        except Exception as e:
            log.error(f'打印代理配置表时出错,{KeyWord.REASON}:"{e}"')
        try:
            # 展示链接内容表格。
            with open(file=links, mode='r', encoding='UTF-8') as _:
                res: list = [content.strip() for content in _.readlines() if content.strip()]
            if res:
                format_res: list = []
                for i in enumerate(res, start=1):
                    format_res.append(list(i))
                link_table = PanelTable(title='链接内容', header=('编号', '链接'),
                                        data=format_res)
                link_table.print_meta()
        except (FileNotFoundError, PermissionError, AttributeError) as e:  # v1.1.3 用户错误填写路径提示。
            log.error(f'读取"{links}"时出错,{KeyWord.REASON}:"{e}"')
        except Exception as e:
            log.error(f'打印链接内容统计表时出错,{KeyWord.REASON}:"{e}"')
        try:
            _dtype: list = download_type.copy()  # 浅拷贝赋值给_dtype,避免传入函数后改变原数据。
            data: list = [[DownloadType.t(DownloadType.VIDEO.text),
                           ProcessConfig.get_dtype(_dtype).get('video')],
                          [DownloadType.t(DownloadType.PHOTO.text),
                           ProcessConfig.get_dtype(_dtype).get('photo')]]
            download_type_table = PanelTable(title='下载类型', header=('类型', '是否下载'), data=data)
            download_type_table.print_meta()
        except Exception as e:
            log.error(f'打印下载类型统计表时出错,{KeyWord.REASON}:"{e}"')


class PanelTable:
    def __init__(self, title: str, header: tuple, data: list, styles: dict = None, show_lines: bool = False):
        self.table = Table(title=title, highlight=True, show_lines=show_lines)
        self.table.title_style = Style(color='white', bold=True)
        # 添加列。
        for _, col in enumerate(header):
            style = styles.get(col, {}) if styles else {}
            self.table.add_column(col, **style)

        # 添加数据行。
        for row in data:
            self.table.add_row(*map(str, row))  # 确保数据项是字符串类型，防止类型错误。

    def print_meta(self):
        console.print(self.table, justify='center')


class MetaData:
    @staticmethod
    def print_current_task_num(num: int) -> None:
        console.log(f'[当前任务数]:{num}。', justify='right', style='#B1DB74')

    @staticmethod
    def check_run_env() -> bool:  # 检测是windows平台下控制台运行还是IDE运行。
        try:
            from ctypes import windll  # v1.2.9 避免非Windows平台运行时报错。
            return windll.kernel32.SetConsoleTextAttribute(windll.kernel32.GetStdHandle(-0xb), 0x7)
        except ImportError:  # v1.2.9 抛出错误代表非Windows平台。
            return True

    @staticmethod
    def pay():
        if MetaData.check_run_env():  # 是终端才打印,生产环境会报错。
            try:
                console.print(
                    MetaData.__qr_terminal_str(
                        'wxp://f2f0g8lKGhzEsr0rwtKWTTB2gQzs9Xg9g31aBvlpbILowMTa5SAMMEwn0JH1VEf2TGbS'),
                    justify='center')
                console.print(
                    GradientColor.gen_gradient_text(text='微信扫码支持作者,您的支持是我持续更新的动力。',
                                                    gradient_color=GradientColor.YELLOW2GREEN_10),
                    justify='center')
            except Exception as _:
                return _

    @staticmethod
    def print_meta():
        console.print(GradientColor.gen_gradient_text(
            text=Banner.C,
            gradient_color=GradientColor.generate_gradient(
                start_color='#fa709a',
                end_color='#fee140',
                steps=10)),
            style='blink',
            highlight=False)
        console.print(f'[bold]{SOFTWARE_FULL_NAME} v{__version__}[/bold],\n[i]{__copyright__}[/i]'
                      )
        console.print(f'Licensed under the terms of the {__license__}.', end='\n')
        console.print(GradientColor.gen_gradient_text('\t软件免费使用!并且在GitHub开源,如果你付费那就是被骗了。',
                                                      gradient_color=GradientColor.BLUE2PURPLE_14))

    @staticmethod
    def suitable_units_display(number: int) -> str:
        result: dict = MetaData.__determine_suitable_units(number)
        return result.get('number') + result.get('unit')

    @staticmethod
    def __determine_suitable_units(number, unit=None) -> dict:
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        if unit in units:
            index = units.index(unit)
            value = number / (1024 ** index)
            return {'number': float('{:.2f}'.format(value)), 'unit': unit}
        else:
            values = [number]
            for i in range(len(units) - 1):
                if values[i] >= 1024:
                    values.append(values[i] / 1024)
                else:
                    break
            return {'number': '{:.2f}'.format(values[-1]), 'unit': units[len(values) - 1]}

    @staticmethod
    def print_helper():
        console.print(Markdown('# 配置文件说明'))
        console.print(Markdown(README))

    @staticmethod
    def __qr_terminal_str(str_obj: str, version: int = 1, render: callable = QrcodeRender.render_2by1) -> str:
        qr = qrcode.QRCode(version)
        qr.add_data(str_obj)
        qr.make()
        qr_row: int = len(qr.modules) + 2
        qr_col: int = len(qr.modules[0]) + 2
        qr_map: list = [[False for _ in range(qr_col)] for _ in range(qr_row)]
        for row_id, row in enumerate(qr.modules):
            for col_id, pixel in enumerate(row):
                qr_map[row_id + 1][col_id + 1] = pixel
        return render(qr_map)


class ProgressBar:
    def __init__(self):
        self.progress = Progress(TextColumn('[bold blue]{task.fields[filename]}', justify='right'),
                                 BarColumn(bar_width=max(int(get_terminal_width() * 0.2), 1)),
                                 '[progress.percentage]{task.percentage:>3.1f}%',
                                 '•',
                                 '[bold green]{task.fields[info]}',
                                 '•',
                                 TransferSpeedColumn(),
                                 '•',
                                 TimeRemainingColumn(),
                                 console=console
                                 )

    @staticmethod
    def download_bar(current, total, progress, task_id) -> None:
        progress.update(task_id,
                        completed=current,
                        info=f'{MetaData.suitable_units_display(current)}/{MetaData.suitable_units_display(total)}',
                        total=total)

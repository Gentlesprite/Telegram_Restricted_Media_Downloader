# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2025/2/25 1:32
# File:config.py
import os
import sys
import datetime
import platform

import yaml

from module import log, console, CustomDumper
from module.path_tool import gen_backup_config, safe_delete
from module.enums import KeyWord, GetStdioParams, ProcessConfig


class Config:
    DIRECTORY_NAME: str = os.path.dirname(os.path.abspath(sys.argv[0]))  # 获取软件工作绝对目录。
    CONFIG_NAME: str = 'config.yaml'  # 配置文件名。
    BOT_NAME: str = 'TRMD_BOT'
    CONFIG_PATH: str = os.path.join(DIRECTORY_NAME, CONFIG_NAME)
    CONFIG_TEMPLATE: dict = {
        'api_id': None,
        'api_hash': None,
        'bot_token': None,
        'proxy': {
            'enable_proxy': None,
            'scheme': None,
            'hostname': None,
            'port': None,
            'username': None,
            'password': None
        },
        'links': None,
        'save_directory': None,  # v1.3.0 将配置文件中save_path的参数名修改为save_directory。
        'max_download_task': None,
        'is_shutdown': None,
        'download_type': None
    }
    TEMP_DIRECTORY: str = os.path.join(os.getcwd(), 'temp')
    BACKUP_DIRECTORY: str = 'ConfigBackup'
    ABSOLUTE_BACKUP_DIRECTORY: str = os.path.join(DIRECTORY_NAME, BACKUP_DIRECTORY)
    WORK_DIRECTORY: str = os.path.join(os.getcwd(), 'sessions')

    def __init__(self, guide: bool = True):
        self.platform: str = platform.system()
        self.history_timestamp: dict = {}
        self.input_link: list = []
        self.last_record: dict = {}
        self.difference_timestamp: dict = {}
        self.download_type: list = []
        self.record_dtype: set = set()
        self.config_path: str = Config.CONFIG_PATH
        self.work_directory: str = Config.WORK_DIRECTORY
        self.temp_directory: str = Config.TEMP_DIRECTORY
        self.record_flag: bool = False
        self.modified: bool = False
        self.get_last_history_record()
        self.is_change_account: bool = True
        self.re_config: bool = False
        self.config_guide() if guide else None
        self.config: dict = self.load_config()  # v1.3.0 修复重复询问重新配置文件。
        self.api_hash = self.config.get('api_hash')
        self.api_id = self.config.get('api_id')
        self.bot_token = self.config.get('bot_token')
        self.download_type: list = self.config.get('download_type')
        self.is_shutdown: bool = self.config.get('is_shutdown')
        self.links: str = self.config.get('links')
        self.max_download_task: int = self.config.get('max_download_task') if isinstance(
            self.config.get('max_download_task'), int) else 3
        self.proxy: dict = self.config.get('proxy', {})
        self.enable_proxy = self.proxy if self.proxy.get('enable_proxy') else None
        self.save_directory: str = self.config.get('save_directory')

    def get_last_history_record(self) -> None:
        """获取最近一次保存的历史配置文件。"""
        # 首先判断是否存在目录文件。
        try:
            res: list = os.listdir(Config.ABSOLUTE_BACKUP_DIRECTORY)
        except FileNotFoundError:
            return
        except Exception as e:
            log.error(f'读取历史文件时发生错误,{KeyWord.REASON}:"{e}"')
            return
        file_start: str = 'history_'
        file_end: str = '_config.yaml'

        now_timestamp: float = datetime.datetime.now().timestamp()  # 获取当前的时间戳。
        if res:
            for i in res:  # 找出离当前时间最近的配置文件。
                try:
                    if i.startswith(file_start) and i.endswith(file_end):
                        format_date_str = i.replace(file_start, '').replace(file_end, '').replace('_', ' ')
                        to_datetime_obj = datetime.datetime.strptime(format_date_str, '%Y-%m-%d %H-%M-%S')
                        timestamp = to_datetime_obj.timestamp()
                        self.history_timestamp[timestamp] = i
                except ValueError:
                    pass
                except Exception as _:
                    pass
            for i in self.history_timestamp.keys():
                self.difference_timestamp[now_timestamp - i] = i
            if self.history_timestamp:  # 如果有符合条件的历史配置文件。
                self.last_record: dict = self.__find_history_config()

        else:
            return

    def __find_history_config(self) -> dict:
        """找到历史配置文件。"""
        if not self.history_timestamp:
            return {}
        if not self.difference_timestamp:
            return {}
        try:
            min_key: int = min(self.difference_timestamp.keys())
            min_diff_timestamp: str = self.difference_timestamp.get(min_key)
            min_config_file: str = self.history_timestamp.get(min_diff_timestamp)
            if not min_config_file:
                return {}
            last_config_file: str = os.path.join(Config.ABSOLUTE_BACKUP_DIRECTORY, min_config_file)  # 拼接文件路径。
            with open(file=last_config_file, mode='r', encoding='UTF-8') as f:
                config: dict = yaml.safe_load(f)
            last_record: dict = self.__check_params(config, history=True)  # v1.1.6修复读取历史如果缺失字段使得flag置True。

            if last_record == Config.CONFIG_TEMPLATE:
                # 从字典中删除当前文件。
                self.history_timestamp.pop(min_diff_timestamp, None)
                self.difference_timestamp.pop(min_key, None)
                # 递归调用。
                return self.__find_history_config()
            else:
                return last_record
        except Exception as _:
            return {}

    def __check_params(self, config: dict, history=False) -> dict:
        """检查配置文件的参数是否完整。"""
        # 如果 config 为 None，初始化为一个空字典。
        if config is None:
            config = {}

        def add_missing_keys(target, template, log_message) -> None:
            """添加缺失的配置文件参数。"""
            for key, value in template.items():
                if key not in target:
                    target[key] = value
                    if not history:
                        console.log(log_message.format(key))
                        self.modified = True
                        self.record_flag = True

        def remove_extra_keys(target, template, log_message) -> None:
            """删除多余的配置文件参数。"""
            keys_to_remove: list = [key for key in target.keys() if key not in template]
            for key in keys_to_remove:
                target.pop(key)
                if not history:
                    console.log(log_message.format(key))
                    self.record_flag = True

        # 处理父级参数。
        add_missing_keys(target=config, template=Config.CONFIG_TEMPLATE, log_message='"{}"不在配置文件中,已添加。')
        # 特殊处理 proxy 参数。
        if 'proxy' in config:
            proxy_template = Config.CONFIG_TEMPLATE.get('proxy')
            proxy_config = config.get('proxy')

            # 确保 proxy_config 是字典。
            if not isinstance(proxy_config, dict):
                proxy_config: dict = {}
                config['proxy'] = proxy_config

            add_missing_keys(proxy_config, proxy_template, '"{}"不在proxy配置中,已添加。')
            remove_extra_keys(proxy_config, proxy_template, '"{}"不在proxy模板中,已删除。')

        # 删除父级模板中没有的字段。
        remove_extra_keys(config, Config.CONFIG_TEMPLATE, '"{}"不在模板中,已删除。')

        return config

    def load_config(self) -> dict:
        """加载一次当前的配置文件,并附带合法性验证、缺失参数的检测以及各种异常时的处理措施。"""
        config: dict = Config.CONFIG_TEMPLATE.copy()
        try:
            if not os.path.exists(self.config_path):
                with open(file=self.config_path, mode='w', encoding='UTF-8') as f:
                    yaml.dump(Config.CONFIG_TEMPLATE, f, Dumper=CustomDumper)
                console.log('未找到配置文件,已生成新的模板文件. . .')
                self.re_config = True  # v1.3.4 修复配置文件不存在时,无法重新生成配置文件的问题。
            with open(self.config_path, 'r') as f:
                config: dict = yaml.safe_load(f)  # v1.1.4 加入对每个字段的完整性检测。
            compare_config: dict = config.copy()
            config: dict = self.__check_params(config)  # 检查所有字段是否完整,modified代表是否有修改记录(只记录缺少的)
            if config != compare_config or config == Config.CONFIG_TEMPLATE:  # v1.3.4 修复配置文件所有参数都为空时报错问题。
                self.re_config = True
        except UnicodeDecodeError as e:  # v1.1.3 加入配置文件路径是中文或特殊字符时的错误提示,由于nuitka打包的性质决定,
            # 中文路径无法被打包好的二进制文件识别,故在配置文件时无论是链接路径还是媒体保存路径都请使用英文命名。
            self.re_config = True
            log.error(
                f'读取配置文件遇到编码错误,可能保存路径中包含中文或特殊字符的文件夹。已生成新的模板文件. . .{KeyWord.REASON}:"{e}"')
            self.backup_config(config, error_config=self.re_config)
        except Exception as e:
            self.re_config = True
            console.print('「注意」链接路径和保存路径不能有引号!', style='#B1DB74')
            log.error(f'检测到无效或损坏的配置文件。已生成新的模板文件. . .{KeyWord.REASON}:"{e}"')
            self.backup_config(config, error_config=self.re_config)
        finally:
            if config is None:
                self.re_config = True
                log.warning('检测到空的配置文件。已生成新的模板文件. . .')
                config: dict = Config.CONFIG_TEMPLATE.copy()
            return config

    def backup_config(self,
                      backup_config: dict,
                      error_config: bool = False,
                      force: bool = False) -> None:  # v1.2.9 更正backup_config参数类型。
        """备份当前的配置文件。"""
        if backup_config != Config.CONFIG_TEMPLATE or force:  # v1.2.9 修复比较变量错误的问题。
            backup_path: str = gen_backup_config(old_path=self.config_path,
                                                 absolute_backup_dir=Config.ABSOLUTE_BACKUP_DIRECTORY,
                                                 error_config=error_config)
            console.log(f'原来的配置文件已备份至"{backup_path}"', style='#B1DB74')
        else:
            console.log('配置文件与模板文件完全一致,无需备份。')

    def config_guide(self) -> None:
        """引导用户以交互式的方式修改、保存配置文件。"""
        pre_load_config: dict = self.load_config()
        gsp = GetStdioParams()
        # v1.1.0 更替api_id和api_hash位置,与telegram申请的api位置对应以免输错。
        try:
            if not self.modified and pre_load_config != Config.CONFIG_TEMPLATE:
                re_config: bool = gsp.get_is_re_config().get('is_re_config')
                if re_config:
                    self.re_config = re_config
                    pre_load_config: dict = Config.CONFIG_TEMPLATE.copy()
                    self.backup_config(backup_config=pre_load_config, error_config=False, force=True)
                    self.get_last_history_record()  # 更新到上次填写的记录。
                    self.is_change_account = gsp.get_is_change_account(valid_format='y|n').get(
                        'is_change_account')
                    if self.is_change_account:
                        if safe_delete(file_p_d=os.path.join(self.DIRECTORY_NAME, 'sessions')):
                            console.log('已删除旧会话文件,稍后需重新登录。')
                        else:
                            console.log(
                                '删除旧会话文件失败,请手动删除软件目录下的sessions文件夹,再进行下一步操作!')
            _api_id: str or None = pre_load_config.get('api_id')
            _api_hash: str or None = pre_load_config.get('api_hash')
            _bot_token: str or None = pre_load_config.get('bot_token')
            _links: str or None = pre_load_config.get('links')
            _save_directory: str or None = pre_load_config.get('save_directory')
            _max_download_task: int or None = pre_load_config.get('max_download_task') if isinstance(
                pre_load_config.get('max_download_task'), int) else None  # v1.4.0 修复同时下载任务数不询问是否配置问题。
            _download_type: list or None = pre_load_config.get('download_type')
            _is_shutdown: bool or None = pre_load_config.get('is_shutdown')
            _proxy_config: dict = pre_load_config.get('proxy', {})
            _enable_proxy: str or bool = _proxy_config.get('enable_proxy', False)
            _proxy_scheme: str or bool = _proxy_config.get('scheme', False)
            _proxy_hostname: str or bool = _proxy_config.get('hostname', False)
            _proxy_port: str or bool = _proxy_config.get('port', False)
            _proxy_username: str or bool = _proxy_config.get('username', False)
            _proxy_password: str or bool = _proxy_config.get('password', False)
            proxy_record: dict = self.last_record.get('proxy', {})  # proxy的历史记录。
            if any([not _api_id, not _api_hash, not _save_directory, not _max_download_task, not _download_type]):
                console.print('「注意」直接回车代表使用上次的记录。',
                              style='#B1DB74')
            if self.is_change_account or _api_id is None or _api_hash is None or self.re_config:
                if not _api_id:
                    api_id, record_flag = gsp.get_api_id(
                        last_record=self.last_record.get('api_id')).values()
                    if record_flag:
                        self.record_flag = record_flag
                        pre_load_config['api_id'] = api_id
                if not _api_hash:
                    api_hash, record_flag = gsp.get_api_hash(
                        last_record=self.last_record.get('api_hash'),
                        valid_length=32).values()
                    if record_flag:
                        self.record_flag = record_flag
                        pre_load_config['api_hash'] = api_hash
            if not _bot_token and self.re_config:
                enable_bot: bool = gsp.get_enable_bot(valid_format='y|n').get('enable_bot')
                if enable_bot:
                    bot_token, record_flag = gsp.get_bot_token(
                        last_record=self.last_record.get('bot_token'),
                        valid_format=':').values()
                    if record_flag:
                        self.record_flag = record_flag
                        pre_load_config['bot_token'] = bot_token
            if not _links or not _bot_token and self.re_config:
                links, record_flag = gsp.get_links(last_record=self.last_record.get('links'),
                                                   valid_format='.txt').values()
                if record_flag:
                    self.record_flag = record_flag
                    pre_load_config['links'] = links
            if not _save_directory or self.re_config:
                save_directory, record_flag = gsp.get_save_directory(
                    last_record=self.last_record.get('save_directory')).values()
                if record_flag:
                    self.record_flag = record_flag
                    pre_load_config['save_directory'] = save_directory
            if not _max_download_task or self.re_config:
                max_download_task, record_flag = gsp.get_max_download_task(
                    last_record=self.last_record.get('max_download_task')).values()
                if record_flag:
                    self.record_flag = record_flag
                    pre_load_config['max_download_task'] = max_download_task
            if not _download_type or self.re_config:
                download_type, record_flag = gsp.get_download_type(
                    last_record=self.last_record.get('download_type')).values()
                if record_flag:
                    self.record_flag = record_flag
                    pre_load_config['download_type'] = download_type
            if _is_shutdown is None or self.re_config:
                is_shutdown, _is_shutdown_record_flag = gsp.get_is_shutdown(
                    last_record=self.last_record.get('is_shutdown'),
                    valid_format='y|n').values()
                if _is_shutdown_record_flag:
                    self.record_flag = True
                    pre_load_config['is_shutdown'] = is_shutdown
            # 是否开启代理
            if not _enable_proxy and self.re_config:
                valid_format: str = 'y|n'
                is_enable_proxy, is_ep_record_flag = gsp.get_enable_proxy(
                    last_record=proxy_record.get('enable_proxy', False),
                    valid_format=valid_format).values()
                if is_ep_record_flag:
                    self.record_flag = True
                    _proxy_config['enable_proxy'] = is_enable_proxy
            # 如果需要使用代理。
            # 如果上面配置的enable_proxy为True或本来配置文件中的enable_proxy就为True。
            if _proxy_config.get('enable_proxy') is True or _enable_proxy is True:
                if ProcessConfig.is_proxy_input(proxy_config=_proxy_config):
                    if not _proxy_scheme:
                        scheme, record_flag = gsp.get_scheme(last_record=proxy_record.get('scheme'),
                                                             valid_format=['http', 'socks4',
                                                                           'socks5']).values()
                        if record_flag:
                            self.record_flag = True
                            _proxy_config['scheme'] = scheme
                    if not _proxy_hostname:
                        hostname, record_flag = gsp.get_hostname(
                            proxy_config=_proxy_config,
                            last_record=proxy_record.get('hostname'),
                            valid_format='x.x.x.x').values()
                        if record_flag:
                            self.record_flag = True
                            _proxy_config['hostname'] = hostname
                    if not _proxy_port:
                        port, record_flag = gsp.get_port(
                            proxy_config=_proxy_config,
                            last_record=proxy_record.get('port'),
                            valid_format='0~65535').values()
                        if record_flag:
                            self.record_flag = True
                            _proxy_config['port'] = port
                    if not all([_proxy_username, _proxy_password]):
                        username, password, record_flag = gsp.get_proxy_authentication().values()
                        if record_flag:
                            self.record_flag = True
                            _proxy_config['username'] = username
                            _proxy_config['password'] = password
        except KeyboardInterrupt:
            n: bool = True
            try:
                if self.record_flag:
                    print('\n')
                    if gsp.get_is_ki_save_config().get('is_ki_save_config'):
                        self.save_config(pre_load_config)
                        console.log('配置已保存!')
                    else:
                        console.log('不保存当前填写参数。')
                else:
                    raise SystemExit(0)
            except KeyboardInterrupt:
                n: bool = False
                print('\n')
                console.log('不保存当前填写参数(用户手动终止配置参数)。')
            finally:
                if n:
                    print('\n')
                    console.log('用户手动终止配置参数。')
                self.ctrl_c()
                raise SystemExit(0)
        self.save_config(pre_load_config)  # v1.3.0 修复不保存配置文件时,配置文件仍然保存的问题。

    def save_config(self, config: dict) -> None:
        """保存配置文件。"""
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)

    def ctrl_c(self):
        os.system('pause') if self.platform == 'Windows' else console.input('请按「Enter」键继续. . .')

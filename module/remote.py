# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2026/9/7 00:00:00
# File:remote.py
import os
import json
import time
import asyncio

from functools import partial
from urllib.request import Request, urlopen

from module import (
    log,
    AUTHOR,
    __version__,
    APPDATA_PATH,
    SOFTWARE_SHORT_NAME
)


class RemoteConfig(object):
    """远程配置,负责远程配置的获取、校验、缓存与解析。"""

    BRANCH: str = 'main'
    URLS: tuple = (
        f'https://cdn.jsdelivr.net/gh/{AUTHOR}/{SOFTWARE_SHORT_NAME}_CONFIG@{BRANCH}/config.json',
        f'https://fastly.jsdelivr.net/gh/{AUTHOR}/{SOFTWARE_SHORT_NAME}_CONFIG@{BRANCH}/config.json',
    )
    HEADERS: dict = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/124.0.0.0 Safari/537.36'
    }
    TIMEOUT: int = 8  # 单个远程地址的请求超时(秒)。
    TTL: int = 24 * 3600  # 本地缓存的有效期,同时作为远程获取失败后的重试间隔(秒)。
    PATH: str = os.path.join(APPDATA_PATH, '.REMOTE_CONFIG')
    DEFAULT_VERSION: str = __version__
    DEFAULT_REFERRAL: str = ''
    CONFIG: dict = {
        'version': (DEFAULT_VERSION, str),
        'referral': (DEFAULT_REFERRAL, str)
    }

    def default_config(self) -> dict:
        """按字段表生成一份内置默认配置,字段缺失或类型不符时都使用它。"""
        return {name: field[0] for name, field in self.CONFIG.items()}

    def verify(self, remote: dict) -> dict:
        """按字段表校验配置并补充缺失字段,忽略未知字段,保证新旧版本配置互相兼容。"""
        config: dict = {}
        for name, field in self.CONFIG.items():
            default, expected_type = field
            value = remote.get(name, default)
            # 字段缺失或类型不符时都退回默认值,避免单个脏字段导致整份配置失效。
            if not isinstance(value, expected_type):
                log.debug(f'Unexpected field value: "{name}={value}", using default: "{default}"')
                value = default
            config[name] = value
        return config

    async def read(self) -> dict:
        """读取配置,缓存未过期时直接使用,否则请求远程,失败时回退到缓存或内置默认值。"""
        default: dict = self.default_config()
        # 远程配置不可用时退回本地缓存,保证离线仍能使用上次的可用配置。
        cached: dict = self.cached_config()
        if cached:
            try:
                # 缓存文件在读取后被删除时视为已过期,直接请求远程。
                remaining: float = self.TTL - (time.time() - os.path.getmtime(self.PATH))
            except OSError:
                remaining: float = 0
            if remaining > 0:
                log.info(f'Using cached remote config from "{self.PATH}", '
                         f'remaining valid time: {remaining / 3600:.1f} hours')
                return cached
        config: dict = await self.fetch()
        self.save(config or cached or default)  # 无论获取成功与否都写入一次,以刷新修改时间,避免远程不可用时反复重试。
        return config or cached or default

    def save(self, config: dict) -> None:
        """把配置写入缓存文件,文件的修改时间即为缓存的生效时刻。"""
        try:
            with open(file=self.PATH, mode='w', encoding='UTF-8') as f:
                json.dump(config, f)
            log.info(f'Remote config cached successfully: {config}')
        except OSError as e:
            log.debug(f'Failed to write to the remote config cache due to {e}')

    async def fetch(self) -> dict:
        """依次尝试各个远程地址获取配置,全部失败时返回空字典。"""
        loop = asyncio.get_running_loop()
        for url in self.URLS:
            try:
                log.info(f'Getting remote config from "{url}".')
                request = Request(url=url, headers=self.HEADERS)
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, partial(urlopen, request, timeout=self.TIMEOUT)),
                    timeout=self.TIMEOUT
                )
                with response:
                    remote: dict = json.loads(response.read().decode('UTF-8'))
                config: dict = self.verify(remote)
                log.info(f'Successfully obtained remote config from "{url}": {config}')
                return config
            except Exception as e:
                # 单个地址失败时继续尝试下一个地址,全部失败才回退本地配置。
                log.info(f'Failed to obtain remote config from "{url}" due to {e}')
        log.info(f'All remote addresses are unavailable, using local default config: {self.default_config()}')
        return {}

    def cached_config(self) -> dict:
        """读取本地缓存中的配置,缓存不存在或不合法时返回空字典,不触发远程请求。"""
        try:
            if os.path.exists(self.PATH):
                with open(file=self.PATH, mode='r', encoding='UTF-8') as f:
                    return self.verify(json.load(f))
        except Exception as e:
            log.debug(f'Failed to read the remote config cache due to {e}')
        return {}


rc = RemoteConfig()

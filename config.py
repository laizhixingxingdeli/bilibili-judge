"""配置加载与B站API签名"""

import json
import hashlib
import os
import urllib.parse
from typing import Any


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(PROJECT_DIR, 'config')


def load_config() -> dict[str, Any]:
    """加载 config.json"""
    path = os.path.join(CONFIG_DIR, 'config.json')
    if not os.path.exists(path):
        raise FileNotFoundError(f'配置文件未找到: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_info() -> dict[str, Any]:
    """加载 info.json（登录凭据）"""
    path = os.path.join(CONFIG_DIR, 'info.json')
    if not os.path.exists(path):
        raise FileNotFoundError(f'登录凭据未找到: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_info(data: dict[str, Any]) -> None:
    """保存 info.json"""
    path = os.path.join(CONFIG_DIR, 'info.json')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False, separators=(',', ':')))


def tvsign(params: dict[str, str], appkey: str, appsec: str) -> dict[str, str]:
    """为B站TV端API参数签名"""
    params['appkey'] = appkey
    params = dict(sorted(params.items()))
    query = urllib.parse.urlencode(params)
    sign = hashlib.md5((query + appsec).encode()).hexdigest()
    params['sign'] = sign
    return params

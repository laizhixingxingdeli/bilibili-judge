"""B站登录认证：扫码登录 + Token刷新"""

import hashlib
import json
import logging
import os
import time
import urllib.parse

import qrcode_terminal
import requests

from config import tvsign, CONFIG_DIR, save_info, load_config

logger = logging.getLogger(__name__)


def first_login() -> dict:
    """首次扫码登录：生成二维码 → 扫码 → 保存info.json"""
    appkey = '4409e2ce8ffd12b8'
    appsec = '59b43e04ad6965f34319062b478f83dd'

    ts = int(time.time())
    auth = requests.post(
        'https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code',
        params=tvsign({'local_id': '0', 'ts': str(ts)}, appkey, appsec),
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                 'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'},
    ).json()

    url = auth['data']['url']
    qrcode_terminal.draw(url)
    logger.info('请使用B站手机APP扫码登录')

    while True:
        poll = requests.post(
            'https://passport.bilibili.com/x/passport-tv-login/qrcode/poll',
            params=tvsign({
                'auth_code': auth['data']['auth_code'],
                'local_id': '0',
                'ts': str(int(time.time())),
            }, appkey, appsec),
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                     'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'},
        ).json()

        code = poll['code']
        if code == 0:
            expires = int(poll['data']['token_info']['expires_in'])
            expiry = time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(time.time() + expires))
            logger.info(f'登录成功，有效期至 {expiry}')

            data = {
                'update_time': int(time.time() * 1000 + 0.5),
                'token_info': poll['data']['token_info'],
                'cookie_info': poll['data']['cookie_info'],
            }
            save_info(data)
            _sync_cookies(data)
            return data

        errors = {-3: 'API校验密匙错误', -400: '请求错误',
                   86038: '二维码已失效'}
        if code in errors:
            logger.error(errors[code])
            raise RuntimeError(errors[code])
        if code == 86039:
            time.sleep(5)
        else:
            logger.error(f'未知错误 (code={code})')
            raise RuntimeError(f'未知错误 (code={code})')


def refresh_token() -> bool:
    """刷新 Token（180天续期）"""
    from config import load_info, save_info

    appkey = '4409e2ce8ffd12b8'
    appsec = '59b43e04ad6965f34319062b478f83dd'

    info = load_info()
    token = info.get('token_info', {})

    rsp = requests.post(
        'https://passport.bilibili.com/api/v2/oauth2/refresh_token',
        params=tvsign({
            'access_key': token.get('access_token', ''),
            'refresh_token': token.get('refresh_token', ''),
            'ts': str(int(time.time())),
        }, appkey, appsec),
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        },
    )

    try:
        data = rsp.json()
    except Exception:
        logger.error('Token刷新响应解析失败')
        return False

    if data.get('code') != 0:
        logger.error(f'Token刷新失败: {data.get("message", "未知错误")}')
        return False

    ts = data.get('ts', int(time.time()))
    expires_in = int(data['data']['token_info']['expires_in'])
    expiry = time.strftime('%Y-%m-%d %H:%M:%S',
                           time.localtime(ts + expires_in))
    logger.info(f'Token刷新成功，有效期至 {expiry}')

    new_info = {
        'update_time': ts,
        'token_info': data['data']['token_info'],
        'cookie_info': data['data']['cookie_info'],
    }
    save_info(new_info)
    _sync_cookies(new_info)
    return True


def _sync_cookies(info: dict) -> None:
    """将info.json中的cookies同步到config.json"""
    config_path = os.path.join(CONFIG_DIR, 'config.json')
    config = load_config()

    cookies = info.get('cookie_info', {}).get('cookies', [])
    cookie_map = {c['name']: c['value'] for c in cookies}

    for user in config.get('users', []):
        cd = user.get('cookieDatas', {})
        if 'SESSDATA' in cookie_map:
            cd['SESSDATA'] = cookie_map['SESSDATA']
        if 'bili_jct' in cookie_map:
            cd['bili_jct'] = cookie_map['bili_jct']
        if 'DedeUserID' in cookie_map:
            cd['DedeUserID'] = cookie_map['DedeUserID']

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    logger.info('Cookies已同步到 config.json')

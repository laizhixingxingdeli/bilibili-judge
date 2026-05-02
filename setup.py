"""开箱即用配置向导：首次扫码登录 + 基础配置"""

import hashlib
import json
import logging
import os
import time
import urllib.parse

import qrcode
import requests

from config import PROJECT_DIR, CONFIG_DIR, load_config, save_info

logger = logging.getLogger('setup')

BANNER = r"""
╔══════════════════════════════════════════╗
║     B站 风纪委员 自动投票脚本 v2         ║
║          开箱即用配置向导                 ║
╚══════════════════════════════════════════╝
"""


def needs_setup() -> bool:
    """检查是否需要首次配置"""
    info_path = os.path.join(CONFIG_DIR, 'info.json')
    config_path = os.path.join(CONFIG_DIR, 'config.json')

    if not os.path.exists(config_path):
        return True
    if not os.path.exists(info_path):
        return True

    # 检查 info.json 是否有内容
    try:
        with open(info_path, 'r') as f:
            data = json.load(f)
        if not data.get('token_info'):
            return True
    except (json.JSONDecodeError, FileNotFoundError):
        return True

    return False


def check_cookie(config: dict) -> bool:
    """快速检查 cookie 是否有效（发起一次 B站 API 请求）"""
    from api import BiliAPI
    import asyncio

    async def _check():
        async with BiliAPI(config['http_header']) as api:
            user = config['users'][0]['cookieDatas']
            return await api.login_by_cookie(user)

    try:
        return asyncio.run(_check())
    except Exception:
        return False


def run_setup() -> None:
    """运行配置向导"""
    print(BANNER)
    print('检测到首次使用，开始配置...\n')

    # 1. 二维码登录
    _do_qrcode_login()

    # 2. 邮件配置
    _setup_email()

    # 3. 投票模式配置
    _setup_vote_mode()

    # 4. 完成
    print()
    print('✅ 配置完成！')
    print('现在运行 python judgement.py 即可开始自动投票')
    print()


def _do_qrcode_login() -> None:
    """扫码登录流程"""
    print('=' * 50)
    print('第一步：B站登录')
    print('=' * 50)

    appkey = '4409e2ce8ffd12b8'
    appsec = '59b43e04ad6965f34319062b478f83dd'

    def _tvsign(params):
        params['appkey'] = appkey
        params = dict(sorted(params.items()))
        query = urllib.parse.urlencode(params)
        sign = hashlib.md5((query + appsec).encode()).hexdigest()
        params['sign'] = sign
        return params

    # 获取二维码
    auth = requests.post(
        'https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code',
        params=_tvsign({'local_id': '0', 'ts': str(int(time.time()))}),
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
    ).json()

    url = auth['data']['url']
    auth_code = auth['data']['auth_code']

    # 生成二维码图片
    img_path = os.path.join(PROJECT_DIR, 'qrcode_login.png')
    img = qrcode.make(url)
    img.save(img_path)

    print(f'\n📱 二维码已生成: {img_path}')
    print('   请使用 B站 APP -> 扫一扫 扫描此二维码')
    print('   （如果无法扫码，请手动打开 B站 APP 扫码页面扫描）')
    print()
    input('   扫码后请按 Enter 键继续... (如果还没扫，现在扫码)')

    # 轮询等待扫码
    print('\n   正在确认登录结果...')
    for _ in range(60):  # 最多等 3 分钟
        poll = requests.post(
            'https://passport.bilibili.com/x/passport-tv-login/qrcode/poll',
            params=_tvsign({
                'auth_code': auth_code, 'local_id': '0',
                'ts': str(int(time.time())),
            }),
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'},
        ).json()

        code = poll.get('code')
        if code == 0:
            expires = int(poll['data']['token_info']['expires_in'])
            expiry = time.strftime('%Y-%m-%d %H:%M:%S',
                                   time.localtime(time.time() + expires))
            print(f'\n✅ 登录成功！有效期至 {expiry}')

            data = {
                'update_time': int(time.time() * 1000 + 0.5),
                'token_info': poll['data']['token_info'],
                'cookie_info': poll['data']['cookie_info'],
            }
            save_info(data)
            _sync_cookies(data)
            return

        elif code == 86039:
            print('.', end='', flush=True)
            time.sleep(3)
        elif code == 86038:
            print('\n❌ 二维码已失效，请重新运行')
            raise SystemExit(1)
        else:
            time.sleep(3)

    print('\n❌ 登录超时，请重新运行')
    raise SystemExit(1)


def _sync_cookies(info: dict) -> None:
    """同步 cookies 到 config.json"""
    config_path = os.path.join(CONFIG_DIR, 'config.json')

    # 如果 config.json 不存在，先生成一个默认的
    if not os.path.exists(config_path):
        default = {
            'appkey': '4409e2ce8ffd12b8',
            'appsec': '59b43e04ad6965f34319062b478f83dd',
            'email': {
                'sender': '',
                'password': '',
                'recipient': '',
                'smtp_server': 'smtp.qq.com',
                'smtp_port': 587,
            },
            'http_header': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Connection': 'keep-alive',
            },
            'default_vote': {'mode': 1, 'vote': [0, 1], 'once': True},
            'users': [{'cookieDatas': {'SESSDATA': '', 'bili_jct': '', 'DedeUserID': ''}}],
            'push': {'enable': False, 'msgtpye': ['CookieExpires', 'UnknownError', 'DailyMissions'],
                     'wxpush': {'enable': False}, 'tgpush': {'enable': False},
                     'server': {'enable': False}, 'ijingniu': {'enable': False},
                     'pushplus': {'enable': False}},
        }
        config = default
    else:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

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
        json.dump(config, f, ensure_ascii=False, indent=2)
    print('   Cookies 已保存')


def _setup_email() -> None:
    """配置邮件通知"""
    print()
    print('=' * 50)
    print('第二步：邮件通知（可选）')
    print('=' * 50)
    print('当 cookie 过期或脚本出错时，会发送邮件提醒')
    print('如不需要，直接回车跳过\n')

    enable = input('是否配置邮件通知？(y/N): ').strip().lower()
    if enable != 'y':
        return

    sender = input('发件人邮箱 (QQ邮箱): ').strip()
    password = input('SMTP授权码 (QQ邮箱需开启SMTP服务获取): ').strip()
    recipient = input('收件人邮箱 (默认同发件人): ').strip() or sender

    config_path = os.path.join(CONFIG_DIR, 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    config['email'] = {
        'sender': sender,
        'password': password,
        'recipient': recipient,
        'smtp_server': 'smtp.qq.com',
        'smtp_port': 587,
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print('✅ 邮件通知已配置')


def _setup_vote_mode() -> None:
    """配置投票模式"""
    print()
    print('=' * 50)
    print('第三步：投票模式')
    print('=' * 50)
    print('  模式1: 有众议观点 -> 跟最多的投票')
    print('         无观点     -> 按默认选项投票')
    print('  模式2: 有众议观点 -> 跟最多的投票')
    print('         无观点     -> 暂存，所有案件拉完后再统一投默认票')
    print()

    mode = input('选择投票模式 (1/2, 默认1): ').strip() or '1'

    print()
    print('默认投票选项（无众议观点时使用）:')
    print('  0 = 违规   1 = 不违规')
    votes_str = input('输入两个数字用逗号分隔 (默认 0,1): ').strip() or '0,1'
    votes = [int(v.strip()) for v in votes_str.split(',') if v.strip().isdigit()]

    print()
    once = input('无案件时是否持续等待？(Y/n, 默认等待): ').strip().lower()
    once_val = once != 'n'

    config_path = os.path.join(CONFIG_DIR, 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    config['default_vote'] = {
        'mode': int(mode),
        'vote': votes,
        'once': once_val,
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f'✅ 投票模式已保存: mode={mode}, vote={votes}, once={once_val}')

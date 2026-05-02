#!/usr/bin/env python3
"""B站风纪委员自动投票脚本 — 开箱即用版"""

import asyncio
import logging
import sys

from config import load_config
from api import BiliAPI
from voter import run_mode_1, run_mode_2
from notify import push, send_email

logger = logging.getLogger(__name__)

MODES = {1: run_mode_1, 2: run_mode_2}


async def start(user: dict, config: dict) -> None:
    """为一个用户执行投票"""
    user_id = user.get('cookieDatas', {}).get('DedeUserID', '?')

    async with BiliAPI(config['http_header']) as api:
        try:
            if not await api.login_by_cookie(user['cookieDatas']):
                logger.error(f'用户 {user_id} cookie已失效，跳过')
                await push(config, user_id, 'CookieExpires')
                send_email(config, '风纪委员脚本运行失败', 'cookie失效')
                print('\n❌ Cookie 已过期，请运行以下命令重新登录:')
                print('   python setup.py')
                return
        except Exception as e:
            logger.error(f'用户 {user_id} 登录失败: {e}')
            await push(config, user_id, 'UnknownError')
            send_email(config, '风纪委员脚本运行失败', f'登录异常: {e}')
            return

        try:
            logger.info(f'{api.name}：开始风纪委员投票')
            mode_fn = MODES.get(config['default_vote']['mode'], run_mode_1)
            await mode_fn(api, config['default_vote'], config)
            await push(config, api.name, 'DailyMissions', api=api)
        except Exception as e:
            logger.error(f'{api.name} 投票异常: {e}')
            await push(config, api.name, 'UnknownError')
            send_email(config, '风纪委员脚本运行失败', f'投票异常: {e}')


async def main() -> None:
    config = load_config()
    users = config.get('users', [])

    # 先刷新 Token（每次运行自动续期 180 天）
    try:
        from auth import refresh_token
        refresh_token()
    except Exception as e:
        logger.warning(f'Token刷新失败（不影响投票）: {e}')

    if not users:
        print('\n❌ 未检测到用户配置，请运行以下命令进行初始化:')
        print('   python setup.py')
        sys.exit(1)
    await asyncio.wait([
        asyncio.ensure_future(start(user, config)) for user in users
    ])


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
    )

    # 检查是否需要首次配置
    try:
        from setup import needs_setup
        if needs_setup():
            print('\n🔧 首次使用，进入配置向导...\n')
            from setup import run_setup
            run_setup()
    except ImportError:
        pass  # setup.py 不存在时正常启动

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('用户中断')
    except Exception as e:
        logger.exception(f'程序异常退出: {e}')
    finally:
        sys.exit(0)

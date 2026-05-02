"""风纪委员投票逻辑"""

import asyncio
import logging
import random
from typing import Any

from api import BiliAPI, VOTE_TEXT
from notify import push, send_email

logger = logging.getLogger(__name__)

MAX_ERRORS = 3


async def _opinion_vote(case_id: str, opinions: list[dict], api: BiliAPI) -> bool:
    """根据众议观点投票：选最多人选的观点的随机一条"""
    stats: dict[str, int] = {}
    for op in opinions:
        vote = op.get('vote', '')
        stats[vote] = stats.get(vote, 0) + 1

    most_vote = max(stats, key=stats.get)
    chosen = random.choice([o for o in opinions if o['vote'] == most_vote])
    vote_text = VOTE_TEXT.get(int(chosen['vote']), chosen.get('vote', '未知'))
    logger.info(f'{api.name}：【{case_id}】众议最多观点 -> {vote_text}')

    result = await api.jury_vote(case_id, int(chosen['vote']))
    if result.get('code') == 0:
        logger.info(f'{api.name}：成功为【{case_id}】投下【{vote_text}】')
        return True
    else:
        logger.warning(f'{api.name}：投票失败 code={result.get("code")} {result.get("message")}')
        return False


async def _replenish_vote(case_id: str, api: BiliAPI, default_vote: int) -> bool:
    """无众议观点时按默认配置投票"""
    info = await api.jury_case_info(case_id)
    if info.get('code') != 0:
        logger.error(f'{api.name}：获取案件信息失败: {info.get("message")}')
        return False

    items = info.get('data', {}).get('vote_items', [])
    if default_vote >= len(items):
        logger.warning(f'{api.name}：默认投票索引 {default_vote} 超出范围')
        return False

    item = items[default_vote]
    vote_text = item.get('vote_text', '未知')
    logger.info(f'{api.name}：【{case_id}】无众议观点 -> 按默认配置投【{vote_text}】')

    result = await api.jury_vote(case_id, int(item['vote']))
    if result.get('code') == 0:
        logger.info(f'{api.name}：成功为【{case_id}】投下【{vote_text}】')
        return True
    else:
        logger.warning(f'{api.name}：投票失败 code={result.get("code")} {result.get("message")}')
        return False


async def run_mode_1(api: BiliAPI, default_vote: dict[str, Any], config: dict[str, Any]) -> None:
    """模式1：无观点时立即默认投票"""
    await _vote_loop(api, config, default_vote, defer=False)


async def run_mode_2(api: BiliAPI, default_vote: dict[str, Any], config: dict[str, Any]) -> None:
    """模式2：无观点时暂存，最后统一默认投票"""
    await _vote_loop(api, config, default_vote, defer=True)


async def _vote_loop(api: BiliAPI, config: dict[str, Any], default_vote: dict[str, Any],
                     defer: bool) -> None:
    """投票主循环 (用 while 循环，无递归)"""
    err = MAX_ERRORS
    deferred: list[str] = []

    while True:
        if err <= 0:
            logger.error(f'{api.name}：错误次数过多，结束任务')
            await push(config, api.name, 'UnknownError')
            send_email(config, '风纪委员脚本运行失败', '发生未知错误')
            return

        # ── 拉取案件 ──────────────────────────────
        try:
            next_ = await api.jury_case_next()
        except Exception as e:
            logger.error(f'{api.name}：请求异常: {e}')
            err -= 1
            await asyncio.sleep(random.uniform(20, 40))
            continue

        code = next_.get('code')

        # 1) 成功获取案件
        if code == 0:
            case_id = next_['data']['case_id']
            await asyncio.sleep(random.uniform(10, 20))

            opinions = await api.jury_opinions(case_id)
            has_opinions = bool(opinions.get('data', {}).get('list'))

            if has_opinions:
                if not await _opinion_vote(case_id, opinions['data']['list'], api):
                    err -= 1
            else:
                if defer:
                    deferred.append(case_id)
                    logger.info(f'{api.name}：【{case_id}】暂存 (deferred)')
                else:
                    vote_idx = random.choice(default_vote.get('vote', [0, 1]))
                    if not await _replenish_vote(case_id, api, vote_idx):
                        err -= 1

        # 2) 已审满
        elif code == 25014:
            logger.info(f'{api.name}：案件已审满')
            return

        # 3) 无新案件
        elif code == 25008:
            logger.info(f'{api.name}：没有新案件')

            # 先处理暂存案件
            if defer and deferred:
                logger.info(f'{api.name}：开始处理 {len(deferred)} 个暂存案件')
                for cid in list(deferred):
                    deferred.remove(cid)
                    vote_idx = random.choice(default_vote.get('vote', [0, 1]))
                    if not await _replenish_vote(cid, api, vote_idx):
                        err -= 1
                    await asyncio.sleep(random.uniform(10, 20))
                return

            # 无暂存 -> 是否继续等待
            if default_vote.get('once', True):
                logger.info(f'{api.name}：休眠30分钟后继续')
                await asyncio.sleep(1800)
                continue  # 继续循环
            else:
                return

        # 4) 资格过期 → 自动重新申请
        elif code == 25006:
            logger.warning(f'{api.name}：风纪委员资格已过期，尝试申请')
            r = await api.jury_apply()
            if r.get('code') != 0:
                logger.info(f'{api.name}：申请结果: {r}')
                return

        # 5) 其他错误
        else:
            logger.warning(f'{api.name}：获取案件失败 code={code} msg={next_.get("message")}')
            err -= 1
            await asyncio.sleep(random.uniform(20, 40))

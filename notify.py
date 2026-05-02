"""通知推送：邮件 + 多渠道推送"""

import asyncio
import json
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional, Any

import aiohttp

logger = logging.getLogger(__name__)

# ── 邮件 ──────────────────────────────────────────────


def send_email(config: dict[str, Any], subject: str, body: str) -> None:
    """通过QQ邮箱SMTP发送邮件"""
    email_cfg = config.get('email', {})
    sender = email_cfg.get('sender', '')
    password = email_cfg.get('password', '')
    recipient = email_cfg.get('recipient', '')
    server_addr = email_cfg.get('smtp_server', 'smtp.qq.com')
    port = email_cfg.get('smtp_port', 587)

    if not password:
        logger.warning('邮箱密码未配置，跳过邮件发送')
        return

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject

    try:
        server = smtplib.SMTP(server_addr, port)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        logger.info(f'邮件发送成功 → {recipient}')
    except Exception as e:
        logger.error(f'邮件发送失败: {e}')


# ── 推送 ──────────────────────────────────────────────


async def push(config: dict[str, Any], user: str, msg_type: str,
               api=None) -> None:
    """多渠道推送通知"""
    push_cfg = config.get('push', {})
    if not push_cfg.get('enable') or msg_type not in push_cfg.get('msgtpye', []):
        return

    msg = await _build_msg(user, msg_type, config, api)
    if msg is None:
        return

    tasks = []
    if push_cfg.get('wxpush', {}).get('enable'):
        tasks.append(_push_wxwork(push_cfg['wxpush'], msg))
    if push_cfg.get('tgpush', {}).get('enable'):
        tasks.append(_push_telegram(push_cfg['tgpush'], msg))
    if push_cfg.get('server', {}).get('enable'):
        tasks.append(_push_server(push_cfg['server'], msg))
    if push_cfg.get('ijingniu', {}).get('enable'):
        tasks.append(_push_ijingniu(push_cfg['ijingniu'], msg))
    if push_cfg.get('pushplus', {}).get('enable'):
        tasks.append(_push_pushplus(push_cfg['pushplus'], msg))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _build_msg(user: str, msg_type: str, config: dict,
                     api) -> Optional[str]:
    """构造推送消息"""
    if msg_type == 'CookieExpires':
        return f'【风纪委员】\n{user}：cookie已过期！请重新获取！'
    if msg_type == 'UnknownError':
        return f'【风纪委员】\n{user}：发生未知错误！'
    if msg_type == 'DailyMissions' and api:
        return await _build_daily_msg(user, api)
    return None


async def _build_daily_msg(user: str, api) -> str:
    """构造每日任务统计消息"""
    jurylist = await api.jury_list()
    count = 0
    if jurylist.get('code') == 0:
        import time
        today_ts = time.time() // (24 * 3600)
        for case in jurylist.get('data', {}).get('list', []):
            if case.get('vote_time', 0) // (24 * 3600) == today_ts:
                count += 1
    else:
        logger.error(f'{user}：已投票案件获取失败')
        return ''
    return f'【风纪委员】\n{user}：今日任务已完成{count}/20'


# ── 各渠道推送实现 ────────────────────────────────────


async def _push_wxwork(cfg: dict, msg: str) -> None:
    async with aiohttp.ClientSession() as s:
        r = await s.post(
            f'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
            f'?corpid={cfg["corpid"]}&corpsecret={cfg["secret"]}'
        )
        token_data = await r.json()
        if token_data.get('errcode') != 0:
            logger.error('企业微信：access_token获取失败')
            return
        token = token_data['access_token']
        r2 = await s.post(
            f'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}',
            json={'touser': cfg['touser'], 'msgtype': 'text',
                  'agentid': cfg['agentid'], 'text': {'content': msg}},
        )
        if (await r2.json()).get('errcode') == 0:
            logger.info('企业微信推送成功')
        else:
            logger.error('企业微信推送失败')


async def _push_telegram(cfg: dict, msg: str) -> None:
    async with aiohttp.ClientSession() as s:
        r = await s.get(
            f'https://api.telegram.org/bot{cfg["bot_token"]}/sendMessage'
            f'?chat_id={cfg["chat_id"]}&text={msg}'
        )
        if r.status == 200:
            logger.info('Telegram推送成功')
        else:
            logger.error('Telegram推送失败')


async def _push_server(cfg: dict, msg: str) -> None:
    async with aiohttp.ClientSession() as s:
        r = await s.post(
            f'https://sctapi.ftqq.com/{cfg["sendkey"]}.send',
            json={'title': '【风纪委员】', 'desp': msg},
        )
        if r.status == 200:
            logger.info('Server酱推送成功')
        else:
            logger.error('Server酱推送失败')


async def _push_ijingniu(cfg: dict, msg: str) -> None:
    async with aiohttp.ClientSession() as s:
        r = await s.post(
            'http://push.ijingniu.cn/send',
            json={'channelkey': cfg['channelkey'],
                  'msgHead': '【风纪委员】', 'msgBody': msg},
        )
        if r.status == 200:
            logger.info('即时达推送成功')
        else:
            logger.error('即时达推送失败')


async def _push_pushplus(cfg: dict, msg: str) -> None:
    async with aiohttp.ClientSession() as s:
        r = await s.post(
            'http://www.pushplus.plus/send',
            json={'token': cfg['token'], 'title': '【风纪委员】', 'content': msg},
        )
        if r.status == 200:
            logger.info('pushplus推送成功')
        else:
            logger.error('pushplus推送失败')

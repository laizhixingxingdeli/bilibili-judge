"""B站API封装（异步）"""

import logging
import random
import warnings
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

VOTE_TEXT: dict[int, str] = {
    1: '合适', 2: '一般', 3: '不合适', 4: '无法判断',
    11: '好', 12: '普通', 13: '差', 14: '无法判断',
}


class BiliAPI:
    """B站风纪委员相关接口"""

    def __init__(self, headers: dict[str, str]) -> None:
        self._name: Optional[str] = None
        self._is_login: bool = False
        self._bili_jct: str = ''
        self._is_banned: Optional[bool] = None
        timeout = aiohttp.ClientTimeout(total=60)
        connector = aiohttp.TCPConnector(limit=50, force_close=True)
        self._session = aiohttp.ClientSession(
            headers=headers, connector=connector,
            timeout=timeout, trust_env=True,
        )

    # ── 属性 ──────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name or '未知用户'

    # ── 登录 ──────────────────────────────────────────

    async def login_by_cookie(self, cookies: dict[str, str],
                              check_banned: bool = True) -> bool:
        """通过 cookie 登录"""
        self._session.cookie_jar.update_cookies(cookies)
        await self._refresh_info()
        if not self._is_login:
            return False
        self._bili_jct = cookies.get('bili_jct', '')

        if check_banned:
            self._is_banned = await self._check_ban()
        return True

    async def _check_ban(self) -> bool:
        code = (await self.like_cv(7793107)).get('code')
        if code not in (0, 65006, -404):
            warnings.warn(f'{self.name}: 账号异常，请检查bili_jct或账号是否被封禁')
            return True
        return False

    async def _refresh_info(self) -> None:
        ret = await self._get('/x/web-interface/nav')
        if ret.get('code') != 0:
            self._is_login = False
            return
        self._is_login = True
        self._name = ret.get('data', {}).get('uname', '未知用户')

    # ── 通用请求 ──────────────────────────────────────

    async def _get(self, path: str, **kwargs) -> dict[str, Any]:
        url = f'https://api.bilibili.com{path}'
        async with self._session.get(url, verify_ssl=False, **kwargs) as r:
            return await r.json()

    async def _post(self, path: str, data: dict[str, str], **kwargs) -> dict[str, Any]:
        url = f'https://api.bilibili.com{path}'
        async with self._session.post(url, data=data, verify_ssl=False, **kwargs) as r:
            return await r.json()

    # ── 接口方法 ──────────────────────────────────────

    async def like_cv(self, cvid: int) -> dict[str, Any]:
        """点赞专栏（用于检测账号状态）"""
        return await self._post('/x/article/like', {'id': str(cvid), 'type': '1', 'csrf': self._bili_jct})

    async def jury_info(self) -> dict[str, Any]:
        """查询风纪委员状态"""
        return await self._get('/x/credit/v2/jury/jury')

    async def jury_apply(self) -> dict[str, Any]:
        """申请风纪委员资格"""
        return await self._post('/x/credit/v2/jury/apply', {'csrf': self._bili_jct})

    async def jury_case_next(self) -> dict[str, Any]:
        """拉取下一个待审案件"""
        return await self._get('/x/credit/v2/jury/case/next', data={'csrf': self._bili_jct})

    async def jury_case_info(self, case_id: str) -> dict[str, Any]:
        """获取案件详情"""
        return await self._get(f'/x/credit/v2/jury/case/info?case_id={case_id}')

    async def jury_opinions(self, case_id: str) -> dict[str, Any]:
        """获取案件的众议观点"""
        return await self._get(f'/x/credit/v2/jury/case/opinion?case_id={case_id}&pn=1&ps=20')

    async def jury_vote(self, case_id: str, vote: int) -> dict[str, Any]:
        """投下一票"""
        return await self._post('/x/credit/v2/jury/vote', {
            'case_id': case_id,
            'vote': str(vote),
            'csrf': self._bili_jct,
            'insiders': str(random.choice([0, 1])),
            'anonymous': '0',
        })

    async def jury_list(self) -> dict[str, Any]:
        """最近20条已投票案件"""
        return await self._get('/x/credit/v2/jury/case/list?pn=1&ps=20')

    # ── 清理 ──────────────────────────────────────────

    async def close(self) -> None:
        await self._session.close()

    async def __aenter__(self) -> 'BiliAPI':
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

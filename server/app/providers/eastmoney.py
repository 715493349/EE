from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import time
import httpx

from ..config import settings

UT = "fa5fd1943c7b386f172d6893dbbd1d0c"

@dataclass
class RawStock:
    code: str
    name: str
    market: int
    price: float
    prev_close: float
    open: float
    high: float
    low: float
    volume_lot: float
    amount_yuan: float
    change_pct: float
    turnover_pct: float
    volume_ratio: float
    amplitude_pct: float
    market_cap_yuan: float
    float_cap_yuan: float
    main_net_yuan: float

@dataclass
class Book:
    bids: list[tuple[float, float]]
    asks: list[tuple[float, float]]

@dataclass
class Trade:
    time: str
    price: float
    volume_lot: float
    amount_yuan: float
    side: int

@dataclass
class FetchResult:
    data: Any
    received_at: str
    latency_ms: int

class EastmoneyClient:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=settings.timeout, headers={
            "User-Agent": settings.user_agent,
            "Referer": settings.referer,
            "Accept": "application/json,text/plain,*/*",
        })

    async def close(self) -> None:
        await self.client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> FetchResult:
        started = time.perf_counter()
        params = {**params, "ut": UT, "_": int(time.time() * 1000)}
        resp = await self.client.get(f"{settings.host}{path}", params=params)
        resp.raise_for_status()
        payload = resp.json()
        latency = int((time.perf_counter() - started) * 1000)
        received_at = datetime.now().astimezone().isoformat()
        if payload.get("rc") not in (0, None):
            raise RuntimeError(f"Eastmoney rc={payload.get('rc')}: {payload.get('rt')}" )
        return FetchResult(payload, received_at, latency)

    async def universe(self) -> FetchResult:
        return await self._get("/api/qt/clist/get", {
            "pn": 1, "pz": 6000, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": "f6", "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f2,f3,f5,f6,f7,f8,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f62,f100",
        })

    async def quote(self, secid: str) -> FetchResult:
        return await self._get("/api/qt/stock/get", {
            "secid": secid,
            "fltt": 2,
            "fields": "f11,f12,f13,f14,f15,f16,f17,f18,f19,f20,f31,f32,f33,f34,f35,f36,f37,f38,f39,f40,f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f71,f116,f117,f162,f167,f168,f169,f170,f171",
        })

    async def details(self, secid: str, limit: int = 80) -> FetchResult:
        return await self._get("/api/qt/stock/details/get", {
            "secid": secid, "fields1": "f1,f2,f3,f4", "fields2": "f51,f52,f53,f54,f55",
            "pos": -limit, "lmt": limit, "fltt": 2,
        })

    async def trends(self, secid: str) -> FetchResult:
        return await self._get("/api/qt/stock/trends2/get", {
            "secid": secid, "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58", "ndays": 1,
            "iscr": 0, "iscca": 0,
        })


def to_float(value: Any, scale: float = 1.0) -> float:
    try:
        if value in (None, "", "-", "--"): return 0.0
        return float(value) / scale
    except (ValueError, TypeError):
        return 0.0


def parse_universe(payload: dict[str, Any]) -> list[RawStock]:
    rows = (payload.get("data") or {}).get("diff") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    result: list[RawStock] = []
    for row in rows:
        if not isinstance(row, dict): continue
        code = str(row.get("f12", ""))
        name = str(row.get("f14", ""))
        if len(code) != 6 or not name or name.startswith("ST"):
            continue
        market = int(row.get("f13") or 0)
        price = to_float(row.get("f2"))
        prev = to_float(row.get("f18"))
        if price <= 0 or prev <= 0:
            continue
        result.append(RawStock(
            code=code, name=name, market=market, price=price, prev_close=prev,
            open=to_float(row.get("f17")), high=to_float(row.get("f15")), low=to_float(row.get("f16")),
            volume_lot=to_float(row.get("f5")), amount_yuan=to_float(row.get("f6")),
            change_pct=to_float(row.get("f3")), turnover_pct=to_float(row.get("f8")),
            volume_ratio=to_float(row.get("f10")), amplitude_pct=to_float(row.get("f7")),
            market_cap_yuan=to_float(row.get("f20")), float_cap_yuan=to_float(row.get("f21")),
            main_net_yuan=to_float(row.get("f62")),
        ))
    return result


def parse_book(payload: dict[str, Any]) -> Book:
    data = payload.get("data") or {}
    bid_fields = [("f19","f20"),("f17","f18"),("f15","f16"),("f13","f14"),("f11","f12")]
    ask_fields = [("f39","f40"),("f37","f38"),("f35","f36"),("f33","f34"),("f31","f32")]
    bids = [(to_float(data.get(p)), to_float(data.get(v))) for p,v in bid_fields]
    asks = [(to_float(data.get(p)), to_float(data.get(v))) for p,v in ask_fields]
    return Book(bids=bids, asks=asks)


def parse_details(payload: dict[str, Any]) -> list[Trade]:
    rows = (payload.get("data") or {}).get("details") or []
    result: list[Trade] = []
    for raw in rows:
        parts = str(raw).split(",")
        if len(parts) < 5: continue
        # f51=time, f52=price, f53=volume, f54=order count, f55=side in the public endpoint mapping.
        result.append(Trade(
            time=parts[0], price=to_float(parts[1]), volume_lot=to_float(parts[2]),
            amount_yuan=to_float(parts[1]) * to_float(parts[2]) * 100,
            side=int(float(parts[4] or 0)),
        ))
    return result


def parse_trends(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (payload.get("data") or {}).get("trends") or []
    result = []
    for raw in rows:
        parts = str(raw).split(",")
        if len(parts) < 8: continue
        result.append({"time":parts[0],"price":to_float(parts[1]),"avg":to_float(parts[2]),"high":to_float(parts[3]),"low":to_float(parts[4]),"volume_lot":to_float(parts[5]),"amount_yuan":to_float(parts[6]),"avg_price":to_float(parts[7])})
    return result

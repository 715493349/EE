from __future__ import annotations
import asyncio
from collections import defaultdict, deque
from datetime import datetime, time as dtime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .providers.eastmoney import EastmoneyClient, parse_book, parse_details, parse_universe, parse_trends
from .analysis.score import score_stock

app = FastAPI(title="A股游资雷达 V2", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173","http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
client = EastmoneyClient()
price_history = defaultdict(lambda: deque(maxlen=40))
last_snapshot: list[dict] = []
last_received_at: str | None = None
last_error: str | None = None
last_latency_ms: int | None = None
deep_cache: dict[str, tuple[float, object, object, int]] = {}


def market_status() -> str:
    now = datetime.now().astimezone()
    if now.weekday() >= 5: return "CLOSED"
    t = now.time()
    if dtime(9,15) <= t < dtime(9,30): return "AUCTION"
    if dtime(9,30) <= t <= dtime(11,30) or dtime(13,0) <= t <= dtime(15,0): return "OPEN"
    return "CLOSED"

async def deep_for(code: str, market: int):
    now = asyncio.get_running_loop().time()
    cache = deep_cache.get(code)
    if cache and now - cache[0] < settings.deep_interval:
        return cache[1], cache[2], None, cache[3]
    secid=f"{market}.{code}"
    q, d = await asyncio.gather(client.quote(secid), client.details(secid, 80))
    value=(now, parse_book(q.data), parse_details(d.data), max(q.latency_ms, d.latency_ms))
    deep_cache[code]=value
    return value[1], value[2], q.received_at, value[3]

async def build_snapshot() -> dict:
    global last_snapshot, last_received_at, last_error, last_latency_ms
    market = market_status()
    if market == "CLOSED":
        return {"type":"snapshot","marketStatus":market,"stocks":[],"meta":{"source":"Eastmoney public quote","receivedAt":last_received_at,"latencyMs":last_latency_ms,"error":last_error,"live":False}}
    try:
        fetched=await client.universe()
        rows=parse_universe(fetched.data)
        last_received_at=fetched.received_at; last_latency_ms=fetched.latency_ms; last_error=None
        prev_map={x["code"]:x for x in last_snapshot}
        candidates=sorted(rows, key=lambda x: (abs(x.change_pct)*0.22 + min(x.volume_ratio,5)*8 + min(x.turnover_pct,20)*1.7 + min(max(x.main_net_yuan,0)/max(x.amount_yuan,1),0.3)*80), reverse=True)[:settings.candidate_count]
        out=[]
        for s in candidates:
            prev_obj=prev_map.get(s.code)
            class Prev: pass
            prev=Prev() if prev_obj else None
            if prev:
                prev.amount_yuan=float(prev_obj.get("amountYuan",s.amount_yuan)); prev.change_pct=float(prev_obj.get("changePct",s.change_pct))
            try:
                book,trades,_,lat=await deep_for(s.code,s.market)
                result=score_stock(s,prev,trades,book)
            except Exception as exc:
                # 全市场仍可用，但深度数据缺失时明确降级为“数据不足”，不作攻击结论。
                result=None
            history=price_history[s.code]
            history.append({"time":datetime.now().strftime("%H:%M:%S"),"score":result.score if result else 0})
            out.append({
                "code":s.code,"name":s.name,"market":s.market,"price":s.price,"changePct":s.change_pct,
                "turnoverPct":s.turnover_pct,"amountWan":s.amount_yuan/10000,"volumeRatio":s.volume_ratio,
                "mainNetWan":s.main_net_yuan/10000,"amplitudePct":s.amplitude_pct,
                "attackScore":result.score if result else 0,"level":result.level if result else "DATA_LOW",
                "buyPressure":result.buy_pressure if result else 50,"bookImbalance":result.book_imbalance if result else 50,
                "amountAccel":result.amount_accel if result else 0,
                "reasons":result.reasons if result else ["盘口/逐笔明细获取失败，暂不评分"],
                "evidence":[e.__dict__ for e in result.evidence] if result else [],
                "history":list(history),
                "timestamp":fetched.received_at,
                "deepLatencyMs":lat if result else None,
            })
        out.sort(key=lambda x:x["attackScore"], reverse=True)
        last_snapshot=out
        return {"type":"snapshot","marketStatus":market,"stocks":out,"meta":{"source":"Eastmoney public quote","receivedAt":last_received_at,"latencyMs":last_latency_ms,"error":last_error,"live":True,"universeCount":len(rows),"candidateCount":len(candidates)}}
    except Exception as exc:
        last_error=f"行情源请求失败: {type(exc).__name__}: {exc}"
        return {"type":"snapshot","marketStatus":market,"stocks":last_snapshot,"meta":{"source":"Eastmoney public quote","receivedAt":last_received_at,"latencyMs":last_latency_ms,"error":last_error,"live":False}}

@app.get("/health")
async def health():
    return {"status":"ok","marketStatus":market_status(),"live":last_error is None and last_received_at is not None,"lastReceivedAt":last_received_at,"error":last_error}

@app.get("/api/stock/{market}/{code}/intraday")
async def intraday(market:int, code:str):
    data=await client.trends(f"{market}.{code}")
    return {"source":"Eastmoney public quote","receivedAt":data.received_at,"latencyMs":data.latency_ms,"data":parse_trends(data.data)}

@app.get("/api/stock/{market}/{code}/details")
async def details(market:int, code:str):
    data=await client.details(f"{market}.{code}",160)
    return {"source":"Eastmoney public quote","receivedAt":data.received_at,"latencyMs":data.latency_ms,"data":[x.__dict__ for x in parse_details(data.data)]}

@app.websocket("/ws/market")
async def ws_market(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload=await build_snapshot()
            await websocket.send_json(payload)
            await asyncio.sleep(settings.scan_interval)
    except WebSocketDisconnect:
        return

@app.on_event("shutdown")
async def shutdown():
    await client.close()

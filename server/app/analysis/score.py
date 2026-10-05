from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Evidence:
    key: str
    label: str
    value: float
    score: float
    weight: float
    note: str

@dataclass
class ScoreResult:
    score: int
    level: str
    buy_pressure: float
    book_imbalance: float
    amount_accel: float
    evidence: list[Evidence]
    reasons: list[str]


def clamp(x: float, lo=0.0, hi=100.0) -> float:
    return max(lo, min(hi, x))


def percentile_score(value: float, center: float, span: float) -> float:
    if span <= 0: return 50.0
    return clamp(50 + (value - center) / span * 25)


def book_score(bids: list[tuple[float,float]], asks: list[tuple[float,float]]) -> float:
    # 五档委买/委卖数量失衡，不等同于真实主动成交。
    bid = sum(max(0, v) for _,v in bids)
    ask = sum(max(0, v) for _,v in asks)
    if bid + ask <= 0: return 50.0
    return clamp(50 + 50 * (bid - ask) / (bid + ask))


def trade_side_ratio(trades) -> float:
    buy = sell = 0.0
    for t in trades:
        # 公共逐笔字段：1=买，2=卖，0=中性，4=竞价。
        if t.side == 1: buy += t.amount_yuan
        elif t.side == 2: sell += t.amount_yuan
    if buy + sell <= 0: return 50.0
    return buy / (buy + sell) * 100


def large_trade_ratio(trades) -> float:
    amounts = sorted(max(0.0, t.amount_yuan) for t in trades if t.amount_yuan > 0)
    if not amounts: return 0.0
    threshold = amounts[max(0, int(len(amounts) * 0.8) - 1)]
    total = sum(amounts)
    large = sum(a for a in amounts if a >= threshold)
    return large / total * 100 if total else 0.0


def score_stock(stock, prev, trades, book) -> ScoreResult:
    buy = trade_side_ratio(trades)
    book_s = book_score(book.bids, book.asks)
    current_amount = stock.amount_yuan
    prior_amount = prev.amount_yuan if prev else current_amount
    delta_per_min = max(0.0, current_amount - prior_amount) / 3.0
    own_baseline = max(1.0, current_amount / max(1.0, 240.0))
    amount_accel = clamp(delta_per_min / own_baseline * 45)

    net_ratio = 50.0
    if current_amount > 0:
        net_ratio = clamp(50 + (stock.main_net_yuan / current_amount) * 160)
    price_accel = clamp(50 + (stock.change_pct - (prev.change_pct if prev else stock.change_pct)) * 8)
    turnover_signal = clamp(stock.turnover_pct * 6.5)
    volume_signal = clamp(stock.volume_ratio * 13)
    evidence = [
        Evidence("buy", "逐笔买方占比", buy, clamp((buy-50)*2.2+50), 0.24, "基于最近逐笔成交的买/卖方向汇总"),
        Evidence("book", "五档盘口失衡", book_s, book_s, 0.14, "委买与委卖数量失衡；不是主动成交"),
        Evidence("net", "主力净流入强度", net_ratio, net_ratio, 0.20, "当日累计主力净流入 / 当日成交额"),
        Evidence("accel", "成交额加速度", amount_accel, amount_accel, 0.18, "当前成交额增量相对自身盘中基线"),
        Evidence("price", "价格加速度", price_accel, price_accel, 0.10, "短周期价格变化"),
        Evidence("turnover", "换手异动", turnover_signal, turnover_signal, 0.07, "当前累计换手率"),
        Evidence("volume", "量比", volume_signal, volume_signal, 0.07, "数据源量比字段"),
    ]
    score = round(sum(e.score * e.weight for e in evidence))
    reasons=[]
    if buy >= 62: reasons.append(f"逐笔买方占比 {buy:.1f}%")
    if book_s >= 68: reasons.append(f"五档委买失衡 {book_s:.0f}")
    if net_ratio >= 65: reasons.append("主力净流入强度偏强")
    if amount_accel >= 70: reasons.append("成交额正在明显加速")
    if stock.change_pct >= 5 and stock.turnover_pct >= 8: reasons.append("涨幅+换手同步进入活跃区")
    if stock.volume_ratio >= 2: reasons.append(f"量比 {stock.volume_ratio:.1f}x")
    if len(reasons) >= 4 and score < 82: score = 82
    level = "ALERT" if score >= 82 and len(reasons) >= 3 else "WATCH" if score >= 65 else "NORMAL"
    if not reasons: reasons.append("暂未形成多证据共振")
    return ScoreResult(score, level, buy, book_s, amount_accel, evidence, reasons)

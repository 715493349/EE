# 仅用于评分函数的离线单元冒烟；不会被主程序调用，也不会提供模拟行情给 UI。
from types import SimpleNamespace
from score import score_stock

s=SimpleNamespace(amount_yuan=80_000_000,change_pct=7.8,turnover_pct=12,volume_ratio=2.8,main_net_yuan=16_000_000)
p=SimpleNamespace(amount_yuan=55_000_000,change_pct=5.7)
trades=[SimpleNamespace(side=1,amount_yuan=900_000),SimpleNamespace(side=1,amount_yuan=700_000),SimpleNamespace(side=2,amount_yuan=120_000)]
book=SimpleNamespace(bids=[(1,100),(1,90),(1,80),(1,70),(1,60)],asks=[(1,25),(1,20),(1,18),(1,17),(1,12)])
r=score_stock(s,p,trades,book)
assert 0 <= r.score <= 100
assert r.level in {'ALERT','WATCH','NORMAL'}
print(r.score, r.level, r.reasons)

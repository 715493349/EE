# 数据源与口径

## 默认实时源

V2 默认使用东方财富公开行情服务：

- 全市场实时截面：`/api/qt/clist/get`
- 个股实时快照 + 五档盘口：`/api/qt/stock/get`
- 当日逐笔成交：`/api/qt/stock/details/get`
- 当日分时：`/api/qt/stock/trends2/get`

公开接口的字段映射可通过以下公开资料交叉核对：

- `qt/stock/get`：https://github.com/WangYang-Rex/eastmoney-data-sdk/blob/main/docs/API_FIELDS.md
- `qt/stock/details/get`：https://github.com/theneao/PA_Agent/blob/main/pa_agent/data/eastmoney_quote_api.py
- 东方财富 API 使用示例：https://github.com/jx1100370217/my-openclaw-skills/blob/main/eastmoney/SKILL.md

## 关键口径

### 主动买方占比

来自当日逐笔成交方向字段的买/卖汇总，只计算可识别为买或卖的成交；中性和竞价不计入买卖双方分母。因此它不是“主力真实账户买入金额”。

### 五档盘口失衡

计算买一至买五与卖一至卖五的挂单量相对差异。挂单可以撤单，因此盘口失衡只作为辅助证据，不等同于已经成交。

### 主力净流入

全市场截面使用数据源提供的当日累计主力净流入字段。它是数据商的分类统计，不是交易所逐笔原始资金归属。

### 成交额加速度

用本程序连续抓取的真实快照计算当前成交额增量，并与该股票自身盘中基线比较。程序绝不把模拟 Tick 当作基线。

## 为什么不输出“游资已买入 XX”

公开行情没有自然人/机构身份标签。即便出现大单连续主动买入，也只能说明“行为形态与某类资金攻击模式相似”。因此 UI 用“强攻击 / 重点关注 / 数据不足”而不是“某游资已买入”。

## SLA 与生产环境

公开网页接口没有本项目可控制的低延迟 SLA。实际延迟取决于数据源、网络和限流。需要稳定 Level-2、逐笔全量、席位/龙虎榜以及授权使用，应将 `EastmoneyClient` 替换为券商或商业数据商 Provider。

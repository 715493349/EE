<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { Payload, Stock } from './types'

const stocks=ref<Stock[]>([])
const selected=ref<Stock|null>(null)
const meta=ref<Payload['meta']>({source:'-',receivedAt:null,latencyMs:null,error:null,live:false})
const marketStatus=ref('CLOSED')
const minScore=ref(60); const mode=ref<'ALL'|'ATTACK'|'NEAR_LIMIT'|'TURNOVER'>('ALL'); const search=ref('')
const alerts=ref<Array<{time:string;name:string;code:string;score:number;reason:string}>>([])
const detailRows=ref<any[]>([]); const intraday=ref<any[]>([]); const muted=ref(false)
let ws:WebSocket|null=null; let chart:echarts.ECharts|null=null; let detailChart:echarts.ECharts|null=null; let lastAlert=new Map<string,number>()

const filtered=computed(()=>stocks.value.filter(s=>{
  const okScore=s.attackScore>=minScore.value
  const text=(s.name+s.code).includes(search.value.trim())
  const okMode=mode.value==='ALL'||(mode.value==='ATTACK'&&s.level==='ALERT')||(mode.value==='NEAR_LIMIT'&&s.changePct>=7)|| (mode.value==='TURNOVER'&&s.turnoverPct>=10)
  return okScore&&text&&okMode
}).sort((a,b)=>b.attackScore-a.attackScore))
const leader=computed(()=>filtered.value[0]||stocks.value[0]||null)
const counts=computed(()=>({up:stocks.value.filter(x=>x.changePct>0).length,down:stocks.value.filter(x=>x.changePct<0).length,attack:stocks.value.filter(x=>x.level==='ALERT').length,watch:stocks.value.filter(x=>x.level==='WATCH').length}))

function fmtWan(v:number){return v>=10000?(v/10000).toFixed(2)+'亿':v.toFixed(0)+'万'}
function stateText(){return marketStatus.value==='OPEN'?'连续竞价':marketStatus.value==='AUCTION'?'集合竞价':'休市'}
function alertOf(s:Stock){
  if(s.level!=='ALERT') return
  const key=s.code; const old=lastAlert.get(key)||0
  if(Date.now()-old<15000) return
  lastAlert.set(key,Date.now())
  alerts.value.unshift({time:new Date().toLocaleTimeString(),name:s.name,code:s.code,score:s.attackScore,reason:s.reasons[0]||'多证据共振'})
  alerts.value=alerts.value.slice(0,12)
  if(!muted.value){const A=(window as any).AudioContext||(window as any).webkitAudioContext;if(A){const c=new A(),o=c.createOscillator(),g=c.createGain();o.frequency.value=920;g.gain.value=.035;o.connect(g);g.connect(c.destination);o.start();o.stop(c.currentTime+.12)}}
}
function connect(){
  ws?.close(); ws=new WebSocket(import.meta.env.VITE_WS_URL||'ws://localhost:8000/ws/market')
  ws.onmessage=async e=>{const p=JSON.parse(e.data) as Payload;marketStatus.value=p.marketStatus;meta.value=p.meta;if(p.meta.live){stocks.value=p.stocks;p.stocks.forEach(alertOf);if(!selected.value&&p.stocks[0])selected.value=p.stocks[0];else if(selected.value)selected.value=p.stocks.find(x=>x.code===selected.value?.code)||selected.value}else if(p.marketStatus==='CLOSED'){stocks.value=[];selected.value=null}}
}
async function select(s:Stock){selected.value=s;await loadSelected(s);await nextTick();drawCharts()}
async function loadSelected(s:Stock){
  try{const [d,t]=await Promise.all([fetch(`http://localhost:8000/api/stock/${s.market}/${s.code}/details`).then(r=>r.json()),fetch(`http://localhost:8000/api/stock/${s.market}/${s.code}/intraday`).then(r=>r.json())]);detailRows.value=d.data;intraday.value=t.data}catch{detailRows.value=[];intraday.value=[]}
}
function drawCharts(){
  if(!selected.value)return
  const h=document.getElementById('scoreChart'); if(h){chart?.dispose();chart=echarts.init(h);chart.setOption({backgroundColor:'transparent',grid:{left:40,right:18,top:20,bottom:30},xAxis:{type:'category',data:selected.value.history.map(x=>x.time),axisLabel:{color:'#718096'},axisLine:{lineStyle:{color:'#22344b'}}},yAxis:{type:'value',min:0,max:100,splitLine:{lineStyle:{color:'#18283b'}},axisLabel:{color:'#718096'}},series:[{type:'line',smooth:true,symbol:'none',data:selected.value.history.map(x=>x.score),areaStyle:{opacity:.12},lineStyle:{width:2}}]})}
  const t=document.getElementById('intradayChart');if(t&&intraday.value.length){detailChart?.dispose();detailChart=echarts.init(t);detailChart.setOption({tooltip:{trigger:'axis'},grid:{left:45,right:18,top:20,bottom:25},xAxis:{type:'category',data:intraday.value.map(x=>x.time),axisLabel:{color:'#718096'}},yAxis:[{type:'value',axisLabel:{color:'#718096'}},{type:'value',axisLabel:{color:'#718096'}}],series:[{name:'价格',type:'line',showSymbol:false,smooth:true,data:intraday.value.map(x=>x.price)},{name:'成交额',type:'bar',yAxisIndex:1,barWidth:2,data:intraday.value.map(x=>x.amount_yuan/1000000)}]})}
}
watch(selected,async s=>{if(s){await loadSelected(s);await nextTick();drawCharts()}})
onMounted(()=>connect())
onBeforeUnmount(()=>{ws?.close();chart?.dispose();detailChart?.dispose()})
</script>

<template>
  <div class="shell">
    <header class="header">
      <div><div class="kicker">LIVE SMART MONEY / A-STOCK</div><h1>A股游资雷达 <em>V2</em></h1><p>真实盘中行情 · 多证据资金攻击识别 · 不使用模拟数据</p></div>
      <div class="header-right"><div class="market-state"><span :class="['pulse',meta.live?'live':'']"></span>{{stateText()}}</div><div class="source">源：{{meta.source}} · {{meta.latencyMs??'—'}}ms</div></div>
    </header>

    <section class="ticker"><div><b>{{counts.up}}</b><span>上涨</span></div><div><b>{{counts.down}}</b><span>下跌</span></div><div class="danger"><b>{{counts.attack}}</b><span>强攻击</span></div><div class="warn"><b>{{counts.watch}}</b><span>重点关注</span></div><div><b>{{meta.universeCount??'—'}}</b><span>全市场样本</span></div><div class="status-wide"><span>数据时间</span><b>{{meta.receivedAt?new Date(meta.receivedAt).toLocaleTimeString():'—'}}</b></div></section>

    <div v-if="meta.error" class="data-error">⚠ {{meta.error}} · 当前不会生成新的攻击结论</div>
    <div v-else-if="!meta.live" class="data-error neutral">当前没有可用的盘中实时快照。休市时不会伪造“实时数据”。</div>

    <section class="layout">
      <div class="main">
        <div class="toolbar panel"><div class="filters"><input v-model="search" placeholder="搜索股票代码/名称"/><select v-model="mode"><option value="ALL">全部候选</option><option value="ATTACK">只看强攻击</option><option value="NEAR_LIMIT">涨幅 ≥ 7%</option><option value="TURNOVER">换手 ≥ 10%</option></select><input v-model.number="minScore" type="range" min="0" max="90"/><span>≥ {{minScore}} 分</span></div><button class="sound" @click="muted=!muted">{{muted?'静音':'🔔 告警声开'}}</button></div>
        <div class="panel table-panel"><div class="table-head"><div><strong>资金攻击候选</strong><span>不是“游资确认”，而是盘中行为证据排行</span></div><span class="refresh">每 {{3}} 秒全市场刷新</span></div>
          <div class="table"><div class="tr th"><span>标的</span><span>攻击分</span><span>涨幅</span><span>换手</span><span>成交额</span><span>主力净流</span><span>买方</span><span>盘口</span><span>状态</span></div>
            <div v-for="s in filtered" :key="s.code" :class="['tr','stock',selected?.code===s.code?'active':'']" @click="select(s)"><span><b>{{s.name}}</b><small>{{s.code}}</small></span><span><b :class="['score',s.level.toLowerCase()]">{{s.attackScore}}</b></span><span :class="{up:s.changePct>0,down:s.changePct<0}">{{s.changePct.toFixed(2)}}%</span><span>{{s.turnoverPct.toFixed(1)}}%</span><span>{{fmtWan(s.amountWan)}}</span><span :class="s.mainNetWan>=0?'up':'down'">{{s.mainNetWan>=0?'+':''}}{{fmtWan(s.mainNetWan)}}</span><span>{{s.buyPressure.toFixed(1)}}%</span><span>{{s.bookImbalance.toFixed(0)}}</span><span><i :class="['tag',s.level.toLowerCase()]">{{s.level==='ALERT'?'强攻击':s.level==='WATCH'?'关注':s.level==='DATA_LOW'?'数据不足':'常态'}}</i></span></div>
            <div v-if="!filtered.length" class="empty">没有达到当前筛选条件的真实行情样本。</div>
          </div>
        </div>
      </div>

      <aside class="right">
        <div class="panel lead" v-if="leader"><div class="panel-title">当前最高攻击</div><div class="lead-name"><b>{{leader.name}}</b><small>{{leader.code}} · {{leader.price.toFixed(2)}}</small></div><div class="lead-score"><strong>{{leader.attackScore}}</strong><span>/100</span></div><div class="bar"><i :style="{width:leader.attackScore+'%'}"></i></div><div class="reasons"><span v-for="r in leader.reasons" :key="r">{{r}}</span></div></div>
        <div class="panel alerts"><div class="panel-title row">实时告警 <b>{{alerts.length}}</b></div><div v-for="a in alerts" :key="a.time+a.code" class="alert"><div><strong>{{a.name}}</strong><small>{{a.code}} · {{a.time}}</small></div><b>{{a.score}}</b><p>{{a.reason}}</p></div><div v-if="!alerts.length" class="empty">等待盘中多证据共振...</div></div>
      </aside>
    </section>

    <section v-if="selected" class="detail panel"><div class="detail-head"><div><strong>{{selected.name}}</strong><span>{{selected.code}} · 实时详情</span></div><div class="detail-metrics"><b>{{selected.changePct.toFixed(2)}}%</b><span>涨幅</span><b>{{selected.turnoverPct.toFixed(1)}}%</b><span>换手</span><b>{{fmtWan(selected.mainNetWan)}}</b><span>主力净流</span></div></div>
      <div class="charts"><div><div class="chart-title">攻击分历史</div><div id="scoreChart" class="chart"></div></div><div><div class="chart-title">当日分时 / 成交额（真实数据）</div><div id="intradayChart" class="chart"></div></div></div>
      <div class="evidence-grid"><div><div class="chart-title">评分证据拆解</div><div v-for="e in selected.evidence" :key="e.key" class="evidence"><span>{{e.label}}</span><div class="e-bar"><i :style="{width:e.score+'%'}"></i></div><b>{{e.score.toFixed(0)}}</b><small>{{e.note}}</small></div></div><div><div class="chart-title">最近逐笔成交（真实来源）</div><div class="ticks"><div v-for="t in detailRows.slice(-12).reverse()" :key="t.time+t.price+t.volume_lot"><span>{{t.time}}</span><b>{{t.price.toFixed(2)}}</b><span>{{t.volume_lot.toFixed(0)}}手</span><i :class="t.side===1?'buy':t.side===2?'sell':'neutral'">{{t.side===1?'买':t.side===2?'卖':t.side===4?'竞价':'中性'}}</i></div></div></div></div>
    </section>
    <footer>数据层：东方财富公开行情接口；V2 强制真实数据模式。公开行情 ≠ 交易所 Level-2 SLA。系统结论仅为盘中行为研究。</footer>
  </div>
</template>

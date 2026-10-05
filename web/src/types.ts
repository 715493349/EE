export type Stock = {
  code:string; name:string; market:number; price:number; changePct:number; turnoverPct:number; amountWan:number;
  volumeRatio:number; mainNetWan:number; amplitudePct:number; attackScore:number; level:string; buyPressure:number;
  bookImbalance:number; amountAccel:number; reasons:string[]; evidence:Array<{label:string;value:number;score:number;weight:number;note:string}>;
  history:Array<{time:string;score:number}>; timestamp:string; deepLatencyMs:number|null;
}
export type Payload = {type:'snapshot';marketStatus:string;stocks:Stock[];meta:{source:string;receivedAt:string|null;latencyMs:number|null;error:string|null;live:boolean;universeCount?:number;candidateCount?:number}}

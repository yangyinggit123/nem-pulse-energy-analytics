'use strict';
const mean = a => a.reduce((s,v)=>s+v,0)/a.length;
const sd = a => {const m=mean(a);return Math.sqrt(a.reduce((s,v)=>s+(v-m)**2,0)/(a.length-1));};
const money = v => v.toLocaleString('en-AU',{minimumFractionDigits:2,maximumFractionDigits:2});
const START=Date.UTC(2026,9,1,0,5), END=Date.UTC(2026,10,1), STEP=300000;
// UTC functions preserve the source clock for arithmetic; they do not convert NEM time to UTC.
function parseCSV(text,region){
 const lines=text.replace(/^\uFEFF/,'').trim().split(/\r?\n/);
 if(lines.shift()!=='REGION,SETTLEMENTDATE,TOTALDEMAND,RRP,PERIODTYPE')throw Error(region+': unexpected columns');
 const seen=new Set();
 const rows=lines.map(line=>{
  const c=line.split(',');
  if(c.length!==5 || c[0]!==region || c[4]!=='TRADE')throw Error(region+': invalid region or period type');
  const m=c[1].match(/^(\d{4})\/(\d{2})\/(\d{2}) (\d{2}):(\d{2}):(\d{2})$/);
  if(!m)throw Error(region+': invalid timestamp');
  const t=Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+m[6]);
  const canonical=new Date(t).toISOString().slice(0,19).replace('T',' ').replaceAll('-','/');
  if(canonical!==c[1] || t<START || t>END || (t-START)%STEP || seen.has(t))throw Error(region+': duplicate or out-of-range timestamp');
  seen.add(t);
  if(!c[2].trim() || !c[3].trim())throw Error(region+': empty number');
  const demand=Number(c[2]),price=Number(c[3]);
  if(!Number.isFinite(demand)||!Number.isFinite(price))throw Error(region+': invalid number');
  return {t,price,demand};
 }).sort((a,b)=>a.t-b.t);
 if(rows.length!==8928 || rows.some((r,i)=>r.t!==START+i*STEP))throw Error(region+': incomplete October coverage');
 return rows;
}
function daily(rows){const groups=new Map();for(const r of rows){const date=new Date(r.t-STEP).toISOString().slice(0,10);if(!groups.has(date))groups.set(date,[]);groups.get(date).push(r);}return [...groups].map(([date,a])=>({date,price:mean(a.map(r=>r.price)),demand:mean(a.map(r=>r.demand))}));}
function chart(id,series,dates,hourlyAxis=false){
 const svg=document.getElementById(id),w=650,h=280,l=65,r=20,t=15,b=40;
 const values=series.flatMap(s=>s.values);let low=Math.min(0,...values),high=Math.max(0,...values),pad=(high-low||1)*.08;low-=pad;high+=pad;
 const X=i=>l+i*(w-l-r)/(dates.length-1),Y=v=>t+(high-v)*(h-t-b)/(high-low);
 let out='';for(let i=0;i<=4;i++){const v=low+(high-low)*i/4;out+=`<line x1="${l}" y1="${Y(v)}" x2="${w-r}" y2="${Y(v)}" stroke="#293b51"/><text x="${l-8}" y="${Y(v)+4}" fill="#9cb0ca" font-size="11" text-anchor="end">${Math.round(v).toLocaleString('en-AU')}</text>`;}
 out+=`<line x1="${l}" y1="${Y(0)}" x2="${w-r}" y2="${Y(0)}" stroke="#9cb0ca"/>`;
 for(let i=0;i<dates.length;i+=(hourlyAxis?2:5))out+=`<text x="${X(i)}" y="${h-12}" fill="#9cb0ca" font-size="11" text-anchor="middle">${hourlyAxis?String(i).padStart(2,'0'):'Oct '+Number(dates[i].slice(-2))}</text>`;
 for(const s of series){out+=`<polyline fill="none" stroke="${s.color}" stroke-width="3" points="${s.values.map((v,i)=>`${X(i)},${Y(v)}`).join(' ')}"/>`;s.values.forEach((v,i)=>{out+=`<circle cx="${X(i)}" cy="${Y(v)}" r="6" fill="${s.color}" fill-opacity=".1"><title>${s.name} | ${dates[i]} | ${money(v)} ${s.unit}</title></circle>`;});}
 svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.innerHTML=out;
}
let datasets,region='TAS1';
function render(){
 if(!datasets)return;
 const selected=region==='BOTH'?['TAS1','VIC1']:[region];
 const metrics={avg:r=>mean(r.map(x=>x.price)),peak:r=>Math.max(...r.map(x=>x.price)),demand:r=>mean(r.map(x=>x.demand)),vol:r=>sd(r.map(x=>x.price))};
 for(const [id,calc] of Object.entries(metrics))document.getElementById(id).textContent=selected.map(key=>(selected.length===2?key+': ':'')+(id==='demand'?'':'$')+money(calc(datasets[key]))).join(' / ');
 document.querySelectorAll('.value').forEach(el=>el.style.fontSize=selected.length===2?'18px':'30px');
 const ds=Object.fromEntries(selected.map(k=>[k,daily(datasets[k])]));
 const dates=daily(datasets.TAS1).map(x=>x.date);
 for(const [id,field,unit] of [['priceChart','price','AUD/MWh'],['demandChart','demand','MW']])chart(id,selected.map(key=>({name:key,values:ds[key].map(x=>x[field]),color:key==='TAS1'?'#46dbc3':'#55b7ff',unit})),dates);
 const ta=daily(datasets.TAS1),vi=daily(datasets.VIC1);
 chart('spreadChart',[{name:'TAS1 − VIC1',values:ta.map((x,i)=>x.price-vi[i].price),color:'#ffbc69',unit:'AUD/MWh'}],dates);
 renderIntraday(selected);
 const spreads=datasets.TAS1.map((x,i)=>x.price-datasets.VIC1[i].price);
 const neg=key=>100*datasets[key].filter(x=>x.price<0).length/8928;
 document.getElementById('alerts').innerHTML=`<div class="alert"><strong>Mean TAS1 − VIC1 spread</strong>${money(mean(spreads))} AUD/MWh. TAS1 is higher in ${(100*spreads.filter(v=>v>0).length/8928).toFixed(2)}% of intervals.</div><div class="alert"><strong>Negative-price intervals</strong>TAS1: ${neg('TAS1').toFixed(2)}% · VIC1: ${neg('VIC1').toFixed(2)}%.</div><div class="alert"><strong>Complete paired coverage</strong>8,928 five-minute intervals per region · 31 days. Spread and observations always compare both regions.</div>`;
}
async function load(){
 const status=document.getElementById('status');
 document.querySelectorAll('[data-region]').forEach(b=>b.disabled=true);
 try{
  const pairs=await Promise.all(['TAS1','VIC1'].map(async key=>{const response=await fetch(`../data/raw/PRICE_AND_DEMAND_202610_${key}.csv`);if(!response.ok)throw Error(`${key}: HTTP ${response.status}`);return [key,parseCSV(await response.text(),key)];}));
  datasets=Object.fromEntries(pairs);render();status.textContent='Loaded: October 2026 · 8,928 validated intervals per region · historical CSV data';
  document.querySelectorAll('[data-region]').forEach(b=>b.disabled=false);
 }catch(error){status.textContent='Data could not be loaded. Check that both CSV files are in data/raw/ and open this page through GitHub Pages or a local web server. Details: '+error.message;status.style.color='#ff7888';}
}
document.querySelectorAll('[data-region]').forEach(b=>b.onclick=()=>{region=b.dataset.region;document.querySelectorAll('[data-region]').forEach(x=>x.classList.toggle('active',x===b));render();});
load();

function hourlySummary(rows){
 const groups=Array.from({length:24},()=>[]);
 for(const row of rows)groups[new Date(row.t-STEP).getUTCHours()].push(row);
 return groups.map((a,hour)=>({hour,count:a.length,price:mean(a.map(r=>r.price)),std:sd(a.map(r=>r.price)),demand:mean(a.map(r=>r.demand))}));
}
function renderIntraday(selected){
 const summaries=Object.fromEntries(selected.map(key=>[key,hourlySummary(datasets[key])]));
 const labels=Array.from({length:24},(_,i)=>String(i).padStart(2,'0')+':00–'+String(i+1).padStart(2,'0')+':00 AEST');
 for(const [id,field,unit] of [['hourPrice','price','AUD/MWh'],['hourStd','std','AUD/MWh'],['hourDemand','demand','MW']]){
  chart(id,selected.map(key=>({name:key,values:summaries[key].map(r=>r[field]),color:key==='TAS1'?'#46dbc3':'#55b7ff',unit})),labels,true);
 }
}

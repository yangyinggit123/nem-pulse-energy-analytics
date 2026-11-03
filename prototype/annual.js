'use strict';
(() => {
 const colors={TAS1:'#46dbc3',VIC1:'#55b7ff'};
 const fmt=v=>Number(v).toLocaleString('en-AU',{maximumFractionDigits:2});
 let monthly,hourly,selected='BOTH';
 function parse(text,required){
  const lines=text.replace(/^\uFEFF/,'').trim().split(/\r?\n/),head=lines.shift().split(',');
  if(required.some(k=>!head.includes(k)))throw Error('Unexpected CSV columns');
  return lines.map(line=>{const values=line.split(',');if(values.length!==head.length)throw Error('Invalid CSV row');const row=Object.fromEntries(head.map((k,i)=>[k,values[i]]));if(!colors[row.region])throw Error('Unexpected region');for(const k of required.filter(k=>!['region','month'].includes(k))){if(!row[k].trim()||!Number.isFinite(Number(row[k])))throw Error('Invalid numeric data');row[k]=Number(row[k]);}return row;});
 }
 function plot(id,rows,key,labels,unit){
  const svg=document.getElementById(id),w=720,h=290,l=80,r=20,t=16,b=48;
  const all=rows.flatMap(s=>s.rows.map(row=>row[key])),max=Math.max(...all),min=Math.min(0,...all),range=max-min||1,low=min<0?min-range*.06:0,high=max+range*.08;
  const X=i=>l+i*(w-l-r)/(labels.length-1),Y=v=>t+(high-v)*(h-t-b)/(high-low);
  let out='';for(let i=0;i<=4;i++){const v=low+(high-low)*i/4;out+=`<line x1="${l}" y1="${Y(v)}" x2="${w-r}" y2="${Y(v)}" stroke="#293b51"/><text x="${l-9}" y="${Y(v)+4}" text-anchor="end" fill="#9cb0ca" font-size="11">${fmt(v)}</text>`;}
  labels.forEach((label,i)=>{if(labels.length===12||i%2===0)out+=`<text x="${X(i)}" y="${h-17}" text-anchor="middle" fill="#9cb0ca" font-size="10">${label}</text>`;});
  for(const series of rows){out+=`<polyline fill="none" stroke="${colors[series.name]}" stroke-width="3" points="${series.rows.map((row,i)=>`${X(i)},${Y(row[key])}`).join(' ')}"/>`;series.rows.forEach((row,i)=>{out+=`<circle cx="${X(i)}" cy="${Y(row[key])}" r="5" fill="${colors[series.name]}"><title>${series.name} | ${row.month||String(row.hour).padStart(2,'0')+':00 AEST'} | ${fmt(row[key])} ${unit}</title></circle>`;});}
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.innerHTML=out;
 }
 function render(){
  if(!monthly||!hourly)return;
  const regions=selected==='BOTH'?['TAS1','VIC1']:[selected];
  const monthSeries=regions.map(name=>({name,rows:monthly.filter(r=>r.region===name).sort((a,b)=>a.month.localeCompare(b.month))}));
  const hourSeries=regions.map(name=>({name,rows:hourly.filter(r=>r.region===name).sort((a,b)=>a.hour-b.hour)}));
  document.getElementById('annualCards').innerHTML=regions.map(region=>{const a=hourly.filter(r=>r.region===region),n=a.reduce((s,r)=>s+r.intervals,0),high=a.reduce((s,r)=>s+r.high_intervals,0);return `<div class="card"><div class="label">${region} · intervals</div><div class="value">${fmt(n)}</div><div class="sub">365 days · 12 months</div></div><div class="card"><div class="label">${region} · RRP &gt; 300</div><div class="value">${high} / ${fmt(100*high/n)}%</div><div class="sub">High-price intervals / annual time share</div></div>`;}).join('');
  plot('annualMonthly',monthSeries,'mean_price',monthSeries[0].rows.map(r=>r.month.slice(2)),'AUD/MWh');
  plot('annualPeak',monthSeries,'peak_price',monthSeries[0].rows.map(r=>r.month.slice(2)),'AUD/MWh');
  for(const [id,key,unit] of [['annualHourPrice','mean_price','AUD/MWh'],['annualHourDemand','mean_demand_mw','MW'],['annualHourRisk','high_pct','%']])plot(id,hourSeries,key,Array.from({length:24},(_,i)=>String(i).padStart(2,'0')),unit);
 }
 document.querySelectorAll('[data-annual]').forEach(b=>{b.disabled=true;b.onclick=()=>{selected=b.dataset.annual;document.querySelectorAll('[data-annual]').forEach(x=>x.classList.toggle('active',x===b));render();};});
 async function load(){try{
  const data=await Promise.all(['annual_monthly_summary','annual_hourly_risk_summary'].map(async file=>{const response=await fetch('../data/processed/'+file+'.csv?v=20261104');if(!response.ok)throw Error('HTTP '+response.status);return response.text();}));
  monthly=parse(data[0],['region','month','intervals','mean_price','peak_price']);hourly=parse(data[1],['region','hour','intervals','mean_demand_mw','mean_price','peak_price','high_intervals','high_pct']);
  const expected=Array.from({length:12},(_,i)=>new Date(Date.UTC(2025,10+i,1)).toISOString().slice(0,7));
  for(const region of ['TAS1','VIC1']){const m=monthly.filter(r=>r.region===region),h=hourly.filter(r=>r.region===region);if(m.length!==12||expected.some(k=>m.filter(r=>r.month===k).length!==1)||m.reduce((s,r)=>s+r.intervals,0)!==105120||h.length!==24||Array.from({length:24},(_,i)=>i).some(k=>h.filter(r=>r.hour===k).length!==1)||h.some(r=>r.intervals!==4380||r.high_intervals<0||r.high_intervals>r.intervals||Math.abs(r.high_pct-100*r.high_intervals/r.intervals)>.006))throw Error('Incomplete or inconsistent summary coverage');}
  render();document.getElementById('annualStatus').textContent='Loaded: 24 monthly groups + 48 hourly groups · November 2025–October 2026';document.querySelectorAll('[data-annual]').forEach(b=>b.disabled=false);
 }catch(error){document.getElementById('annualStatus').textContent='Annual data unavailable: '+error.message;document.getElementById('annualStatus').style.color='#ff7888';}}
 load();
})();

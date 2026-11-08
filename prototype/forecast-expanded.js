(() => {
  const metrics = {"TAS1":[11.75475810185185,12.64840273611111,11.600135404973521,11.190779104011053],"VIC1":[11.358594907407408,9.818195203703704,12.44474803382944,10.187759788681033]};
  const words = {
    en: {
      title:'New experiment · AEMO supply and demand features',
      note:'Train: August 2026 · Evaluate: September 2026 · 744 training and 720 evaluation hours per region. Both trees use the same training period and parameters.',
      region:'Region', model:'Method', mae:'MAE · AUD/MWh', names:['Previous-hour baseline','AEMO reference','History-only tree · August training','Tree + AEMO features · August training'],
      result:'Lower MAE is better. Added features reduce MAE versus the history-only tree by 3.5% in TAS1 and 18.1% in VIC1. AEMO has the lowest MAE in VIC1.',
      limits:'Development evaluation, not an independent test. AEMO inputs include forecast demand, available generation, net interchange, wind and solar. Report generation time is only a proxy for publication availability. Prior-hour actuals are assumed available at the forecast origin. These results do not establish procurement savings.',
      download:'Download hourly predictions (both regions)',
      earlier:'Earlier experiment · longer historical training · VIC1'
    },
    zh: {
      title:'新增实验 · 加入 AEMO 供需预测信息',
      note:'训练：2026 年八月 · 评估：2026 年九月 · 每州训练 744 小时、评估 720 小时。两个树模型使用相同训练期和参数。',
      region:'选择区域', model:'方法', mae:'平均绝对误差 · AUD/MWh', names:['上一小时价格基准','AEMO 参考预测','仅历史信息树模型 · 八月训练','加入 AEMO 信息的树模型 · 八月训练'],
      result:'误差越低越好。相比相同条件的历史模型，加入新信息后塔州 MAE 下降约 3.5%，维州下降约 18.1%。维州仍以 AEMO 参考预测的 MAE 最低。',
      limits:'本次为开发评估，并非独立测试。新增输入包括预测需求、可用发电容量、净交换、风电和光伏。报告生成时间只是实际发布时间的代理；假设整点已可取得上一小时实际数据。结果尚不能证明能节省购电成本。',
      download:'下载两州逐小时预测结果',
      earlier:'早期实验 · 使用更长历史训练期 · 维州'
    }
  };
  const el = id => document.getElementById(id);
  const earlier = document.createElement('h2');
  earlier.style.marginTop='32px';
  el('metrics').before(earlier);
  function render(lang) {
    const t=words[lang] || words.en;
    el('expandedTitle').textContent=t.title;
    el('expandedNote').textContent=t.note;
    el('expandedRegionLabel').textContent=t.region;
    el('expandedHead').innerHTML=`<tr><th>${t.model}</th><th>${t.mae}</th></tr>`;
    const values=metrics[el('expandedRegion').value], best=Math.min(...values);
    el('expandedRows').innerHTML=values.map((n,i)=>`<tr><td>${t.names[i]}</td><td${n===best?' style="color:#46dbc3;font-weight:800"':''}>${n.toFixed(2)}</td></tr>`).join('');
    el('expandedResult').textContent=t.result;
    el('expandedLimits').textContent=t.limits;
    el('expandedDownload').textContent=t.download;
    earlier.textContent=t.earlier;
  }
  let language=localStorage.getItem('nem-language') || 'en';
  render(language);
  el('expandedRegion').addEventListener('change',()=>render(language));
  document.querySelectorAll('[data-lang]').forEach(b=>b.addEventListener('click',()=>{language=b.dataset.lang;render(language);}));
})();

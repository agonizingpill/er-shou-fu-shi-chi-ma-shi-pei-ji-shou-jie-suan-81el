import{esc}from'../utils/format.js';
import{form,input,select,badge}from'../components/tailor.js';
import{FIT_LABELS,NONE_SUGGESTION,CUT_NAMES}from'../constants.js';
const SUG_COLS=[...FIT_LABELS,NONE_SUGGESTION];

export function trialOf(d,fittingId){return d.trials.find(t=>t.fitting_id===fittingId)}

export function liveConfusion(d){
 const byCut={};
 for(const t of d.trials.filter(x=>x.state==='completed')){
  const cut=t.cut;
  if(!byCut[cut])byCut[cut]={cut,cut_name:CUT_NAMES[cut]??cut,total:0,mismatch:0,matrix:Object.fromEntries(FIT_LABELS.map(a=>[a,Object.fromEntries(SUG_COLS.map(b=>[b,0]))]))};
  const cell=byCut[cut],sug=t.suggested??NONE_SUGGESTION;
  cell.matrix[t.actual][sug]++;cell.total++;
  if(t.suggested===null||t.suggested!==t.actual)cell.mismatch++;
 }
 return Object.values(byCut).sort((a,b)=>a.cut-b.cut);
}

function matrixTable(cell){
 return `<table class="confusion"><thead><tr><th>实际 ＼ 模型建议</th>${SUG_COLS.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${FIT_LABELS.map(a=>`<tr><td><b>${esc(a)}</b></td>${SUG_COLS.map(b=>`<td class="${a!==b?'off':''}">${cell.matrix[a][b]||''}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

export function confusionSection(d){
 const cells=liveConfusion(d);
 if(!cells.length)return `<div class="fit-result"><h2>按版型看错判</h2><p>还没有试完登记的松紧记录。开试并登记实际松紧后，这里按版型展示实际松紧被模型建议成了哪一类。</p></div>`;
 return `<div class="fit-result confusion-block"><h2>按版型看错判（实际松紧 ＼ 模型建议）</h2>${cells.map(c=>`<article class="confusion-card"><h3>版型 ${c.cut} · ${esc(c.cut_name)}<small>共 ${c.total} 次试衣，错判/无建议 ${c.mismatch} 次</small></h3>${matrixTable(c)}</article>`).join('')}<small>行是买家试衣后的实际松紧，列是开试时记下的模型建议；“${NONE_SUGGESTION}”列单独统计开试时没有拿到适配建议的试衣。</small></div>`;
}

export function trialLedger(d){
 if(!d.trials.length)return '';
 return `<div class="fit-result"><h2>试衣松紧登记与改判</h2><table><thead><tr><th>试衣</th><th>衣物/版型</th><th>归账日期</th><th>模型建议</th><th>实际松紧</th><th>版本</th><th>状态</th></tr></thead><tbody>${d.trials.map(t=>{const g=d.garments.find(x=>x.id===t.garment_id);return `<tr><td>#${t.id}<br>预约#${t.fitting_id}</td><td>${esc(g?.code??'')}<br>${esc(CUT_NAMES[t.cut]??t.cut)}</td><td>${esc(t.fitting_day)}</td><td>${esc(t.suggested??NONE_SUGGESTION)}</td><td>${esc(t.actual??'—')}</td><td>v${t.version}</td><td>${badge(t.state)}</td></tr>`}).join('')}</tbody></table>${d.trial_revisions.length?`<h3>改判留痕</h3><table><thead><tr><th>试衣</th><th>原判定</th><th>改判后</th><th>基于版本</th><th>改判人</th><th>时间</th><th>理由</th></tr></thead><tbody>${d.trial_revisions.map(r=>`<tr><td>#${r.trial_id}</td><td>${esc(r.old_actual)}</td><td><b>${esc(r.new_actual)}</b></td><td>v${r.base_version}→v${r.new_version}</td><td>${esc(r.actor)}</td><td>${esc(r.revised_at)}</td><td>${esc(r.reason)}</td></tr>`).join('')}</tbody></table>`:''}</div>`;
}

function reportMatrix(payload){
 if(!payload?.by_cut?.length)return '<p>该归账日期下暂无已完成试衣。</p>';
 return payload.by_cut.map(c=>`<article class="confusion-card"><h3>版型 ${c.cut} · ${esc(c.cut_name)}<small>共 ${c.total} 次，错判/无建议 ${c.mismatch} 次</small></h3>${matrixTable({matrix:c.matrix})}</article>`).join('');
}

export function reportsSection(d,canWrite){
 const groups={};
 for(const r of d.daily_reports)(groups[r.day]??=[]).push(r);
 const days=Object.keys(groups).sort().reverse();
 return `<div class="fit-result reports-block"><h2>试衣松紧日报（按试衣当天归账）</h2>${canWrite?form('daily-run','重跑/补发某日日报','/daily-reports/run',input('day','试衣日期 YYYY-MM-DD','2026-11-16')):'<p>只读账号可查看全部原版与修订版，不能重跑。</p>'}${days.length?days.map(day=>`<article class="report-day"><h3>${esc(day)} · ${groups[day].length} 个版本</h3>${groups[day].map(r=>`<details class="report-version" ${r.version===Math.max(...groups[day].map(x=>x.version))?'open':''}><summary>v${r.version} · ${r.version===Math.max(...groups[day].map(x=>x.version))?'最新修订版':'原版'} · 生成于 ${esc(r.created_at)}${r.reused?` · 重跑沿用 ${r.reused} 次`:''}</summary><p>试衣 ${r.payload.trial_total} 次；数据指纹 <code>${esc(r.data_hash.slice(0,16))}…</code>；数据没变的重跑只累加沿用次数，不产生新版本。</p>${reportMatrix(r.payload)}</details>`).join('')}</article>`).join(''):'<p>还没有发布过日报。输入试衣日期重跑：迟到登记与改判归试衣当天，数据变化才生成修订版，原版照样保留可查。</p>'}</div>`;
}

export function trialActions(d,canWrite){
 return d.fittings.map(f=>{
  const t=trialOf(d,f.id);
  if(f.state==='cancelled')return '';
  const g=d.garments.find(x=>x.id===f.garment_id);
  const block=[];
  if(!t&&canWrite&&f.state==='reserved')block.push(form(`trial-start-${f.id}`,'开试：记下本件建议','/trials/start',`<input type="hidden" name="fitting_id" value="${f.id}"><p>衣物 ${esc(g?.code??'')}，开试时自动留存当时模型建议；没有适配结果将记为“${NONE_SUGGESTION}”并另计。</p>`));
  if(t&&t.state==='in_progress')block.push(canWrite?form(`trial-complete-${f.id}`,'试完登记实际松紧','/trials/complete',`<input type="hidden" name="fitting_id" value="${f.id}">${select('actual','实际松紧',FIT_LABELS.map(x=>`<option ${x==='偏紧'?'selected':''}>${esc(x)}</option>`).join(''))}`):`<p>${badge(t.state)}建议：${esc(t.suggested??NONE_SUGGESTION)}</p>`);
  if(t&&t.state==='completed')block.push(`<p class="receipt">开试建议 <b>${esc(t.suggested??NONE_SUGGESTION)}</b> ／ 实际 <b>${esc(t.actual)}</b>（v${t.version}，归 ${esc(t.fitting_day)}）</p>`+(canWrite?form(`trial-revise-${t.id}`,'改判（先看最新判定）','/trials/revise',`<input type="hidden" name="trial_id" value="${t.id}">${input('base_version','当前最新版本（已自动带出）',t.version,'number')}${select('actual','改判为',FIT_LABELS.filter(x=>x!==t.actual).map(x=>`<option>${esc(x)}</option>`).join(''))}${input('reason','改判理由（至少8字）','买家复穿后确认肩部仍偏紧')}`):''));
  return block.join('');
 }).filter(Boolean).join('');
}

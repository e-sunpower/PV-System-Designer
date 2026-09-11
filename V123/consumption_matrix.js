(function(){
  'use strict';
  const MATRIX_KEY='esun_power_consumption_matrix_v2';
  let rows=[];
  let originalGetAnnual=null;
  let originalGetProjectFormState=null;
  let originalSetProjectFormState=null;

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function num(v,def=0){const n=Number(v);return Number.isFinite(n)?n:def;}
  function fmt(v,d=2){return num(v).toLocaleString('es-CO',{minimumFractionDigits:d,maximumFractionDigits:d});}
  function timeToMinutes(t){
    if(!/^\d{2}:\d{2}$/.test(String(t||''))) return null;
    const [h,m]=String(t).split(':').map(Number);
    if(h>23||m>59)return null;
    return h*60+m;
  }
  function minutesToHours(on,off){
    const a=timeToMinutes(on),b=timeToMinutes(off);
    if(a===null||b===null)return 0;
    let d=b-a;
    if(d<=0)d+=1440;
    return d/60;
  }
  function calc(r){
    const qty=Math.max(0,num(r.qty,1));
    const power=Math.max(0,num(r.power,0));
    const hours=minutesToHours(r.on,r.off);
    const days=Math.max(0,Math.min(31,num(r.days,30)));
    const util=Math.max(0,Math.min(100,num(r.util,100)))/100;
    const daily=qty*power*hours*util/1000;
    return {hours,daily,monthly:daily*days,annual:daily*days*12};
  }
  function defaultRow(){return{id:'cm_'+Date.now()+'_'+Math.random().toString(36).slice(2,8),equipment:'',qty:1,power:0,on:'08:00',off:'17:00',days:30,util:100};}
  function normalizeRow(r){
    const x={...defaultRow(),...(r||{})};
    // Migrate V1 rows that only had hours/day. Preserve their energy by mapping the hours to a start/end interval.
    if(!x.on && x.hours>0){x.on='08:00';const end=(8+Number(x.hours))%24;x.off=String(Math.floor(end)).padStart(2,'0')+':'+String(Math.round(((8+Number(x.hours))%1)*60)).padStart(2,'0');}
    return x;
  }
  function totalAnnual(){return rows.reduce((s,r)=>s+calc(r).annual,0);}
  function totalMonthly(){return rows.reduce((s,r)=>s+calc(r).monthly,0);}
  function totalDaily(){return rows.reduce((s,r)=>s+calc(r).daily,0);}

  function hourlyProfile(){
    const profile=Array.from({length:24},()=>0);
    rows.forEach(r=>{
      const on=timeToMinutes(r.on),off=timeToMinutes(r.off);
      if(on===null||off===null)return;
      const qty=Math.max(0,num(r.qty,1));
      const power=Math.max(0,num(r.power,0));
      const util=Math.max(0,Math.min(100,num(r.util,100)))/100;
      if(!power||!qty||!util)return;
      let end=off;
      if(end<=on)end+=1440;
      for(let h=0;h<24;h++){
        const start=h*60,finish=(h+1)*60;
        // Check this hour and the corresponding next-day hour for overnight operation.
        let overlap=Math.max(0,Math.min(end,finish)-Math.max(on,start));
        if(end>1440){
          const nextStart=start+1440,nextFinish=finish+1440;
          overlap+=Math.max(0,Math.min(end,nextFinish)-Math.max(on,nextStart));
        }
        if(overlap>0)profile[h]+=qty*power/1000*(overlap/60)*util;
      }
    });
    return profile;
  }

  function ensureStyles(){
    if(document.getElementById('consumptionMatrixStyles'))return;
    const st=document.createElement('style');st.id='consumptionMatrixStyles';
    st.textContent=`
      #panel-matrix{display:none}#panel-matrix.active{display:block}
      .cm-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
      .cm-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
      .cm-table-wrap{width:100%;overflow-x:auto;border:1px solid #414141;border-radius:8px}
      .cm-table{width:100%;min-width:1160px;border-collapse:collapse;margin:0}
      .cm-table th{font-size:10px;white-space:normal;text-align:center;background:#303030;padding:8px 5px;line-height:1.15}
      .cm-table td{padding:6px;border-bottom:1px solid #414141;vertical-align:middle}
      .cm-table input{width:100%;min-width:0;padding:8px 6px;font-size:12px}
      .cm-table .cm-eq{min-width:170px}.cm-table .cm-num{min-width:70px;text-align:right}.cm-table .cm-time{min-width:100px;text-align:center}
      .cm-table .cm-result{font-weight:700;text-align:right;white-space:nowrap;font-size:12px}.cm-hours{color:#fff;font-weight:700;text-align:center;white-space:nowrap}
      .cm-delete{background:#5d6972;padding:8px 10px;font-size:11px;white-space:nowrap}
      .cm-totals{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.cm-total{background:#303030;border:1px solid #414141;border-radius:8px;padding:12px}.cm-total small{display:block;color:#fff}.cm-total b{display:block;font-size:20px;margin-top:5px}
      .cm-note{padding:10px;background:#302d24;border:1px solid #655b3e;border-radius:7px;margin-top:12px}
      .cm-profile{margin-top:18px;background:#252525;border:1px solid #414141;border-radius:8px;padding:14px}.cm-profile h3{margin:0 0 5px;font-size:16px}.cm-profile p{margin:0 0 12px;font-size:12px;color:#ddd}
      .cm-chart{display:grid;grid-template-columns:repeat(24,minmax(20px,1fr));gap:4px;align-items:end;height:220px;padding:12px 8px 0;border-bottom:1px solid #555;background:#202020;border-radius:6px;overflow-x:auto}
      .cm-barcol{height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;min-width:20px}.cm-bar{width:70%;min-height:2px;background:#f2b705;border-radius:3px 3px 0 0;transition:height .15s}.cm-hour{font-size:9px;color:#ddd;margin-top:5px;white-space:nowrap}.cm-barval{font-size:8px;color:#fff;min-height:11px;white-space:nowrap;transform:rotate(-45deg);transform-origin:center}
      .cm-profile-summary{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;font-size:12px}.cm-profile-summary b{font-size:14px}
      @media(max-width:900px){.cm-totals{grid-template-columns:1fr}.cm-profile{overflow:hidden}.cm-chart{min-width:720px}}
    `;document.head.appendChild(st);
  }

  function render(){
    const body=document.getElementById('consumptionMatrixBody');if(!body)return;
    body.innerHTML=rows.map((r,i)=>{
      const c=calc(r);
      return `<tr data-id="${esc(r.id)}">
        <td style="text-align:center">${i+1}</td>
        <td><input class="cm-eq" data-field="equipment" value="${esc(r.equipment)}" placeholder="Ej. Aire acondicionado"></td>
        <td><input class="cm-num" data-field="qty" type="number" min="0" step="1" value="${num(r.qty,1)}"></td>
        <td><input class="cm-num" data-field="power" type="number" min="0" step="1" value="${num(r.power,0)}"></td>
        <td><input class="cm-time" data-field="on" type="time" value="${esc(r.on||'08:00')}"></td>
        <td><input class="cm-time" data-field="off" type="time" value="${esc(r.off||'17:00')}"></td>
        <td class="cm-hours">${fmt(c.hours,2)} h</td>
        <td><input class="cm-num" data-field="days" type="number" min="0" max="31" step="1" value="${num(r.days,30)}"></td>
        <td><input class="cm-num" data-field="util" type="number" min="0" max="100" step="1" value="${num(r.util,100)}"></td>
        <td class="cm-result cm-daily">${fmt(c.daily)}</td>
        <td class="cm-result cm-monthly">${fmt(c.monthly)}</td>
        <td class="cm-result cm-annual">${fmt(c.annual)}</td>
        <td><button type="button" class="cm-delete" data-delete="1">ELIMINAR</button></td>
      </tr>`;
    }).join('');
    updateTotals();renderProfile();
  }

  function updateTotals(){
    const d=totalDaily(),m=totalMonthly(),a=totalAnnual();
    const set=(id,v,suf)=>{const e=document.getElementById(id);if(e)e.textContent=fmt(v)+(suf||'');};
    set('cmTotalDaily',d,' kWh/día');set('cmTotalMonthly',m,' kWh/mes');set('cmTotalAnnual',a,' kWh/año');
    const annualView=document.getElementById('annualView');
    if(window.__esunConsumptionMatrixActive&&annualView)annualView.textContent=a>0?fmt(a)+' kWh/año':'—';
  }

  function renderProfile(){
    const chart=document.getElementById('cmHourlyChart');if(!chart)return;
    const p=hourlyProfile();const max=Math.max(...p,0.001);const total=p.reduce((a,b)=>a+b,0);
    chart.innerHTML=p.map((v,h)=>{const pct=Math.max(0,Math.min(100,(v/max)*100));return `<div class="cm-barcol"><div class="cm-barval">${v>0?fmt(v,2):''}</div><div class="cm-bar" style="height:${Math.max(v>0?2:0,pct)}%" title="${String(h).padStart(2,'0')}:00 — ${fmt(v,2)} kWh"></div><div class="cm-hour">${String(h).padStart(2,'0')}h</div></div>`;}).join('');
    const peak=Math.max(...p);const peakH=p.indexOf(peak);const peakEl=document.getElementById('cmPeak');if(peakEl)peakEl.textContent=peak>0?`${String(peakH).padStart(2,'0')}:00 — ${fmt(peak,2)} kWh/h`:'—';
    const profileTotal=document.getElementById('cmProfileTotal');if(profileTotal)profileTotal.textContent=fmt(total)+' kWh/día';
  }

  function activateMatrix(){window.__esunConsumptionMatrixActive=true;document.querySelectorAll('.tabs .tab').forEach(x=>x.classList.toggle('active',x.dataset.tab==='matrix'));document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id==='panel-matrix'));updateTotals();renderProfile();if(typeof window.updateConsumption==='function')window.updateConsumption();}
  function deactivateMatrix(){window.__esunConsumptionMatrixActive=false;}
  function persistLocal(){try{localStorage.setItem(MATRIX_KEY,JSON.stringify(rows));}catch(e){}}
  function loadLocal(){
    try{
      let raw=localStorage.getItem(MATRIX_KEY);
      if(!raw)raw=localStorage.getItem('esun_power_consumption_matrix_v1');
      const r=JSON.parse(raw||'[]');if(Array.isArray(r)&&r.length)rows=r.map(normalizeRow);
    }catch(e){}
  }

  function installPanel(){
    const tabs=document.querySelector('.tabs');if(!tabs||document.getElementById('panel-matrix'))return;
    ensureStyles();
    const b=document.createElement('button');b.type='button';b.className='tab';b.dataset.tab='matrix';b.textContent='Matriz de consumo';tabs.appendChild(b);
    const panel=document.createElement('div');panel.id='panel-matrix';panel.className='panel';
    panel.innerHTML=`
      <div class="cm-head"><div><label class="label" style="margin-top:0">Matriz de consumo por equipos</label><p class="muted" style="margin:0">Utilice esta opción cuando no disponga de una factura o de un consumo histórico confiable. Defina el horario de operación de cada carga; E-SUN POWER calculará automáticamente las horas/día, el consumo diario, mensual y anual y el perfil horario de demanda.</p></div></div>
      <div class="cm-actions"><button type="button" class="sun-btn" id="cmAdd">+ AÑADIR EQUIPO</button><button type="button" class="secondary" id="cmExample">CARGAR EJEMPLO</button></div>
      <div class="cm-table-wrap"><table class="cm-table"><thead><tr><th>#</th><th>Equipo / carga</th><th>Cantidad</th><th>Potencia (W)</th><th>Hora de encendido</th><th>Hora de apagado</th><th>Horas/día</th><th>Días/mes</th><th>Utilización (%)</th><th>kWh/día</th><th>kWh/mes</th><th>kWh/año</th><th>Acción</th></tr></thead><tbody id="consumptionMatrixBody"></tbody></table></div>
      <div class="cm-totals"><div class="cm-total"><small>CONSUMO DIARIO TOTAL</small><b id="cmTotalDaily">0,00 kWh/día</b></div><div class="cm-total"><small>CONSUMO MENSUAL TOTAL</small><b id="cmTotalMonthly">0,00 kWh/mes</b></div><div class="cm-total"><small>CONSUMO ANUAL TOTAL</small><b id="cmTotalAnnual">0,00 kWh/año</b></div></div>
      <div class="cm-profile"><h3>DIAGRAMA DE CONSUMO — 24 HORAS</h3><p>Perfil horario estimado del consumo diario. Cada barra representa los kWh consumidos durante esa hora, considerando cantidad, potencia, horario de operación y factor de utilización de cada equipo.</p><div class="cm-chart" id="cmHourlyChart"></div><div class="cm-profile-summary"><span>Consumo representado: <b id="cmProfileTotal">0,00 kWh/día</b></span><span>Pico horario: <b id="cmPeak">—</b></span></div></div>
      <div class="cm-note"><b>Criterio de cálculo:</b> Horas/día se obtiene automáticamente a partir de la hora de encendido y la hora de apagado. Si la hora de apagado es anterior o igual a la de encendido, E-SUN POWER interpreta que el equipo continúa funcionando después de medianoche. El consumo diario es Cantidad × Potencia × Horas/día × Utilización / 1.000. El perfil de 24 horas distribuye ese consumo según el horario real de operación.</div>`;
    tabs.parentNode.insertBefore(panel,tabs.nextSibling);
    if(!rows.length)rows=[defaultRow()];
    render();
    b.addEventListener('click',activateMatrix);
    tabs.querySelectorAll('.tab:not([data-tab="matrix"])').forEach(x=>x.addEventListener('click',deactivateMatrix));
    panel.addEventListener('input',e=>{if(e.target.matches('[data-field]')){updateRowFromInput(e.target);persistLocal();}});
    panel.addEventListener('change',e=>{if(e.target.matches('[data-field]')){updateRowFromInput(e.target);persistLocal();}});
    panel.addEventListener('click',e=>{
      const del=e.target.closest('[data-delete]');
      if(del){const tr=del.closest('tr');rows=rows.filter(r=>String(r.id)!==String(tr?.dataset.id));if(!rows.length)rows=[defaultRow()];render();persistLocal();if(window.__esunConsumptionMatrixActive&&typeof window.updateConsumption==='function')window.updateConsumption();}
      if(e.target.id==='cmAdd'){rows.push(defaultRow());render();persistLocal();}
      if(e.target.id==='cmExample'){rows=[
        {id:'ex1',equipment:'Aire acondicionado',qty:2,power:1200,on:'18:00',off:'00:00',days:30,util:70},
        {id:'ex2',equipment:'Nevera',qty:1,power:300,on:'00:00',off:'23:59',days:30,util:60},
        {id:'ex3',equipment:'Iluminación LED',qty:12,power:12,on:'18:00',off:'23:00',days:30,util:100},
        {id:'ex4',equipment:'Computador',qty:2,power:150,on:'08:00',off:'17:00',days:22,util:80},
        {id:'ex5',equipment:'Bomba de agua',qty:1,power:750,on:'06:00',off:'08:00',days:30,util:80}
      ];render();persistLocal();activateMatrix();}
    });
  }

  function updateRowFromInput(input){
    const tr=input.closest('tr');if(!tr)return;
    const r=rows.find(x=>String(x.id)===String(tr.dataset.id));if(!r)return;
    const field=input.dataset.field;
    if(field==='equipment'||field==='on'||field==='off')r[field]=input.value;
    else r[field]=num(input.value,0);
    const c=calc(r);
    const hours=tr.querySelector('.cm-hours');if(hours)hours.textContent=fmt(c.hours,2)+' h';
    const daily=tr.querySelector('.cm-daily'),monthly=tr.querySelector('.cm-monthly'),annual=tr.querySelector('.cm-annual');
    if(daily)daily.textContent=fmt(c.daily);if(monthly)monthly.textContent=fmt(c.monthly);if(annual)annual.textContent=fmt(c.annual);
    updateTotals();renderProfile();
  }

  function patchAnnual(){
    if(typeof window.getAnnual==='function'&&!window.getAnnual.__matrixPatched){
      originalGetAnnual=window.getAnnual;
      const patched=function(){return window.__esunConsumptionMatrixActive?totalAnnual():originalGetAnnual();};patched.__matrixPatched=true;window.getAnnual=patched;
    }
    if(typeof window.getProjectFormState==='function'&&!window.getProjectFormState.__matrixPatched){
      originalGetProjectFormState=window.getProjectFormState;
      const fn=function(){const state=originalGetProjectFormState();state.fields=state.fields||{};state.fields.consumptionMatrix=rows.map(normalizeRow);return state;};fn.__matrixPatched=true;window.getProjectFormState=fn;
    }
    if(typeof window.setProjectFormState==='function'&&!window.setProjectFormState.__matrixPatched){
      originalSetProjectFormState=window.setProjectFormState;
      const fn=function(state){const matrix=state?.fields?.consumptionMatrix;if(Array.isArray(matrix)){rows=matrix.map(normalizeRow);render();}originalSetProjectFormState(state);if(Array.isArray(matrix))render();};fn.__matrixPatched=true;window.setProjectFormState=fn;
    }
  }
  function init(){loadLocal();installPanel();patchAnnual();let n=0;const t=setInterval(()=>{patchAnnual();if(++n>30)clearInterval(t);},250);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

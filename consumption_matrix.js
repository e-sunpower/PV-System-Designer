(function(){
  'use strict';
  const MATRIX_KEY='esun_power_consumption_matrix_v2';
  let rows=[];
  let originalGetAnnual=null;
  let originalGetProjectFormState=null;
  let originalSetProjectFormState=null;
  const $=id=>document.getElementById(id);
  const num=(v,d=0)=>{const n=Number(v);return Number.isFinite(n)?n:d;};
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>num(v).toLocaleString('es-CO',{minimumFractionDigits:2,maximumFractionDigits:2});
  const offGrid=()=>($('systemType')?.value||'ON-GRID')==='OFF-GRID';

  function timeMinutes(v){
    if(typeof v!=='string')return null;
    const m=v.match(/^(\d{1,2}):(\d{2})$/); if(!m)return null;
    const h=Number(m[1]),mi=Number(m[2]);
    return h>=0&&h<24&&mi>=0&&mi<60?h*60+mi:null;
  }
  function hoursFromSchedule(r){
    const a=timeMinutes(r.start),b=timeMinutes(r.end);
    if(a===null||b===null)return Math.max(0,num(r.hours,0));
    let d=b-a;if(d<0)d+=1440;
    return d/60;
  }
  function calc(r){
    const qty=Math.max(0,num(r.qty,1)),power=Math.max(0,num(r.power,0)),hours=hoursFromSchedule(r),days=Math.max(0,num(r.days,30)),util=Math.max(0,Math.min(100,num(r.util,100)))/100;
    const daily=qty*power*hours*util/1000;
    return {daily,monthly:daily*days,annual:daily*days*12,hours};
  }
  function defaultRow(){return{id:'cm_'+Date.now()+'_'+Math.random().toString(36).slice(2,8),equipment:'',qty:1,power:0,start:'08:00',end:'13:00',hours:5,days:30,util:100,backup:false};}
  function normalize(r){const x={...defaultRow(),...(r||{})};if(!x.start&&x.start!==0)x.start='08:00';if(!x.end&&x.end!==0)x.end='13:00';x.hours=hoursFromSchedule(x);x.backup=Boolean(x.backup);return x;}
  function total(kind){return rows.reduce((s,r)=>s+calc(r)[kind],0);}
  function backupRows(){return offGrid()?rows.filter(r=>r.backup):[];}
  function backupTotal(k){return backupRows().reduce((s,r)=>s+calc(r)[k],0);}
  function backupPeakKw(){return backupRows().reduce((s,r)=>s+Math.max(0,num(r.qty,1))*Math.max(0,num(r.power,0))/1000,0);}

  function battery(){
    try{const arr=typeof batteries!=='undefined'?batteries:(window.batteries||[]);return arr?.[Number($('battery')?.value)||0]||null;}catch(e){return null;}
  }
  function autonomy(){return Math.max(.25,num($('batteryStorageHours')?.value,1));}
  function batterySizing(){
    if(!offGrid())return null;
    const b=battery();if(!b)return null;
    const usable=Number(b.usable_capacity_kwh||0)||Number(b.capacity_kwh||0)*(Number(b.recommended_dod_pct||80)/100);if(usable<=0)return null;
    const daily=backupTotal('daily'),required=daily*autonomy(),peak=backupPeakKw();
    const qe=required>0?Math.max(1,Math.ceil(required/usable)):0;
    const dp=Number(b.recommended_discharge_power_kw||0),cp=Number(b.recommended_charge_power_kw||0);
    const qd=dp>0&&peak>0?Math.max(1,Math.ceil(peak/dp)):0;
    const dc=Number((typeof lastDesign!=='undefined'&&lastDesign?.system?.dc_kwp)||0)||0;
    const qc=cp>0&&dc>0?Math.max(1,Math.ceil(dc/cp)):0;
    const qty=Math.max(qe,qd,qc,required>0?1:0);
    return{daily,monthly:backupTotal('monthly'),annual:backupTotal('annual'),required,usable,qty,installed:qty*usable,cost:qty*Number(b.price_cop||0),peak,qe,qd,qc,days:autonomy()};
  }

  function batteryIcon(){return '<span class="cm-batt-icon"><svg viewBox="0 0 24 24"><rect x="3" y="6" width="16" height="12" rx="2" fill="#f2b705" stroke="#1d1d1d" stroke-width="1.4"/><rect x="19" y="10" width="2" height="4" rx=".6" fill="#f2b705"/><rect x="6" y="9" width="3" height="6" rx=".7" fill="#fff2a6"/><rect x="10.5" y="9" width="3" height="6" rx=".7" fill="#fff2a6"/></svg></span>';}
  function backupBtn(r){const a=Boolean(r.backup);return '<button type="button" class="cm-backup '+(a?'active':'')+'" data-backup="1" '+(!offGrid()?'disabled':'')+'>'+batteryIcon()+'<span>'+(a?'RESPALDO ACTIVO':'RESPALDAR')+'</span></button><span class="cm-backup-hint">'+(!offGrid()?'Solo OFF-GRID':(a?'Quitar respaldo':'Agregar al respaldo'))+'</span>';}

  function ensureStyles(){if($('consumptionMatrixStyles'))return;const st=document.createElement('style');st.id='consumptionMatrixStyles';st.textContent=`
#panel-matrix{display:none}#panel-matrix.active{display:block}.cm-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}.cm-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.cm-table-wrap{width:100%;overflow-x:auto;border:1px solid #414141;border-radius:8px}.cm-table{width:100%;min-width:1240px;border-collapse:collapse}.cm-table th{font-size:11px;white-space:normal;text-align:center;background:#303030;padding:8px 6px}.cm-table td{padding:6px;border-bottom:1px solid #414141;vertical-align:middle}.cm-table input{width:100%;min-width:0;padding:8px 7px;font-size:12px}.cm-table .cm-eq{min-width:170px}.cm-table .cm-num{min-width:72px;text-align:right}.cm-table .cm-time{min-width:88px;text-align:center}.cm-result{font-weight:700;text-align:right;white-space:nowrap;font-size:12px}.cm-delete{background:#5d6972;padding:8px 10px;font-size:11px}.cm-backup{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-width:112px;background:#3d4246;color:#fff;border:1px solid #666;padding:8px 9px;font-size:10px;font-weight:700;white-space:nowrap}.cm-batt-icon{display:inline-flex;width:17px;height:17px}.cm-batt-icon svg{width:17px;height:17px}.cm-backup.active{background:#f2b705;color:#151515;border-color:#ffd33d;box-shadow:0 0 9px rgba(255,205,40,.38)}.cm-backup:disabled{opacity:.42;cursor:not-allowed}.cm-backup-hint{display:block;margin-top:3px;font-size:9px;color:#bbb}.cm-totals{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.cm-total{background:#303030;border:1px solid #414141;border-radius:8px;padding:12px}.cm-total small{display:block;color:#fff}.cm-total b{display:block;font-size:20px;margin-top:5px}.cm-backup-total{margin-top:12px;background:#302d24;border:1px solid #8a7220;border-radius:8px;padding:13px}.cm-backup-total .cm-bt-title{font-weight:800;color:#ffd33d}.cm-backup-total .cm-bt-value{font-size:23px;font-weight:800;margin-top:3px}.cm-chart-card{margin-top:14px;background:#303030;border:1px solid #414141;border-radius:8px;padding:14px}.cm-chart-wrap{height:300px;position:relative}.cm-chart-wrap canvas{width:100%;height:100%;display:block}.cm-chart-legend{display:flex;gap:18px;flex-wrap:wrap;font-size:11px;margin-top:8px}.cm-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;background:#f2b705}.cm-dot2{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;background:#6f8798}@media(max-width:900px){.cm-totals{grid-template-columns:1fr}.cm-chart-wrap{height:240px}}
`;document.head.appendChild(st);}

  function render(){
    const body=$('consumptionMatrixBody');if(!body)return;
    body.innerHTML=rows.map((r,i)=>{const c=calc(r);return `<tr data-id="${esc(r.id)}"><td style="text-align:center">${i+1}</td><td><input class="cm-eq" data-field="equipment" value="${esc(r.equipment)}" placeholder="Ej. Bomba de riego"></td><td><input class="cm-num" data-field="qty" type="number" min="0" step="1" value="${num(r.qty,1)}"></td><td><input class="cm-num" data-field="power" type="number" min="0" step="1" value="${num(r.power,0)}"></td><td><input class="cm-time" data-field="start" type="time" value="${esc(r.start||'08:00')}"></td><td><input class="cm-time" data-field="end" type="time" value="${esc(r.end||'13:00')}"></td><td class="cm-result cm-hours">${fmt(c.hours)}</td><td><input class="cm-num" data-field="days" type="number" min="0" max="31" step="1" value="${num(r.days,30)}"></td><td><input class="cm-num" data-field="util" type="number" min="0" max="100" step="1" value="${num(r.util,100)}"></td><td class="cm-result cm-daily">${fmt(c.daily)}</td><td class="cm-result cm-monthly">${fmt(c.monthly)}</td><td class="cm-result cm-annual">${fmt(c.annual)}</td><td>${backupBtn(r)}<button type="button" class="cm-delete" data-delete="1" style="margin-top:4px">ELIMINAR</button></td></tr>`;}).join('');
    updateTotals();
  }
  function updateTotals(){
    const d=total('daily'),m=total('monthly'),a=total('annual'),bd=backupTotal('daily'),bm=backupTotal('monthly'),ba=backupTotal('annual');
    const set=(id,v)=>{if($(id))$(id).textContent=fmt(v);};set('cmTotalDaily',d);set('cmTotalMonthly',m);set('cmTotalAnnual',a);set('cmBackupDaily',bd);set('cmBackupMonthly',bm);set('cmBackupAnnual',ba);
    if(window.__esunConsumptionMatrixActive&&$('annualView'))$('annualView').textContent=a>0?fmt(a)+' kWh/año':'—';
    updateBattery();drawChart();
  }
  function updateRow(input){
    const tr=input.closest('tr');if(!tr)return;const r=rows.find(x=>String(x.id)===String(tr.dataset.id));if(!r)return;const f=input.dataset.field;
    if(f==='equipment'||f==='start'||f==='end')r[f]=input.value;else r[f]=num(input.value,0);r.hours=hoursFromSchedule(r);
    const c=calc(r);tr.querySelector('.cm-hours').textContent=fmt(c.hours);tr.querySelector('.cm-daily').textContent=fmt(c.daily);tr.querySelector('.cm-monthly').textContent=fmt(c.monthly);tr.querySelector('.cm-annual').textContent=fmt(c.annual);updateTotals();persist();
  }

  function updateBattery(){
    const card=$('offgridBatteryCard');if(card){const title=card.querySelector('h2');if(title)title.textContent='2. Banco de baterías — OFF-GRID';const labels=card.querySelectorAll('.metrics .metric span');if(labels[0])labels[0].textContent='CONSUMO A RESPALDAR';if(labels[1])labels[1].textContent='Energía requerida de batería';const input=$('batteryStorageHours');if(input){input.min='.25';input.step='.25';if(!input.dataset.cmInit){input.value='1';input.dataset.cmInit='1';}const lab=input.parentElement?.querySelector('.label');if(lab)lab.textContent='Días de autonomía';}const note=$('batterySizingNote');if(note)note.textContent='Criterio: consumo seleccionado para respaldo × días de autonomía. Se verifica energía útil y potencia de descarga/carga.';}
    const r=batterySizing();const set=(id,v)=>{if($(id))$(id).textContent=v;};
    if(!offGrid()||!r){set('batteryDcKwp',offGrid()?fmt(backupTotal('daily'))+' kWh/día':'—');set('batteryRequired','—');set('batteryQty','—');set('batteryInstalled','—');set('batteryCost','—');return;}
    set('batteryDcKwp',fmt(r.daily)+' kWh/día');set('batteryRequired',fmt(r.required)+' kWh útiles');set('batteryQty',r.qty+' und.');set('batteryInstalled',fmt(r.installed)+' kWh útiles');set('batteryCost','$ '+Number(r.cost||0).toLocaleString('es-CO',{maximumFractionDigits:0}));const note=$('batterySizingNote');if(note)note.textContent=`${fmt(r.daily)} kWh/día respaldados × ${fmt(r.days)} día(s) = ${fmt(r.required)} kWh útiles. Mínimos: energía ${r.qe}, carga ${r.qc}, descarga ${r.qd}. Se adopta el mayor: ${r.qty} unidad(es).`;
    syncBudgetBattery(r);
  }
  function syncBudgetBattery(r){try{if(typeof budgetRows==='undefined'||!Array.isArray(budgetRows))return;const b=battery();if(!b)return;const ex=budgetRows.find(x=>x.category==='Baterías');if(ex){ex.qty=r.qty;ex.cost_price=Number(b.price_cop||0);ex.detail=`${b.manufacturer} ${b.model} — ${fmt(b.capacity_kwh||0)} kWh nominal c/u · ${fmt(r.installed)} kWh útiles · ${r.qty} unidad(es) · ${num(b.voltage_v,0)} V`;}if(typeof renderBudgetRows==='function')renderBudgetRows();if(typeof calcBudget==='function')calcBudget();}catch(e){}}

  function drawChart(){
    const canvas=$('cmHourlyChart');if(!canvas)return;const box=canvas.parentElement,rect=box.getBoundingClientRect(),dpr=window.devicePixelRatio||1,w=Math.max(500,rect.width),h=Math.max(220,rect.height);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);canvas.style.width=w+'px';canvas.style.height=h+'px';const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    const vals=Array(24).fill(0),bvals=Array(24).fill(0);
    rows.forEach(r=>{const a=timeMinutes(r.start),b=timeMinutes(r.end);if(a===null||b===null)return;let mins=b-a;if(mins<=0)mins+=1440;const p=Math.max(0,num(r.qty,1))*Math.max(0,num(r.power,0))*Math.max(0,Math.min(100,num(r.util,100)))/100/1000;const perHour=p;for(let k=0;k<mins;k+=60){const t=(a+k)%1440,hr=Math.floor(t/60),frac=Math.min(60,mins-k)/60;vals[hr]+=perHour*frac;bvals[hr]+=r.backup&&offGrid()?perHour*frac:0;}});
    const max=Math.max(0.01,...vals),L=48,R=16,T=18,B=38,gw=w-L-R,gh=h-T-B;ctx.font='11px Arial';ctx.strokeStyle='#555';ctx.fillStyle='#fff';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(L,T);ctx.lineTo(L,T+gh);ctx.lineTo(L+gw,T+gh);ctx.stroke();
    for(let i=0;i<6;i++){const y=T+gh-i*gh/5,v=max*i/5;ctx.strokeStyle='#444';ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(L+gw,y);ctx.stroke();ctx.fillText(fmt(v),4,y+4);}ctx.beginPath();ctx.strokeStyle='#f2b705';ctx.lineWidth=2;for(let i=0;i<24;i++){const x=L+i*gw/23,y=T+gh-(vals[i]/max)*gh;i?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.stroke();ctx.beginPath();ctx.strokeStyle='#6f8798';ctx.lineWidth=2;for(let i=0;i<24;i++){const x=L+i*gw/23,y=T+gh-(bvals[i]/max)*gh;i?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.stroke();ctx.fillStyle='#fff';for(let i=0;i<24;i+=2){const x=L+i*gw/23;ctx.fillText(String(i).padStart(2,'0'),x-7,T+gh+18);}ctx.fillText('Hora del día',L+gw/2-25,h-5);
  }
  function chartCard(){const p=$('panel-matrix');if(!p||$('cmHourlyChart'))return;const d=document.createElement('div');d.className='cm-chart-card';d.innerHTML='<div style="font-weight:800;font-size:16px">GRÁFICO DE CONSUMO POR HORAS</div><div class="muted" style="margin:4px 0 10px">Perfil horario calculado a partir de la hora de inicio y la hora de apagado de cada equipo.</div><div class="cm-chart-wrap"><canvas id="cmHourlyChart"></canvas></div><div class="cm-chart-legend"><span><i class="cm-dot"></i>Consumo total</span><span><i class="cm-dot2"></i>Consumo a respaldar</span></div>';p.appendChild(d);}

  function activate(){window.__esunConsumptionMatrixActive=true;document.querySelectorAll('.tabs .tab').forEach(x=>x.classList.toggle('active',x.dataset.tab==='matrix'));document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id==='panel-matrix'));updateTotals();}
  function deactivate(){window.__esunConsumptionMatrixActive=false;}
  function persist(){try{localStorage.setItem(MATRIX_KEY,JSON.stringify(rows));}catch(e){}}
  function load(){try{const a=JSON.parse(localStorage.getItem(MATRIX_KEY)||'[]');if(Array.isArray(a)&&a.length)rows=a.map(normalize);}catch(e){}if(!rows.length)rows=[defaultRow()];}
  function install(){
    const tabs=document.querySelector('.tabs');if(!tabs||$('panel-matrix'))return;ensureStyles();
    const tab=document.createElement('button');tab.type='button';tab.className='tab';tab.dataset.tab='matrix';tab.textContent='1. Consumo Eléctrico';tabs.appendChild(tab);
    const panel=document.createElement('div');panel.id='panel-matrix';panel.className='panel';panel.innerHTML='<div class="cm-head"><div><label class="label" style="margin-top:0;font-size:18px">1. Consumo Eléctrico — Matriz de consumo</label><p class="muted" style="margin:0">Defina la programación de cada carga mediante hora de inicio y hora de apagado. Las horas/día se calculan automáticamente y alimentan el consumo y el gráfico horario.</p></div></div><div class="cm-actions"><button type="button" class="sun-btn" id="cmAdd">+ AÑADIR EQUIPO</button><button type="button" class="secondary" id="cmExample">CARGAR EJEMPLO</button></div><div class="cm-table-wrap"><table class="cm-table"><thead><tr><th>#</th><th>Equipo / carga</th><th>Cantidad</th><th>Potencia (W)</th><th>Hora inicio</th><th>Hora apagado</th><th>Horas/día</th><th>Días/mes</th><th>Utilización (%)</th><th>kWh/día</th><th>kWh/mes</th><th>kWh/año</th><th>Respaldo</th></tr></thead><tbody id="consumptionMatrixBody"></tbody></table></div><div class="cm-totals"><div class="cm-total"><small>CONSUMO DIARIO TOTAL</small><b id="cmTotalDaily">0,00</b> kWh/día</div><div class="cm-total"><small>CONSUMO MENSUAL TOTAL</small><b id="cmTotalMonthly">0,00</b> kWh/mes</div><div class="cm-total"><small>CONSUMO ANUAL TOTAL</small><b id="cmTotalAnnual">0,00</b> kWh/año</div></div><div class="cm-backup-total"><div class="cm-bt-title">CONSUMO A RESPALDAR</div><div class="cm-bt-value"><span id="cmBackupDaily">0,00</span> kWh/día</div><div class="muted" style="margin-top:4px"><span id="cmBackupMonthly">0,00</span> kWh/mes · <span id="cmBackupAnnual">0,00</span> kWh/año</div></div><div class="cm-note"><b>Criterio:</b> Cantidad × Potencia × Horas/día × Utilización. Las horas/día provienen de la diferencia entre hora de inicio y hora de apagado; se admite cruce de medianoche.</div>';
    tabs.parentNode.insertBefore(panel,tabs.nextSibling);chartCard();render();
    tab.addEventListener('click',activate);tabs.querySelectorAll('.tab:not([data-tab="matrix"])').forEach(x=>x.addEventListener('click',deactivate));
    panel.addEventListener('input',e=>{if(e.target.matches('[data-field]'))updateRow(e.target);});
    panel.addEventListener('change',e=>{if(e.target.matches('[data-field]'))updateRow(e.target);});
    panel.addEventListener('click',e=>{const del=e.target.closest('[data-delete]');if(del){const tr=del.closest('tr');rows=rows.filter(r=>String(r.id)!==String(tr?.dataset.id));if(!rows.length)rows=[defaultRow()];render();persist();return;}const bk=e.target.closest('[data-backup]');if(bk&&!bk.disabled){const tr=bk.closest('tr'),r=rows.find(x=>String(x.id)===String(tr?.dataset.id));if(r){r.backup=!r.backup;render();persist();}}if(e.target.id==='cmAdd'){rows.push(defaultRow());render();persist();}if(e.target.id==='cmExample'){rows=[{id:'ex1',equipment:'Aire acondicionado',qty:2,power:1200,start:'14:00',end:'20:00',days:30,util:70,backup:false},{id:'ex2',equipment:'Nevera',qty:1,power:300,start:'00:00',end:'24:00',days:30,util:60,backup:false},{id:'ex3',equipment:'Iluminación LED',qty:12,power:12,start:'18:00',end:'23:00',days:30,util:100,backup:false},{id:'ex4',equipment:'Computador',qty:2,power:150,start:'08:00',end:'16:00',days:30,util:80,backup:false}].map(normalize);render();persist();activate();}});
    window.addEventListener('resize',()=>{if(window.__esunConsumptionMatrixActive)drawChart();});
  }
  function patchState(){
    if(typeof window.getAnnual==='function'&&!window.getAnnual.__matrixPatched){originalGetAnnual=window.getAnnual;const f=function(){return window.__esunConsumptionMatrixActive?total('annual'):originalGetAnnual();};f.__matrixPatched=true;window.getAnnual=f;}
    if(typeof window.getProjectFormState==='function'&&!window.getProjectFormState.__matrixPatched){originalGetProjectFormState=window.getProjectFormState;const f=function(){const s=originalGetProjectFormState();s.fields=s.fields||{};s.fields.consumptionMatrix=rows.map(normalize);return s;};f.__matrixPatched=true;window.getProjectFormState=f;}
    if(typeof window.setProjectFormState==='function'&&!window.setProjectFormState.__matrixPatched){originalSetProjectFormState=window.setProjectFormState;const f=function(s){const a=s?.fields?.consumptionMatrix;if(Array.isArray(a)){rows=a.map(normalize);render();}originalSetProjectFormState(s);if(Array.isArray(a))render();};f.__matrixPatched=true;window.setProjectFormState=f;}
  }
  function init(){load();install();patchState();let n=0;const t=setInterval(()=>{patchState();if($('cmHourlyChart'))drawChart();if(++n>120)clearInterval(t);},500);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

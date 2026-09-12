(function(){
  'use strict';
  const MATRIX_KEY='esun_power_consumption_matrix_v1';
  let rows=[];
  let originalGetAnnual=null;
  let originalGetProjectFormState=null;
  let originalSetProjectFormState=null;

  function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));}
  function num(v,def=0){const n=Number(v);return Number.isFinite(n)?n:def;}
  function fmtKwh(v){return num(v).toLocaleString('es-CO',{minimumFractionDigits:2,maximumFractionDigits:2});}
  function fmtMoney(v){return num(v).toLocaleString('es-CO',{maximumFractionDigits:0});}
  function isOffGrid(){return (document.getElementById('systemType')?.value||'ON-GRID')==='OFF-GRID';}
  function calc(r){
    const qty=Math.max(0,num(r.qty,1)),power=Math.max(0,num(r.power,0)),hours=Math.max(0,num(r.hours,0)),days=Math.max(0,num(r.days,30)),util=Math.max(0,Math.min(100,num(r.util,100)))/100;
    const daily=qty*power*hours*util/1000;
    return {daily,monthly:daily*days,annual:daily*days*12};
  }
  function defaultRow(){return{id:'cm_'+Date.now()+'_'+Math.random().toString(36).slice(2,8),equipment:'',qty:1,power:0,hours:0,days:30,util:100,backup:false};}
  function normalizeRow(r){return{...defaultRow(),...(r||{}),backup:Boolean(r?.backup)};}
  function totalAnnual(){return rows.reduce((s,r)=>s+calc(r).annual,0);}
  function totalMonthly(){return rows.reduce((s,r)=>s+calc(r).monthly,0);}
  function totalDaily(){return rows.reduce((s,r)=>s+calc(r).daily,0);}
  function backupRows(){return isOffGrid()?rows.filter(r=>r.backup):[];}
  function backupDaily(){return backupRows().reduce((s,r)=>s+calc(r).daily,0);}
  function backupMonthly(){return backupRows().reduce((s,r)=>s+calc(r).monthly,0);}
  function backupAnnual(){return backupRows().reduce((s,r)=>s+calc(r).annual,0);}
  function backupPeakKw(){return backupRows().reduce((s,r)=>s+(Math.max(0,num(r.qty,1))*Math.max(0,num(r.power,0)))/1000,0);}

  function batteryData(){
    try{
      const arr=typeof batteries!=='undefined'?batteries:(window.batteries||[]);
      const sel=document.getElementById('battery');
      return arr?.[Number(sel?.value)||0]||null;
    }catch(e){return null;}
  }
  function autonomyDays(){
    const el=document.getElementById('batteryStorageHours');
    const v=Math.max(.25,num(el?.value,1));
    return v;
  }
  function calculateBackupBattery(){
    if(!isOffGrid())return null;
    const b=batteryData();
    if(!b)return null;
    const usable=Number(b.usable_capacity_kwh||0)||Number(b.capacity_kwh||0)*(Number(b.recommended_dod_pct||80)/100);
    if(usable<=0)return null;
    const daily=backupDaily();
    const days=autonomyDays();
    const required=Math.max(0,daily*days);
    const peak=backupPeakKw();
    const qe=required>0?Math.max(1,Math.ceil(required/usable)):0;
    const acKw=Number((typeof lastDesign!=='undefined'&&lastDesign?.inverter?.ac_kw_total)||0)||0;
    const dischargePower=Number(b.recommended_discharge_power_kw||0);
    const powerForSizing=Math.max(peak,acKw>0?peak:0);
    const qd=dischargePower>0&&powerForSizing>0?Math.max(1,Math.ceil(powerForSizing/dischargePower)):0;
    const dcKw=Number((typeof lastDesign!=='undefined'&&lastDesign?.system?.dc_kwp)||0)||0;
    const chargePower=Number(b.recommended_charge_power_kw||0);
    const qc=chargePower>0&&dcKw>0?Math.max(1,Math.ceil(dcKw/chargePower)):0;
    const qty=Math.max(qe,qd,qc,required>0?1:0);
    return {
      daily_kwh:daily,monthly_kwh:backupMonthly(),annual_kwh:backupAnnual(),autonomy_days:days,
      required_usable_kwh:required,usable_per_battery_kwh:usable,quantity:qty,
      installed_usable_kwh:qty*usable,installed_kwh:qty*Number(b.capacity_kwh||0),cost:qty*Number(b.price_cop||0),
      peak_kw:peak,qty_energy:qe,qty_discharge_power:qd,qty_charge_power:qc
    };
  }

  function ensureStyles(){
    if(document.getElementById('consumptionMatrixStyles'))return;
    const st=document.createElement('style');st.id='consumptionMatrixStyles';
    st.textContent=`
#panel-matrix{display:none}#panel-matrix.active{display:block}
.cm-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
.cm-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
.cm-table-wrap{width:100%;overflow-x:auto;border:1px solid #414141;border-radius:8px}
.cm-table{width:100%;min-width:1100px;border-collapse:collapse;margin:0}
.cm-table th{font-size:11px;white-space:normal;text-align:center;background:#303030;padding:8px 6px}
.cm-table td{padding:6px;border-bottom:1px solid #414141;vertical-align:middle}
.cm-table input{width:100%;min-width:0;padding:8px 7px;font-size:12px}
.cm-table .cm-eq{min-width:180px}.cm-table .cm-num{min-width:76px;text-align:right}
.cm-table .cm-result{font-weight:700;text-align:right;white-space:nowrap;font-size:12px}
.cm-delete{background:#5d6972;padding:8px 10px;font-size:11px;white-space:nowrap}
.cm-backup{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-width:108px;background:#3d4246;color:#fff;border:1px solid #666;padding:8px 9px;font-size:10px;font-weight:700;white-space:nowrap}
.cm-backup .cm-batt-icon{display:inline-flex;width:17px;height:17px;align-items:center;justify-content:center}
.cm-backup .cm-batt-icon svg{width:17px;height:17px;display:block}
.cm-backup.active{background:#f2b705;color:#151515;border-color:#ffd33d;box-shadow:0 0 9px rgba(255,205,40,.38)}
.cm-backup:disabled{opacity:.42;cursor:not-allowed;box-shadow:none}
.cm-backup-hint{display:block;margin-top:3px;font-size:9px;color:#bbb}
.cm-totals{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}
.cm-total{background:#303030;border:1px solid #414141;border-radius:8px;padding:12px}.cm-total small{display:block;color:#fff}.cm-total b{display:block;font-size:20px;margin-top:5px}
.cm-backup-total{margin-top:12px;background:#302d24;border:1px solid #8a7220;border-radius:8px;padding:13px}.cm-backup-total .cm-bt-title{font-weight:800;color:#ffd33d}.cm-backup-total .cm-bt-value{font-size:23px;font-weight:800;margin-top:3px}
.cm-note{padding:10px;background:#302d24;border:1px solid #655b3e;border-radius:7px;margin-top:12px}
#offgridBatteryCard .battery-backup-summary{margin:12px 0;background:#302d24;border:1px solid #8a7220;border-radius:8px;padding:13px}
#offgridBatteryCard .battery-backup-summary strong{color:#ffd33d}
#offgridBatteryCard .battery-backup-summary .bb-value{font-size:24px;font-weight:800;margin-top:4px}
@media(max-width:900px){.cm-totals{grid-template-columns:1fr}}
`;
    document.head.appendChild(st);
  }

  function batteryIcon(){return `<span class="cm-batt-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><rect x="3" y="6" width="16" height="12" rx="2" fill="#f2b705" stroke="#1d1d1d" stroke-width="1.4"/><rect x="19" y="10" width="2" height="4" rx=".6" fill="#f2b705"/><rect x="6" y="9" width="3" height="6" rx=".7" fill="#fff2a6"/><rect x="10.5" y="9" width="3" height="6" rx=".7" fill="#fff2a6"/></svg></span>`;}
  function backupButton(r){
    const active=Boolean(r.backup),disabled=!isOffGrid();
    return `<button type="button" class="cm-backup ${active?'active':''}" data-backup="1" ${disabled?'disabled':''}>${batteryIcon()}<span>${active?'RESPALDO ACTIVO':'RESPALDAR'}</span></button><span class="cm-backup-hint">${disabled?'Solo OFF-GRID':(active?'Quitar respaldo':'Agregar al respaldo')}</span>`;
  }
  function render(){
    const body=document.getElementById('consumptionMatrixBody');if(!body)return;
    body.innerHTML=rows.map((r,i)=>{const c=calc(r);return `<tr data-id="${esc(r.id)}"><td style="text-align:center">${i+1}</td><td><input class="cm-eq" data-field="equipment" value="${esc(r.equipment)}" placeholder="Ej. Aire acondicionado"></td><td><input class="cm-num" data-field="qty" type="number" min="0" step="1" value="${num(r.qty,1)}"></td><td><input class="cm-num" data-field="power" type="number" min="0" step="1" value="${num(r.power,0)}"></td><td><input class="cm-num" data-field="hours" type="number" min="0" step="0.25" value="${num(r.hours,0)}"></td><td><input class="cm-num" data-field="days" type="number" min="0" max="31" step="1" value="${num(r.days,30)}"></td><td><input class="cm-num" data-field="util" type="number" min="0" max="100" step="1" value="${num(r.util,100)}"></td><td class="cm-result cm-daily">${fmtKwh(c.daily)}</td><td class="cm-result cm-monthly">${fmtKwh(c.monthly)}</td><td class="cm-result cm-annual">${fmtKwh(c.annual)}</td><td>${backupButton(r)}<button type="button" class="cm-delete" data-delete="1" style="margin-top:4px">ELIMINAR</button></td></tr>`;}).join('');
    updateTotals();
  }
  function updateTotals(){
    const d=totalDaily(),m=totalMonthly(),a=totalAnnual(),bd=backupDaily(),bm=backupMonthly(),ba=backupAnnual();
    const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=fmtKwh(v);};
    set('cmTotalDaily',d);set('cmTotalMonthly',m);set('cmTotalAnnual',a);set('cmBackupDaily',bd);set('cmBackupMonthly',bm);set('cmBackupAnnual',ba);
    const annualView=document.getElementById('annualView');if(window.__esunConsumptionMatrixActive&&annualView)annualView.textContent=a>0?fmtKwh(a)+' kWh/año':'—';
    updateBatteryFromBackup();
  }
  function updateRowFromInput(input){
    const tr=input.closest('tr');if(!tr)return;const r=rows.find(x=>String(x.id)===String(tr.dataset.id));if(!r)return;const field=input.dataset.field;if(field==='equipment')r[field]=input.value;else r[field]=num(input.value,0);
    const c=calc(r);tr.querySelector('.cm-daily').textContent=fmtKwh(c.daily);tr.querySelector('.cm-monthly').textContent=fmtKwh(c.monthly);tr.querySelector('.cm-annual').textContent=fmtKwh(c.annual);updateTotals();
  }

  function updateBatteryCardStructure(){
    const card=document.getElementById('offgridBatteryCard');if(!card)return;
    const title=card.querySelector('h2');if(title)title.textContent='2. Banco de baterías — OFF-GRID';
    const ps=card.querySelectorAll('p.muted');
    if(ps[0])ps[0].textContent='E-SUN POWER dimensiona el banco de baterías a partir de los equipos marcados como RESPALDAR en la Matriz de consumo. Puede aceptar la selección automática o elegir manualmente una referencia.';
    if(ps[1])ps[1].textContent='El consumo respaldado se suma únicamente cuando el sistema es OFF-GRID. La capacidad se determina con el consumo diario respaldado, los días de autonomía y la capacidad útil de la batería, verificando además las restricciones de potencia registradas en la ficha técnica.';
    const old=card.querySelector('.battery-backup-summary');
    if(!old){
      const summary=document.createElement('div');summary.className='battery-backup-summary';summary.innerHTML='<strong>CONSUMO A RESPALDAR</strong><div class="bb-value" id="batteryBackupSummaryValue">0,00 kWh/día</div><div id="batteryBackupSummaryDetail" class="muted" style="margin-top:4px">Seleccione equipos en la Matriz de consumo mediante RESPALDAR.</div>';
      const row=card.querySelector('.row');if(row)card.insertBefore(summary,row);
    }
    const labels=card.querySelectorAll('.metrics .metric span');
    if(labels[0])labels[0].textContent='CONSUMO A RESPALDAR';
    if(labels[1])labels[1].textContent='Energía requerida de batería';
    const storageInput=document.getElementById('batteryStorageHours');
    if(storageInput){storageInput.min='0.25';storageInput.step='0.25';if(!storageInput.dataset.backupInit){storageInput.value='1';storageInput.dataset.backupInit='1';}}
    const storageLabel=storageInput?.parentElement?.querySelector('.label');if(storageLabel)storageLabel.textContent='Días de autonomía';
    const note=document.getElementById('batterySizingNote');if(note)note.textContent='Criterio: consumo seleccionado para respaldo × días de autonomía. Se verifica energía útil y potencia de descarga/carga de la batería.';
  }

  function updateBatteryFromBackup(){
    updateBatteryCardStructure();
    const bd=backupDaily(),bm=backupMonthly(),ba=backupAnnual();
    const summary=document.getElementById('batteryBackupSummaryValue');if(summary)summary.textContent=fmtKwh(bd)+' kWh/día';
    const detail=document.getElementById('batteryBackupSummaryDetail');if(detail)detail.textContent=backupRows().length?`${backupRows().length} equipo(s) seleccionado(s) · ${fmtKwh(bm)} kWh/mes · ${fmtKwh(ba)} kWh/año`:'Seleccione equipos en la Matriz de consumo mediante RESPALDAR.';
    const r=calculateBackupBattery();
    const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v;};
    if(!isOffGrid()){
      set('batteryDcKwp','—');set('batteryRequired','—');set('batteryQty','—');set('batteryInstalled','—');set('batteryCost','—');
      return;
    }
    const b=batteryData();
    if(!b||!r){set('batteryDcKwp',fmtKwh(bd)+' kWh/día');set('batteryRequired','—');set('batteryQty','—');set('batteryInstalled','—');set('batteryCost','—');return;}
    set('batteryDcKwp',fmtKwh(bd)+' kWh/día');
    set('batteryRequired',fmtKwh(r.required_usable_kwh)+' kWh útiles');
    set('batteryQty',fmtMoney(r.quantity)+' und.');
    set('batteryInstalled',fmtKwh(r.installed_usable_kwh)+' kWh útiles');
    set('batteryCost','$ '+fmtMoney(r.cost));
    const note=document.getElementById('batterySizingNote');
    if(note)note.textContent=`${fmtKwh(r.daily_kwh)} kWh/día respaldados × ${fmtKwh(r.autonomy_days)} día(s) = ${fmtKwh(r.required_usable_kwh)} kWh útiles requeridos. Mínimos: energía ${r.qty_energy||0}, carga ${r.qty_charge_power||0}, descarga ${r.qty_discharge_power||0}. Se adopta el mayor: ${r.quantity} unidad(es).`;
  }

  function syncBatteryBudgetFromBackup(){
    try{
      if(typeof budgetRows==='undefined'||!Array.isArray(budgetRows))return;
      const off=isOffGrid();
      const existing=budgetRows.find(r=>r.category==='Baterías');
      if(!off){return;}
      const b=batteryData(),r=calculateBackupBattery();
      if(!b||!r)return;
      if(existing){
        existing.qty=r.quantity;existing.cost_price=Number(b.price_cop||0);
        existing.detail=`${b.manufacturer} ${b.model} — ${fmtKwh(b.capacity_kwh||0)} kWh nominal c/u · ${fmtKwh(r.installed_usable_kwh)} kWh útiles · ${r.quantity} unidad(es) · ${num(b.voltage_v,0)} V`;
      }
      if(typeof renderBudgetRows==='function')renderBudgetRows();
      if(typeof calcBudget==='function')calcBudget();
    }catch(e){}
  }

  function activateMatrix(){window.__esunConsumptionMatrixActive=true;document.querySelectorAll('.tabs .tab').forEach(x=>x.classList.toggle('active',x.dataset.tab==='matrix'));document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id==='panel-matrix'));updateTotals();if(typeof window.updateConsumption==='function')window.updateConsumption();}
  function deactivateMatrix(){window.__esunConsumptionMatrixActive=false;}
  function persistLocal(){try{localStorage.setItem(MATRIX_KEY,JSON.stringify(rows));}catch(e){}}
  function loadLocal(){try{const r=JSON.parse(localStorage.getItem(MATRIX_KEY)||'[]');if(Array.isArray(r)&&r.length)rows=r.map(normalizeRow);}catch(e){}}

  function moveBatterySectionAfterConsumption(){
    const panel=document.getElementById('panel-matrix'),card=document.getElementById('offgridBatteryCard');if(!panel||!card)return;
    if(panel.parentNode)panel.parentNode.insertBefore(card,panel.nextSibling);
  }

  function installPanel(){
    const tabs=document.querySelector('.tabs');if(!tabs||document.getElementById('panel-matrix'))return;
    ensureStyles();
    const b=document.createElement('button');b.type='button';b.className='tab';b.dataset.tab='matrix';b.textContent='1. Consumo Eléctrico';tabs.appendChild(b);
    const panel=document.createElement('div');panel.id='panel-matrix';panel.className='panel';
    panel.innerHTML=`<div class="cm-head"><div><label class="label" style="margin-top:0;font-size:18px">1. Consumo Eléctrico — Matriz de consumo</label><p class="muted" style="margin:0">Ingrese las cargas del proyecto. Para sistemas OFF-GRID puede seleccionar exactamente qué equipos desea respaldar con baterías mediante el botón amarillo RESPALDAR.</p></div></div><div class="cm-actions"><button type="button" class="sun-btn" id="cmAdd">+ AÑADIR EQUIPO</button><button type="button" class="secondary" id="cmExample">CARGAR EJEMPLO</button></div><div class="cm-table-wrap"><table class="cm-table"><thead><tr><th>#</th><th>Equipo / carga</th><th>Cantidad</th><th>Potencia (W)</th><th>Horas/día</th><th>Días/mes</th><th>Utilización (%)</th><th>kWh/día</th><th>kWh/mes</th><th>kWh/año</th><th>Respaldo</th></tr></thead><tbody id="consumptionMatrixBody"></tbody></table></div><div class="cm-totals"><div class="cm-total"><small>CONSUMO DIARIO TOTAL</small><b id="cmTotalDaily">0,00</b> <span>kWh/día</span></div><div class="cm-total"><small>CONSUMO MENSUAL TOTAL</small><b id="cmTotalMonthly">0,00</b> <span>kWh/mes</span></div><div class="cm-total"><small>CONSUMO ANUAL TOTAL</small><b id="cmTotalAnnual">0,00</b> <span>kWh/año</span></div></div><div class="cm-backup-total"><div class="cm-bt-title">CONSUMO A RESPALDAR</div><div class="cm-bt-value"><span id="cmBackupDaily">0,00</span> kWh/día</div><div class="muted" style="margin-top:4px"><span id="cmBackupMonthly">0,00</span> kWh/mes · <span id="cmBackupAnnual">0,00</span> kWh/año</div></div><div class="cm-note"><b>Criterio:</b> Cantidad × Potencia × Horas/día × Utilización. El consumo respaldado corresponde exclusivamente a los equipos marcados con RESPALDAR y solo se utiliza para dimensionamiento de baterías cuando el sistema es OFF-GRID.</div>`;
    tabs.parentNode.insertBefore(panel,tabs.nextSibling);
    if(!rows.length)rows=[defaultRow()];
    render();
    b.addEventListener('click',activateMatrix);
    tabs.querySelectorAll('.tab:not([data-tab="matrix"])').forEach(x=>x.addEventListener('click',deactivateMatrix));
    panel.addEventListener('input',e=>{if(e.target.matches('[data-field]')){updateRowFromInput(e.target);persistLocal();}});
    panel.addEventListener('click',e=>{
      const del=e.target.closest('[data-delete]');
      if(del){const tr=del.closest('tr');rows=rows.filter(r=>String(r.id)!==String(tr?.dataset.id));if(!rows.length)rows=[defaultRow()];render();persistLocal();return;}
      const backup=e.target.closest('[data-backup]');
      if(backup&&!backup.disabled){const tr=backup.closest('tr');const r=rows.find(x=>String(x.id)===String(tr?.dataset.id));if(r){r.backup=!r.backup;persistLocal();render();}}
      if(e.target.id==='cmAdd'){rows.push(defaultRow());render();persistLocal();}
      if(e.target.id==='cmExample'){rows=[{id:'ex1',equipment:'Aire acondicionado',qty:2,power:1200,hours:6,days:30,util:70,backup:false},{id:'ex2',equipment:'Nevera',qty:1,power:300,hours:10,days:30,util:60,backup:false},{id:'ex3',equipment:'Iluminación LED',qty:12,power:12,hours:6,days:30,util:100,backup:false},{id:'ex4',equipment:'Computador',qty:2,power:150,hours:8,days:30,util:80,backup:false}];render();persistLocal();activateMatrix();}
    });
  }

  function patchAnnual(){
    if(typeof window.getAnnual==='function'&&!window.getAnnual.__matrixPatched){originalGetAnnual=window.getAnnual;const patched=function(){return window.__esunConsumptionMatrixActive?totalAnnual():originalGetAnnual();};patched.__matrixPatched=true;window.getAnnual=patched;}
    if(typeof window.getProjectFormState==='function'&&!window.getProjectFormState.__matrixPatched){originalGetProjectFormState=window.getProjectFormState;const fn=function(){const state=originalGetProjectFormState();state.fields=state.fields||{};state.fields.consumptionMatrix=rows.map(normalizeRow);return state;};fn.__matrixPatched=true;window.getProjectFormState=fn;}
    if(typeof window.setProjectFormState==='function'&&!window.setProjectFormState.__matrixPatched){originalSetProjectFormState=window.setProjectFormState;const fn=function(state){const matrix=state?.fields?.consumptionMatrix;if(Array.isArray(matrix)){rows=matrix.map(normalizeRow);render();}originalSetProjectFormState(state);if(Array.isArray(matrix))render();};fn.__matrixPatched=true;window.setProjectFormState=fn;}
  }

  function refresh(){
    const off=isOffGrid();
    document.querySelectorAll('#consumptionMatrixBody [data-backup]').forEach(btn=>{btn.disabled=!off;});
    moveBatterySectionAfterConsumption();
    updateBatteryFromBackup();
    syncBatteryBudgetFromBackup();
  }

  function init(){
    loadLocal();installPanel();patchAnnual();moveBatterySectionAfterConsumption();updateBatteryCardStructure();render();
    const sys=document.getElementById('systemType');if(sys)sys.addEventListener('change',()=>{render();refresh();});
    ['battery','batteryMode','batteryStorageHours'].forEach(id=>{const el=document.getElementById(id);if(el)el.addEventListener('input',refresh);if(el)el.addEventListener('change',refresh);});
    let n=0;const t=setInterval(()=>{patchAnnual();refresh();if(++n>240)clearInterval(t);},500);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

(function(){
  'use strict';
  const KEY='esun_power_consumption_matrix_v2';
  let rows=[];
  let active=false;
  const $=id=>document.getElementById(id);
  const n=(v,d=0)=>{const x=Number(v);return Number.isFinite(x)?x:d;};
  const f=v=>n(v).toLocaleString('es-CO',{minimumFractionDigits:2,maximumFractionDigits:2});
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const isOffGrid=()=>($('systemType')?.value||'ON-GRID')==='OFF-GRID';

  function minutes(v){
    if(typeof v!=='string') return null;
    const m=v.match(/^(\d{1,2}):(\d{2})$/); if(!m) return null;
    const h=Number(m[1]), mm=Number(m[2]);
    if(mm<0||mm>59||h<0||h>24||(h===24&&mm!==0)) return null;
    return h*60+mm;
  }
  function duration(r){
    const a=minutes(r.start),b=minutes(r.end);
    if(a===null||b===null) return Math.max(0,n(r.hours,0));
    if(a===b) return 24;
    let d=b-a; if(d<0)d+=1440;
    return d/60;
  }
  function calc(r){
    const qty=Math.max(0,n(r.qty,1));
    const power=Math.max(0,n(r.power,0));
    const hrs=duration(r);
    const days=Math.max(0,n(r.days,30));
    const util=Math.max(0,Math.min(100,n(r.util,100)))/100;
    const daily=qty*power*hrs*util/1000;
    return {hours:hrs,daily,monthly:daily*days,annual:daily*days*12};
  }
  function fresh(){return{id:'cm_'+Date.now()+'_'+Math.random().toString(36).slice(2,8),equipment:'',qty:1,power:0,start:'08:00',end:'13:00',hours:5,days:30,util:100,backup:false};}
  function norm(r){const x=Object.assign(fresh(),r||{});if(!x.start)x.start='08:00';if(!x.end)x.end='13:00';x.hours=duration(x);x.backup=!!x.backup;return x;}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(rows));}catch(e){}}
  function load(){try{const a=JSON.parse(localStorage.getItem(KEY)||'[]');if(Array.isArray(a)&&a.length)rows=a.map(norm);}catch(e){}if(!rows.length)rows=[fresh()];}
  function total(k){return rows.reduce((s,r)=>s+calc(r)[k],0);}
  function backup(k){return isOffGrid()?rows.filter(r=>r.backup).reduce((s,r)=>s+calc(r)[k],0):0;}
  function backupPeak(){return isOffGrid()?rows.filter(r=>r.backup).reduce((s,r)=>s+Math.max(0,n(r.qty,1))*Math.max(0,n(r.power,0))/1000,0):0;}

  function styles(){
    if($('cmSafeStyles'))return;
    const s=document.createElement('style');s.id='cmSafeStyles';s.textContent=`
#panel-matrix{display:none}#panel-matrix.active{display:block}.cm-actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.cm-table-wrap{width:100%;overflow-x:auto;border:1px solid #414141;border-radius:8px}.cm-table{width:100%;min-width:1240px;border-collapse:collapse}.cm-table th{font-size:11px;white-space:normal;text-align:center;background:#303030;padding:8px 6px}.cm-table td{padding:6px;border-bottom:1px solid #414141;vertical-align:middle}.cm-table input{width:100%;min-width:0;padding:8px 7px;font-size:12px}.cm-eq{min-width:170px}.cm-num{min-width:72px;text-align:right}.cm-time{min-width:88px;text-align:center}.cm-result{font-weight:700;text-align:right;white-space:nowrap;font-size:12px}.cm-delete{background:#5d6972;padding:8px 10px;font-size:11px}.cm-backup{display:inline-flex;align-items:center;justify-content:center;gap:5px;min-width:112px;background:#3d4246;color:#fff;border:1px solid #666;padding:8px 9px;font-size:10px;font-weight:700;white-space:nowrap}.cm-backup.active{background:#f2b705;color:#151515;border-color:#ffd33d;box-shadow:0 0 9px rgba(255,205,40,.38)}.cm-backup:disabled{opacity:.42;cursor:not-allowed}.cm-hint{display:block;margin-top:3px;font-size:9px;color:#bbb}.cm-totals{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.cm-total{background:#303030;border:1px solid #414141;border-radius:8px;padding:12px}.cm-total small{display:block;color:#fff}.cm-total b{display:block;font-size:20px;margin-top:5px}.cm-backup-total{margin-top:12px;background:#302d24;border:1px solid #8a7220;border-radius:8px;padding:13px}.cm-bt-title{font-weight:800;color:#ffd33d}.cm-bt-value{font-size:23px;font-weight:800;margin-top:3px}.cm-chart-card{margin-top:14px;background:#303030;border:1px solid #414141;border-radius:8px;padding:14px}.cm-chart-wrap{height:300px;position:relative}.cm-chart-wrap canvas{width:100%;height:100%;display:block}.cm-legend{display:flex;gap:18px;flex-wrap:wrap;font-size:11px;margin-top:8px}.cm-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;background:#f2b705}.cm-dot2{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;background:#6f8798}@media(max-width:900px){.cm-totals{grid-template-columns:1fr}.cm-chart-wrap{height:240px}}
`;document.head.appendChild(s);
  }

  function render(){
    const body=$('consumptionMatrixBody');if(!body)return;
    body.innerHTML=rows.map((r,i)=>{const c=calc(r);return `<tr data-id="${esc(r.id)}"><td style="text-align:center">${i+1}</td><td><input class="cm-eq" data-field="equipment" value="${esc(r.equipment)}" placeholder="Ej. Bomba de riego"></td><td><input class="cm-num" data-field="qty" type="number" min="0" step="1" value="${n(r.qty,1)}"></td><td><input class="cm-num" data-field="power" type="number" min="0" step="1" value="${n(r.power,0)}"></td><td><input class="cm-time" data-field="start" type="time" value="${esc(r.start||'08:00')}"></td><td><input class="cm-time" data-field="end" type="time" value="${esc(r.end||'13:00')}"></td><td class="cm-result cm-hours">${f(c.hours)}</td><td><input class="cm-num" data-field="days" type="number" min="0" max="31" step="1" value="${n(r.days,30)}"></td><td><input class="cm-num" data-field="util" type="number" min="0" max="100" step="1" value="${n(r.util,100)}"></td><td class="cm-result cm-daily">${f(c.daily)}</td><td class="cm-result cm-monthly">${f(c.monthly)}</td><td class="cm-result cm-annual">${f(c.annual)}</td><td><button type="button" class="cm-backup ${r.backup?'active':''}" data-backup="1" ${!isOffGrid()?'disabled':''}><span>▣</span> ${r.backup?'RESPALDO ACTIVO':'RESPALDAR'}</button><span class="cm-hint">${!isOffGrid()?'Solo OFF-GRID':(r.backup?'Quitar respaldo':'Agregar al respaldo')}</span><button type="button" class="cm-delete" data-delete="1" style="margin-top:4px">ELIMINAR</button></td></tr>`;}).join('');
    totals();
  }
  function totals(){
    const d=total('daily'),m=total('monthly'),a=total('annual');
    const set=(id,v)=>{if($(id))$(id).textContent=f(v);};
    set('cmTotalDaily',d);set('cmTotalMonthly',m);set('cmTotalAnnual',a);set('cmBackupDaily',backup('daily'));set('cmBackupMonthly',backup('monthly'));set('cmBackupAnnual',backup('annual'));
    window.__esunConsumptionMatrixAnnual=a;
    if(active&&$('annualView'))$('annualView').textContent=a>0?f(a)+' kWh/año':'—';
    if(active)draw();
  }

  function hourProfile(){
    const out=Array(24).fill(0), b=Array(24).fill(0);
    rows.forEach(r=>{
      const a=minutes(r.start),z=minutes(r.end);if(a===null||z===null)return;
      let end=z;if(end<=a)end+=1440;
      const kw=Math.max(0,n(r.qty,1))*Math.max(0,n(r.power,0))*Math.max(0,Math.min(100,n(r.util,100)))/100/1000;
      for(let h=0;h<24;h++){
        const hs=h*60,he=hs+60;
        let overlap=0;
        for(let base=0;base<=1440;base+=1440){overlap+=Math.max(0,Math.min(end,he+base)-Math.max(a,hs+base));}
        out[h]+=kw*overlap/60;
        if(r.backup&&isOffGrid())b[h]+=kw*overlap/60;
      }
    });
    return {out,b};
  }
  function draw(){
    const c=$('cmHourlyChart');if(!c||!active)return;
    const box=c.parentElement,rect=box.getBoundingClientRect();if(!rect.width)return;
    const dpr=window.devicePixelRatio||1,w=Math.max(500,rect.width),h=Math.max(220,rect.height);c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);c.style.width=w+'px';c.style.height=h+'px';
    const x=c.getContext('2d');x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,w,h);
    const p=hourProfile(),max=Math.max(.01,...p.out),L=50,R=16,T=18,B=38,gw=w-L-R,gh=h-T-B;
    x.font='11px Arial';x.fillStyle='#fff';x.strokeStyle='#555';x.lineWidth=1;x.beginPath();x.moveTo(L,T);x.lineTo(L,T+gh);x.lineTo(L+gw,T+gh);x.stroke();
    for(let i=0;i<6;i++){const y=T+gh-i*gh/5;x.strokeStyle='#444';x.beginPath();x.moveTo(L,y);x.lineTo(L+gw,y);x.stroke();x.fillStyle='#fff';x.fillText(f(max*i/5),4,y+4);}
    const line=(arr,color)=>{x.beginPath();x.strokeStyle=color;x.lineWidth=2;arr.forEach((v,i)=>{const xx=L+i*gw/23,yy=T+gh-(v/max)*gh;i?x.lineTo(xx,yy):x.moveTo(xx,yy);});x.stroke();};
    line(p.out,'#f2b705');line(p.b,'#6f8798');x.fillStyle='#fff';for(let i=0;i<24;i+=2)x.fillText(String(i).padStart(2,'0'),L+i*gw/23-7,T+gh+18);x.fillText('Hora del día',L+gw/2-25,h-5);
  }

  function makePanel(tabs){
    const tab=document.createElement('button');tab.type='button';tab.className='tab';tab.dataset.tab='matrix';tab.textContent='1. Consumo Eléctrico';tabs.appendChild(tab);
    const panel=document.createElement('div');panel.id='panel-matrix';panel.className='panel';
    panel.innerHTML='<div><label class="label" style="margin-top:0;font-size:18px">1. Consumo Eléctrico — Matriz de consumo</label><p class="muted" style="margin:0">Defina la hora de inicio y la hora de apagado de cada equipo. Las horas/día y el gráfico horario se calculan automáticamente.</p></div><div class="cm-actions"><button type="button" class="sun-btn" id="cmAdd">+ AÑADIR EQUIPO</button><button type="button" class="secondary" id="cmExample">CARGAR EJEMPLO</button></div><div class="cm-table-wrap"><table class="cm-table"><thead><tr><th>#</th><th>Equipo / carga</th><th>Cantidad</th><th>Potencia (W)</th><th>Hora inicio</th><th>Hora apagado</th><th>Horas/día</th><th>Días/mes</th><th>Utilización (%)</th><th>kWh/día</th><th>kWh/mes</th><th>kWh/año</th><th>Respaldo</th></tr></thead><tbody id="consumptionMatrixBody"></tbody></table></div><div class="cm-totals"><div class="cm-total"><small>CONSUMO DIARIO TOTAL</small><b id="cmTotalDaily">0,00</b> kWh/día</div><div class="cm-total"><small>CONSUMO MENSUAL TOTAL</small><b id="cmTotalMonthly">0,00</b> kWh/mes</div><div class="cm-total"><small>CONSUMO ANUAL TOTAL</small><b id="cmTotalAnnual">0,00</b> kWh/año</div></div><div class="cm-backup-total"><div class="cm-bt-title">CONSUMO A RESPALDAR</div><div class="cm-bt-value"><span id="cmBackupDaily">0,00</span> kWh/día</div><div class="muted" style="margin-top:4px"><span id="cmBackupMonthly">0,00</span> kWh/mes · <span id="cmBackupAnnual">0,00</span> kWh/año</div></div><div class="cm-chart-card"><div style="font-weight:800;font-size:16px">GRÁFICO DE CONSUMO POR HORAS</div><div class="muted" style="margin:4px 0 10px">Perfil horario calculado a partir de las horas programadas.</div><div class="cm-chart-wrap"><canvas id="cmHourlyChart"></canvas></div><div class="cm-legend"><span><i class="cm-dot"></i>Consumo total</span><span><i class="cm-dot2"></i>Consumo a respaldar</span></div></div><div class="cm-note" style="margin-top:10px"><b>Criterio:</b> Cantidad × Potencia × Horas/día × Utilización. Se admite cruce de medianoche.</div>';
    tabs.parentNode.insertBefore(panel,tabs.nextSibling);return {tab,panel};
  }

  function install(){
    const tabs=document.querySelector('.tabs');if(!tabs||$('panel-matrix'))return;
    styles();const ui=makePanel(tabs);render();
    ui.tab.addEventListener('click',()=>{active=true;document.querySelectorAll('.tabs .tab').forEach(t=>t.classList.toggle('active',t===ui.tab));document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p===ui.panel));totals();});
    tabs.querySelectorAll('.tab:not([data-tab="matrix"])').forEach(t=>t.addEventListener('click',()=>{active=false;}));
    ui.panel.addEventListener('input',e=>{if(!e.target.matches('[data-field]'))return;const tr=e.target.closest('tr'),r=rows.find(x=>String(x.id)===String(tr?.dataset.id));if(!r)return;const field=e.target.dataset.field;r[field]=field==='equipment'||field==='start'||field==='end'?e.target.value:n(e.target.value,0);r.hours=duration(r);const c=calc(r);tr.querySelector('.cm-hours').textContent=f(c.hours);tr.querySelector('.cm-daily').textContent=f(c.daily);tr.querySelector('.cm-monthly').textContent=f(c.monthly);tr.querySelector('.cm-annual').textContent=f(c.annual);save();totals();});
    ui.panel.addEventListener('change',e=>{if(e.target.matches('[data-field]'))e.target.dispatchEvent(new Event('input',{bubbles:true}));});
    ui.panel.addEventListener('click',e=>{
      const del=e.target.closest('[data-delete]');if(del){const tr=del.closest('tr');rows=rows.filter(r=>String(r.id)!==String(tr?.dataset.id));if(!rows.length)rows=[fresh()];render();save();return;}
      const bk=e.target.closest('[data-backup]');if(bk&&!bk.disabled){const tr=bk.closest('tr'),r=rows.find(x=>String(x.id)===String(tr?.dataset.id));if(r){r.backup=!r.backup;render();save();}return;}
      if(e.target.id==='cmAdd'){rows.push(fresh());render();save();return;}
      if(e.target.id==='cmExample'){rows=[
        {id:'ex1',equipment:'Aire acondicionado',qty:2,power:1200,start:'14:00',end:'20:00',days:30,util:70,backup:false},
        {id:'ex2',equipment:'Nevera',qty:1,power:300,start:'00:00',end:'24:00',days:30,util:60,backup:false},
        {id:'ex3',equipment:'Iluminación LED',qty:12,power:12,start:'18:00',end:'23:00',days:30,util:100,backup:false},
        {id:'ex4',equipment:'Computador',qty:2,power:150,start:'08:00',end:'16:00',days:30,util:80,backup:false}
      ].map(norm);render();save();active=true;ui.tab.click();}
    });
    window.addEventListener('resize',()=>{if(active)draw();});
  }
  function boot(){load();install();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
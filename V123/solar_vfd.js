(function(){
  'use strict';
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const fmt=(v,d=2)=>Number(v||0).toLocaleString('es-CO',{minimumFractionDigits:d,maximumFractionDigits:d});
  let vfds=[];
  const STORAGE='esun_power_equipment_mode_v1';

  function inject(){
    const inv=$('inverter');
    if(!inv||$('equipmentMode'))return;
    const section=inv.closest('section.card');
    if(!section)return;
    const label=inv.previousElementSibling;
    const mode=document.createElement('div');
    mode.innerHTML='<label class="label" style="margin-top:0">Tipo de equipo de conversión</label><select id="equipmentMode"><option value="inverter">INVERSOR FOTOVOLTAICO — BASE EXISTENTE</option><option value="solar_vfd">VARIADOR DE FRECUENCIA SOLAR — BASE DE BOMBEO</option></select><p class="muted" style="margin-top:8px">Seleccione si el sistema utilizará el inversor fotovoltaico convencional o un variador solar con MPPT. En modo variador, la selección se dimensiona con la potencia máxima simultánea de la Matriz de Consumo.</p>';
    section.insertBefore(mode,label);
    const block=document.createElement('div');
    block.id='solarVfdBlock';
    block.style.display='none';
    block.innerHTML='<label class="label">Variador de frecuencia solar <span class="pill">TRIFÁSICO</span></label><select id="solarVfd"></select><input id="solarVfdRequiredInput" type="hidden" value=""><div id="solarVfdTechCard" class="equipment-spec-grid" style="margin-top:12px"></div><div class="resultbox" style="margin-top:12px"><div><b>POTENCIA MÁXIMA SIMULTÁNEA DE LA MATRIZ</b><div id="solarVfdPeakKw" class="big">—</div></div><div style="margin-top:10px"><b>POTENCIA DE DISEÑO DEL VARIADOR (+10 %)</b><div id="solarVfdRequiredKw" class="big">—</div></div><div id="solarVfdSizingNote" class="muted" style="margin-top:8px">Ingrese equipos y horarios en la Matriz de Consumo para seleccionar automáticamente el variador.</div></div>';
    section.insertBefore(block,inv);
  }
  function matrixRows(){
    return [...document.querySelectorAll('#consumptionMatrixBody tr')].map(tr=>{const get=k=>tr.querySelector(`[data-field="${k}"]`)?.value||'';return{power:Number(get('power'))||0,qty:Number(get('qty'))||0,start:get('start'),end:get('end'),util:Number(get('util'))||0};}).filter(r=>r.power>0&&r.qty>0&&r.start&&r.end);
  }
  function minutes(v){const m=String(v||'').match(/^(\d{1,2}):(\d{2})$/);if(!m)return null;const h=+m[1],mm=+m[2];return h>=0&&h<=24&&mm>=0&&mm<60?(h*60+mm):null;}
  function peak(){const rows=matrixRows(),hour=Array(24).fill(0);rows.forEach(r=>{let a=minutes(r.start),b=minutes(r.end);if(a===null||b===null)return;if(a===b)b=a+1440;else if(b<a)b+=1440;const kw=r.power*r.qty*Math.max(0,Math.min(100,r.util))/100/1000;for(let h=0;h<24;h++){let ov=0;for(let base=0;base<=1440;base+=1440)ov+=Math.max(0,Math.min(b,h*60+60+base)-Math.max(a,h*60+base));if(ov>0)hour[h]+=kw*ov/60;}});return Math.max(0,...hour);}
  function required(){const p=peak();return p>0?p*1.10:0;}
  function renderVfd(){const s=$('solarVfd');if(!s)return;const req=required();const phase=$('systemPhase')?.value||'TRIFASICO';s.disabled=phase!=='TRIFASICO';const candidates=vfds.filter(v=>v.phase_class===phase);const current=s.value;s.innerHTML=candidates.map((v,i)=>`<option value="${i}">${esc(v.manufacturer)} — ${esc(v.model)} — ${fmt(v.power_kw,0)} kW · ${esc(v.motor_recommended_hp)} · $ ${fmt(v.price_cop,0)}</option>`).join('')||'<option value="">No hay variadores para esta fase</option>';if(candidates.some((v,i)=>String(i)===String(current)))s.value=current;let idx=candidates.findIndex(v=>v.power_kw>=req-1e-9);if(idx<0&&candidates.length)idx=candidates.length-1;if(idx>=0)s.value=String(idx);const v=candidates[idx];if(v){s.dataset.globalIndex=vfds.indexOf(v);tech(v,req);}else{s.dataset.globalIndex='';tech(null,req);}}
  function tech(v,req){const p=$('solarVfdPeakKw'),r=$('solarVfdRequiredKw'),n=$('solarVfdSizingNote'),box=$('solarVfdTechCard');if(p)p.textContent=fmt(peak(),2)+' kW';if(r)r.textContent=req>0?fmt(req,2)+' kW':'—';const hi=$('solarVfdRequiredInput');if(hi)hi.value=req>0?String(req):'';if(!box)return;if(!v){box.innerHTML='';if(n)n.textContent='No existe un variador compatible con la fase seleccionada.';return;}box.innerHTML=[['Potencia',fmt(v.power_kw,0)+' kW'],['Motor recomendado',v.motor_recommended_hp],['Tensión de salida',v.output_voltage],['MPPT solar',v.mppt_solar?'Sí':'No'],['Precio publicado','$ '+fmt(v.price_cop,0)],['Base','Variadores de frecuencia solar']].map(x=>`<div class="equipment-spec"><small>${x[0]}</small><b>${esc(x[1])}</b></div>`).join('');if(n)n.textContent=req>0?(v.power_kw>=req?'Selección automática: '+v.manufacturer+' '+v.model+' cubre la potencia de diseño con margen del 10 %.':'La potencia de diseño supera la base disponible; seleccione una referencia y valide ingeniería del motor.'):'La selección automática requiere potencia de carga de la Matriz de Consumo.';}
  function sync(){const mode=$('equipmentMode')?.value||'inverter',on=mode==='solar_vfd';$('inverter').style.display=on?'none':'';const lbl=$('inverterTechnicalLabel')||$('inverter').previousElementSibling;if(lbl)lbl.style.display=on?'none':'';$('inverterTechCard')?.style.setProperty('display',on?'none':'');$('inverterTechStatus')?.style.setProperty('display',on?'none':'');$('inverterDatasheet')?.style.setProperty('display',on?'none':'');$('solarVfdBlock').style.display=on?'block':'none';if(on)renderVfd();try{localStorage.setItem(STORAGE,mode);}catch(e){}}
  function install(){inject();if(!$('equipmentMode'))return;fetch('data/solar_vfd.json').then(r=>r.json()).then(d=>{vfds=Array.isArray(d)?d:[];const saved=localStorage.getItem(STORAGE);if(saved==='solar_vfd')$('equipmentMode').value='solar_vfd';sync();}).catch(()=>{vfds=[];sync();});$('equipmentMode').addEventListener('change',sync);$('solarVfd').addEventListener('change',()=>{const cs=vfds.filter(v=>v.phase_class===($('systemPhase')?.value||'TRIFASICO'));const v=cs[Number($('solarVfd').value)];tech(v,required());});$('systemPhase')?.addEventListener('change',()=>{if($('equipmentMode')?.value==='solar_vfd')renderVfd();});document.addEventListener('input',e=>{if($('equipmentMode')?.value==='solar_vfd'&&e.target.closest('#consumptionMatrixBody'))renderVfd();});}
  function wrapProjectState(){
    if(typeof window.getProjectFormState==='function'&&!window.getProjectFormState.__vfdWrapped){const orig=window.getProjectFormState;const w=function(){const s=orig();s.fields=s.fields||{};s.fields.equipmentMode=$('equipmentMode')?.value||'inverter';s.fields.solarVfdIndex=$('solarVfd')?.value||'';s.fields.solarVfdRequiredKw=required();return s;};w.__vfdWrapped=true;window.getProjectFormState=w;}
    if(typeof window.setProjectFormState==='function'&&!window.setProjectFormState.__vfdWrapped){const orig=window.setProjectFormState;const w=function(s){orig(s);const mode=s?.fields?.equipmentMode;if(mode&&$('equipmentMode')){$('equipmentMode').value=mode;sync();}if(s?.fields?.solarVfdIndex!=null&&$('solarVfd')){$('solarVfd').value=s.fields.solarVfdIndex;$('solarVfd').dispatchEvent(new Event('change'));}};w.__vfdWrapped=true;window.setProjectFormState=w;}
  }
  function boot(){inject();wrapProjectState();install();setTimeout(wrapProjectState,0);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();

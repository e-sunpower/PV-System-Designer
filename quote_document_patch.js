(function(){
  'use strict';
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const fmt=(v,d=2)=>Number(v||0).toLocaleString('es-CO',{minimumFractionDigits:d,maximumFractionDigits:d});
  const num=v=>Number(v||0);

  function matrixBackup(){
    const daily=num(window.__esunConsumptionMatrixBackupDaily);
    const monthly=num(window.__esunConsumptionMatrixBackupMonthly);
    const annual=num(window.__esunConsumptionMatrixBackupAnnual);
    return {daily,monthly,annual};
  }

  function ensureFields(){
    const grid=document.querySelector('.quote-tech-grid');
    if(!grid)return;
    const defs=[
      ['qqEquipmentLabel','Equipo de conversión','—'],
      ['qqEquipmentDetail','Equipo seleccionado','—'],
      ['qqBatteryCapacityRow','Capacidad banco de baterías','—'],
      ['qqBackupConsumptionRow','Consumo a respaldar','—']
    ];
    if(!$('qqEquipmentLabel')){
      const d=document.createElement('div');d.innerHTML='<span id="qqEquipmentLabel">Equipo de conversión</span><strong id="qqEquipmentDetail">—</strong>';grid.appendChild(d);
    }
    if(!$('qqBatteryCapacityRow')){
      const d=document.createElement('div');d.id='qqBatteryCapacityRow';d.style.display='none';d.innerHTML='<span>Capacidad banco de baterías</span><strong id="qqBatteryCapacity">—</strong>';grid.appendChild(d);
    }
    if(!$('qqBackupConsumptionRow')){
      const d=document.createElement('div');d.id='qqBackupConsumptionRow';d.style.display='none';d.innerHTML='<span>Consumo a respaldar</span><strong id="qqBackupConsumption">—</strong>';grid.appendChild(d);
    }
  }

  function syncExtras(){
    ensureFields();
    const d=window.lastDesign||null;
    const vfd=d?.solar_vfd?.is_solar_vfd?d.solar_vfd:null;
    const inv=d?.inverter||null;
    const equipmentLabel=$('qqEquipmentLabel');
    const equipmentDetail=$('qqEquipmentDetail');
    const invQty=$('qqInvQty');
    const invPower=$('qqInvPower');
    const invModel=$('qqInvModel');
    const invTech=$('qqTechInv');
    const acTech=$('qqTechAc');
    if(vfd){
      const qty=num(vfd.quantity)||1;
      const power=num(vfd.power_kw);
      const motor=vfd.motor_recommended_hp||'—';
      const voltage=vfd.output_voltage||'—';
      if(equipmentLabel)equipmentLabel.textContent='Variador de frecuencia solar';
      if(equipmentDetail)equipmentDetail.textContent=`${vfd.manufacturer||''} ${vfd.model||''} · ${fmt(power,0)} kW · motor ${motor} · ${voltage}`.trim();
      if(invQty)invQty.textContent=fmt(qty,0);
      if(invPower)invPower.textContent=power?fmt(power,1)+' kW':'—';
      if(invModel)invModel.textContent=`${vfd.manufacturer||''} ${vfd.model||''}`.trim();
      if(invTech)invTech.textContent=power?fmt(power,1)+' kW':'—';
      if(acTech)acTech.textContent='No aplica — variador solar';
    }else if(inv){
      const qty=num(inv.quantity)||1;
      const power=num(inv.ac_kw);
      if(equipmentLabel)equipmentLabel.textContent='Inversor fotovoltaico';
      if(equipmentDetail)equipmentDetail.textContent=`${inv.manufacturer||''} ${inv.model||''} · ${fmt(power,1)} kW AC · ${fmt(qty,0)} unidad(es)`.trim();
      if(invQty)invQty.textContent=fmt(qty,0);
      if(invPower)invPower.textContent=power?fmt(power,1)+' kW AC':'—';
      if(invModel)invModel.textContent=`${inv.manufacturer||''} ${inv.model||''}`.trim();
      if(invTech)invTech.textContent=power?fmt(power,1)+' kW AC':'—';
      if(acTech)acTech.textContent=power?fmt(power,1)+' kW AC':'—';
    }else{
      if(equipmentLabel)equipmentLabel.textContent='Equipo de conversión';
      if(equipmentDetail)equipmentDetail.textContent='Pendiente';
    }

    const batteryRow=$('qqBatteryCapacityRow');
    const backupRow=$('qqBackupConsumptionRow');
    const offgrid=d?.inputs?.system_type==='OFF-GRID' || $('systemType')?.value==='OFF-GRID';
    const battery=d?.battery;
    if(batteryRow){
      if(offgrid && battery){
        const qty=num(battery.quantity)||1;
        const unit=num(battery.capacity_kwh);
        const usable=num(battery.usable_capacity_kwh);
        const total=qty*unit;
        batteryRow.style.display='block';
        const detail=usable>0?`${fmt(total,2)} kWh nominales · ${fmt(qty,0)} unidad(es) · ${fmt(qty*usable,2)} kWh útiles`:`${fmt(total,2)} kWh nominales · ${fmt(qty,0)} unidad(es)`;
        const e=$('qqBatteryCapacity');if(e)e.textContent=detail;
      }else batteryRow.style.display='none';
    }
    if(backupRow){
      const b=matrixBackup();
      if(offgrid && (b.daily>0||b.monthly>0||b.annual>0)){
        backupRow.style.display='block';
        const e=$('qqBackupConsumption');if(e)e.textContent=`${fmt(b.daily,2)} kWh/día · ${fmt(b.monthly,2)} kWh/mes · ${fmt(b.annual,2)} kWh/año`;
      }else backupRow.style.display='none';
    }
    const badge=$('qqInvPower');
    const labelSpan=badge?.previousElementSibling;
    if(labelSpan)labelSpan.textContent=vfd?'VARIADOR SOLAR(ES)':'INVERSOR(ES)';
    const techInvLabel=$('qqTechInv')?.parentElement?.querySelector('span');
    if(techInvLabel)techInvLabel.textContent=vfd?'Variador(es) solar':'Inversor(es)';
  }

  function install(){
    ensureFields();
    if(typeof window.syncQuoteDocument==='function'&&!window.syncQuoteDocument.__quotePatch){
      const orig=window.syncQuoteDocument;
      const wrapped=function(){orig();syncExtras();};
      wrapped.__quotePatch=true;
      window.syncQuoteDocument=wrapped;
    }
    syncExtras();
    setTimeout(syncExtras,250);
    setTimeout(syncExtras,1000);
    ['systemType','systemPhase','equipmentMode','solarVfd','inverter','battery','batteryMode','batteryStorageHours','batteryDod','batteryUsable'].forEach(id=>$(id)?.addEventListener('change',syncExtras));
    window.addEventListener('resize',syncExtras);
    document.addEventListener('input',e=>{if(e.target.closest('#consumptionMatrixBody'))setTimeout(syncExtras,0);});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();

(function(){
 'use strict';
 const $=id=>document.getElementById(id);
 function matrixSummary(){try{if(typeof window.__esunConsumptionMatrixGetSummary==='function')return window.__esunConsumptionMatrixGetSummary();}catch(e){}return{daily:0,monthly:0,annual:0,backupDaily:0,backupMonthly:0,backupAnnual:0,rows:[]};}
 function matrixRows(){try{if(typeof window.__esunConsumptionMatrixGetRows==='function')return window.__esunConsumptionMatrixGetRows();}catch(e){}return[];}
 window.__esunConsumptionSystemSummary=matrixSummary;
 const oldGetAnnual=window.getAnnual;if(typeof oldGetAnnual==='function')window.getAnnual=function(){const s=matrixSummary();return s.annual>0?s.annual:oldGetAnnual.apply(this,arguments);};
 const oldUpdateConsumption=window.updateConsumption;if(typeof oldUpdateConsumption==='function')window.updateConsumption=function(){const r=oldUpdateConsumption.apply(this,arguments);const s=matrixSummary();if(s.annual>0&&$('annualView'))$('annualView').textContent=Number(s.annual).toLocaleString('es-CO',{minimumFractionDigits:0,maximumFractionDigits:0})+' kWh/año';return r;};
 const oldGetState=window.getProjectFormState;if(typeof oldGetState==='function')window.getProjectFormState=function(){const st=oldGetState.apply(this,arguments)||{};st.fields=st.fields||{};const s=matrixSummary();st.fields.consumptionMatrix=matrixRows();st.fields.consumptionMatrixTotals={daily:s.daily,monthly:s.monthly,annual:s.annual,backupDaily:s.backupDaily,backupMonthly:s.backupMonthly,backupAnnual:s.backupAnnual};return st;};
 const oldSetState=window.setProjectFormState;if(typeof oldSetState==='function')window.setProjectFormState=function(state){const r=oldSetState.apply(this,arguments);try{const saved=state?.fields?.consumptionMatrix;if(Array.isArray(saved)&&saved.length&&typeof window.__esunConsumptionMatrixSetRows==='function')window.__esunConsumptionMatrixSetRows(saved);else if(typeof window.__esunConsumptionMatrixRerender==='function')window.__esunConsumptionMatrixRerender();setTimeout(()=>{try{if(typeof window.updateConsumption==='function')window.updateConsumption();if(typeof window.updateBatterySelection==='function')window.updateBatterySelection();if(typeof window.syncBatteryBudgetRow==='function')window.syncBatteryBudgetRow();if(typeof window.updateBatteryPreview==='function')window.updateBatteryPreview();refreshBackupButtons();reorderSections();}catch(e){}},0);}catch(e){}return r;};
 const oldBattery=window.estimateBatteryFromKwp;if(typeof oldBattery==='function')window.estimateBatteryFromKwp=function(batteryData,dc_kwp,storageHours,acKw){const s=matrixSummary();if(s.backupDaily>0){const usable=Number(batteryData?.usable_capacity_kwh||0)||Number(batteryData?.capacity_kwh||0)*(Number(batteryData?.recommended_dod_pct||80)/100);if(usable<=0)return null;const required=s.backupDaily;const qe=Math.max(1,Math.ceil(required/usable));const qc=Number(batteryData?.recommended_charge_power_kw||0)>0?Math.max(1,Math.ceil(Number(dc_kwp||0)/Number(batteryData.recommended_charge_power_kw))):1;const qd=Number(batteryData?.recommended_discharge_power_kw||0)>0&&Number(acKw||0)>0?Math.max(1,Math.ceil(Number(acKw)/Number(batteryData.recommended_discharge_power_kw))):1;const qty=Math.max(qe,qc,qd);return{required_usable_kwh:required,usable_capacity_per_battery_kwh:usable,qty_energy:qe,qty_charge_power:qc,qty_discharge_power:qd,quantity:qty,installed_usable_kwh:qty*usable,installed_kwh:qty*Number(batteryData?.capacity_kwh||0),cost:qty*Number(batteryData?.price_cop||0)};}return oldBattery.apply(this,arguments);};
 const oldBatteryPreview=window.updateBatteryPreview;if(typeof oldBatteryPreview==='function')window.updateBatteryPreview=function(){const r=oldBatteryPreview.apply(this,arguments);const s=matrixSummary();if(s.backupDaily>0&&$('batterySizingNote'))$('batterySizingNote').textContent='CONSUMO A RESPALDAR: '+Number(s.backupDaily).toLocaleString('es-CO',{minimumFractionDigits:2,maximumFractionDigits:2})+' kWh/día. La batería se dimensiona con base en esta energía de respaldo y los límites técnicos de energía, carga y descarga de la batería seleccionada.';return r;};
 function refreshBackupButtons(){const off=(($('systemType')?.value||'ON-GRID')==='OFF-GRID');document.querySelectorAll('.cm-backup').forEach(b=>{b.disabled=!off;});}
 function reorderSections(){
   const m=$('panel-matrix');if(!m)return;
   const candidates=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6,.label,.section-title,.card-title,.section-heading')];
   const h=candidates.find(el=>/Banco de bater[ií]as/i.test((el.textContent||'').trim());
   if(!h)return;
   const b=h.closest('.offgrid-battery-card')||h.closest('.card')||h.parentElement;if(!b||b===m)return;
   const container=b.closest('.grid')||b.parentElement;
   if(!container)return;
   if(m.parentNode!==container){
     container.insertBefore(m,b);
   }else if(b.previousElementSibling!==m){
     container.insertBefore(m,b);
   }
   if(container.classList.contains('grid'))m.style.gridColumn='1 / -1';
 }
 const oldOpen=window.openSavedProject;if(typeof oldOpen==='function')window.openSavedProject=function(){const r=oldOpen.apply(this,arguments);setTimeout(()=>{refreshBackupButtons();reorderSections();},0);return r;};
 document.addEventListener('change',e=>{if(e.target?.id==='systemType'){setTimeout(()=>{refreshBackupButtons();try{if(typeof window.updateBatterySelection==='function')window.updateBatterySelection();if(typeof window.syncBatteryBudgetRow==='function')window.syncBatteryBudgetRow();if(typeof window.updateBatteryPreview==='function')window.updateBatteryPreview();}catch(err){}},0);}});
 function boot(){setTimeout(()=>{refreshBackupButtons();reorderSections();},0);}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
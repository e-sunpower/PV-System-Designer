(function(){
'use strict';
function isVFD(){return document.getElementById('equipmentMode')?.value==='solar_vfd'}
function fix(){
  if(!isVFD())return;
  document.querySelectorAll('img[src*="quote-inverter-icon"],img[alt*="Inversor"],img[alt*="inversor"]').forEach(function(img){img.src='quote-vfd-icon.svg?v=2';img.alt='Variador de frecuencia';});
  document.querySelectorAll('.qstat span,.qstat b,.qstat strong,.qstat p').forEach(function(n){if(/^(INVERSOR\(ES\)|INVERSOR|VARIADOR SOLAR\(ES\)|VARIADOR SOLAR)$/i.test((n.textContent||'').trim()))n.textContent='VARIADOR DE FRECUENCIA';});
}
function install(){fix();document.getElementById('equipmentMode')?.addEventListener('change',function(){setTimeout(fix,0);});new MutationObserver(fix).observe(document.body,{childList:true,subtree:true});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();

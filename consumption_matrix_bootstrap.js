(function(){
  'use strict';
  function activateMatrix(){
    const panel=document.getElementById('panel-matrix');
    if(!panel)return;
    const tab=document.querySelector('.tabs .tab[data-tab="matrix"]');
    if(!tab)return;
    if(!panel.classList.contains('active')){
      try{tab.click();}catch(e){}
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(activateMatrix,0),{once:true});
  else setTimeout(activateMatrix,0);
})();
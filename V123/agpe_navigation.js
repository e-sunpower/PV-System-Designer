(function(){
  'use strict';
  if(window.__esunAgpeNavigationLoaded)return;
  window.__esunAgpeNavigationLoaded=true;

  const css=`
  #agpeShell{position:fixed;inset:0;z-index:9000;background:#1d1d1d;color:#fff;font-family:Arial,sans-serif;display:none;overflow:auto}
  #agpeShell.visible{display:block}
  #agpeShell .agpe-wrap{max-width:1180px;margin:0 auto;padding:34px 24px 50px}
  #agpeShell .agpe-head{display:flex;align-items:center;gap:18px;border-bottom:1px solid #414141;padding-bottom:18px;margin-bottom:34px}
  #agpeShell .agpe-mark{width:52px;height:52px;border-radius:50%;border:2px solid #f3c000;display:grid;place-items:center;color:#f3c000;font-weight:800;font-size:20px}
  #agpeShell h1{margin:0;font-size:28px;letter-spacing:.04em}
  #agpeShell .agpe-sub{margin:5px 0 0;color:#bdbdbd;font-size:13px}
  #agpeShell .agpe-view{display:none}
  #agpeShell .agpe-view.active{display:block}
  #agpeShell .agpe-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
  #agpeShell .agpe-card{min-height:150px;background:#252525;border:1px solid #454545;border-radius:12px;padding:24px;cursor:pointer;transition:.15s ease;display:flex;flex-direction:column;justify-content:center}
  #agpeShell .agpe-card:hover{border-color:#f3c000;transform:translateY(-2px);box-shadow:0 8px 28px #0008}
  #agpeShell .agpe-card h2{margin:0 0 8px;font-size:20px}
  #agpeShell .agpe-card p{margin:0;color:#bdbdbd;font-size:13px;line-height:1.45}
  #agpeShell .agpe-card.primary{border-color:#a98300}
  #agpeShell .agpe-card.primary h2{color:#f3c000}
  #agpeShell .agpe-back{background:#5d6972;color:#fff;margin-bottom:22px}
  #agpeShell .agpe-title{font-size:22px;margin:0 0 20px}
  #agpeShell .agpe-path{color:#999;font-size:12px;margin-bottom:18px}
  #agpeShell .agpe-placeholder{max-width:720px;background:#252525;border:1px solid #454545;border-radius:12px;padding:26px;color:#cfcfcf;line-height:1.55}
  @media(max-width:850px){#agpeShell .agpe-grid{grid-template-columns:1fr}#agpeShell .agpe-wrap{padding:22px 16px}}
  `;
  const style=document.createElement('style');style.id='agpeNavigationStyle';style.textContent=css;document.head.appendChild(style);

  const shell=document.createElement('div');
  shell.id='agpeShell';
  shell.innerHTML=`
    <div class="agpe-wrap">
      <div class="agpe-head">
        <div class="agpe-mark">E</div>
        <div><h1>E-SUN POWER AGPE</h1><p class="agpe-sub">Diseño y gestión de proyectos de autogeneración a pequeña escala</p></div>
      </div>

      <section id="agpeHome" class="agpe-view active">
        <div class="agpe-grid">
          <div class="agpe-card primary" data-open="calculo"><h2>CÁLCULO DE</h2><p>Crear y dimensionar proyectos fotovoltaicos.</p></div>
          <div class="agpe-card" data-open="proyectos"><h2>PROYECTOS AGPE</h2><p>Gestión y seguimiento de proyectos AGPE.</p></div>
          <div class="agpe-card" data-open="clientes"><h2>CLIENTES</h2><p>Administración de la información de clientes.</p></div>
        </div>
      </section>

      <section id="agpeCalculo" class="agpe-view">
        <button class="agpe-back" data-back="home">← VOLVER</button>
        <div class="agpe-path">E-SUN POWER AGPE / CÁLCULO DE</div>
        <h2 class="agpe-title">CÁLCULO DE</h2>
        <div class="agpe-grid">
          <div class="agpe-card primary" data-action="new-traditional"><h2>NUEVO PROYECTO</h2><p>Crear un nuevo proyecto y seleccionar el tipo de sistema.</p></div>
          <div class="agpe-card" data-action="saved"><h2>PROYECTOS GUARDADOS</h2><p>Abrir proyectos previamente almacenados.</p></div>
        </div>
      </section>

      <section id="agpeNew" class="agpe-view">
        <button class="agpe-back" data-back="calculo">← VOLVER</button>
        <div class="agpe-path">E-SUN POWER AGPE / CÁLCULO DE / NUEVO PROYECTO</div>
        <h2 class="agpe-title">NUEVO PROYECTO</h2>
        <div class="agpe-grid">
          <div class="agpe-card primary" data-action="traditional"><h2>SFV TRADICIONAL</h2><p>Diseño de sistemas fotovoltaicos tradicionales.</p></div>
          <div class="agpe-card primary" data-action="pumping"><h2>SFV BOMBEO SOLAR</h2><p>Diseño de sistemas fotovoltaicos para bombeo solar.</p></div>
        </div>
      </section>

      <section id="agpeProjects" class="agpe-view">
        <button class="agpe-back" data-back="home">← VOLVER</button>
        <div class="agpe-path">E-SUN POWER AGPE / PROYECTOS AGPE</div>
        <h2 class="agpe-title">PROYECTOS AGPE</h2>
        <div class="agpe-placeholder">Este módulo queda reservado para la gestión de proyectos AGPE. En esta primera fase se incorpora la estructura de navegación sin alterar todavía el motor de cálculo existente.</div>
      </section>

      <section id="agpeClients" class="agpe-view">
        <button class="agpe-back" data-back="home">← VOLVER</button>
        <div class="agpe-path">E-SUN POWER AGPE / CLIENTES</div>
        <h2 class="agpe-title">CLIENTES</h2>
        <div class="agpe-placeholder">Este módulo queda reservado para la base de datos de clientes. En esta primera fase se incorpora la estructura de navegación sin alterar todavía los datos existentes.</div>
      </section>
    </div>`;
  document.body.appendChild(shell);

  function visible(el){return !!el && getComputedStyle(el).display!=='none' && getComputedStyle(el).visibility!=='hidden';}
  function showView(name){
    const map={home:'agpeHome',calculo:'agpeCalculo',new:'agpeNew',proyectos:'agpeProjects',clientes:'agpeClients'};
    Object.values(map).forEach(id=>document.getElementById(id)?.classList.remove('active'));
    document.getElementById(map[name]||map.home)?.classList.add('active');
  }
  function findClickableText(text){
    const els=[...document.querySelectorAll('button,a,[role="button"],.tab')];
    const target=text.trim().toLowerCase();
    return els.find(el=>!el.closest('#agpeShell') && (el.textContent||'').trim().toLowerCase()===target)
      || els.find(el=>!el.closest('#agpeShell') && (el.textContent||'').trim().toLowerCase().includes(target));
  }
  function revealLegacy(mode){
    shell.classList.remove('visible');
    document.body.classList.remove('agpe-shell-active');
    document.querySelectorAll('body>header,body>main').forEach(el=>{el.style.visibility='';el.style.pointerEvents='';});
    if(mode){
      const sel=document.getElementById('equipmentMode');
      if(sel){sel.value=mode==='pumping'?'solar_vfd':'inverter';sel.dispatchEvent(new Event('change',{bubbles:true}));}
    }
    window.scrollTo({top:0,behavior:'instant'});
  }
  function openLegacyApp(mode){revealLegacy(mode);}
  function openSaved(){
    revealLegacy(null);
    const btn=findClickableText('PROYECTOS GUARDADOS');
    if(btn){setTimeout(()=>{try{btn.click();}catch(e){}},50);}
  }
  function activate(){
    const portal=document.getElementById('accessPortal');
    const locked=document.body.classList.contains('app-locked');
    if(locked || (portal && visible(portal))){shell.classList.remove('visible');return false;}
    document.body.classList.add('agpe-shell-active');
    document.querySelectorAll('body>header,body>main').forEach(el=>{el.style.visibility='hidden';el.style.pointerEvents='none';});
    shell.classList.add('visible');
    return true;
  }
  function activateAfterAccess(){
    let tries=0;
    const tick=()=>{
      tries++;
      const portal=document.getElementById('accessPortal');
      const locked=document.body.classList.contains('app-locked');
      if(!locked && (!portal || !visible(portal))){activate();return;}
      if(tries<20)setTimeout(tick,250);
    };
    setTimeout(tick,150);
  }
  shell.addEventListener('click',e=>{
    const card=e.target.closest('[data-open]');
    if(card){showView(card.dataset.open);return;}
    const back=e.target.closest('[data-back]');
    if(back){showView(back.dataset.back);return;}
    const action=e.target.closest('[data-action]');
    if(!action)return;
    switch(action.dataset.action){
      case 'new-traditional': showView('new'); break;
      case 'traditional': openLegacyApp('traditional'); break;
      case 'pumping': openLegacyApp('pumping'); break;
      case 'saved': openSaved(); break;
    }
  });

  function hookAccessButton(){
    const btn=findClickableText('INGRESAR A E-SUN POWER');
    if(!btn || btn.__esunAgpeHooked)return;
    btn.__esunAgpeHooked=true;
    btn.addEventListener('click',()=>activateAfterAccess(),{capture:false});
  }
  function waitForAccess(){
    hookAccessButton();
    const portal=document.getElementById('accessPortal');
    if(portal){
      const obs=new MutationObserver(()=>{hookAccessButton();if(!document.body.classList.contains('app-locked') && !visible(portal))activate();});
      obs.observe(document.body,{attributes:true,attributeFilter:['class']});
      obs.observe(portal,{attributes:true,attributeFilter:['class','style','hidden']});
    }
    setTimeout(hookAccessButton,250);
    setTimeout(hookAccessButton,700);
    setTimeout(activate,1200);
    setTimeout(activate,2200);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',waitForAccess,{once:true});else waitForAccess();
})();

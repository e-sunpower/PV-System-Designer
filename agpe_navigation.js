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

  /* Selector de tipo de proyecto: anillos solares independientes */
  #agpeShell .agpe-project-types{display:grid;grid-template-columns:repeat(2,minmax(340px,1fr));gap:70px;justify-items:center;align-items:start;margin:28px auto 0;max-width:980px}
  #agpeShell .agpe-project-ring-card{position:relative;width:430px;height:430px;display:grid;place-items:center;cursor:pointer;background:transparent;border:0;padding:0;color:#fff;transition:transform .25s ease,filter .25s ease}
  #agpeShell .agpe-project-ring-card:hover{transform:translateY(-5px) scale(1.015);filter:brightness(1.08)}
  #agpeShell .agpe-project-ring-card:focus-visible{outline:2px solid #f3c000;outline-offset:8px;border-radius:50%}
  #agpeShell .agpe-solar-ring{position:absolute;inset:7px;border-radius:50%;background:radial-gradient(circle at center,#070707 0 54%,transparent 54.5%),conic-gradient(from 0deg,transparent 0 12%,rgba(243,192,0,.98) 13%,rgba(255,229,92,.25) 16%,transparent 19% 36%,rgba(243,192,0,.9) 37%,transparent 41% 58%,rgba(255,244,150,1) 59%,rgba(243,192,0,.18) 62%,transparent 66% 82%,rgba(243,192,0,.9) 83%,transparent 87% 100%);box-shadow:0 0 10px rgba(243,192,0,.8),0 0 28px rgba(243,192,0,.52),inset 0 0 18px rgba(243,192,0,.32);animation:agpeRingWave 5.2s linear infinite}
  #agpeShell .agpe-solar-ring:before{content:"";position:absolute;inset:13px;border-radius:50%;border:2px solid rgba(243,192,0,.96);box-shadow:0 0 8px rgba(243,192,0,.85),0 0 20px rgba(243,192,0,.45);animation:agpeRingPulse 2.8s ease-in-out infinite}
  #agpeShell .agpe-solar-ring:after{content:"";position:absolute;inset:29px;border-radius:50%;border:3px solid rgba(243,192,0,.9);box-shadow:0 0 12px rgba(243,192,0,.72),inset 0 0 10px rgba(243,192,0,.22);animation:agpeRingWave2 3.7s ease-in-out infinite}
  #agpeShell .agpe-project-ring-card:nth-child(2) .agpe-solar-ring{animation-delay:-2.1s}
  #agpeShell .agpe-project-ring-card:nth-child(2) .agpe-solar-ring:before{animation-delay:-1.15s}
  #agpeShell .agpe-project-ring-card:nth-child(2) .agpe-solar-ring:after{animation-delay:-2.25s}
  #agpeShell .agpe-solar-rays{position:absolute;inset:0;border-radius:50%;background:repeating-conic-gradient(from 0deg,rgba(243,192,0,.95) 0deg 1.3deg,transparent 1.3deg 30deg);mask:radial-gradient(circle,#0000 0 54%,#000 55% 57%,#0000 58%);-webkit-mask:radial-gradient(circle,#0000 0 54%,#000 55% 57%,#0000 58%);animation:agpeRayPulse 2.9s ease-in-out infinite}
  #agpeShell .agpe-project-ring-card:nth-child(2) .agpe-solar-rays{animation-delay:-1.4s}
  #agpeShell .agpe-ring-content{position:relative;z-index:2;width:270px;min-height:285px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px}
  #agpeShell .agpe-project-icon{width:118px;height:118px;margin-bottom:8px;filter:drop-shadow(0 0 7px rgba(243,192,0,.95)) drop-shadow(0 0 18px rgba(243,192,0,.55))}
  #agpeShell .agpe-ring-content h3{margin:5px 0 10px;font-size:20px;line-height:1.12;letter-spacing:.035em;color:#fff;text-shadow:0 0 8px rgba(255,255,255,.12)}
  #agpeShell .agpe-ring-content p{margin:0;color:#bdbdbd;font-size:13px;line-height:1.4;max-width:235px}
  #agpeShell .agpe-ring-arrow{width:48px;height:48px;border:1.5px solid #f3c000;border-radius:50%;display:grid;place-items:center;margin-top:16px;color:#f3c000;font-size:24px;line-height:1;box-shadow:0 0 10px rgba(243,192,0,.45);transition:.2s ease}
  #agpeShell .agpe-project-ring-card:hover .agpe-ring-arrow{background:#f3c000;color:#111;box-shadow:0 0 22px rgba(243,192,0,.8)}
  @keyframes agpeRingWave{0%{transform:rotate(0deg) scale(1);filter:brightness(.95)}50%{transform:rotate(180deg) scale(1.012);filter:brightness(1.15)}100%{transform:rotate(360deg) scale(1);filter:brightness(.95)}}
  @keyframes agpeRingPulse{0%,100%{opacity:.72;transform:scale(.99)}50%{opacity:1;transform:scale(1.015)}}
  @keyframes agpeRingWave2{0%,100%{opacity:.58;transform:scale(.985)}50%{opacity:1;transform:scale(1.025)}}
  @keyframes agpeRayPulse{0%,100%{opacity:.55;transform:rotate(0deg)}50%{opacity:1;transform:rotate(5deg)}}
  @media(max-width:850px){#agpeShell .agpe-grid{grid-template-columns:1fr}#agpeShell .agpe-wrap{padding:22px 16px}#agpeShell .agpe-project-types{grid-template-columns:1fr;gap:30px}#agpeShell .agpe-project-ring-card{width:min(430px,92vw);height:min(430px,92vw)}}
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
        <div style="text-align:center;margin-top:12px">
          <div style="color:#999;font-size:12px;letter-spacing:.22em;margin-bottom:8px">AGPE / CÁLCULO DE / NUEVO PROYECTO</div>
          <h2 class="agpe-title" style="font-size:30px;margin-bottom:8px">NUEVO PROYECTO</h2>
          <p style="margin:0;color:#bdbdbd;font-size:16px">Seleccione el tipo de proyecto que desea crear.</p>
        </div>
        <div class="agpe-project-types">
          <button class="agpe-project-ring-card" type="button" data-action="traditional" aria-label="Proyecto SFV Tradicional">
            <span class="agpe-solar-ring" aria-hidden="true"></span>
            <span class="agpe-solar-rays" aria-hidden="true"></span>
            <span class="agpe-ring-content">
              <svg class="agpe-project-icon" viewBox="0 0 120 120" aria-hidden="true">
                <g fill="none" stroke="#f3c000" stroke-width="3" stroke-linejoin="round">
                  <path d="M18 60 60 31l42 29v38H18z"/>
                  <path d="M48 98V77h24v21"/>
                  <path d="M28 64h64"/>
                  <path d="M36 56 52 45l25 17-16 11z"/>
                  <path d="M42 52 67 69"/>
                  <path d="M53 44 79 61"/>
                  <circle cx="27" cy="29" r="9"/>
                  <path d="M27 14v-7M27 51v-7M12 29H5M49 29h-7M16 18l-5-5M38 40l-5-5M38 18l5-5"/>
                </g>
              </svg>
              <h3>PROYECTO<br>SFV TRADICIONAL</h3>
              <p>Diseño y dimensionamiento de sistemas fotovoltaicos tradicionales.</p>
              <span class="agpe-ring-arrow" aria-hidden="true">→</span>
            </span>
          </button>

          <button class="agpe-project-ring-card" type="button" data-action="pumping" aria-label="Proyecto Bombeo Solar">
            <span class="agpe-solar-ring" aria-hidden="true"></span>
            <span class="agpe-solar-rays" aria-hidden="true"></span>
            <span class="agpe-ring-content">
              <svg class="agpe-project-icon" viewBox="0 0 120 120" aria-hidden="true">
                <g fill="none" stroke="#f3c000" stroke-width="3" stroke-linejoin="round" stroke-linecap="round">
                  <circle cx="28" cy="22" r="9"/>
                  <path d="M28 7V1M28 43v-6M13 22H7M49 22h-6M17 11l-5-5M39 33l-5-5M39 11l5-5"/>
                  <path d="M18 61 51 39l35 25-33 21z"/>
                  <path d="M29 58 59 79M40 51l31 22M51 44l31 22"/>
                  <path d="M51 85v23M73 83v25M42 108h40"/>
                  <path d="M86 63h11v-18h9"/>
                  <path d="M106 45c0 0 4 3 4 7 0 4-4 6-4 10 0 4 4 6 4 10 0 4-4 7-4 11"/>
                  <path d="M91 76c4 4 9 4 13 0M91 84c4 4 9 4 13 0M91 92c4 4 9 4 13 0"/>
                </g>
              </svg>
              <h3>PROYECTO<br>BOMBEO SOLAR</h3>
              <p>Diseño y dimensionamiento de sistemas fotovoltaicos para bombeo solar.</p>
              <span class="agpe-ring-arrow" aria-hidden="true">→</span>
            </span>
          </button>
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

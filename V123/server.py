import base64, io, json, math, os, re, sqlite3, urllib.parse, urllib.request, subprocess, tempfile, time, shutil, socket, uuid, datetime, random, xml.etree.ElementTree as ET, concurrent.futures
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
MODULES = DATA / 'modules.json'
INVERTERS = DATA / 'inverters.json'
BATTERIES = DATA / 'batteries.json'
COSTS = DATA / 'costs_emergente.json'
SUPPLIER_PRICES = DATA / 'supplier_prices.json'
METERS = DATA / 'meters.json'
VER = '153.26'
ESUNA_DB = DATA / 'esuna.db'
PROJECTS_FILE = DATA / 'projects.json'
PROJECTS_BACKUP = DATA / 'projects.backup.json'
# Online hosting: platforms such as Render inject PORT; localhost remains the fallback for local use.
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', '8765'))

# Default engineering assumption used only to translate annual energy target to DC size.
# It is deliberately exposed in the UI as an editable technical assumption.
DEFAULT_YIELD_KWH_KWP_YEAR = 1500.0
DEFAULT_LOSSES_PCT = 14.0
UPME_SOLAR_LAYER = 'https://geo.upme.gov.co/server/rest/services/Capas_FuenteEnergia_Solar/prediccion_radiacion/FeatureServer/8'
DANE_MUNICIPALITY_LAYER = 'https://portalgis.dane.gov.co/mparcgis/rest/services/Divipola/Serv_DIVIPOLA_MGN_2025/FeatureServer/317'
DIVIPOLA_API = 'https://www.datos.gov.co/resource/gdxc-w37w.json?$limit=5000'
DIVIPOLA_CACHE = DATA / 'divipola_datosgov.json'

PUBLICIDAD_DIR = DATA / 'publicidad_generated'
PUBLICIDAD_DIR.mkdir(exist_ok=True)
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY','').strip()
OPENAI_TEXT_MODEL = os.environ.get('OPENAI_TEXT_MODEL','gpt-5.1').strip()
AI_CONFIG_PATH = Path.home() / '.esun_power_ai_config.json'

def _effective_openai_key():
    if OPENAI_API_KEY: return OPENAI_API_KEY
    try:
        cfg=json.loads(AI_CONFIG_PATH.read_text(encoding='utf-8'))
        return str(cfg.get('openai_api_key','')).strip()
    except Exception:
        return ''

def _save_openai_key(key):
    key=str(key or '').strip()
    if not key: raise ValueError('Debes ingresar una clave de OpenAI.')
    cfg={}
    try:
        cfg=json.loads(AI_CONFIG_PATH.read_text(encoding='utf-8'))
        if not isinstance(cfg,dict): cfg={}
    except Exception: pass
    cfg['openai_api_key']=key
    AI_CONFIG_PATH.write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
    try: os.chmod(AI_CONFIG_PATH,0o600)
    except Exception: pass
    return True

def _clear_openai_key():
    try:
        cfg=json.loads(AI_CONFIG_PATH.read_text(encoding='utf-8'))
        if not isinstance(cfg,dict): cfg={}
    except Exception: cfg={}
    cfg.pop('openai_api_key',None)
    try:
        if cfg: AI_CONFIG_PATH.write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
        elif AI_CONFIG_PATH.exists(): AI_CONFIG_PATH.unlink()
    except Exception: pass

def publicidad_config_status():
    env=bool(OPENAI_API_KEY)
    saved=bool(_effective_openai_key()) and not env
    return {'ok':True,'openai_configured':bool(_effective_openai_key()),'source':'environment' if env else ('server_config' if saved else 'none'),'model':OPENAI_TEXT_MODEL}

def publicidad_test_openai():
    if not _effective_openai_key(): raise RuntimeError('No hay una clave de OpenAI configurada para Esuna.')
    data=_openai_json('https://api.openai.com/v1/responses',{'model':OPENAI_TEXT_MODEL,'input':'Responde únicamente: CONEXIÓN ESUNA OK'},timeout=30)
    txt=''
    for item in data.get('output',[]):
        for c in item.get('content',[]) if isinstance(item,dict) else []:
            if isinstance(c,dict) and c.get('type') in ('output_text','text'): txt+=c.get('text','')
    return {'ok':True,'message':txt.strip() or 'Conexión con OpenAI establecida.','model':OPENAI_TEXT_MODEL}
OPENAI_IMAGE_MODEL = os.environ.get('OPENAI_IMAGE_MODEL','gpt-image-2').strip()

PUBLICIDAD_LOCAL_IDEAS = [
 {'kind':'FLYER COMERCIAL','title':'Energía solar para tu empresa','desc':'Flyer premium B2B mostrando una instalación fotovoltaica comercial, ahorro energético y mensaje de conversión.','prompt':'Diseño publicitario fotorealista premium para E-SUN POWER: empresa colombiana instalando un sistema solar fotovoltaico comercial sobre cubierta industrial al atardecer, módulos monocristalinos negros perfectamente alineados, inversores y tableros visibles de forma técnica pero elegante, ejecutivos revisando el proyecto, estética corporativa negra y amarilla, iluminación cinematográfica, composición vertical para flyer, espacio limpio para titular y CTA, sin texto ilegible.'},
 {'kind':'REDES SOCIALES','title':'Tu techo puede producir energía','desc':'Contenido educativo para Instagram/Facebook que convierte una idea técnica en una pieza visual sencilla.','prompt':'Post vertical para redes sociales de E-SUN POWER explicando visualmente que una cubierta residencial puede producir energía solar, casa moderna colombiana con paneles fotovoltaicos, flujo de energía visible de los paneles hacia inversor y vivienda, estilo editorial tecnológico, negro, amarillo y blanco, fotorealismo cinematográfico, composición limpia, área reservada para copy, sin texto generado dentro de la imagen.'},
 {'kind':'BATERÍAS','title':'Energía cuando el sol no está','desc':'Campaña visual enfocada en almacenamiento y continuidad energética.','prompt':'Campaña publicitaria fotorealista para E-SUN POWER sobre almacenamiento energético: vivienda y pequeña empresa con paneles solares, batería de litio de alta tecnología visible en primer plano, energía fluyendo del sol hacia batería y cargas, noche entrando gradualmente, estética premium tecnológica, negro y amarillo E-SUN, iluminación cinematográfica, formato vertical para redes sociales, espacio para titular.'},
 {'kind':'AGPE','title':'Autogenera tu energía','desc':'Pieza comercial enfocada en autogeneración a pequeña escala y reducción de consumo de red.','prompt':'Publicidad premium de autogeneración solar para E-SUN POWER en Colombia: vivienda y comercio pequeño con sistema fotovoltaico conectado a red, medidor bidireccional sugerido, paneles monocristalinos, visualización elegante del flujo solar y reducción del consumo de red, fotorealismo 8K, estética corporativa negra y amarilla, formato vertical, espacio para copy y llamada a la acción.'},
 {'kind':'GD','title':'Generación distribuida','desc':'Visualización corporativa para proyectos solares de mayor escala y generación distribuida.','prompt':'Key visual corporativo para E-SUN POWER sobre generación distribuida: planta solar fotovoltaica de escala industrial en Colombia, filas extensas de módulos, subestación y líneas eléctricas claramente representadas, ingeniería limpia, topografía tropical, perspectiva aérea cinematográfica, fotorealismo de alta gama, identidad visual negra y amarilla, composición horizontal para publicación profesional, espacio para información técnica.'},
 {'kind':'MARCA','title':'E-SUN POWER · tecnología que genera','desc':'Imagen institucional para posicionamiento de marca.','prompt':'Imagen institucional premium de E-SUN POWER: especialista en soluciones de energía solar caminando frente a una instalación fotovoltaica moderna, arquitectura contemporánea, paneles solares impecables, sensación de ingeniería, confianza e innovación, fotografía publicitaria cinematográfica, negros profundos, acentos amarillos, luz de amanecer, composición editorial de marca, espacio negativo para mensaje corporativo.'}
]

def _openai_json(url, payload, timeout=180):
    key=_effective_openai_key()
    if not key: raise RuntimeError('No hay una clave de OpenAI configurada para Esuna.')
    req=urllib.request.Request(url,data=json.dumps(payload).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def publicidad_ideas(user='',offset=0):
    if not _effective_openai_key():
        n=len(PUBLICIDAD_LOCAL_IDEAS); return {'ok':True,'source':'catalogo_local','ideas':[PUBLICIDAD_LOCAL_IDEAS[(offset+i)%n] for i in range(min(6,n))]}
    prompt=f"""Actúa como Esuna, directora creativa de E-SUN POWER y especialista en diseño gráfico publicitario y sistemas fotovoltaicos. Usuario: {user or 'usuario'}. Genera exactamente 6 ideas NUEVAS de publicaciones, diferentes de las anteriores, integrando diseño visual y conocimiento fotovoltaico. Deben ser escogibles y cada una debe incluir kind, title, desc y prompt. Los prompts deben ser instrucciones visuales detalladas para un generador de imágenes, evitando texto ilegible dentro de la imagen. Responde SOLO JSON válido con una clave ideas que contenga una lista de 6 objetos.""" 
    data=_openai_json('https://api.openai.com/v1/responses',{'model':OPENAI_TEXT_MODEL,'input':prompt},timeout=90)
    txt=''
    for item in data.get('output',[]):
        for c in item.get('content',[]) if isinstance(item,dict) else []:
            if isinstance(c,dict) and c.get('type') in ('output_text','text'): txt+=c.get('text','')
    try:
        obj=json.loads(txt.strip().strip('`').replace('json\n','',1)); ideas=obj.get('ideas',[])
    except Exception: ideas=[]
    if not ideas: raise RuntimeError('Esuna no pudo devolver ideas válidas. Intenta nuevamente.')
    return {'ok':True,'source':'openai','ideas':ideas}

def _google_news_context(query, max_items=8):
    q=urllib.parse.quote((query or 'energía solar fotovoltaica Colombia').strip())
    url=f'https://news.google.com/rss/search?q={q}&hl=es-419&gl=CO&ceid=CO:es-419'
    req=urllib.request.Request(url,headers={'User-Agent':'E-SUN-POWER-Esuna/149.0'})
    with urllib.request.urlopen(req,timeout=12) as r:
        root=ET.fromstring(r.read())
    items=[]
    for it in root.findall('./channel/item')[:max_items]:
        title=(it.findtext('title') or '').strip(); link=(it.findtext('link') or '').strip(); pub=(it.findtext('pubDate') or '').strip(); source=(it.findtext('source') or '').strip()
        if title: items.append({'title':title,'source':source,'date':pub,'url':link})
    return items

def _research_for_message(message):
    text=(message or '').lower()
    triggers=('tendencia','tendencias','actual','actuales','mercado','competencia','competidor','empresa','empresas','redes sociales','instagram','facebook','linkedin','horario','horarios','publicación','publicaciones','colombia','qué están haciendo','que estan haciendo','investiga','investigar')
    if not any(t in text for t in triggers): return [],''
    queries=['mercado energía solar fotovoltaica Colombia','empresas energía solar fotovoltaica Colombia']
    if any(t in text for t in ('redes sociales','instagram','facebook','linkedin','horario','publicación')): queries.append('marketing redes sociales Colombia empresas energía solar')
    if any(t in text for t in ('compet','empresa','qué están haciendo','que estan haciendo')): queries.append('empresa fotovoltaica Colombia paneles solares oferta')
    results=[]
    for q in queries:
        try: results.extend(_google_news_context(q,6))
        except Exception: pass
    seen=set(); unique=[]
    for x in results:
        k=x['title'].lower()
        if k not in seen: seen.add(k); unique.append(x)
    note='Se consultaron titulares públicos recientes para contextualizar esta respuesta; la muestra no es exhaustiva.' if unique else 'No fue posible consultar titulares públicos en este momento; la respuesta se basará en estrategia y conocimiento disponible.'
    return unique[:12],note


def _projects_read():
    """Read the persistent project portfolio stored inside the application data folder."""
    if not PROJECTS_FILE.exists():
        return []
    try:
        raw=json.loads(PROJECTS_FILE.read_text(encoding='utf-8'))
        return raw if isinstance(raw,list) else []
    except Exception:
        # If the active file is damaged, use the last known backup rather than losing the portfolio.
        try:
            raw=json.loads(PROJECTS_BACKUP.read_text(encoding='utf-8'))
            return raw if isinstance(raw,list) else []
        except Exception:
            return []

def _projects_write(projects):
    """Atomically persist the complete project portfolio and keep a previous copy as backup."""
    projects=list(projects or [])
    tmp=PROJECTS_FILE.with_suffix('.tmp')
    payload=json.dumps(projects,ensure_ascii=False,indent=2)
    # Preserve the previous valid version before replacing the active file.
    if PROJECTS_FILE.exists():
        try: shutil.copy2(PROJECTS_FILE, PROJECTS_BACKUP)
        except Exception: pass
    tmp.write_text(payload,encoding='utf-8')
    os.replace(tmp,PROJECTS_FILE)
    return projects

def _project_upsert(project):
    if not isinstance(project,dict) or not project.get('id'):
        raise ValueError('Proyecto inválido.')
    projects=_projects_read()
    pid=str(project['id'])
    idx=next((i for i,x in enumerate(projects) if str(x.get('id',''))==pid),-1)
    if idx>=0: projects[idx]=project
    else: projects.insert(0,project)
    _projects_write(projects)
    return project

def _project_delete(pid):
    pid=str(pid or '')
    projects=_projects_read()
    new=[x for x in projects if str(x.get('id',''))!=pid]
    if len(new)==len(projects):
        return False
    _projects_write(new)
    return True

def _esuna_db():
    con=sqlite3.connect(ESUNA_DB)
    con.row_factory=sqlite3.Row
    return con

def _esuna_tokens(text):
    import unicodedata
    text=(text or '').lower()
    text=''.join(c for c in unicodedata.normalize('NFD',text) if unicodedata.category(c)!='Mn')
    stop={'de','la','el','los','las','un','una','unos','unas','que','para','por','con','del','al','en','y','o','es','como','mi','tu','su','se','me','te','lo','le','qué','cual','cuales','donde','hay','puede','pueden'}
    return [x for x in re.findall(r'[a-z0-9][a-z0-9+&.-]{1,}',text) if len(x)>=3 and x not in stop]

def _esuna_expand(text, con):
    toks=_esuna_tokens(text); out=list(toks)
    for t in toks:
        r=con.execute('SELECT expansion FROM synonyms WHERE term=?',(t,)).fetchone()
        if r: out.extend(_esuna_tokens(r['expansion']))
    return list(dict.fromkeys(out))

def _esuna_intent(text):
    t=' '.join(_esuna_tokens(text))
    if any(x in t for x in ('campana','anuncio','publicidad','copy','contenido','instagram','facebook','linkedin','whatsapp')): return 'MARKETING'
    if any(x in t for x in ('bateria','baterias','bess','saeb','almacenamiento')): return 'BESS'
    if any(x in t for x in ('norma','retie','creg','upme','regulacion','requisito')): return 'NORMATIVA'
    if any(x in t for x in ('competencia','competidor','comparar','comparacion')): return 'COMPETENCIA'
    if any(x in t for x in ('mercado','tendencia','tendencias','colombia','oportunidad','segmento')): return 'MERCADO'
    if any(x in t for x in ('panel','modulo','inversor','fabricante','producto')): return 'PRODUCTO'
    if any(x in t for x in ('venta','vender','cliente','lead','prospecto','objecion','cierre')): return 'VENTAS'
    return 'GENERAL'

def _esuna_search(text, limit=8):
    con=_esuna_db(); toks=_esuna_expand(text,con)
    if not toks: con.close(); return []
    q=' OR '.join('"'+t.replace('"','')+'"' for t in toks[:24])
    rows=[]
    try:
        rows=con.execute("""SELECT k.id,k.title,k.content,k.tags,k.source_id,s.name source_name,s.url,s.authority,c.name category,
                            bm25(knowledge_fts,5.0,1.0,1.5) rank
                            FROM knowledge_fts f JOIN knowledge k ON k.id=f.rowid
                            JOIN sources s ON s.id=k.source_id JOIN categories c ON c.id=k.category_id
                            WHERE knowledge_fts MATCH ? ORDER BY rank LIMIT ?""",(q,limit*3)).fetchall()
    except Exception:
        rows=[]
    lower=(text or '').lower(); exact=[]
    for r in con.execute('SELECT k.id,k.title,k.content,k.tags,k.source_id,s.name source_name,s.url,s.authority,c.name category FROM knowledge k JOIN sources s ON s.id=k.source_id JOIN categories c ON c.id=k.category_id').fetchall():
        if r['source_name'].lower() in lower or any(tok in r['source_name'].lower() for tok in toks if len(tok)>3): exact.append(r)
    merged={r['id']:r for r in rows}
    for r in exact: merged[r['id']]=r
    out=list(merged.values())
    def score(r):
        txt=' '.join([r['title'] or '',r['content'] or '',r['tags'] or '',r['source_name'] or '']).lower()
        hits=sum(1 for t in toks if t in txt)
        name_low=(r['source_name'] or '').lower(); exact_name=any(tok in name_low.split() for tok in toks if len(tok)>3); return hits*3 + float(r['authority'] or .5)*4 + (30 if name_low in lower else (18 if exact_name else 0))
    out.sort(key=score,reverse=True)
    con.close(); return out[:limit]

def _esuna_fetch_source(source_row):
    url=source_row['url'] if isinstance(source_row,sqlite3.Row) else source_row.get('url')
    if not url or not url.startswith(('http://','https://')): return ''
    try:
        import html as _html
        req=urllib.request.Request(url,headers={'User-Agent':'E-SUN-POWER-Esuna-Knowledge/150.0'})
        with urllib.request.urlopen(req,timeout=4) as r: raw=r.read(700000).decode('utf-8','ignore')
        title=''; m=re.search(r'<title[^>]*>(.*?)</title>',raw,re.I|re.S)
        if m: title=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',m.group(1))).strip()
        raw=re.sub(r'<script[^>]*>.*?</script>',' ',raw,flags=re.I|re.S); raw=re.sub(r'<style[^>]*>.*?</style>',' ',raw,flags=re.I|re.S)
        text=re.sub(r'<[^>]+>',' ',raw); text=_html.unescape(text); text=re.sub(r'\s+',' ',text).strip()
        if len(text)<100: return ''
        return (title+' — '+text)[:12000]
    except Exception: return ''

def _esuna_refresh_relevant(text, rows, max_sources=3):
    con=_esuna_db(); refreshed=[]; seen=set()
    for r in rows:
        sid=r['source_id']
        if sid in seen: continue
        seen.add(sid); src=con.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone()
        if not src or src['source_type'] not in ('COMPETIDOR','FABRICANTE','REFERENTE_MARKETING'): continue
        body=_esuna_fetch_source(src)
        if not body: continue
        con.execute('UPDATE knowledge SET content=? WHERE id=(SELECT id FROM knowledge WHERE source_id=? ORDER BY id LIMIT 1)',(body,sid))
        con.execute('UPDATE sources SET last_checked=CURRENT_TIMESTAMP WHERE id=?',(sid,)); refreshed.append(src['name'])
        if len(refreshed)>=max_sources: break
    con.commit(); con.close(); return refreshed

def _esuna_status():
    con=_esuna_db()
    vals={'sources':con.execute('SELECT COUNT(*) FROM sources').fetchone()[0],'knowledge':con.execute('SELECT COUNT(*) FROM knowledge').fetchone()[0],'categories':con.execute('SELECT COUNT(*) FROM categories').fetchone()[0],'rules':con.execute('SELECT COUNT(*) FROM rules WHERE active=1').fetchone()[0],'competitors':con.execute("SELECT COUNT(*) FROM sources WHERE source_type='COMPETIDOR'").fetchone()[0],'manufacturers':con.execute("SELECT COUNT(*) FROM sources WHERE source_type='FABRICANTE'").fetchone()[0]}
    con.close(); return {'ok':True,'version':'152.0','mode':'LOCAL_KNOWLEDGE','ai_required':False,**vals}

def _esuna_format_sources(rows):
    seen=set(); out=[]
    for r in rows:
        if r['source_name'] in seen: continue
        seen.add(r['source_name']); out.append(f"• {r['source_name']} — {r['category']}")
    return '\n'.join(out[:6])

def _esuna_world_news(max_items=18):
    """Consulta señales públicas recientes del mercado FV en paralelo. No genera texto con IA."""
    queries=[
        ('COLOMBIA','energia solar fotovoltaica Colombia baterias almacenamiento regulacion', 'es-419','CO','CO:es-419'),
        ('MUNDO FV','solar photovoltaic market battery storage 2026', 'en','US','US:en'),
        ('TECNOLOGIA','solar PV TOPCon HJT back contact battery storage technology 2026', 'en','US','US:en'),
        ('MERCADO','solar energy commercial industrial C&I battery storage 2026', 'en','US','US:en'),
        ('MOVILIDAD','solar EV charging energy storage 2026', 'en','US','US:en'),
    ]
    def fetch(spec):
        label,q,hl,gl,ceid=spec; items=[]
        try:
            url=f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={hl}&gl={gl}&ceid={ceid}"
            req=urllib.request.Request(url,headers={'User-Agent':'E-SUN-POWER-ESUNA/151.0'})
            with urllib.request.urlopen(req,timeout=4) as r: root=ET.fromstring(r.read())
            for it in root.findall('./channel/item')[:6]:
                title=(it.findtext('title') or '').strip(); link=(it.findtext('link') or '').strip(); pub=(it.findtext('pubDate') or '').strip(); source=(it.findtext('source') or '').strip()
                if title: items.append({'region':label,'title':title,'source':source or 'Google News','date':pub,'url':link})
        except Exception: pass
        return items
    items=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        for group in ex.map(fetch,queries): items.extend(group)
    seen=set(); unique=[]
    for x in items:
        k=re.sub(r'\s+',' ',x['title'].lower())
        if k in seen: continue
        seen.add(k); unique.append(x)
    return unique[:max_items]

def _esuna_news_tags(news):
    text=' '.join((x.get('title','') for x in news)).lower()
    tags=[]
    if any(k in text for k in ('battery','batteries','storage','almacenamiento','bess','saeb')): tags.append('ALMACENAMIENTO')
    if any(k in text for k in ('topcon','hjt','back contact','bc ','perovskite','tandem','efficien')): tags.append('TECNOLOGÍA FV')
    if any(k in text for k in ('ev ','vehicle','charging','cargadores','movilidad')): tags.append('MOVILIDAD')
    if any(k in text for k in ('grid','transmission','curtail','red eléctrica','transmisión')): tags.append('RED Y FLEXIBILIDAD')
    if any(k in text for k in ('colombia','minenergia','creg','regulation','regulación')): tags.append('REGULACIÓN / COLOMBIA')
    if any(k in text for k in ('commercial','industrial','c&i','business','empresas')): tags.append('C&I')
    return tags

def _esuna_build_campaign(opportunity, rows, news):
    """Construye un plan de campaña accionable combinando marketing, ventas, FV y señales actuales."""
    title=(opportunity.get('title') or '').lower()
    kind=(opportunity.get('kind') or '').lower()
    if 'sol' in title or 'aliado' in title or 'generación solar' in title or 'generacion solar' in title:
        campaign_name='El sol, tu mejor aliado'
        central='El sol no es solo una fuente de energía: es un activo que puede ayudar a controlar el costo energético cuando se convierte en un sistema bien diseñado.'
        duration='5 días'
    elif 'bess' in kind or 'almacenamiento' in title or 'energía gestionable' in title:
        campaign_name='Cuando el sol se oculta, la energía continúa'
        central='La energía solar se vuelve más útil cuando el sistema puede producir, almacenar y gestionar energía según la necesidad del cliente.'
        duration='7 días'
    elif 'factura' in title or 'c&i' in kind:
        campaign_name='Tu factura está diciendo algo'
        central='La factura eléctrica puede ser el punto de partida para descubrir una oportunidad de eficiencia, generación y gestión energética.'
        duration='5 días'
    elif 'compet' in kind or 'compar' in kind:
        campaign_name='No compares paneles. Compara sistemas.'
        central='La decisión solar debe evaluarse por diseño, ingeniería, equipos, protecciones, garantías, desempeño y acompañamiento; no solo por precio.'
        duration='5 días'
    elif 'tecnolog' in kind:
        campaign_name='El futuro solar ya está aquí'
        central='Las nuevas arquitecturas de módulos, almacenamiento y gestión energética están cambiando lo que una solución fotovoltaica puede hacer.'
        duration='7 días'
    elif 'hotel' in title or 'turismo' in kind:
        campaign_name='Tu hotel también puede controlar su energía'
        central='El sector hotelero puede convertir una parte de su consumo energético en una estrategia de control de costos, continuidad y sostenibilidad.'
        duration='5 días'
    elif 'arquitect' in kind or 'alianzas' in kind:
        campaign_name='Diseñar energía desde el proyecto'
        central='La energía solar genera más valor cuando se integra desde la etapa de diseño y no cuando el proyecto ya está construido.'
        duration='5 días'
    elif 'postventa' in kind:
        campaign_name='Tu sistema solar no termina en la instalación'
        central='La postventa, el monitoreo y la optimización pueden convertirse en una relación continua con el cliente.'
        duration='7 días'
    else:
        campaign_name='E-SUN POWER · La energía se diseña'
        central='Transformar conocimiento técnico en una propuesta comercial que eduque, genere confianza y conduzca a una conversación de diagnóstico.'
        duration='5 días'

    # El motor usa varias disciplinas a la vez: marketing + ventas + mercado + competencia + producto + regulación.
    categories=[]; sources=[]
    for r in rows:
        cat=r['category'] if isinstance(r,sqlite3.Row) else r.get('category')
        src=r['source_name'] if isinstance(r,sqlite3.Row) else r.get('source_name')
        if cat and cat not in categories: categories.append(cat)
        if src and src not in sources: sources.append(src)
    text=' '.join([(r['title'] if isinstance(r,sqlite3.Row) else r.get('title',''))+' '+(r['content'] if isinstance(r,sqlite3.Row) else r.get('content','')) for r in rows]).lower()
    is_bess=any(k in title+' '+kind+' '+text for k in ('bess','saeb','almacenamiento','bater'))
    is_ci=any(k in title+' '+kind+' '+text for k in ('c&i','comercial','industrial','empresa','hotel'))
    is_ev=any(k in title+' '+kind+' '+text for k in ('movilidad','ev ','cargador','vehículo'))
    audience=opportunity.get('audience') or ('Empresas y tomadores de decisión' if is_ci else 'Clientes residenciales y empresariales con interés en energía solar')
    channels=['Instagram','Facebook','LinkedIn','WhatsApp Business']
    if is_ci: channels=['LinkedIn','Instagram','WhatsApp Business','Email comercial']
    if is_ev: channels.append('Contenido especializado de movilidad eléctrica')
    if 'arquitect' in kind: channels=['LinkedIn','Instagram','Email comercial','Networking / alianzas']
    if is_bess: channels=['LinkedIn','Instagram','WhatsApp Business','Email comercial']

    days=[
      {'day':'DÍA 1','objective':'Captar atención y cambiar la forma de pensar el problema.','content':'Publicar la pieza principal de campaña con una idea simple, visual y memorable. Abrir una pregunta que conecte energía con la vida o el negocio del cliente.','format':'Reel de 20–30 s + publicación estática + Stories.','visual':'Imagen fotorealista/cinematográfica del sol integrado con una solución FV E-SUN POWER; logo visible y espacio limpio para el mensaje.','copy':central,'cta':'Descubre qué puede hacer la energía solar por tu consumo.','sales_action':'Responder comentarios y derivar interesados a WhatsApp con una pregunta de diagnóstico.'},
      {'day':'DÍA 2','objective':'Educar y demostrar conocimiento.','content':'Explicar el problema con datos sencillos: cómo se consume energía, cuándo produce el sol y por qué el diseño importa.','format':'Carrusel de 5–7 láminas + Stories con encuesta.','visual':'Diagrama simple de consumo vs. generación, equipos y flujo de energía; estética técnica premium.','copy':'No se trata solo de instalar paneles. Se trata de diseñar una solución que tenga sentido para tu consumo.','cta':'¿Quieres saber qué solución tendría sentido para tu caso?','sales_action':'Guardar respuestas de la encuesta y clasificar leads por interés.'},
      {'day':'DÍA 3','objective':'Convertir educación en deseo y confianza.','content':'Mostrar un caso, escenario o comparación antes/después. Explicar qué se decidió y por qué.','format':'Video corto o carrusel comparativo.','visual':'Antes/después o escenario de empresa/hogar con paneles, inversor, protecciones y/o batería según la oportunidad.','copy':'Una buena solución energética empieza antes de escoger el panel.','cta':'Solicita un diagnóstico de tu proyecto.','sales_action':'Contactar de forma directa a los leads calificados y solicitar factura/datos básicos.'},
      {'day':'DÍA 4','objective':'Vencer objeciones.','content':'Responder las tres objeciones más frecuentes para esta oportunidad: precio, confiabilidad y retorno/beneficio.','format':'Flyer + Reel FAQ + Stories de preguntas.','visual':'Pieza limpia con tres objeciones y tres respuestas; incluir marca, evidencia y lenguaje verificable.','copy':'Antes de comparar precios, compara qué incluye realmente cada solución.','cta':'Compara tu propuesta con criterio técnico y comercial.','sales_action':'Enviar checklist o guía de evaluación a prospectos.'},
      {'day':'DÍA 5','objective':'Cerrar la campaña con una acción comercial concreta.','content':'Recapitular la idea central, presentar la oferta de entrada y crear urgencia legítima para conversar.','format':'Flyer comercial + Reel final + WhatsApp Status + publicación.','visual':'Hero visual de E-SUN POWER con sol, sistema FV y cliente/negocio; CTA dominante.','copy':'El siguiente paso no es comprar paneles. Es conocer qué solución necesita tu energía.','cta':'Agenda un diagnóstico con E-SUN POWER.','sales_action':'Seguimiento individual de todos los leads, registrar fuente, interés y siguiente paso.'}
    ]
    if duration=='7 días':
        days += [
          {'day':'DÍA 6','objective':'Profundizar autoridad y prueba social.','content':'Publicar una pieza técnica avanzada, testimonio o análisis de una tecnología/escenario real.','format':'Carrusel técnico + LinkedIn.','visual':'Detalle de arquitectura del sistema, datos y componentes relevantes.','copy':'La tecnología solo importa cuando resuelve un problema real.','cta':'Hablemos de tu necesidad energética.','sales_action':'Reactivar prospectos que interactuaron durante los primeros cinco días.'},
          {'day':'DÍA 7','objective':'Medir, optimizar y convertir.','content':'Publicar cierre con los aprendizajes de la campaña y CTA final. Revisar métricas y clasificar oportunidades.','format':'Reel/resumen + Stories + WhatsApp.','visual':'Resumen visual de la campaña y resultados/beneficios sin inventar cifras.','copy':'Tu energía merece una estrategia, no una compra improvisada.','cta':'Solicita tu diagnóstico.','sales_action':'Reunión de cierre y creación de propuestas para los leads calificados.'}
        ]

    assets=[
      '1 pieza hero principal para redes',
      '1 Reel de 20–30 segundos',
      '1 carrusel educativo de 5–7 láminas',
      '1 flyer comercial para WhatsApp',
      '1 set de 3–5 Stories',
      '1 pieza comparativa/objeciones',
      '1 pieza final con CTA a diagnóstico',
      '1 guion corto para el equipo comercial',
    ]
    if is_bess: assets.insert(4,'1 infografía FV + BESS mostrando producción, almacenamiento y uso de energía')
    if is_ev: assets.insert(5,'1 pieza sobre solar + almacenamiento + movilidad eléctrica')
    if 'compet' in kind or 'compar' in kind: assets.insert(4,'1 checklist “Cómo comparar una propuesta solar”')
    creative_briefs=[
      {'piece':'PIEZA HERO','headline':central[:90],'visual':'Composición fotorealista premium con sol, sistema fotovoltaico y contexto del cliente; iluminación cinematográfica; identidad E-SUN POWER.','copy_direction':'Titular corto + beneficio + CTA; dejar zona limpia para texto y utilizar el logo oficial E-SUN POWER.'},
      {'piece':'REEL','headline':'Una idea que se entienda en 3 segundos','visual':'Secuencia: problema energético → sol/FV → sistema diseñado → llamada a la acción.','copy_direction':'Guion de 20–30 s con gancho inicial, explicación simple, prueba/criterio y CTA a diagnóstico.'},
      {'piece':'CARRUSEL','headline':'5 cosas que debes entender antes de tomar una decisión solar','visual':'Diseño editorial técnico, una idea por lámina, iconografía limpia y datos solo cuando estén sustentados.','copy_direction':'Lámina 1: gancho; 2–5: educación; última: CTA a diagnóstico.'},
      {'piece':'FLYER WHATSAPP','headline':'Convierte el sol en una estrategia para tu energía','visual':'Formato vertical, lectura inmediata en móvil, imagen hero y CTA dominante a WhatsApp.','copy_direction':'Problema → beneficio → qué incluye el diagnóstico → CTA.'},
      {'piece':'PUBLICIDAD DIGITAL','headline':'No compres una solución genérica','visual':'Anuncio de alto contraste con una sola idea, rostro/escena de cliente y sistema FV según segmento.','copy_direction':'Dos versiones para prueba A/B: enfoque ahorro/control vs. enfoque ingeniería/confianza.'}
    ]

    paid={
      'objective':'Generación de demanda y conversaciones calificadas, no solamente alcance.',
      'audience':audience,
      'structure':['Campaña de reconocimiento/educación para audiencia fría.','Campaña de interacción/video viewers para crear audiencia tibia.','Campaña de leads/WhatsApp para personas que demostraron intención.'],
      'budget_rule':'Distribuir el presupuesto por etapas y optimizar hacia conversaciones o leads calificados. No fijar una cifra sin conocer presupuesto, zona y ticket objetivo.',
      'creative_test':'Probar al menos dos ganchos: beneficio económico/control energético vs. ingeniería/confianza.'
    }
    sales=[
      'Registrar cada lead con fuente, campaña, segmento y nivel de intención.',
      'Responder rápidamente con una pregunta de diagnóstico, no con un catálogo genérico.',
      'Solicitar los datos mínimos para evaluar el proyecto antes de prometer ahorro.',
      'Convertir el diagnóstico en propuesta técnica-comercial con supuestos explícitos.',
      'Programar seguimiento a 24 h, 72 h y cierre de campaña.'
    ]
    kpis=['Alcance e impresiones','Retención de video','Interacciones y compartidos','Clics/visitas a WhatsApp','Leads generados','Leads calificados','Diagnósticos agendados','Propuestas emitidas','Tasa de conversión','Costo por lead calificado']
    if is_bess: kpis += ['Interés específico en almacenamiento','Solicitudes de evaluación FV + BESS']
    if is_ci: kpis += ['Empresas contactadas','Facturas/datos recibidos','Reuniones B2B']
    return {
      'campaign_name':campaign_name,'duration':duration,'campaign_type':'Campaña comercial educativa · generación de demanda','central_message':central,
      'campaign_objective':opportunity.get('objective',''),'specific_goals':['Generar atención en un problema energético concreto.','Educar sin saturar con tecnicismos.','Construir autoridad y diferenciación.','Convertir interacción en diagnóstico.','Entregar leads calificados al proceso comercial.'],
      'audience':audience,'customer_insight':opportunity.get('customer_problem',''),'strategic_idea':opportunity.get('positioning',''),'value_proposition':opportunity.get('value_proposition',''),'offer':opportunity.get('offer',''),'tone':'Técnico, claro, premium, educativo y comercial; sin exageraciones ni promesas no verificadas.','channels':channels,
      'actions':days,'pieces_to_create':assets,'creative_briefs':creative_briefs,'paid_media':paid,'sales_plan':sales,'kpis':kpis,
      'measurement_plan':'Medir diariamente contenido y demanda; al cierre, separar métricas de vanidad (alcance/interacciones) de métricas de negocio (leads calificados, diagnósticos, propuestas y ventas).',
      'implementation_order':['Definir oferta y CTA.','Crear concepto visual y copy maestro.','Producir las piezas del DÍA 1–5/7.','Programar publicaciones.','Activar pauta si aplica.','Responder y clasificar leads diariamente.','Cerrar con informe de resultados y decisiones para la siguiente campaña.'],
      'knowledge_mix':categories[:14], 'knowledge_sources':sources[:14],
      'fresh_signals':news[:8],
      'guardrails':opportunity.get('guardrails','No prometer ahorros, retornos, financiación, disponibilidad de equipos o cumplimiento normativo sin sustento y datos del proyecto.'),
    }

def _esuna_strategy(opportunity, rows, news):
    """Amplía una oportunidad con un informe de campaña accionable, usando conocimiento interno + señales recientes."""
    source_names=[]
    for r in rows:
        n=r['source_name'] if isinstance(r,sqlite3.Row) else r.get('source_name')
        if n and n not in source_names: source_names.append(n)
    fresh=[f"{n['title']} — {n['source']}" for n in news[:8]]
    campaign=_esuna_build_campaign(opportunity, rows, news)
    return {
        'opportunity': opportunity['title'],'why_now': opportunity['why_now'],'objective': opportunity['objective'],'audience': opportunity['audience'],
        'customer_problem': opportunity['customer_problem'],'positioning': opportunity['positioning'],'value_proposition': opportunity['value_proposition'],
        'offer': opportunity['offer'],'funnel': opportunity['funnel'],'content_pillars': opportunity['content_pillars'],'campaign_sequence': opportunity['campaign_sequence'],
        'sales_route': opportunity['sales_route'],'competitive_angle': opportunity['competitive_angle'],'cta': opportunity['cta'],'kpis': opportunity['kpis'],
        'next_7_days': opportunity['next_7_days'],'guardrails': opportunity['guardrails'],'knowledge_sources': source_names[:10],'fresh_signals': fresh,
        'campaign':campaign
    }

def _esuna_proactive_opportunities(limit=8, seed=None, exclude_ids=None, exclude_titles=None):
    """Motor de oportunidades ESUNA: combina segmentos, soluciones FV, marketing, competencia y señales recientes.
    Cada actualización usa una semilla distinta y excluye las oportunidades que ya estaban visibles.
    """
    con=_esuna_db(); con.row_factory=sqlite3.Row
    def bycat(names, n=30):
        ph=','.join('?'*len(names))
        return con.execute(f"""SELECT k.id,k.title,k.content,k.tags,s.name source_name,s.url,s.authority,c.name category
                              FROM knowledge k JOIN sources s ON s.id=k.source_id JOIN categories c ON c.id=k.category_id
                              WHERE c.name IN ({ph}) AND k.status='ACTIVE' ORDER BY s.authority DESC,k.id DESC LIMIT ?""",tuple(names)+(n,)).fetchall()
    market=bycat(['MERCADO COLOMBIANO','AGPE','GENERACIÓN DISTRIBUIDA','AUTOGENERACIÓN REMOTA','COMUNIDADES ENERGÉTICAS'],28)
    comp=bycat(['COMPETENCIA'],24)
    tech=bycat(['BESS / SAEB','SISTEMAS HÍBRIDOS','TECNOLOGÍAS Y OPORTUNIDADES','MOVILIDAD ELÉCTRICA','C&I','EMS','ZNI','MICROREDES','AGROINDUSTRIA'],36)
    mkt=bycat(['MARKETING ESTRATÉGICO','NEUROMARKETING','BRANDING','COPYWRITING','REDES SOCIALES','PUBLICIDAD DIGITAL','VENTAS'],28)
    prod=bycat(['PRODUCTOS FV','FABRICANTES','PROVEEDORES COLOMBIA'],24)
    allrows=market+comp+tech+mkt+prod
    con.close()
    news=_esuna_world_news(18)
    tags=_esuna_news_tags(news)
    seed_text=str(seed or int(time.time()*1000))
    rng=random.Random(seed_text)
    excluded=set(str(x) for x in (exclude_ids or []) if x)
    excluded_titles=set(str(x).strip().lower() for x in (exclude_titles or []) if str(x).strip())

    def pick(rows, terms=(), default=None):
        if not rows: return default
        pool=[]
        for r in rows:
            txt=((r['title'] or '')+' '+(r['tags'] or '')+' '+(r['content'] or '')).lower()
            if not terms or any(t in txt for t in terms): pool.append(r)
        return rng.choice(pool or rows)
    def source_names(*groups):
        vals=[]
        for g in groups:
            if not g: continue
            vals.append(g['source_name'])
        # add additional cross-domain sources so ESUNA does not reason from one source only
        candidates=[pick(mkt),pick(market),pick(tech),pick(comp),pick(prod)]
        for r in candidates:
            if r and r['source_name'] not in vals: vals.append(r['source_name'])
        return list(dict.fromkeys(vals))[:7]
    def make_id(slug):
        import hashlib
        return 'GEN-'+hashlib.sha1((slug+'|'+seed_text).encode()).hexdigest()[:10].upper()
    def opp(slug, kind, title, desc, why, objective, audience, problem, positioning, value, offer, funnel, pillars, sequence, sales, angle, cta, kpis, next7, guardrails, relevant_terms=()):
        a=pick(tech,relevant_terms); b=pick(market,relevant_terms); c=pick(mkt,('posicion','copy','contenido','neuromarketing','embudo')); d=pick(comp,('diferenc','servicio','ahorro','cotiz')); e=pick(prod,('topcon','bateria','invers','modul','storage','deye','longi','jinko'))
        return {'id':make_id(slug),'kind':kind,'title':title,'desc':desc,'why_now':why,'objective':objective,'audience':audience,'customer_problem':problem,'positioning':positioning,'value_proposition':value,'offer':offer,'funnel':funnel,'content_pillars':pillars,'campaign_sequence':sequence,'sales_route':sales,'competitive_angle':angle,'cta':cta,'kpis':kpis,'next_7_days':next7,'guardrails':guardrails,'sources':source_names(a,b,c,d,e),'news_tags':tags,'_signal_terms':relevant_terms}

    specs=[]
    specs.append(opp('sol-el-mejor-aliado','CAMPAÑA EDUCATIVA','El sol, tu mejor aliado.','Convertir el sol en un aliado cotidiano: pasar de mostrar paneles a explicar cómo la energía solar puede apoyar el ahorro y la gestión energética.','El mercado necesita mensajes simples que conecten energía solar con una necesidad concreta; una idea fácil de recordar puede abrir la puerta al diagnóstico técnico.','Dar a conocer la importancia del sol como recurso energético y llevar la conversación hacia una evaluación real del consumo.','Hogares, comercios y pequeñas empresas que pagan energía y aún ven la solar como una compra técnica.','El cliente sabe que existe la energía solar, pero no siempre entiende cómo se relaciona con su consumo, su factura y sus decisiones energéticas.','El sol no es solo una fuente de luz: puede convertirse en un aliado energético cuando el sistema está bien diseñado.','E-SUN POWER transforma el recurso solar en una solución diseñada alrededor del consumo y del objetivo del cliente.','Diagnóstico solar inicial a partir de consumo/factura y características del inmueble.','Contenido educativo → interacción → diagnóstico → revisión de datos → propuesta → seguimiento.',['El sol como recurso energético','De la radiación al consumo útil','Qué hace que un sistema sea bien diseñado','Ahorro y energía: qué debe comprobarse antes de prometer'],['Día 1: Reel “El sol está ahí. ¿Por qué no usarlo a tu favor?” + pieza principal.','Día 2: Carrusel “Cómo el sol se convierte en energía útil”.','Día 3: Flyer “Tu techo puede trabajar para ti”.','Día 4: Historia con pregunta + encuesta sobre factura/consumo.','Día 5: CTA “Evalúa tu oportunidad solar”.'],'WhatsApp con diagnóstico guiado; solicitar factura/datos antes de hacer afirmaciones económicas.','No competir con mensajes genéricos de paneles; apropiarse del concepto de “sol como aliado” y demostrarlo con ingeniería.','Descubre cómo convertir el sol en un aliado energético.','Alcance, reproducciones, interacciones, leads, diagnósticos y propuestas.','Crear concepto visual, Reel, carrusel, flyer, stories y secuencia de WhatsApp.','No prometer un porcentaje de ahorro sin datos del proyecto ni presentar una cifra como universal.',('solar','ahorro','marketing')))
    specs.append(opp('factura-puerta-entrada','C&I · CAPTACIÓN','Tu factura tiene una historia. ESUNA sabe leerla.','Usar la factura eléctrica como puerta de entrada comercial para descubrir oportunidades FV, BESS o gestión energética.','Las empresas necesitan claridad antes de comprar; la factura es un activo comercial para iniciar una conversación consultiva.','Generar leads empresariales calificados y convertir una factura en un diagnóstico energético.','Comercio, hoteles, restaurantes, oficinas, bodegas e industria.','El empresario paga energía, pero no sabe qué variables determinan si una solución solar o de almacenamiento tiene sentido.','No empieces por los paneles. Empieza por entender tu energía.','E-SUN POWER convierte datos de consumo en una primera hipótesis de solución y luego la valida con ingeniería.','Diagnóstico energético inicial con factura + datos básicos + llamada de descubrimiento.','Anuncio → WhatsApp/formulario → factura → lectura inicial → reunión → propuesta.',['Lectura de factura','Perfil de consumo','Errores al cotizar C&I','Solar vs. almacenamiento vs. solución híbrida'],['Día 1: anuncio “¿Sabes qué te está diciendo tu factura?”.','Día 2: carrusel de 4 datos clave.','Día 3: ejemplo sectorial.','Día 4: objeciones de inversión.','Día 5: CTA de diagnóstico.'],'WhatsApp + checklist comercial + reunión técnica-comercial.','Competir por diagnóstico y claridad, no por precio por kWp.','Envíanos tu factura y revisamos tu oportunidad energética.','Costo por lead, facturas recibidas, diagnósticos, reuniones, propuestas y conversión.','Crear tres anuncios sectoriales, checklist, guion de WhatsApp y plantilla de diagnóstico.','Una factura aislada no basta para concluir ahorro, retorno o dimensionamiento definitivo.',('c&i','comercial','factura')))
    specs.append(opp('energia-gestionable','BESS · NUEVA LÍNEA','El sol produce. Tu sistema decide cuándo utilizar la energía.','Posicionar FV + BESS como una arquitectura energética que permite aprovechar mejor la energía y abordar respaldo, continuidad y gestión.','El almacenamiento está pasando de ser un complemento técnico a una conversación comercial relevante en Colombia y en el mercado global.','Abrir una línea de ventas FV + BESS basada en diagnóstico y no en vender baterías como producto aislado.','Empresas con cargas críticas, consumo nocturno, interés en respaldo o necesidad de gestión energética.','La producción solar y el momento de consumo no siempre coinciden.','Más que almacenar energía: diseñar cuándo y cómo utilizarla.','E-SUN POWER integra generación, almacenamiento y gestión según el perfil real del cliente.','Diagnóstico FV + BESS con perfil horario, criticidad y escenario de operación.','Contenido → diagnóstico → perfil de carga → arquitectura conceptual → propuesta → cierre.',['Por qué almacenar','FV + BESS','Continuidad y cargas críticas','Cómo decidir capacidad y potencia'],['Día 1: Reel “El sol produce de día…”.','Día 2: infografía de flujo energético.','Día 3: caso de uso.','Día 4: comparación FV vs FV+BESS.','Día 5: CTA de evaluación.'],'Capturar factura/perfil horario y cargas críticas; luego dimensionar técnicamente.','Mover la conversación de precio por kWp a arquitectura energética, operación y continuidad.','Evalúa si tu empresa necesita almacenamiento.','Leads BESS, diagnósticos, propuestas híbridas, ticket y conversión.','Crear línea gráfica BESS, caso de uso, comparativo, landing/WhatsApp y guion comercial.','No prometer autonomía, retorno o ahorro sin datos eléctricos y condiciones de operación.',('bess','saeb','almacenamiento')))
    specs.append(opp('hotel-genera','TURISMO · SEGMENTACIÓN','Hoteles que generan: el sol también trabaja mientras el huésped descansa.','Crear una campaña vertical para hoteles y turismo que conecte consumo energético, experiencia del huésped y sostenibilidad.','Hoteles tienen perfiles de consumo particulares y necesitan soluciones que no comprometan operación ni imagen.','Construir un segmento comercial específico para turismo y hospitality.','Hoteles, hostales, resorts, restaurantes turísticos y operadores de alojamiento.','El hotel necesita controlar costos y continuidad sin convertir la infraestructura energética en una carga operativa.','Energía solar diseñada para la operación real del hotel.','Diseño técnico que considera ocupación, cargas, horarios y espacio disponible.','Diagnóstico energético para hospitality + visita técnica.','Contenido sectorial → caso → diagnóstico → visita → propuesta.',['Consumo hotelero','Cubiertas y arquitectura','Solar + BESS','Sostenibilidad que se puede demostrar'],['Día 1: pieza “El hotel también puede generar”.','Día 2: Reel de recorrido energético.','Día 3: carrusel de cargas hoteleras.','Día 4: caso/escenario.','Día 5: CTA para diagnóstico.'],'Prospección directa + LinkedIn/Instagram + WhatsApp comercial.','Hablar el idioma del negocio hotelero, no el del catálogo de equipos.','Revisemos la oportunidad energética de tu hotel.','Leads por segmento, reuniones, diagnósticos, propuestas y ventas.','Crear base de 30 hoteles objetivo, campaña visual, guion comercial y oferta de diagnóstico.','No presentar retornos genéricos ni asumir horarios de operación.',('hotel','turismo','c&i')))
    specs.append(opp('sol-carga-futuro','MOVILIDAD · FV','Carga el futuro con energía solar.','Unir movilidad eléctrica, generación solar y almacenamiento en una propuesta de ecosistema energético.','La electrificación del transporte abre una nueva carga eléctrica que puede convertirse en oportunidad comercial para FV y gestión.','Generar demanda de soluciones solares para vehículos eléctricos y puntos de carga.','Empresas con flotas, parqueaderos, hoteles, conjuntos y usuarios con vehículos eléctricos.','El cliente agrega consumo por movilidad y necesita entender cómo gestionarlo.','Tu vehículo eléctrico también puede formar parte de tu sistema energético.','E-SUN POWER diseña generación y gestión alrededor del nuevo perfil de carga.','Evaluación FV + carga EV + posibilidad de almacenamiento.','Contenido → calculadora/diagnóstico → perfil de carga → propuesta.',['Movilidad eléctrica','Carga solar','Gestión de demanda','FV + almacenamiento'],['Día 1: Reel “¿De dónde sale la energía de tu próximo viaje?”.','Día 2: diagrama FV → batería → cargador → vehículo.','Día 3: contenido para flotas.','Día 4: caso de hotel/parqueadero.','Día 5: CTA de evaluación.'],'Prospección B2B + WhatsApp + alianzas con instaladores de cargadores.','Ocupar el territorio de integración energética, no solamente el de instalación de cargadores.','Diseñemos la energía detrás de tu movilidad.','Leads EV, evaluaciones, reuniones B2B y propuestas integradas.','Crear piezas para flotas, hoteles y residencias; construir oferta conjunta FV+EV.','No prometer tiempos de carga o ahorro sin especificaciones del vehículo, cargador y perfil.',('movilidad','carga','ev')))
    specs.append(opp('campo-impulsa-sol','AGROINDUSTRIA · SEGMENTACIÓN','El campo también se impulsa con el sol.','Crear una línea comercial para agroindustria que conecte energía solar con bombeo, refrigeración, procesamiento y operación rural.','La energía es una variable operativa del agro; comunicar usos concretos puede ser más potente que vender “paneles”.','Abrir oportunidades en agroindustria mediante casos de uso energéticos.','Fincas productivas, sistemas de riego, ganadería tecnificada, frigoríficos, centros de acopio y agroindustria.','Las cargas rurales pueden tener costos altos, restricciones de red o necesidades operativas particulares.','La energía solar debe adaptarse al proceso productivo.','E-SUN POWER diseña el sistema a partir de la carga que mueve el negocio.','Diagnóstico energético de proceso + visita técnica.','Contenido por aplicación → contacto → levantamiento → diseño → propuesta.',['Bombeo','Refrigeración','Procesamiento','Sistemas híbridos y almacenamiento'],['Día 1: pieza “El campo también se impulsa con el sol”.','Día 2: carrusel por aplicación.','Día 3: video de proceso productivo.','Día 4: caso económico/operativo sin cifras universales.','Día 5: diagnóstico.'],'Prospección sectorial + alianzas con proveedores agroindustriales.','Hablar de productividad y continuidad, no solamente de kWp.','Cuéntanos qué carga mueve tu operación rural.','Leads agro, visitas, diagnósticos, propuestas y conversión.','Construir lista de prospectos y 4 piezas por aplicación.','No dimensionar ni prometer desempeño sin conocer proceso, potencia y horarios.',('agro','rural','bombeo')))
    specs.append(opp('energia-donde-no-llega','ZNI · MICROREDES','Energía donde la red no llega.','Presentar soluciones híbridas, solares y de almacenamiento para lugares con restricciones de red o necesidades de autonomía energética.','La energía distribuida y las soluciones aisladas permiten entrar en conversaciones que no compiten con el mercado residencial convencional.','Posicionar a E-SUN POWER como integrador de sistemas energéticos en zonas no interconectadas o con suministro limitado.','Proyectos rurales, institucionales, productivos y comunidades con necesidades de energía confiable.','La ausencia o debilidad de red limita productividad, servicios y continuidad.','Diseñar energía alrededor del lugar, no alrededor de una red que no está disponible.','Integrar generación, almacenamiento, respaldo y gestión según la realidad del sitio.','Evaluación de recurso + cargas + autonomía requerida + arquitectura híbrida.','Caso de uso → diagnóstico → visita → arquitectura → propuesta.',['Sistemas híbridos','BESS','Microredes','Gestión de cargas'],['Día 1: video “¿Qué haces cuando la red no llega?”.','Día 2: diagrama de microred.','Día 3: aplicación productiva.','Día 4: almacenamiento y respaldo.','Día 5: contacto técnico.'],'Prospección institucional/B2B + aliados locales.','Diferenciarse por integración y diseño de sistema completo.','Evaluemos una solución energética para tu ubicación.','Leads calificados, levantamientos, estudios, propuestas y cierres.','Preparar ficha de solución híbrida y 3 casos de uso.','No prometer autonomía sin balance energético, recurso solar y cargas verificadas.',('zni','microred','hibrid')))
    specs.append(opp('diseñamos-sistemas','POSICIONAMIENTO · INGENIERÍA','No compares paneles. Compara sistemas.','Convertir la ingeniería de diseño en una herramienta comercial visible para diferenciar a E-SUN POWER.','Cuando varias empresas venden equipos similares, la forma de diseñar y resolver el sistema se convierte en una ventaja.','Reducir la comparación exclusivamente por precio y elevar la percepción de valor.','Clientes que están comparando dos o más cotizaciones.','Las ofertas parecen iguales y el cliente no sabe qué hay detrás del precio.','No solo instalamos paneles. Diseñamos sistemas.','Partir del consumo, arquitectura, operación, protecciones, almacenamiento y objetivo antes de seleccionar equipos.','Diagnóstico comparativo de propuestas.','Contenido comparativo → guía → diagnóstico → propuesta técnica-comercial.',['Cómo comparar cotizaciones','Qué debe tener un diseño serio','Protecciones y arquitectura','Equipos vs sistema completo'],['Día 1: Reel “No compares paneles”.','Día 2: carrusel de 7 criterios.','Día 3: antes/después de una decisión de diseño.','Día 4: FAQ.','Día 5: CTA de revisión.'],'Reunión técnica-comercial con checklist de diagnóstico.','Analizar territorios saturados de competidores y demostrar proceso propio sin desacreditarlos.','Compara sistemas, no solamente precios.','Leads, diagnósticos, reuniones, propuestas y conversión.','Crear guía de comparación, Reel, carrusel, checklist y guion comercial.','No afirmar que un competidor incumple sin evidencia verificable.',('competencia','diferenc','ingenier')))
    specs.append(opp('tecnologia-autoridad','TECNOLOGÍA · AUTORIDAD','La nueva generación solar: explica la tecnología antes de venderla.','Convertir TOPCon, HJT, back-contact, BESS y gestión energética en contenido de autoridad comprensible.','La innovación FV cambia rápidamente; explicar qué significa para el usuario posiciona a E-SUN POWER como asesor y no como catálogo.','Construir autoridad técnica que genere confianza comercial.','Clientes técnicos, empresarios, arquitectos, ingenieros y compradores informados.','El mercado recibe términos tecnológicos sin contexto y puede confundir novedad con conveniencia.','La tecnología solo importa cuando mejora una decisión del proyecto.','E-SUN POWER traduce innovación técnica en criterios de selección y aplicación.','Serie educativa “Tecnología sin humo” + diagnóstico de aplicación.','Contenido técnico → interacción → consulta → diagnóstico → propuesta.',['TOPCon/HJT/back-contact','Degradación y rendimiento','BESS','Selección de tecnología'],['Día 1: comparativo tecnológico.','Día 2: Reel explicativo.','Día 3: ficha visual.','Día 4: pregunta interactiva.','Día 5: CTA de asesoría.'],'Capturar preguntas y convertirlas en reuniones consultivas.','Competir por autoridad y claridad, no por afirmar que el equipo más nuevo siempre es mejor.','¿Qué tecnología tiene sentido para tu proyecto?','Alcance cualificado, guardados, consultas, diagnósticos y propuestas.','Crear serie de 5 piezas y una matriz interna de tecnologías.','No recomendar una tecnología solo por tendencia; considerar proyecto, disponibilidad y evidencia.',('topcon','hjt','tecnologia')))
    specs.append(opp('arquitectura-alianza','ALIANZAS · ARQUITECTURA','Diseñemos el proyecto desde el plano, no al final.','Convertir arquitectos y constructores en aliados comerciales para integrar FV desde la etapa de diseño.','La integración temprana evita decisiones tardías de estructura, orientación, espacio técnico y rutas eléctricas.','Generar un canal B2B de proyectos mediante alianzas con arquitectura y construcción.','Arquitectos, constructoras, desarrolladores, diseñadores y gerencias de proyecto.','La solar suele entrar tarde al proyecto y termina condicionada por decisiones ya tomadas.','La energía solar debe diseñarse con la arquitectura, no después de ella.','E-SUN POWER aporta criterios de integración energética desde el diseño.','Revisión de planos + checklist FV para proyectos.','Contenido B2B → contacto → revisión de proyecto → reunión → propuesta.',['FV y arquitectura','Cubiertas','Espacios técnicos','BIM y coordinación'],['Día 1: pieza “No pongas los paneles al final”.','Día 2: carrusel de coordinación.','Día 3: ejemplo de cubierta.','Día 4: checklist descargable.','Día 5: invitación a alianza.'],'LinkedIn + correo + contacto directo con oficinas y constructoras.','Entrar antes que el instalador convencional y convertirse en socio técnico.','Revisemos cómo integrar energía solar en tu proyecto.','Contactos B2B, planos recibidos, reuniones y proyectos originados.','Crear kit para arquitectos y lista de 50 aliados objetivo.','No sustituir estudios ni responsabilidades de otros diseñadores; delimitar alcance.',('arquitect','bim','cubierta')))
    specs.append(opp('postventa-recurrencia','POSTVENTA · FIDELIZACIÓN','Tu sistema solar no termina cuando se instala.','Convertir postventa, monitoreo, revisión y optimización en una relación comercial de largo plazo.','La base instalada es una oportunidad de confianza, referidos, mantenimiento y nuevas soluciones como BESS/EMS.','Aumentar recurrencia, referidos y ventas cruzadas.','Clientes existentes y sus administradores/gerentes de operación.','Después de la instalación, el cliente puede perder acompañamiento o no saber interpretar el desempeño.','La relación continúa después de encender el sistema.','E-SUN POWER convierte la postventa en información, confianza y nuevas decisiones energéticas.','Revisión anual + informe de desempeño + recomendación de mejora.','Postventa → reporte → recomendación → upsell/referido.',['Monitoreo','Mantenimiento','BESS/EMS','Referidos'],['Día 1: mensaje de revisión.','Día 2: informe visual.','Día 3: contenido educativo.','Día 4: oferta de revisión.','Día 5: programa de referidos.'],'CRM/WhatsApp + seguimiento programado.','Competir por relación y evidencia de desempeño.','Revisemos cómo está funcionando tu sistema.','Tasa de respuesta, revisiones, upsells, referidos y recompra.','Crear plantilla de informe y programa de referidos.','No atribuir fallas sin diagnóstico técnico.',('postventa','monitoreo','referid')))
    specs.append(opp('energia-inteligente','EMS · GESTIÓN','No basta con producir energía. Hay que saber gestionarla.','Introducir EMS y gestión energética como una conversación comercial para clientes con múltiples cargas y decisiones operativas.','La transición energética aumenta la necesidad de medir, gestionar y decidir cuándo consumir, almacenar o producir.','Abrir una línea consultiva de gestión energética.','C&I, hoteles, industrias y usuarios con múltiples cargas.','El cliente tiene datos pero no una forma clara de convertirlos en decisiones.','La información energética se convierte en acción cuando existe una estrategia de gestión.','Integrar medición, FV, BESS y cargas en una arquitectura gestionable.','Evaluación de gestión energética + roadmap.','Contenido → evaluación → datos → roadmap → implementación.',['Medición','Gestión de cargas','FV+BESS','Decisiones basadas en datos'],['Día 1: “¿Cuánta energía consumes sin saber cuándo?”.','Día 2: gráfico de carga.','Día 3: caso conceptual.','Día 4: beneficios de gestionar.','Día 5: evaluación.'],'Diagnóstico consultivo y posterior ingeniería.','Mover la marca de instalador a integrador energético.','Descubre qué puede hacer la gestión energética por tu operación.','Consultas, datos recibidos, evaluaciones, propuestas y recurrencia.','Crear demo visual, contenido educativo y oferta de evaluación.','No afirmar ahorros sin medición y análisis del perfil de carga.',('ems','gestion','datos')))
    specs.append(opp('radar-esuna','INTELIGENCIA · CONTENIDO','Radar Solar E-SUN POWER: lo que cambia hoy, lo que puede cambiar mañana.','Crear una propiedad editorial periódica que convierta noticias y cambios del sector en oportunidades comerciales explicadas.','El mercado FV cambia por tecnología, regulación, almacenamiento y competencia; comunicar esa lectura crea autoridad.','Hacer que E-SUN POWER sea una fuente recurrente de interpretación del mercado FV.','Empresarios, compradores, ingenieros, arquitectos y seguidores interesados en energía.','Hay mucha noticia y poca interpretación útil para tomar decisiones.','No solo informamos lo que pasa. Explicamos qué significa para tu energía.','ESUNA convierte señales públicas en contenidos, preguntas comerciales y oportunidades de diagnóstico.','Radar semanal + CTA a diagnóstico según el tema.','Señal → interpretación → contenido → interacción → oportunidad comercial.',['Noticias FV','Regulación Colombia','Tecnología','Almacenamiento','Competencia'],['Publicar radar semanal.','Destacar una señal.','Explicar impacto comercial.','Relacionarla con una solución.','Cerrar con CTA.'],'Redes + LinkedIn + WhatsApp + base de prospectos.','Ser intérprete del mercado, no un agregador de noticias.','¿Quieres saber qué significa esta tendencia para tu proyecto?','Alcance, seguidores cualificados, consultas, leads y reuniones.','Crear formato editorial y calendario de 4 semanas.','Separar hechos de opiniones y citar fuentes públicas cuando se use información reciente.',('regulacion','tecnologia','mercado')))
    specs.append(opp('comparacion-inteligente','CONFIANZA · COMPARACIÓN','La cotización más barata no siempre es la solución más conveniente.','Crear una campaña de educación para enseñar al cliente a comparar sistemas, garantías, diseño, servicio y condiciones comerciales.','La presión por precio es una de las principales amenazas para una venta consultiva; educar reduce la asimetría de información.','Aumentar conversión de clientes que comparan propuestas y defender valor.','Clientes con cotizaciones de diferentes proveedores.','No tienen criterios para saber si dos ofertas realmente son equivalentes.','Antes de comparar números, asegúrate de estar comparando lo mismo.','E-SUN POWER entrega criterios de decisión transparentes y una propuesta basada en necesidades reales.','Checklist gratuito de comparación + revisión de cotización.','Anuncio → checklist → cotización → revisión → reunión → propuesta.',['Precio vs valor','Equipos y garantías','Diseño','Protecciones','Postventa'],['Día 1: “¿Dos cotizaciones iguales?”.','Día 2: checklist.','Día 3: explicación de equipos.','Día 4: garantías/servicio.','Día 5: revisión gratuita inicial.'],'WhatsApp con carga de documento y checklist.','Convertir transparencia en diferenciación.','¿Quieres comparar dos propuestas? Te ayudamos a ver las diferencias.','Descargas, cotizaciones recibidas, revisiones, reuniones y cierres.','Diseñar checklist y campaña de captura.','No hacer comparaciones técnicas concluyentes sin revisar documentos completos.',('competencia','cotizacion','valor')))

    # Variantes híbridas: cuando una misma necesidad puede cruzarse con otro segmento/solución,
    # ESUNA crea una oportunidad comercial nueva en lugar de limitarse a reordenar las anteriores.
    hybrid_pairs=[
        ('Hoteles + BESS','HOTEL + ALMACENAMIENTO','Hoteles que no pueden dejar la energía al azar.','Combinar hospitality con almacenamiento para hablar de continuidad y gestión.'),
        ('Restaurantes + FV','GASTRONOMÍA · FV','Tu restaurante también puede producir su propia energía.','Convertir la operación gastronómica en un caso de uso solar concreto.'),
        ('Bodegas + EMS','LOGÍSTICA · EMS','Tu bodega consume energía. También puede aprender de ella.','Llevar gestión energética a centros logísticos y bodegas.'),
        ('Constructores + BESS','CONSTRUCCIÓN · ENERGÍA','El proyecto se entrega mejor cuando la energía también se diseña.','Integrar FV+BESS en proyectos inmobiliarios desde el anteproyecto.'),
        ('Conjuntos + movilidad','RESIDENCIAL · MOVILIDAD','El parqueadero puede convertirse en infraestructura energética.','Cruzar conjuntos residenciales, FV y carga de vehículos eléctricos.'),
        ('Agro + bombeo','AGRO · BOMBEO SOLAR','El agua también necesita una estrategia energética.','Usar el bombeo como puerta de entrada para soluciones solares rurales.'),
        ('Industria + calidad','INDUSTRIA · CONTINUIDAD','La energía industrial no solo debe ser más barata: debe ser gestionable.','Crear una conversación B2B sobre continuidad, gestión y arquitectura energética.'),
        ('Arquitectura + autoridad','ARQUITECTURA · CONTENIDO','El plano también puede contar la historia energética del proyecto.','Convertir coordinación arquitectónica y FV en contenido de autoridad.'),
        ('Clientes existentes + BESS','FIDELIZACIÓN · BESS','Tu sistema solar puede tener una segunda etapa.','Usar la base instalada para detectar oportunidades de almacenamiento.'),
        ('Competencia + transparencia','COMPETENCIA · CONFIANZA','Que el cliente sepa comparar también es una ventaja.','Convertir transparencia y educación en una defensa frente a la guerra de precios.'),
    ]
    base_for_hybrid=list(specs)
    for label,kind,title,desc in hybrid_pairs:
        base=rng.choice(base_for_hybrid)
        h=dict(base)
        h['id']=make_id('hybrid-'+label.lower().replace(' ','-')+'-'+base['id'])
        h['kind']=kind
        h['title']=title
        h['desc']=desc+' '+base['desc']
        h['why_now']=base['why_now']+' ESUNA cruza además este segmento con el conocimiento técnico y comercial disponible para encontrar una entrada específica.'
        h['objective']=base['objective']
        h['audience']=label+' y prospectos relacionados.'
        h['positioning']=base['positioning']
        h['value_proposition']=base['value_proposition']
        h['offer']=base['offer']
        h['sources']=list(dict.fromkeys(base.get('sources',[])))
        specs.append(h)

    # Mezcla adicional: cada refresh cambia el conjunto, no solo el orden. Se ponderan señales recientes.
    for x in specs:
        blob=(x['title']+' '+x['desc']+' '+' '.join(x.get('_signal_terms',()))).lower()
        score=rng.random()*3
        if 'ALMACENAMIENTO' in tags and any(t in blob for t in ('bess','almacenamiento','gestion')): score+=4
        if 'TECNOLOGÍA FV' in tags and any(t in blob for t in ('tecnologia','topcon','hjt')): score+=3
        if 'REGULACIÓN / COLOMBIA' in tags and any(t in blob for t in ('regulacion','colombia','saeb')): score+=2.5
        if 'C&I' in tags and any(t in blob for t in ('c&i','comercial','hotel','empresa')): score+=2.5
        if 'MOVILIDAD' in tags and any(t in blob for t in ('movilidad','carga','ev')): score+=3
        x['_score']=score
    # Excluir las tarjetas ya visibles. Si se excluye demasiado, completar con las mejores restantes.
    available=[x for x in specs if x['id'] not in excluded and x['title'].strip().lower() not in excluded_titles]
    rng.shuffle(available)
    available.sort(key=lambda x:x['_score'], reverse=True)
    chosen=available[:limit]
    if len(chosen)<limit:
        fallback=[x for x in specs if x not in chosen and x['title'].strip().lower() not in excluded_titles]
        rng.shuffle(fallback); chosen += fallback[:limit-len(chosen)]
    now=datetime.datetime.now().astimezone(); today=now.strftime('%d/%m/%Y %H:%M')
    result=[]
    for x in chosen:
        x.pop('_score',None); x.pop('_signal_terms',None)
        x['fresh_signals']=news[:6]; x['updated_at']=today
        rr=[r for r in allrows if r['source_name'] in x.get('sources',[])][:10]
        x['strategy_detail']=_esuna_strategy(x,rr,news)
        result.append(x)
    return result, news, tags, today

def esuna_proactive(seed=None, exclude_ids=None, exclude_titles=None):
    ideas,news,tags,today=_esuna_proactive_opportunities(8, seed=seed, exclude_ids=exclude_ids, exclude_titles=exclude_titles)
    st=_esuna_status()
    return {'ok':True,'ideas':ideas,'news':news[:10],'news_tags':tags,'updated_at':today,'generated_by':'motor local de reglas + conocimiento interno + señales públicas recientes','mode':'LOCAL_KNOWLEDGE','research_note':f"Actualizado {today}. ESUNA cruzó {st['knowledge']} registros, {st['sources']} fuentes internas y señales públicas recientes del mundo FV. No utiliza IA externa.",'current_date':datetime.datetime.now().astimezone().strftime('%d/%m/%Y')}

def _esuna_answer(message, campaign=None, history=None):
    if not message: raise ValueError('Escribe una pregunta o solicitud para Esuna.')
    intent=_esuna_intent(message); rows=_esuna_search(message,18)
    # Para preguntas abiertas de marketing, ampliar deliberadamente la búsqueda a otros dominios.
    if intent in ('MARKETING','MERCADO','COMPETENCIA','GENERAL'):
        extra=[]
        for q in ('posicionamiento ventaja competitiva propuesta de valor', 'mercado fotovoltaico Colombia tendencias oportunidades', 'competencia fotovoltaica Colombia segmentos ofertas', 'BESS C&I almacenamiento energía solar Colombia'):
            extra.extend(_esuna_search(q,5))
        seen={r['id'] for r in rows}
        rows += [r for r in extra if r['id'] not in seen]
    allowed={
      'BESS':{'BESS / SAEB','SISTEMAS HÍBRIDOS','TECNOLOGÍAS Y OPORTUNIDADES'},
      'COMPETENCIA':{'COMPETENCIA','MARKETING ESTRATÉGICO','VENTAS'},
      'MERCADO':{'MERCADO COLOMBIANO','TECNOLOGÍAS Y OPORTUNIDADES','C&I','BESS / SAEB','MOVILIDAD ELÉCTRICA'},
      'NORMATIVA':{'NORMATIVA COLOMBIANA','AGPE','GENERACIÓN DISTRIBUIDA','AUTOGENERACIÓN REMOTA','COMUNIDADES ENERGÉTICAS','BESS / SAEB','MOVILIDAD ELÉCTRICA'},
      'PRODUCTO':{'PRODUCTOS FV','FABRICANTES','PROVEEDORES COLOMBIA','BESS / SAEB'},
      'MARKETING':{'MARKETING ESTRATÉGICO','NEUROMARKETING','BRANDING','COPYWRITING','REDES SOCIALES','PUBLICIDAD DIGITAL','VENTAS','MERCADO COLOMBIANO','COMPETENCIA','BESS / SAEB','SISTEMAS HÍBRIDOS','C&I','EMS','MOVILIDAD ELÉCTRICA','TECNOLOGÍAS Y OPORTUNIDADES'}
    }.get(intent)
    if allowed:
        filtered=[r for r in rows if r['category'] in allowed]
        if filtered: rows=filtered
    con=_esuna_db(); con.execute('INSERT INTO query_log(query,intent,result_count) VALUES(?,?,?)',(message,intent,len(rows))); con.commit(); con.close()
    low=' '.join(_esuna_tokens(message))
    c=campaign or {}
    if intent=='MARKETING' and 'campana' in low:
        obj=c.get('objective','GENERAR LEADS'); aud=c.get('audience') or 'definir con base en segmento y capacidad de compra'; prod=c.get('product') or 'solución fotovoltaica E-SUN POWER'; chan=c.get('channels') or 'Instagram + Facebook + WhatsApp'; market=c.get('market') or 'Colombia'; horizon=c.get('horizon') or '30 días'
        # La campaña cruza los registros recuperados y mantiene una salida determinística.
        evidence='\n'.join(f"• {r['title']} — {r['source_name']}" for r in rows[:6])
        ans=f"PROPUESTA DE CAMPAÑA E-SUN POWER\n\nObjetivo: {obj}\nPúblico: {aud}\nSolución: {prod}\nMercado: {market}\nCanales: {chan}\nHorizonte: {horizon}\n\n1. INSIGHT\nEl cliente no compra paneles; compra una mejora concreta en su economía, continuidad o gestión energética.\n\n2. CONCEPTO\n‘No solo instalamos paneles. Diseñamos sistemas.’\n\n3. PROPUESTA DE VALOR\nDiseñar una solución energética según consumo, espacio, objetivos y condiciones del proyecto, con acompañamiento técnico-comercial.\n\n4. EMBUDO\nContenido/Anuncio → Landing o WhatsApp → diagnóstico → propuesta → seguimiento → cierre.\n\n5. CONTENIDOS\n• Dolor/problema\n• Educación\n• Autoridad/prueba\n• Diferenciación\n• Oferta/CTA\n\n6. CTA\n‘Solicita un diagnóstico energético de tu proyecto.’\n\n7. WHATSAPP\nIdentificar consumo → solicitar factura/datos → detectar oportunidad → presentar solución → seguimiento.\n\n8. KPI\nCTR, leads, costo por lead, tasa de contacto, citas, propuestas, conversión y CAC.\n\n9. DIFERENCIACIÓN\nNo competir únicamente por precio. Convertir ingeniería, diseño personalizado, confiabilidad y acompañamiento en activos de marca.\n\nSEÑALES INTERNAS UTILIZADAS\n{evidence}"
    elif intent=='COMPETENCIA':
        names=list(dict.fromkeys(r['source_name'] for r in rows if r['source_name']))
        ans="INTELIGENCIA COMPETITIVA ESUNA\n\nESUNA cruzó las empresas registradas con referentes de marketing y conocimiento de mercado.\n\nACTORES ENCONTRADOS\n"+('\n'.join('• '+n for n in names[:12]) if names else 'No encontré un competidor específico en la base.')+"\n\nLECTURA ESTRATÉGICA\n• Identificar qué territorios de comunicación están saturados.\n• Separar beneficios repetidos (por ejemplo, ahorro) de diferenciadores reales.\n• Buscar espacios donde E-SUN POWER pueda competir por valor y no solamente por precio.\n• Analizar CTA, prueba social, experiencia digital y embudo.\n\nREGLA ESUNA\nAnalizar para superar, nunca copiar."
    elif intent=='MERCADO':
        ans="ANÁLISIS DE MERCADO · ESUNA\n\nESUNA no se limita a enumerar datos: cruza señales de mercado con oportunidades comerciales.\n\nSEÑALES ENCONTRADAS\n"+('\n'.join(f"• {r['title']}: {r['content'][:430].strip()}" for r in rows[:7]) if rows else 'No encontré suficiente información local.')+"\n\nOPORTUNIDAD PARA E-SUN POWER\nConvertir las señales en segmentos, ofertas, contenidos y embudos concretos. Priorizar soluciones que permitan diferenciarse: ingeniería personalizada, C&I, almacenamiento, sistemas híbridos, gestión energética y nuevas aplicaciones.\n\nCRITERIO\nLos datos de mercado se presentan como hechos solo cuando la fuente lo permite; las oportunidades son recomendaciones de ESUNA."
    elif intent in ('BESS','NORMATIVA','PRODUCTO'):
        ans=f"ESUNA — {intent}\n\n"
        if rows:
            for r in rows[:7]: ans+=f"• {r['title']}\n  {r['content'][:620].strip()}\n\n"
        else: ans+="No encontré una fuente suficientemente específica en la base local.\n\n"
        ans+="APLICACIÓN DE MARKETING\nLa información técnica se utiliza para construir beneficios, argumentos y contenidos verificables; no para sustituir una memoria de diseño ni una asesoría regulatoria."
    else:
        if rows:
            ans="ESUNA · RECOMENDACIÓN BASADA EN CONOCIMIENTO\n\n"
            # Cruzamos hasta 6 piezas de conocimiento para evitar respuestas de una sola fuente.
            for r in rows[:6]: ans+=f"• {r['title']} — {r['source_name']}\n  {r['content'][:420].strip()}\n\n"
            ans+="SÍNTESIS ESUNA\nLa oportunidad debe evaluarse cruzando marketing, mercado, competencia, producto y ventas. Si quieres, puedo convertir esta señal en una campaña, oferta, calendario de contenidos o estrategia comercial."
        else: ans="No encuentro suficiente información en la base de conocimiento E-SUN POWER para responder con seguridad. Agrega aquí el documento o la página que quieras convertir en conocimiento de ESUNA."
    # El motor consolida duplicados de la misma fuente/título para que la respuesta sea limpia.
    if rows:
        unique_rows=[]; seen_keys=set()
        for r in rows:
            key=((r['source_name'] or '').strip().lower(),(r['title'] or '').strip().lower())
            if key in seen_keys: continue
            seen_keys.add(key); unique_rows.append(r)
        rows=unique_rows
        if intent in ('MARKETING','MERCADO','COMPETENCIA','GENERAL') and 'FUENTES CONSULTADAS' not in ans:
            # Recalcular una síntesis ejecutable cuando la pregunta no fue una solicitud de campaña.
            evidence=rows[:6]
            ans += "\n\nDECISIÓN ESTRATÉGICA ESUNA\n"
            if intent=='COMPETENCIA':
                ans += "La competencia muestra que ahorro, cotización, acompañamiento y amplitud de servicios son territorios frecuentes. E-SUN POWER debe evitar competir solo por precio y construir un territorio propio alrededor de diseño de sistemas, ingeniería, solución personalizada y acompañamiento."
            elif intent=='MERCADO':
                ans += "La señal más útil no es solamente el crecimiento del mercado: es la diversificación de soluciones. ESUNA recomienda convertir crecimiento, almacenamiento, C&I y nuevas aplicaciones en ofertas específicas para segmentos concretos, en lugar de comunicar energía solar de forma genérica."
            else:
                ans += "ESUNA recomienda cruzar la necesidad del cliente con el segmento, la oferta, la competencia y la evidencia disponible. Para E-SUN POWER, la diferenciación debe convertir la ingeniería y el diseño de sistemas en una ventaja comercial visible."
        ans += "\n\nFUENTES CONSULTADAS\n"+_esuna_format_sources(rows)
    
    st=_esuna_status(); return {'ok':True,'answer':ans,'research_note':f"ESUNA cruzó conocimiento interno: {st['knowledge']} registros, {st['sources']} fuentes, {st['competitors']} competidores y {st['manufacturers']} fabricantes. No utiliza un motor de IA externo.",'mode':'LOCAL_KNOWLEDGE','sources_used':list(dict.fromkeys(r['source_name'] for r in rows[:8]))}

def publicidad_marketing_chat(message, history=None, user='', campaign=None):
    return _esuna_answer(str(message or '').strip(),campaign)

def publicidad_generate(prompt,title='Publicidad E-SUN POWER'):
    if not _effective_openai_key(): raise RuntimeError('Para generar imágenes debes configurar una clave de OpenAI en el servidor.')
    full=f"""Crea una pieza publicitaria profesional para E-SUN POWER, empresa de soluciones de energía solar fotovoltaica. Concepto: {title}. {prompt} Prioriza coherencia técnica de los componentes fotovoltaicos, estética premium y composición publicitaria. No inventes logotipos ni textos pequeños ilegibles; deja espacio limpio para textos que serán agregados posteriormente."""
    data=_openai_json('https://api.openai.com/v1/images/generations',{'model':OPENAI_IMAGE_MODEL,'prompt':full,'size':'1024x1024','quality':'high'},timeout=240)
    item=(data.get('data') or [{}])[0]
    b64=item.get('b64_json')
    if not b64: raise RuntimeError('El motor de imágenes no devolvió una imagen.')
    raw=base64.b64decode(b64); name=f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.png"; path=PUBLICIDAD_DIR/name; path.write_bytes(raw)
    return {'ok':True,'url':'/data/publicidad_generated/'+name,'filename':name}


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def equipment():
    return {'version': VER, 'modules': load(MODULES, []), 'inverters': load(INVERTERS, [])}

def batteries():
    return load(BATTERIES, [])

def meters():
    d=load(METERS, {'version':VER,'meters':[]})
    return d if isinstance(d,dict) else {'version':VER,'meters':d}

def supplier_prices():
    return load(SUPPLIER_PRICES, {'version':'1.0','items':[]})

def costs():
    return load(COSTS, {'version':'1.0','items':[]})

def cost_items():
    return costs().get('items',[])

def quote_budget(payload):
    rows=payload.get('rows') or []
    clean=[]; subtotal=0.0
    for r in rows:
        try:
            qty=float(r.get('qty') or 0); cost=float(r.get('cost_price') or 0); markup=float(r.get('markup_pct') or 0); unit=cost*(1+markup/100)
        except Exception: continue
        total=qty*unit; subtotal+=total
        clean.append({'code':r.get('code',''),'category':r.get('category',''),'description':r.get('description',''),'unit':r.get('unit','und'),'qty':qty,'cost_price':cost,'markup_pct':markup,'sale_price':unit,'total':total,'source':r.get('source','')})
    admin=float(payload.get('admin_pct') or 0); overhead=float(payload.get('overhead_pct') or 0); profit=float(payload.get('profit_pct') or 0); vat=float(payload.get('vat_pct') or 0)
    admin_v=subtotal*admin/100; overhead_v=subtotal*overhead/100; base=subtotal+admin_v+overhead_v; profit_v=base*profit/100; before_vat=base+profit_v; vat_v=before_vat*vat/100; grand=before_vat+vat_v
    return {'rows':clean,'subtotal':subtotal,'admin_pct':admin,'admin_value':admin_v,'overhead_pct':overhead,'overhead_value':overhead_v,'profit_pct':profit,'profit_value':profit_v,'subtotal_before_vat':before_vat,'vat_pct':vat,'vat_value':vat_v,'grand_total':grand}



def module_area(m):
    if m.get('width_m') and m.get('length_m'):
        return float(m['width_m']) * float(m['length_m'])
    if m.get('area_m2'):
        return float(m['area_m2'])
    return None



def upme_query(where, out_fields='*', return_geometry=False, result_offset=None, result_record_count=None):
    params = {
        'where': where, 'outFields': out_fields, 'returnGeometry': 'true' if return_geometry else 'false',
        'f': 'json', 'outSR': '9377'
    }
    if result_offset is not None: params['resultOffset'] = str(result_offset)
    if result_record_count is not None: params['resultRecordCount'] = str(result_record_count)
    url = UPME_SOLAR_LAYER + '/query?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent':'PV-System-Designer/17'})
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode('utf-8'))

def parse_range_midpoint(text):
    if not text: return None
    nums = re.findall(r'\d+(?:[.,]\d+)?', str(text))
    if len(nums) >= 2:
        lo=float(nums[0].replace(',','.')); hi=float(nums[1].replace(',','.'))
        return (lo+hi)/2.0
    if len(nums)==1: return float(nums[0].replace(',','.'))
    return None

def dane_query(where='1=1', out_fields='DPTO_CCDGO,DPTO_CNMBRE,MPIO_CDPMP,MPIO_CNMBRE', return_geometry=False):
    params={
        'where':where, 'outFields':out_fields,
        'returnGeometry':'true' if return_geometry else 'false',
        'f':'json'
    }
    url=DANE_MUNICIPALITY_LAYER+'/query?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':'PV-System-Designer/19'})
    with urllib.request.urlopen(req,timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))

def dane_locations():
    data=dane_query()
    feats=data.get('features',[])
    if not feats: raise ValueError('DANE no devolvió unidades territoriales.')
    rows=[]
    for f in feats:
        a=f.get('attributes',{})
        code=str(a.get('MPIO_CDPMP') or '').strip()
        if not re.fullmatch(r'\d{5}',code): continue
        rows.append({'department_code':str(a.get('DPTO_CCDGO') or code[:2]).zfill(2),
                     'department':a.get('DPTO_CNMBRE') or '',
                     'code':code,
                     'municipality':a.get('MPIO_CNMBRE') or ''})
    # Preserve unique DIVIPOLA codes and deterministic ordering.
    rows={x['code']:x for x in rows}
    rows=sorted(rows.values(),key=lambda x:(x['department'],x['municipality']))
    return {'ok':True,'count':len(rows),'locations':rows,
            'source':'DANE — DIVIPOLA MGN 2025'}

def divipola_locations():
    # Primary source requested by the user: Datos Abiertos Colombia / DIVIPOLA.
    # Cache locally after the first successful download so the dropdowns do not depend
    # on a GIS service being available on every startup.
    try:
        req=urllib.request.Request(DIVIPOLA_API,headers={'User-Agent':'PV-System-Designer/21','Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=json.loads(r.read().decode('utf-8'))
        if not isinstance(raw,list) or len(raw)<100:
            raise ValueError('Datos.gov no devolvió un catálogo DIVIPOLA válido.')
        DIVIPOLA_CACHE.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
    except Exception as e:
        raw=load(DIVIPOLA_CACHE,[])
        if not raw:
            raise ValueError('No fue posible cargar DIVIPOLA desde Datos.gov.co: '+str(e))
    rows=[]
    for a in raw:
        code=str(a.get('cod_mpio') or '').strip()
        if not re.fullmatch(r'\d{5}',code): continue
        try: lat=float(str(a.get('latitud','')).replace(',','.')); lon=float(str(a.get('longitud','')).replace(',','.'))
        except: lat=lon=None
        rows.append({'department_code':str(a.get('cod_dpto') or code[:2]).zfill(2),
                     'department':a.get('dpto') or '', 'code':code,
                     'municipality':a.get('nom_mpio') or '', 'type':a.get('tipo_municipio') or '',
                     'lat':lat,'lon':lon})
    rows={x['code']:x for x in rows}
    rows=sorted(rows.values(),key=lambda x:(x['department'],x['municipality']))
    return {'ok':True,'count':len(rows),'locations':rows,'source':'Datos Abiertos Colombia — DIVIPOLA (gdxc-w37w)'}



def _string_config_for_inverter(v, m, total_modules, qty):
    """Find a preliminary equal-length string arrangement per inverter using the registered datasheet limits."""
    if qty <= 0 or total_modules <= 0: return None
    power_w=float(m.get('power_w') or 0)
    voc=float(m.get('voc_v') or 0); vmp=float(m.get('vmp_v') or 0)
    isc=float(m.get('isc_a') or 0); imp=float(m.get('imp_a') or 0)
    max_v=float(v.get('max_dc_v') or 0); mpmin=float(v.get('mppt_min_v') or 0); mpmax=float(v.get('mppt_max_v') or 0)
    mppt_count=int(float(v.get('mppt_count') or 0)); spmp=int(float(v.get('strings_per_mppt') or 1))
    maximp=float(v.get('max_current_mppt_a') or 0); maxisc=float(v.get('max_isc_mppt_a') or 0)
    if not (power_w and voc and vmp and mppt_count): return None
    # Distribute modules as evenly as possible among identical inverters.
    counts=[total_modules//qty + (1 if i < total_modules%qty else 0) for i in range(qty)]
    maxdc=float(v.get('max_dc_kw') or 0)
    ac=float(v.get('ac_kw') or 0)
    if maxdc and any(c*power_w/1000 > maxdc+1e-9 for c in counts): return None
    for mps in range(6,41):
        if max_v and mps*voc >= max_v: continue
        if mpmin and mps*vmp < mpmin: continue
        if mpmax and mps*vmp > mpmax: continue
        configs=[]; valid=True
        for c in counts:
            strings=math.ceil(c/mps)
            if strings > mppt_count*spmp: valid=False; break
            spm=math.ceil(strings/mppt_count)
            cur=spm*imp; isc_mppt=spm*isc
            if maximp and cur > maximp+1e-9: valid=False; break
            if maxisc and isc_mppt > maxisc+1e-9: valid=False; break
            configs.append((c,strings,spm,cur,isc_mppt))
        if not valid: continue
        cold_coeff=float(m.get('temp_coeff_voc_pct_c') or 0)
        cold_voc=mps*voc*(1+(cold_coeff/100)*(-10-25)) if cold_coeff else mps*voc
        if max_v and cold_voc >= max_v: continue
        total_strings=sum(x[1] for x in configs)
        return {
            'modules_per_string':mps,
            'strings_total':total_strings,
            'voc_string_v':mps*voc,
            'vmp_string_v':mps*vmp,
            'strings_per_mppt_max':max(x[2] for x in configs),
            'current_mppt_a_max':max(x[3] for x in configs),
            'isc_mppt_a_max':max(x[4] for x in configs),
            'per_inverter':configs,
            'cold_voc_check_c':-10
        }
    return None


def calc_design(payload):
    eq=equipment(); modules=eq['modules']; inverters=eq['inverters']
    mi=int(payload.get('module_index',0))
    if mi<0 or mi>=len(modules): raise ValueError('Módulo no válido.')
    m=modules[mi]
    monthly=float(payload.get('consumption_monthly_kwh') or 0)
    annual_input=float(payload.get('consumption_annual_kwh') or 0)
    annual=annual_input if annual_input>0 else monthly*12
    calculation_method=str(payload.get('calculation_method') or 'consumption').lower().strip()
    if calculation_method not in ('consumption','consumption_or_check','grid_capacity'):
        calculation_method='consumption'
    grid_available=float(payload.get('grid_available_kw') or 0)
    grid_dc_ac_ratio=float(payload.get('grid_dc_ac_ratio') or 1.20)
    if grid_dc_ac_ratio<=0: grid_dc_ac_ratio=1.20
    area=float(payload.get('area_m2') or 0)
    savings=float(payload.get('savings_pct') or 0)
    yield_factor=float(payload.get('yield_kwh_kwp_year') or DEFAULT_YIELD_KWH_KWP_YEAR)
    losses_pct=float(payload.get('losses_pct') or DEFAULT_LOSSES_PCT)
    solar_hsp=float(payload.get('solar_hsp') or 0)
    solar_source=str(payload.get('solar_source') or 'Factor de producción manual')
    area_restriction=str(payload.get('area_restriction','true')).lower() in ('1','true','yes','si','sí','on')
    phase=str(payload.get('system_phase') or 'TRIFASICO').upper()
    if phase not in ('MONOFASICO','BIFASICO','TRIFASICO'): raise ValueError('Tipo de sistema no válido. Seleccione MONOFÁSICO, BIFÁSICO o TRIFÁSICO.')
    if calculation_method in ('consumption','consumption_or_check') and annual<=0: raise ValueError('Ingrese un consumo mensual o anual válido.')
    if calculation_method=='grid_capacity' and grid_available<=0: raise ValueError('La Capacidad disponible reportada por OR debe ser mayor que cero para calcular por capacidad disponible.')
    if savings<0 or savings>100: raise ValueError('El porcentaje de ahorro debe estar entre 0 y 100 %.')
    if yield_factor<=0: raise ValueError('El factor de producción debe ser mayor que cero.')
    if losses_pct<0 or losses_pct>=100: raise ValueError('Las pérdidas deben estar entre 0 y menos de 100 %.')
    ma=module_area(m)
    if not ma: raise ValueError('El módulo seleccionado no tiene dimensiones verificadas.')
    power_w=float(m['power_w'])
    if solar_hsp>0:
        yield_factor=solar_hsp*365.0*(1-losses_pct/100.0); solar_mode=True
    else: solar_mode=False
    if calculation_method=='grid_capacity':
        # The OR-reported available capacity is an AC connection/export limit.
        # The requested DC field is derived from the selected design DC/AC ratio.
        target_ac_kw=grid_available
        target_kwh=0.0
        required_kwp=target_ac_kw*grid_dc_ac_ratio
        required_modules=math.ceil(required_kwp*1000.0/power_w) if required_kwp>0 else 0
    else:
        target_ac_kw=None
        target_kwh=annual*savings/100.0
        required_kwp=target_kwh/yield_factor if target_kwh>0 else 0.0
        required_modules=math.ceil(required_kwp*1000.0/power_w) if required_kwp>0 else 0
    max_modules_area=math.floor(area/ma) if area>0 else 0
    selected_modules=min(required_modules,max_modules_area) if area_restriction else required_modules
    dc_kwp=selected_modules*power_w/1000.0
    occupied=selected_modules*ma
    remaining=max(0.0,area-occupied) if area>0 else None
    achieved_kwh=dc_kwp*yield_factor
    achieved_savings=achieved_kwh/annual*100.0 if annual>0 else 0.0
    area_limited=area_restriction and selected_modules<required_modules

    # Phase filter is driven EXCLUSIVELY by the Fases column in the supplied workbook.
    phase_candidates=[(idx,v) for idx,v in enumerate(inverters) if str(v.get('phase_class','')).upper()==phase]
    ii_raw=payload.get('inverter_index'); selected_inv=None; candidates=[]
    # If a manual index is supplied, it must belong to the selected phase.
    if ii_raw not in (None,''):
        ii=int(ii_raw)
        if ii<0 or ii>=len(inverters): raise ValueError('Inversor no válido.')
        v=inverters[ii]
        if str(v.get('phase_class','')).upper()!=phase:
            raise ValueError(f"El inversor {v.get('manufacturer','')} {v.get('model','')} pertenece a {v.get('phase_class','')} según la base y no corresponde al sistema {phase}.")
        # Determine how many identical units are required by the registered DC/AC limits.
        ac=float(v.get('ac_kw') or 0); maxdc=float(v.get('max_dc_kw') or 0)
        qty=max(1,math.ceil(dc_kwp/maxdc)) if maxdc and dc_kwp else 1
        if ac and dc_kwp/(qty*ac)>1.5: qty=math.ceil(dc_kwp/(1.5*ac))
        cfg=_string_config_for_inverter(v,m,selected_modules,qty)
        if cfg is None: raise ValueError('El inversor seleccionado no admite la configuración preliminar de módulos/strings según los límites registrados de su ficha técnica.')
        selected_inv={'index':ii,**v,'quantity':qty,'ac_kw_total':qty*ac,'dc_ac_ratio':dc_kwp/(qty*ac) if ac else None,'string_config':cfg}
    else:
        for idx,v in phase_candidates:
            try:
                ac=float(v.get('ac_kw') or 0); maxdc=float(v.get('max_dc_kw') or 0)
                if ac<=0: continue
                minqty=max(1,math.ceil(dc_kwp/maxdc)) if maxdc and dc_kwp else 1
                for qty in range(minqty, minqty+6):
                    total_ac=qty*ac
                    ratio=dc_kwp/total_ac if total_ac else 999
                    if ratio<0.8 or ratio>1.5: continue
                    cfg=_string_config_for_inverter(v,m,selected_modules,qty)
                    if not cfg: continue
                    # Prefer fewer units, then ratio near 1.2, then lower supplied-base price.
                    unit_price=float(v.get('price_cop') or 0)
                    total_price=qty*unit_price
                    candidates.append((qty,abs(ratio-1.2),total_price,idx,v,cfg))
                    break
            except Exception: continue
        candidates.sort(key=lambda x:(x[0],x[1],x[2]))
        if candidates:
            qty,_,_,idx,v,cfg=candidates[0]; ac=float(v.get('ac_kw') or 0)
            selected_inv={'index':idx,**v,'quantity':qty,'ac_kw_total':qty*ac,'dc_ac_ratio':dc_kwp/(qty*ac) if ac else None,'string_config':cfg}
        elif calculation_method=='grid_capacity' and grid_available>0:
            # If the theoretical DC target cannot be matched by a feasible inverter/string layout,
            # step the module count down until a real inverter configuration exists without exceeding
            # the OR-reported AC capacity. This keeps the result physically selectable.
            for trial_modules in range(required_modules,0,-1):
                trial_dc=trial_modules*power_w/1000.0
                local=[]
                for idx,v in phase_candidates:
                    try:
                        ac=float(v.get('ac_kw') or 0); maxdc=float(v.get('max_dc_kw') or 0)
                        if ac<=0 or ac>grid_available+1e-9: continue
                        for qty in range(1,10):
                            total_ac=qty*ac
                            if total_ac>grid_available+1e-9: break
                            if maxdc and trial_dc>qty*maxdc: continue
                            ratio=trial_dc/total_ac if total_ac else 999
                            if ratio<0.8 or ratio>1.5: continue
                            cfg=_string_config_for_inverter(v,m,trial_modules,qty)
                            if cfg:
                                local.append((qty,abs(ratio-grid_dc_ac_ratio),total_ac,idx,v,cfg)); break
                    except Exception: continue
                if local:
                    local.sort(key=lambda x:(x[1],x[2],x[0],x[3]))
                    qty,_,total_ac,idx,v,cfg=local[0]
                    selected_modules=trial_modules
                    dc_kwp=trial_dc
                    occupied=selected_modules*ma
                    remaining=max(0.0,area-occupied) if area>0 else None
                    achieved_kwh=dc_kwp*yield_factor
                    achieved_savings=achieved_kwh/annual*100.0 if annual>0 else 0.0
                    area_limited=area_restriction and selected_modules<required_modules
                    selected_inv={'index':idx,**v,'quantity':qty,'ac_kw_total':total_ac,'dc_ac_ratio':ratio,'string_config':cfg}
                    break
    if calculation_method=='grid_capacity' and selected_inv:
        actual_ac=float(selected_inv.get('ac_kw_total') or 0)
        if actual_ac > grid_available + 1e-9:
            if ii_raw not in (None,''):
                raise ValueError(f'El inversor seleccionado suma {actual_ac:.3f} kW AC y supera la capacidad disponible reportada por el OR ({grid_available:.3f} kW).')
            # Automatic selection must never authorize more AC than the OR reports.
            selected_inv=None
            feasible=[c for c in candidates if float(c[4].get('ac_kw') or 0)*c[0] <= grid_available+1e-9]
            if feasible:
                qty,_,_,idx,v,cfg=sorted(feasible,key=lambda x:(x[1],float(x[4].get('ac_kw') or 0)*x[0],x[0],x[3]))[0]
                total_ac=qty*float(v.get('ac_kw') or 0)
                selected_inv={'index':idx,**v,'quantity':qty,'ac_kw_total':total_ac,'dc_ac_ratio':dc_kwp/total_ac if total_ac else None,'string_config':cfg}
            else:
                # If the theoretical DC target cannot be paired with a feasible inverter under the OR AC cap,
                # reduce modules until a technically valid configuration exists.
                found=False
                for trial_modules in range(required_modules,0,-1):
                    trial_dc=trial_modules*power_w/1000.0
                    local=[]
                    for idx,v in phase_candidates:
                        try:
                            ac=float(v.get('ac_kw') or 0); maxdc=float(v.get('max_dc_kw') or 0)
                            if ac<=0 or ac>grid_available+1e-9: continue
                            for qty in range(1,10):
                                total_ac=qty*ac
                                if total_ac>grid_available+1e-9: break
                                if maxdc and trial_dc>qty*maxdc: continue
                                ratio=trial_dc/total_ac if total_ac else 999
                                if ratio<0.8 or ratio>1.5: continue
                                cfg=_string_config_for_inverter(v,m,trial_modules,qty)
                                if cfg:
                                    local.append((qty,abs(ratio-grid_dc_ac_ratio),total_ac,idx,v,cfg)); break
                        except Exception: continue
                    if local:
                        local.sort(key=lambda x:(x[1],x[2],x[0],x[3]))
                        qty,_,total_ac,idx,v,cfg=local[0]
                        selected_modules=trial_modules; dc_kwp=trial_dc
                        occupied=selected_modules*ma; remaining=max(0.0,area-occupied) if area>0 else None
                        achieved_kwh=dc_kwp*yield_factor; achieved_savings=achieved_kwh/annual*100.0 if annual>0 else 0.0
                        area_limited=area_restriction and selected_modules<required_modules
                        selected_inv={'index':idx,**v,'quantity':qty,'ac_kw_total':total_ac,'dc_ac_ratio':ratio,'string_config':cfg}
                        found=True; break
                if not found:
                    raise ValueError(f'No se encontró una configuración técnicamente válida sin superar la capacidad disponible reportada por el OR ({grid_available:.3f} kW).')

    phase_note=None
    if not phase_candidates:
        phase_note=f'La base suministrada no contiene inversores clasificados como {phase}.'
    # Technical warning for the supplied 2F records: manufacturer datasheets identify these MIN models as single-phase.
    if phase=='BIFASICO' and phase_candidates:
        mism=[v for _,v in phase_candidates if v.get('technical_connection')=='Monofásico']
        if mism:
            phase_note='Advertencia técnica: la columna Fases de la base suministrada clasifica estos equipos como 2F, pero la ficha técnica del fabricante los identifica como monofásicos. Verificar compatibilidad con la red bifásica específica antes de aprobar el diseño.'

    electrical={'status':'NO_INVERTER'}
    if selected_inv and selected_modules:
        cfg=selected_inv.get('string_config')
        if cfg:
            electrical={'status':'PRELIMINAR','modules_per_string':cfg['modules_per_string'],'strings':cfg['strings_total'],'voc_string_v':cfg['voc_string_v'],'vmp_string_v':cfg['vmp_string_v'],'strings_per_mppt':cfg['strings_per_mppt_max'],'current_mppt_a':cfg['current_mppt_a_max'],'isc_mppt_a':cfg['isc_mppt_a_max'],'cold_voc_check_c':cfg['cold_voc_check_c'],'inverters':selected_inv['quantity']}
        else:
            electrical={'status':'NO_VALID_STRING','message':'No se encontró una configuración preliminar de strings compatible con los límites de tensión, corriente y capacidad de MPPT registrados en la ficha técnica.'}

    # OFF-GRID: size the battery bank automatically from daily energy demand and the selected battery database record.
    system_type=str(payload.get('system_type') or 'ON-GRID').upper()
    battery_result=None
    if system_type=='OFF-GRID':
        bats=batteries()
        if not bats:
            raise ValueError('No existe una base de datos de baterías disponible.')
        storage_hours=max(0.25,float(payload.get('battery_storage_hours') or 2.0))
        dc_kwp=float(dc_kwp or 0)
        ac_required=float(selected_inv.get('ac_kw_total') or 0) if selected_inv else 0

        def battery_calc(bat):
            usable=float(bat.get('usable_capacity_kwh') or 0)
            nominal=float(bat.get('capacity_kwh') or 0)
            if usable<=0 and nominal>0:
                usable=nominal*float(bat.get('recommended_dod_pct') or 80.0)/100.0
            if usable<=0:
                return None
            required=dc_kwp*storage_hours
            qe=max(1,math.ceil(required/usable))
            cp=float(bat.get('recommended_charge_power_kw') or 0)
            dp=float(bat.get('recommended_discharge_power_kw') or 0)
            qc=max(1,math.ceil(dc_kwp/cp)) if cp>0 and dc_kwp>0 else 1
            qd=max(1,math.ceil(ac_required/dp)) if dp>0 and ac_required>0 else 1
            qty=max(qe,qc,qd)
            mp=bat.get('max_parallel')
            if mp and qty>int(mp):
                return None
            total=qty*float(bat.get('price_cop') or 0)
            return {'usable':usable,'nominal':nominal,'required':required,'qty_energy':qe,'qty_charge':qc,'qty_discharge':qd,'quantity':qty,'total_price':total}

        mode=str(payload.get('battery_selection_mode') or 'auto').lower()
        bi_raw=payload.get('battery_index')
        recommended=[]
        for i,bat0 in enumerate(bats):
            r0=battery_calc(bat0)
            if r0:
                recommended.append((r0['total_price'], float(bat0.get('price_per_kwh_cop') or 1e99), r0['quantity'], i, r0))
        if not recommended:
            raise ValueError('Ninguna batería de la base suministrada cumple simultáneamente los criterios de energía, potencia y paralelo máximo para esta configuración.')
        recommended.sort(key=lambda x:(x[0],x[1],x[2],x[3]))
        suggested_index=recommended[0][3]
        if mode=='manual':
            if bi_raw in (None,''):
                raise ValueError('Seleccione una batería cuando el modo de selección sea MANUAL.')
            bi=int(bi_raw)
            if bi<0 or bi>=len(bats): raise ValueError('Batería no válida.')
        else:
            bi=suggested_index
        bat=bats[bi]
        calc=battery_calc(bat)
        if not calc:
            raise ValueError('La batería seleccionada no cumple los límites técnicos registrados para esta configuración. Revise la referencia o vuelva a selección automática.')
        qty_energy,qty_charge,qty_discharge,qty=calc['qty_energy'],calc['qty_charge'],calc['qty_discharge'],calc['quantity']
        usable_per_battery,nominal_per_battery=calc['usable'],calc['nominal']
        required_usable_kwh=calc['required']
        installed_nominal=qty*nominal_per_battery
        installed_usable=qty*usable_per_battery
        battery_result={'index':bi,'selection_mode':mode,'suggested_index':suggested_index,'is_suggested':bi==suggested_index,**bat,'quantity':qty,'dc_kwp_reference':dc_kwp,'storage_hours_per_kwp':storage_hours,'required_usable_kwh':required_usable_kwh,'usable_capacity_per_battery_kwh':usable_per_battery,'required_nominal_kwh':required_usable_kwh/(float(bat.get('recommended_dod_pct') or 80.0)/100.0),'installed_kwh':installed_nominal,'installed_usable_kwh':installed_usable,'qty_energy':qty_energy,'qty_charge_power':qty_charge,'qty_discharge_power':qty_discharge,'pv_charge_power_kw':dc_kwp,'inverter_ac_power_kw':ac_required,'total_price_cop':qty*float(bat.get('price_cop') or 0),'price_per_kwh_cop':float(bat.get('price_per_kwh_cop') or 0),'suggested_total_price_cop':recommended[0][0],'design_method':'kWp DC × horas equivalentes de almacenamiento + límites de potencia de carga/descarga de la ficha técnica'}
    return {
        'version':VER,
        'inputs':{'consumption_monthly_kwh':monthly if monthly>0 else None,'consumption_annual_kwh':annual,'calculation_method':calculation_method,'grid_available_kw':grid_available if calculation_method in ('grid_capacity','consumption_or_check') else None,'grid_dc_ac_ratio':grid_dc_ac_ratio if calculation_method=='grid_capacity' else None,'area_m2':area,'savings_pct':savings,'yield_kwh_kwp_year':yield_factor,'area_restriction':area_restriction,'losses_pct':losses_pct,'solar_hsp':solar_hsp,'solar_source':solar_source,'solar_mode':solar_mode,'system_phase':phase,'system_type':system_type,'battery_storage_hours':storage_hours if system_type=='OFF-GRID' else None},
        'module':{'index':mi,**m,'area_m2':ma},
        'target':{'target_kwh_year':target_kwh,'required_kwp':required_kwp,'required_modules':required_modules,'max_modules_area':max_modules_area,'target_ac_kw':target_ac_kw,'basis':calculation_method},
        'area':{'available_area_m2':area,'module_area_m2':ma,'max_modules':max_modules_area,'occupied_area_m2':occupied,'remaining_area_m2':remaining,'status':'OK' if (not area_restriction or selected_modules<=max_modules_area) else 'AREA_LIMIT'},
        'system':{'modules':selected_modules,'dc_kwp':dc_kwp,'area_occupied_m2':occupied,'area_remaining_m2':remaining,'achieved_kwh_year':achieved_kwh,'achieved_savings_pct':achieved_savings,'area_limited':area_limited,'phase':phase,'calculation_method':calculation_method,'grid_available_kw':grid_available if calculation_method in ('grid_capacity','consumption_or_check') else None,'ac_connection_limit_kw':grid_available if calculation_method in ('grid_capacity','consumption_or_check') else None},
        'inverter':selected_inv,'electrical':electrical,'phase_note':phase_note,'battery':battery_result,
        'note':'Los equipos utilizados provienen exclusivamente de la base de datos suministrada por el usuario. Los límites eléctricos incorporados se contrastan con fichas técnicas de fabricante cuando existe fuente registrada; la columna Fases de la base suministrada gobierna el filtro BIFÁSICO/TRIFÁSICO.'
    }

def ocr_invoice(data_url):
    try:
        import pytesseract
        from PIL import Image, ImageOps, ImageEnhance
    except Exception as e:
        raise ValueError('OCR no disponible en esta instalación: '+str(e))
    if not data_url or ',' not in data_url: raise ValueError('Archivo de imagen no válido.')
    raw=base64.b64decode(data_url.split(',',1)[1])
    if len(raw)>15*1024*1024: raise ValueError('La imagen supera 15 MB.')
    img=Image.open(io.BytesIO(raw)).convert('RGB')
    # Mild preprocessing improves printed invoice recognition without destroying digits.
    gray=ImageOps.grayscale(img)
    if gray.width < 1400:
        scale=1400/gray.width; gray=gray.resize((int(gray.width*scale),int(gray.height*scale)))
    gray=ImageEnhance.Contrast(gray).enhance(1.5)
    text=pytesseract.image_to_string(gray, lang='spa+eng', config='--psm 6')
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    # Prefer kWh figures close to consumption-related words; otherwise return candidates for user review.
    candidates=[]
    patterns=[
        r'(?:consumo|consumido|consumo\s+del\s+mes|energ[ií]a\s+consumida)[^\n]{0,80}?([0-9]{1,7}(?:[\.,][0-9]{1,3})?)\s*kwh',
        r'([0-9]{1,7}(?:[\.,][0-9]{1,3})?)\s*kwh'
    ]
    for pat in patterns:
        for match in re.finditer(pat,text,re.I):
            s=match.group(1).replace('.','').replace(',','.')
            try:
                val=float(s)
                if 1 <= val <= 100000: candidates.append(val)
            except: pass
    # Unique, ordered candidates.
    uniq=[]
    for x in candidates:
        if not any(abs(x-y)<1e-6 for y in uniq): uniq.append(x)
    suggested=uniq[0] if uniq else None
    return {'ok':True,'text':'\n'.join(lines),'candidates':uniq[:20],'suggested_monthly_kwh':suggested}



def ocr_rut(data_url, filename=''):
    """Extract common DIAN RUT fields from text PDFs or scanned RUTs.
    The extractor is deliberately conservative: it returns only fields that have
    a recognizable label/pattern and leaves the rest for user verification.
    """
    try:
        import pytesseract
        from PIL import Image, ImageOps, ImageEnhance
    except Exception as e:
        raise ValueError('OCR no disponible en esta instalación: '+str(e))
    if not data_url or ',' not in data_url: raise ValueError('Archivo RUT no válido.')
    raw=base64.b64decode(data_url.split(',',1)[1])
    if len(raw)>20*1024*1024: raise ValueError('El archivo supera 20 MB.')
    ext=os.path.splitext(filename or '')[1].lower(); texts=[]
    if ext=='.pdf' or data_url.lower().startswith('data:application/pdf'):
        try:
            import fitz
            doc=fitz.open(stream=raw,filetype='pdf')
            for page in doc:
                t=page.get_text('text') or ''
                if t.strip(): texts.append(t)
            # OCR each page when the PDF has no usable text, and also OCR pages
            # that contain very little text (common for scanned RUTs).
            for page,t in zip(doc,texts if len(texts)==len(doc) else ['']*len(doc)):
                if len((t or '').strip())<80:
                    pix=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False)
                    img=Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')
                    gray=ImageOps.grayscale(img); gray=ImageEnhance.Contrast(gray).enhance(1.7)
                    texts.append(pytesseract.image_to_string(gray,lang='spa+eng',config='--psm 6'))
        except Exception as e:
            raise ValueError('No fue posible procesar el PDF del RUT: '+str(e))
    else:
        try: img=Image.open(io.BytesIO(raw)).convert('RGB')
        except Exception as e: raise ValueError('Imagen RUT no válida: '+str(e))
        if img.width<1800:
            scale=1800/img.width; img=img.resize((int(img.width*scale),int(img.height*scale)))
        gray=ImageOps.grayscale(img); gray=ImageEnhance.Contrast(gray).enhance(1.7)
        texts.append(pytesseract.image_to_string(gray,lang='spa+eng',config='--psm 6'))
    text='\n'.join(texts)
    def clean(v): return re.sub(r'\s+',' ',v or '').strip(' :;-|')
    fields={}
    # Normalize OCR noise while retaining the original text for diagnostics.
    norm=text.replace('\r','\n')
    norm=re.sub(r'[ \t]+',' ',norm)
    # NIT and DV.
    m=re.search(r'\bNIT\b[^0-9]{0,25}([0-9][0-9\. ]{5,16})(?:\s*[-–]\s*([0-9]))?',norm,re.I)
    if m:
        fields['clientNit']=re.sub(r'\D','',m.group(1))
        if m.group(2): fields['clientDv']=m.group(2)
    if 'clientDv' not in fields:
        m=re.search(r'\bDV\b[^0-9]{0,12}([0-9])\b',norm,re.I)
        if m: fields['clientDv']=m.group(1)

    # Generic label -> following text line extractor. It works with both
    # text PDFs where labels and values are adjacent and OCR line layouts.
    def after_label(patterns, max_chars=180):
        pat='|'.join(patterns)
        m=re.search(r'(?:'+pat+r')\s*[:\-]?\s*([^\n]{2,'+str(max_chars)+r'})',norm,re.I)
        return clean(m.group(1)) if m else ''

    fields['clientLegalName']=after_label([r'RAZ[ÓO]N\s+SOCIAL',r'NOMBRE\s+O\s+RAZ[ÓO]N\s+SOCIAL'])
    fields['clientTradeName']=after_label([r'NOMBRE\s+COMERCIAL'])
    fields['clientAddress']=after_label([r'DIRECCI[ÓO]N\s+PRINCIPAL',r'DIRECCION\s+PRINCIPAL'])
    fields['clientMunicipality']=after_label([r'MUNICIPIO',r'CIUDAD\s*/\s*MUNICIPIO'])
    fields['clientDepartment']=after_label([r'DEPARTAMENTO'])
    fields['clientPhone']=after_label([r'TEL[ÉE]FONO\s*1',r'TEL[ÉE]FONO',r'TELEFONO\s*1',r'TELEFONO',r'TEL'])
    fields['clientEmail']=after_label([r'CORREO\s+ELECTR[ÓO]NICO',r'CORREO',r'EMAIL',r'E-MAIL'])

    # DIAN RUT numbered fields: label and value may be separated by one or
    # more lines in the extracted PDF text.
    numbered={
      'clientNit': [r'5\.\s*N[uú]mero\s+de\s+Identificaci[oó]n\s+Tributaria\s*\(NIT\)',r'5\.\s*N[uú]mero\s+de\s+Identificaci[oó]n\s+Tributaria'],
      'clientDv': [r'6\.\s*DV\b'],
      'clientLegalName': [r'35\.\s*Raz[oó]n\s+social'],
      'clientTradeName': [r'36\.\s*Nombre\s+comercial'],
      'clientAddress': [r'41\.\s*Direcci[oó]n\s+principal'],
      'clientMunicipality': [r'40\.\s*Ciudad\s*/\s*Municipio'],
      'clientEmail': [r'42\.\s*Correo\s+electr[oó]nico'],
      'clientPhone': [r'44\.\s*Tel[eé]fono\s*1',r'44\.\s*Tel[eé]fono']
    }
    lines=[clean(x) for x in norm.split('\n') if clean(x)]
    for key,pats in numbered.items():
        if fields.get(key): continue
        for pat in pats:
            for i,line in enumerate(lines):
                if re.search(pat,line,re.I):
                    # Value can be on same line after the label or in the next 1-3 lines.
                    tail=re.sub(pat,'',line,flags=re.I).strip(' :|-')
                    candidates=[tail]+lines[i+1:i+4]
                    for cand in candidates:
                        cand=clean(cand)
                        if not cand: continue
                        if key=='clientNit':
                            mm=re.search(r'\d[\d\. ]{5,16}(?:[-–]\s*\d)?',cand)
                            if mm: fields[key]=re.sub(r'\D','',mm.group(0).split('-')[0]);
                            if mm and '-' in mm.group(0) and 'clientDv' not in fields: fields['clientDv']=mm.group(0).split('-')[-1].strip();
                        elif key=='clientDv':
                            mm=re.search(r'\b(\d)\b',cand)
                            if mm: fields[key]=mm.group(1)
                        elif key=='clientEmail':
                            mm=re.search(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}',cand,re.I)
                            if mm: fields[key]=mm.group(0)
                        elif key=='clientPhone':
                            mm=re.search(r'(?:\+?57\s*)?[0-9][0-9\s\-\(\)]{6,20}',cand)
                            if mm: fields[key]=clean(mm.group(0))
                        else:
                            # Avoid swallowing another numbered RUT field.
                            if not re.match(r'^\d+\.\s*',cand): fields[key]=cand
                        if fields.get(key): break
                if fields.get(key): break
            if fields.get(key): break

    # Final cleanups and safe fallbacks.
    if fields.get('clientNit'):
        fields['clientNit']=re.sub(r'\D','',fields['clientNit'])
    if fields.get('clientDv'):
        m=re.search(r'\d',fields['clientDv']); fields['clientDv']=m.group(0) if m else ''
    if fields.get('clientEmail'):
        m=re.search(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}',fields['clientEmail'],re.I); fields['clientEmail']=m.group(0) if m else ''
    if not fields.get('clientLegalName'):
        m=re.search(r'(?i)(?:persona\s+jur[ií]dica|persona\s+natural)[\s\S]{0,180}?\n\s*([A-ZÁÉÍÓÚÑ0-9][^\n]{3,100})',norm)
        if m: fields['clientLegalName']=clean(m.group(1))
    fields={k:v for k,v in fields.items() if v}
    return {'ok':True,'fields':fields,'text':text[:16000]}


def _find_chromium():
    """Find a Chromium-family browser, including the common per-user Windows installs."""
    env_candidates=[os.environ.get('CHROME_PATH',''),os.environ.get('EDGE_PATH','')]
    candidates=env_candidates + [
        shutil.which('chrome'), shutil.which('google-chrome'), shutil.which('chromium'),
        shutil.which('chromium-browser'), shutil.which('msedge'),
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    ]
    local=os.environ.get('LOCALAPPDATA','')
    if local:
        candidates += [
            os.path.join(local,'Google','Chrome','Application','chrome.exe'),
            os.path.join(local,'Microsoft','Edge','Application','msedge.exe'),
            os.path.join(local,'Chromium','Application','chrome.exe'),
        ]
    for c in candidates:
        if c and Path(c).exists(): return str(Path(c))
    return None

def _free_port():
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]

def _or_debug_dir():
    d=DATA/'or_debug'; d.mkdir(parents=True,exist_ok=True); return d

def _browser_visible_mode():
    # Local Windows/Linux desktop: visible browser is preferable while developing the OR automation.
    # Set ESUN_OR_HEADLESS=1 for servers without a desktop.
    forced=str(os.environ.get('ESUN_OR_HEADLESS','')).strip().lower()
    if forced in ('1','true','yes','on'): return False
    if forced in ('0','false','no','off'): return True
    return os.name=='nt'

def _launch_cdp_browser(url, tag):
    """Launch a fresh Chromium profile and connect through DevTools, with diagnostics."""
    try: import websocket
    except Exception: raise RuntimeError('Falta websocket-client. Ejecute start_local.bat para instalar las dependencias del proyecto.')
    chrome=_find_chromium()
    if not chrome:
        raise RuntimeError('No se encontró Chrome/Edge/Chromium. En Windows se buscan también las instalaciones de usuario en %LOCALAPPDATA%. Configure CHROME_PATH si usa una instalación personalizada.')
    port=0; profile=tempfile.mkdtemp(prefix='esun_or_'); proc=None; ws=None
    visible=_browser_visible_mode(); log_path=_or_debug_dir()/f'{tag}_browser.log'
    log=open(log_path,'w',encoding='utf-8',errors='replace')
    args=[chrome,
          '--no-first-run','--no-default-browser-check','--disable-popup-blocking','--no-sandbox','--remote-allow-origins=*',
          '--disable-background-networking','--disable-dev-shm-usage','--disable-gpu',
          '--disable-features=Translate,OptimizationHints',
          '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
          f'--user-data-dir={profile}','--window-size=1440,1100']
    if not visible: args.insert(1,'--headless=new')
    args.append(url)
    try:
        creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0) if os.name=='nt' else 0
        proc=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=creationflags)
        version=None; target=None; last_error=''
        deadline=time.time()+35
        while time.time()<deadline:
            if proc.poll() is not None:
                log.flush()
                try: details=log_path.read_text(encoding='utf-8',errors='replace')[-4000:]
                except Exception: details=''
                raise RuntimeError(f'El navegador terminó al iniciar (código {proc.returncode}). Revisar {log_path.name}. {details[-800:]}')
            # Chromium may choose a different debugging port when --remote-debugging-port=0.
            # Read the actual DevTools endpoint from the browser log instead of assuming the port.
            try:
                log.flush(); logtxt=log_path.read_text(encoding='utf-8',errors='replace')
                m=re.search(r'DevTools listening on ws://127\.0\.0\.1:(\d+)/',logtxt)
                if m: port=int(m.group(1))
            except Exception: pass
            if port:
                for endpoint in ('/json/version','/json/list','/json'):
                    try:
                        raw=urllib.request.urlopen(f'http://127.0.0.1:{port}{endpoint}',timeout=1.5).read().decode('utf-8')
                        data=json.loads(raw)
                        if endpoint=='/json/version': version=data
                        elif isinstance(data,list):
                            target=next((x for x in data if x.get('type')=='page' and x.get('webSocketDebuggerUrl')),None)
                        if target: break
                    except Exception as ex:
                        last_error=str(ex)
            if target: break
            time.sleep(.25)
        if not target:
            log.flush()
            details=log_path.read_text(encoding='utf-8',errors='replace')[-4000:] if log_path.exists() else ''
            raise RuntimeError(f'Chrome/Edge fue encontrado pero DevTools no abrió una pestaña en 35 s. Puerto detectado {port or "no disponible"}. Navegador: {chrome}. Último error: {last_error}. Revise {log_path.name}.')
        ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=30,origin='http://127.0.0.1')
        ws._esun_events=[]; ws._esun_tag=tag; ws._esun_debug_dir=str(_or_debug_dir())
        # Enable domains needed both for interaction and for diagnosing the GIS network calls.
        for method in ('Runtime.enable','Page.enable','Network.enable'):
            try:
                cid=int(time.time()*1000000)%2147483647
                ws.send(json.dumps({'id':cid,'method':method,'params':{}}))
                ws.settimeout(.5)
                for _ in range(6):
                    try:
                        msg=json.loads(ws.recv()); ws._esun_events.append(msg)
                        if msg.get('id')==cid: break
                    except Exception: break
                ws.settimeout(30)
            except Exception: pass
        # Explicit navigation is more reliable than passing the URL only on the Chromium command line:
        # some Chromium builds expose an initial about:blank target before committing the requested page.
        try:
            cid=int(time.time()*1000000)%2147483647
            ws.send(json.dumps({'id':cid,'method':'Page.navigate','params':{'url':url}}))
            deadline=time.time()+10
            while time.time()<deadline:
                msg=json.loads(ws.recv()); ws._esun_events.append(msg)
                if msg.get('id')==cid: break
        except Exception as ex:
            raise RuntimeError(f'No fue posible navegar al portal del OR mediante DevTools: {ex}')
        deadline=time.time()+25
        while time.time()<deadline:
            try:
                state=_cdp_eval(ws,'({href:location.href,ready:document.readyState,title:document.title})')
                if state and state.get('href') and state.get('href')!='about:blank' and state.get('ready') in ('interactive','complete'): break
            except Exception: pass
            time.sleep(.4)
        return proc,ws,profile,log,{'browser':chrome,'port':port,'visible':visible,'version':version or {},'debug_log':str(log_path)}
    except Exception:
        try: log.close()
        except Exception: pass
        if proc:
            try: proc.terminate(); proc.wait(timeout=2)
            except Exception:
                try: proc.kill()
                except Exception: pass
        shutil.rmtree(profile,ignore_errors=True)
        raise

def _cdp_eval(ws, expression, await_promise=False):
    import websocket
    cid=int(time.time()*1000000)%2147483647
    ws.send(json.dumps({'id':cid,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True,'awaitPromise':await_promise}}))
    deadline=time.time()+25
    while time.time()<deadline:
        msg=json.loads(ws.recv())
        if getattr(ws,'_esun_events',None) is not None: ws._esun_events.append(msg)
        if msg.get('id')==cid:
            if 'exceptionDetails' in msg.get('result',{}):
                ex=msg.get('result',{}).get('exceptionDetails',{}).get('exception',{}) or {}
                raise RuntimeError(ex.get('description') or ex.get('value') or 'El navegador no pudo ejecutar la consulta.')
            return msg.get('result',{}).get('result',{}).get('value')
    raise TimeoutError('Tiempo de espera agotado consultando el OR.')

def _cdp_mouse_click(ws, x, y):
    import websocket
    base=int(time.time()*1000000)%2147483647
    for i,(typ,button) in enumerate((('mousePressed','left'),('mouseReleased','left'))):
        ws.send(json.dumps({'id':base+i,'method':'Input.dispatchMouseEvent','params':{'type':typ,'x':float(x),'y':float(y),'button':button,'clickCount':1}}))
    ws.settimeout(0.25)
    try:
        for _ in range(4):
            msg=json.loads(ws.recv())
            if getattr(ws,'_esun_events',None) is not None: ws._esun_events.append(msg)
    except Exception: pass
    finally: ws.settimeout(25)

def _cdp_wait(ws, seconds=2.0):
    time.sleep(max(0.1, float(seconds)))

def _save_or_debug_snapshot(ws, tag):
    """Save DOM + screenshot + observed network URLs so portal changes can be diagnosed without guessing."""
    d=_or_debug_dir(); stamp=time.strftime('%Y%m%d_%H%M%S'); base=d/f'{tag}_{stamp}'
    try:
        html=_cdp_eval(ws,"document.documentElement?.outerHTML||''") or ''
        (base.with_suffix('.html')).write_text(str(html)[:1000000],encoding='utf-8')
    except Exception: pass
    try:
        import websocket, base64 as _b64
        cid=int(time.time()*1000000)%2147483647; ws.send(json.dumps({'id':cid,'method':'Page.captureScreenshot','params':{'format':'png','captureBeyondViewport':False}})); ws.settimeout(5)
        while True:
            msg=json.loads(ws.recv())
            if getattr(ws,'_esun_events',None) is not None: ws._esun_events.append(msg)
            if msg.get('id')==cid:
                data=msg.get('result',{}).get('data')
                if data:(base.with_suffix('.png')).write_bytes(_b64.b64decode(data))
                break
    except Exception: pass
    try:
        urls=[]
        for e in getattr(ws,'_esun_events',[]):
            if e.get('method') in ('Network.requestWillBeSent','Network.responseReceived'):
                u=e.get('params',{}).get('request',{}).get('url') or e.get('params',{}).get('response',{}).get('url')
                if u and u not in urls: urls.append(u)
        (base.with_suffix('.network.txt')).write_text('\n'.join(urls[-500:]),encoding='utf-8')
    except Exception: pass
    return str(base)

def _browser_set_input(ws, selector, value):
    expr = r"""(()=>{
      const e=document.querySelector(%s); if(!e) throw new Error('No se encontró el campo solicitado.');
      const proto=e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      const d=Object.getOwnPropertyDescriptor(proto,'value');
      if(d&&d.set)d.set.call(e,%s); else e.value=%s;
      for(const type of ['input','change','blur']) e.dispatchEvent(new Event(type,{bubbles:true}));
      e.focus(); return {tag:e.tagName,id:e.id,name:e.name,value:e.value};
    })()""" % (json.dumps(selector),json.dumps(str(value)),json.dumps(str(value)))
    return _cdp_eval(ws,expr)

def _browser_click_text(ws, text, *, exact=False, preferred=None):
    expr = r"""(()=>{
      const needle=%s, exact=%s, pref=%s;
      const norm=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toLowerCase();
      const n=norm(needle);
      const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
      const els=[...document.querySelectorAll('button,[role=button],[role=option],mat-option,mat-select,.mat-mdc-select,.mat-select,select,input[type=submit],a')].filter(visible);
      const scored=els.map(e=>{
        const txt=norm((e.innerText||e.textContent||'')+' '+(e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')+' '+(e.id||''));
        let score=0;
        if(exact ? txt===n : txt.includes(n)) score+=100;
        if(pref && (e.matches(pref)||e.querySelector(pref))) score+=35;
        if(/consultar|buscar|lupa/.test(n) && /consultar|buscar|search|magnif|lupa/.test(txt)) score+=20;
        return {e,score,txt};
      }).filter(x=>x.score>=100).sort((a,b)=>b.score-a.score);
      const x=scored[0]; if(!x) return null;
      x.e.click(); return {tag:x.e.tagName,id:x.e.id,cls:String(x.e.className||''),text:(x.txt||'').slice(0,180)};
    })()""" % (json.dumps(text), 'true' if exact else 'false', json.dumps(preferred or ''))
    return _cdp_eval(ws,expr)

def _browser_choose_select(ws, label_text, option_text):
    expr = r"""(()=>{
      const label=%s, option=%s;
      const norm=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/\s+/g,' ').trim().toLowerCase();
      const L=norm(label), O=norm(option);
      const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
      const controls=[...document.querySelectorAll('select,[role=combobox],mat-select,.mat-mdc-select,.mat-select')].filter(visible);
      let c=controls.find(e=>{const p=norm((e.getAttribute('aria-label')||'')+' '+(e.getAttribute('placeholder')||'')+' '+(e.parentElement?.innerText||''));return p.includes(L);});
      if(!c)c=controls.shift();
      if(!c)throw new Error('No se encontró la lista desplegable: '+label);
      if(c.tagName==='SELECT'){
        const opt=[...c.options].find(o=>norm(o.textContent)===O || norm(o.textContent).includes(O));
        if(!opt)throw new Error('No se encontró la opción '+option+' en '+label+'.');
        c.value=opt.value; c.dispatchEvent(new Event('input',{bubbles:true})); c.dispatchEvent(new Event('change',{bubbles:true}));
        return {mode:'native',value:c.value,text:opt.textContent};
      }
      c.click(); return {mode:'custom',tag:c.tagName,id:c.id,cls:String(c.className||'')};
    })()""" % (json.dumps(label_text),json.dumps(option_text))
    r=_cdp_eval(ws,expr)
    if r and r.get('mode')=='custom':
        _cdp_wait(ws,.35)
        opt=_browser_click_text(ws,option_text,exact=False,preferred='[role=option],mat-option')
        if not opt: opt=_browser_click_text(ws,option_text,exact=False)
        if not opt: raise RuntimeError('No fue posible seleccionar '+option_text+'.')
    return r

def _browser_click_air_e_search(ws):
    expr = r"""(()=>{
      const norm=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
      const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
      const inputs=[...document.querySelectorAll('input')].filter(visible);
      let nic=inputs.find(e=>norm((e.placeholder||'')+' '+(e.name||'')+' '+(e.id||'')+' '+(e.getAttribute('aria-label')||'')).includes('nic')) || inputs[0];
      if(!nic)throw new Error('No se encontró el campo NIC de AIR-E.');
      const nr=nic.getBoundingClientRect();
      const controls=[...document.querySelectorAll('button,a,[role=button],i,span,svg')].filter(visible);
      const near=controls.map(e=>{const r=e.getBoundingClientRect(),txt=norm((e.innerText||e.textContent||'')+' '+(e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')+' '+(e.className||''));
        const dx=r.left-nr.right,dy=Math.abs((r.top+r.height/2)-(nr.top+nr.height/2)); let score=0;
        if(/search|buscar|lupa|magnif/.test(txt))score+=100;
        if(dx>=-15&&dx<180)score+=60-Math.min(Math.abs(dx),60)/2;
        if(dy<35)score+=35;
        if(r.width<=70&&r.height<=70)score+=10;
        return {e,score};}).sort((a,b)=>b.score-a.score)[0];
      if(!near||near.score<60)throw new Error('No se encontró la lupa de consulta de AIR-E junto al NIC.');
      near.e.click(); return {x:near.e.getBoundingClientRect().left+near.e.getBoundingClientRect().width/2,y:near.e.getBoundingClientRect().top+near.e.getBoundingClientRect().height/2};
    })()"""
    return _cdp_eval(ws,expr)

def _browser_click_blinking_transformer(ws, timeout=18):
    deadline=time.time()+timeout; last=None
    while time.time()<deadline:
        expr = r"""(()=>{
          const norm=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
          const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'&&r.width>1&&r.height>1};
          const maps=[...document.querySelectorAll('[id*=map],[class*=map],[class*=leaflet],[class*=ol-],[class*=google]')].filter(visible);
          const mr=maps.map(e=>({e,r:e.getBoundingClientRect()})).sort((a,b)=>(b.r.width*b.r.height)-(a.r.width*a.r.height))[0];
          const mapRect=mr?.r;
          const all=[...document.querySelectorAll('img,svg,svg circle,svg path,canvas,div,span,button,a,[role=button]')].filter(visible);
          const candidates=[];
          for(const e of all){
            const r=e.getBoundingClientRect(); if(!mapRect)continue;
            const inside=r.left>=mapRect.left-3&&r.right<=mapRect.right+3&&r.top>=mapRect.top-3&&r.bottom<=mapRect.bottom+3;
            if(!inside||r.width>140||r.height>140)continue;
            const s=getComputedStyle(e), cls=norm(String(e.className||'')), id=norm(e.id||''), title=norm((e.getAttribute('title')||'')+' '+(e.getAttribute('aria-label')||'')+' '+(e.getAttribute('alt')||''));
            const anim=(s.animationName&&s.animationName!=='none')||(s.animationDuration&&s.animationDuration!=='0s');
            let score=0;
            if(anim)score+=90;
            if(/blink|pulse|titil|parpade|flash/.test(cls+' '+id+' '+title))score+=100;
            if(/selected|active|highlight|focus|current/.test(cls+' '+id))score+=35;
            if(/transform|trafo|transformador/.test(cls+' '+id+' '+title))score+=40;
            if(e.tagName==='IMG'&&/marker|icon|transform|trafo/.test((e.src||'')+' '+title))score+=25;
            if(r.width<=70&&r.height<=70)score+=12;
            if(r.width<=35&&r.height<=35)score+=15;
            if(score>40)candidates.push({score,x:r.left+r.width/2,y:r.top+r.height/2,cls:cls.slice(0,180),title:title.slice(0,120),anim});
          }
          candidates.sort((a,b)=>b.score-a.score);
          if(candidates.length){const c=candidates[0];return {found:true,x:c.x,y:c.y,score:c.score,cls:c.cls,title:c.title,anim:c.anim};}
          return {found:false};
        })()"""
        r=_cdp_eval(ws,expr); last=r
        if r and r.get('found'):
            _cdp_mouse_click(ws,r['x'],r['y']); _cdp_wait(ws,1.5); return r
        _cdp_wait(ws,.7)
    raise RuntimeError('No fue posible identificar automáticamente el transformador titilando en el mapa del OR. El portal abrió correctamente, pero el marcador no pudo ser distinguido de forma segura.' + ((' Último estado: '+str(last)) if last else ''))

def _browser_wait_for_result(ws, timeout=15):
    deadline=time.time()+timeout; text=''
    while time.time()<deadline:
        text=_cdp_eval(ws,"document.body.innerText||document.body.textContent||''") or ''
        if re.search(r'POTENCIA\s*NOMINAL|CAPACIDAD\s*DISPONIBLE|POTENCIA\s*M[ÁA]XIMA',text,re.I): return text
        time.sleep(.6)
    return text

def _playwright_browser_path():
    system_path = _find_chromium()
    if system_path:
        return system_path
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        try:
            bundled = pw.chromium.executable_path
        finally:
            pw.stop()
        if bundled and Path(bundled).exists():
            return str(Path(bundled))
    except Exception:
        pass
    return None


def _playwright_visible_mode():
    forced=str(os.environ.get('ESUN_OR_HEADLESS','')).strip().lower()
    if forced in ('1','true','yes','on'): return False
    if forced in ('0','false','no','off'): return True
    return os.name=='nt'


def _pw_save_diagnostics(page, tag, network, extra=None):
    d=_or_debug_dir(); stamp=time.strftime('%Y%m%d_%H%M%S'); base=d/f'{tag}_{stamp}'
    try: (base.with_suffix('.html')).write_text(page.content()[:1500000],encoding='utf-8')
    except Exception: pass
    try: page.screenshot(path=str(base.with_suffix('.png')),full_page=False)
    except Exception: pass
    try:
        payload=[]; seen=set()
        for item in network:
            key=(item.get('method'),item.get('url'))
            if key in seen: continue
            seen.add(key); payload.append(f"{item.get('method','GET')} {item.get('status','')} {item.get('url','')}")
        (base.with_suffix('.network.txt')).write_text('\n'.join(payload[-1000:]),encoding='utf-8')
    except Exception: pass
    if extra is not None:
        try: (base.with_suffix('.json')).write_text(json.dumps(extra,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception: pass
    return str(base)


def _pw_find_nic_input(page, hint):
    inputs=page.locator('input:visible'); count=inputs.count()
    for i in range(count):
        e=inputs.nth(i)
        try:
            meta=e.evaluate("e=>({placeholder:e.placeholder||'',name:e.name||'',id:e.id||'',aria:e.getAttribute('aria-label')||''})")
            txt=' '.join(str(meta.get(k,'')) for k in ('placeholder','name','id','aria')).lower()
            if 'nic' in txt: return e
        except Exception: pass
    if count: return inputs.nth(0)
    raise RuntimeError(f'No se encontró el campo {hint} en el portal del OR.')


def _pw_click_air_e_search(page, nic_input):
    handle=nic_input.element_handle()
    result=page.evaluate(r'''(nic)=>{
      const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
      const nr=nic.getBoundingClientRect();
      const controls=[...document.querySelectorAll('button,a,[role=button],i,span,svg')].filter(visible);
      const scored=controls.map(e=>{const r=e.getBoundingClientRect();const txt=((e.innerText||'')+' '+(e.getAttribute('aria-label')||'')+' '+(e.getAttribute('title')||'')+' '+(e.className||'')).toLowerCase();const dx=r.left-nr.right,dy=Math.abs((r.top+r.height/2)-(nr.top+nr.height/2));let score=0;if(/search|buscar|lupa|magnif/.test(txt))score+=100;if(dx>=-20&&dx<220)score+=60-Math.min(Math.abs(dx),60)/2;if(dy<45)score+=35;if(r.width<=80&&r.height<=80)score+=10;return {score,x:r.left+r.width/2,y:r.top+r.height/2,txt};}).sort((a,b)=>b.score-a.score)[0];
      if(!scored||scored.score<60)return null;return {x:scored.x,y:scored.y,score:scored.score,txt:scored.txt};
    }''', handle)
    if not result: raise RuntimeError('No se encontró la lupa de consulta de AIR-E junto al NIC.')
    page.mouse.click(result['x'],result['y']); return result


def _pw_choose_afinia_option(page, label, option):
    combos=page.locator('[role="combobox"]:visible, select:visible'); n=combos.count()
    if n:
        idx=0 if 'tipo' in label.lower() else 1
        if idx>=n: idx=n-1
        c=combos.nth(idx); tag=c.evaluate('e=>e.tagName')
        if tag=='SELECT':
            opts=c.locator('option')
            for i in range(opts.count()):
                o=opts.nth(i)
                if option.lower() in (o.inner_text() or '').lower(): c.select_option(value=o.get_attribute('value')); return
        else:
            c.click(); page.wait_for_timeout(250)
            opt=page.get_by_text(option,exact=True).last
            if opt.count(): opt.click(); return
            opt=page.get_by_text(re.compile(re.escape(option),re.I)).last
            if opt.count(): opt.click(); return
    raise RuntimeError(f'No fue posible seleccionar {option} en {label} de AFINIA.')


def _pw_click_afinia_consultar(page):
    btn=page.get_by_role('button',name=re.compile(r'^\s*consultar\s*$',re.I)).last
    if btn.count(): btn.click(); return
    btn=page.get_by_text(re.compile(r'^\s*consultar\s*$',re.I)).last
    if btn.count(): btn.click(); return
    raise RuntimeError('No se encontró el botón CONSULTAR de AFINIA.')


def _pw_find_map_box(page):
    """Return the largest visible GIS/map rectangle in viewport coordinates."""
    try:
        return page.evaluate(r'''()=>{
          const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&parseFloat(s.opacity||'1')>0&&r.width>200&&r.height>150};
          const els=[...document.querySelectorAll('[id*=map],[class*=map],[class*=leaflet],[class*=ol-],[class*=arcgis],[class*=esri],canvas')].filter(visible);
          const a=els.map(e=>{const r=e.getBoundingClientRect();return {x:Math.max(0,r.left),y:Math.max(0,r.top),width:Math.min(innerWidth,r.right)-Math.max(0,r.left),height:Math.min(innerHeight,r.bottom)-Math.max(0,r.top),area:r.width*r.height,tag:e.tagName,id:e.id||'',cls:String(e.className||'').slice(0,160)}}).filter(x=>x.width>200&&x.height>150).sort((a,b)=>b.area-a.area)[0];
          return a||{x:0,y:0,width:innerWidth,height:innerHeight,area:innerWidth*innerHeight,tag:'VIEWPORT'};
        }''')
    except Exception:
        return None


def _pw_color_components(arr, mode):
    """Return connected colored components likely to be transformer triangles."""
    import numpy as np
    r,g,b=arr[:,:,0],arr[:,:,1],arr[:,:,2]
    if mode == 'green':
        mask=(g>70)&(g>r*1.20)&(g>b*1.08)&(r<165)&(b<180)
    elif mode == 'light':
        white=(r>218)&(g>215)&(b>215)&((np.maximum.reduce([r,g,b])-np.minimum.reduce([r,g,b]))<45)
        yellow=(r>210)&(g>175)&(b<95)&(r>g*0.95)
        mask=white|yellow
    else:
        mask=np.zeros(r.shape,dtype=bool)
    # Small dilation bridges anti-aliased triangle edges without joining distant markers.
    for _ in range(1):
        mask=mask|np.roll(mask,1,0)|np.roll(mask,-1,0)|np.roll(mask,1,1)|np.roll(mask,-1,1)
    h,w=mask.shape; seen=np.zeros(mask.shape,dtype=np.uint8); out=[]
    ys,xs=np.nonzero(mask)
    for sy,sx in zip(ys,xs):
        if seen[sy,sx]: continue
        stack=[(int(sy),int(sx))]; seen[sy,sx]=1; pts=[]
        while stack:
            y,x=stack.pop(); pts.append((y,x))
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    if not(dx or dy): continue
                    yy,xx=y+dy,x+dx
                    if 0<=yy<h and 0<=xx<w and mask[yy,xx] and not seen[yy,xx]:
                        seen[yy,xx]=1; stack.append((yy,xx))
        area=len(pts)
        if area<80: continue
        py=np.fromiter((q[0] for q in pts),dtype=np.int32); px=np.fromiter((q[1] for q in pts),dtype=np.int32)
        x0,x1=int(px.min()),int(px.max())+1; y0,y1=int(py.min()),int(py.max())+1
        ww,hh=x1-x0,y1-y0
        if not (15<=ww<=65 and 15<=hh<=65): continue
        density=area/(ww*hh)
        if not (0.28<=density<=0.90): continue
        # Filled upright triangle signature: rows generally grow toward the base.
        row=[]
        for yy in range(y0,y1):
            n=int(np.sum(py==yy))
            if n: row.append(n)
        if len(row)<8: continue
        rw=np.array(row,dtype=float)
        mid=max(1,len(rw)//2)
        top=float(rw[:mid].mean()); bot=float(rw[mid:].mean())
        tri_ratio=bot/(top+1e-6)
        # A triangle has a substantially narrower top than bottom; tolerate icon rasterization.
        shape_score=0
        if tri_ratio>1.20: shape_score+=40
        if abs(ww-hh)<=14: shape_score+=20
        if 0.42<=density<=0.72: shape_score+=20
        if shape_score<40: continue
        out.append({'x':float(px.mean()),'y':float(py.mean()),'bbox':[x0,y0,x1,y1],
                    'area':area,'density':density,'tri_ratio':tri_ratio,'shape_score':shape_score,'mode':mode})
    return out


def _pw_visual_transformer_candidates(png_bytes, clip_box):
    """Detect upright green/white/yellow triangular transformer markers."""
    try:
        from PIL import Image
        import numpy as np, io
        arr=np.asarray(Image.open(io.BytesIO(png_bytes)).convert('RGB'))
        out=[]
        for mode in ('green','light'):
            for c in _pw_color_components(arr,mode):
                c=dict(c); c['x']+=float(clip_box['x']); c['y']+=float(clip_box['y'])
                c['score']=c['area']+c['shape_score']*12
                out.append(c)
        return sorted(out,key=lambda z:z['score'],reverse=True)[:20]
    except Exception:
        return []


def _pw_transition_pairs(prev_png, curr_png, clip_box):
    """Match a green triangle in one frame with a light (white/yellow) triangle at the same place in another frame."""
    try:
        from PIL import Image
        import numpy as np, io, math
        a=np.asarray(Image.open(io.BytesIO(prev_png)).convert('RGB'))
        b=np.asarray(Image.open(io.BytesIO(curr_png)).convert('RGB'))
        if a.shape!=b.shape: return []
        greens=_pw_color_components(a,'green'); lights=_pw_color_components(b,'light')
        # Also test reverse direction (light -> green) because capture can start in either phase.
        reverse_greens=_pw_color_components(b,'green'); reverse_lights=_pw_color_components(a,'light')
        pairs=[]
        def pair(gs,ls,phase):
            for g in gs:
                gx,gy=g['x'],g['y']; gw=(g['bbox'][2]-g['bbox'][0]); gh=(g['bbox'][3]-g['bbox'][1])
                best=None
                for l in ls:
                    lx,ly=l['x'],l['y']; lw=(l['bbox'][2]-l['bbox'][0]); lh=(l['bbox'][3]-l['bbox'][1])
                    d=math.hypot(gx-lx,gy-ly)
                    if d>12: continue
                    if abs(gw-lw)>18 or abs(gh-lh)>18: continue
                    score=1000-d*55-abs(gw-lw)*8-abs(gh-lh)*8+min(g['shape_score'],l['shape_score'])*4
                    if best is None or score>best[0]: best=(score,l)
                if best:
                    l=best[1]
                    pairs.append({'score':float(best[0]),'x':float(clip_box['x']+(gx+lx)/2),
                                  'y':float(clip_box['y']+(gy+ly)/2),'distance':float(math.hypot(gx-lx,gy-ly)),
                                  'green_bbox':g['bbox'],'light_bbox':l['bbox'],'phase':phase,
                                  'green':g,'light':l,'mode':'green↔white/yellow triangle transition'})
        pair(greens,lights,'green-to-light'); pair(reverse_greens,reverse_lights,'light-to-green')
        return sorted(pairs,key=lambda z:z['score'],reverse=True)[:10]
    except Exception:
        return []


def _pw_difference_triangle_candidates(prev_png, curr_png, clip_box):
    """Find a small triangular region that changed color between two screenshots.
    This is the primary detector because the blinking marker may overlap another green marker.
    It uses only Pillow + NumPy, so no OpenCV dependency is required.
    """
    try:
        from PIL import Image
        import numpy as np, io
        a=np.asarray(Image.open(io.BytesIO(prev_png)).convert('RGB')).astype(np.int16)
        b=np.asarray(Image.open(io.BytesIO(curr_png)).convert('RGB')).astype(np.int16)
        if a.shape!=b.shape: return []
        diff=np.max(np.abs(a-b),axis=2)
        mask=diff>=30
        # Remove isolated pixels and build connected components with an 8-neighbour flood fill.
        # The blinking triangle is a compact component ~30x30 px in the real AIR-E visor.
        h,w=mask.shape; seen=np.zeros(mask.shape,dtype=np.uint8); out=[]
        ys,xs=np.nonzero(mask)
        for sy,sx in zip(ys,xs):
            if seen[sy,sx]: continue
            stack=[(int(sy),int(sx))]; seen[sy,sx]=1; pts=[]
            while stack:
                y,x=stack.pop(); pts.append((y,x))
                for dy in (-1,0,1):
                    for dx in (-1,0,1):
                        if not(dx or dy): continue
                        yy,xx=y+dy,x+dx
                        if 0<=yy<h and 0<=xx<w and mask[yy,xx] and not seen[yy,xx]:
                            seen[yy,xx]=1; stack.append((yy,xx))
            area=len(pts)
            if not (60<=area<=1800): continue
            py=np.fromiter((q[0] for q in pts),dtype=np.int32); px=np.fromiter((q[1] for q in pts),dtype=np.int32)
            x0,x1=int(px.min()),int(px.max())+1; y0,y1=int(py.min()),int(py.max())+1
            bw,bh=x1-x0,y1-y0
            if not (14<=bw<=65 and 14<=bh<=65): continue
            density=area/(bw*bh)
            if density<0.25: continue
            rows=np.bincount(py-y0,minlength=bh).astype(float)
            mid=max(1,bh//2); top=rows[:mid].mean(); bottom=rows[mid:].mean()
            tri_ratio=bottom/(top+1e-6)
            # The real icon is an upright filled triangle: narrow top, wide base.
            if tri_ratio<1.12: continue
            # Require a color transition from green to light or vice versa in this exact box.
            pa=a[y0:y1,x0:x1].astype(np.int32); pb=b[y0:y1,x0:x1].astype(np.int32)
            def greenish(z):
                r,g,bl=z[:,:,0],z[:,:,1],z[:,:,2]
                return int(((g>65)&(g>r*1.18)&(g>bl*1.05)).sum())
            def lightish(z):
                r,g,bl=z[:,:,0],z[:,:,1],z[:,:,2]
                return int((((r>205)&(g>200)&(bl>200))|((r>205)&(g>165)&(bl<120))).sum())
            ga,la=greenish(pa),lightish(pa); gb,lb=greenish(pb),lightish(pb)
            transition=(ga>40 and lb>40) or (gb>40 and la>40)
            if not transition: continue
            cx=float(px.mean()); cy=float(py.mean())
            out.append({'score':float(area+tri_ratio*100+density*100),'x':float(clip_box['x']+cx),'y':float(clip_box['y']+cy),
                        'bbox':[x0,y0,x1,y1],'area':area,'density':density,'tri_ratio':tri_ratio,
                        'mode':'temporal pixel-difference green↔white/yellow'})
        return sorted(out,key=lambda z:z['score'],reverse=True)[:12]
    except Exception:
        return []

def _pw_point_panel_text(page):
    """Read ONLY the visible left-side PUNTO panel, including same-origin iframes."""
    script="""()=>{
      const norm=s=>(s||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toUpperCase();
      const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&parseFloat(s.opacity||'1')>0&&r.width>80&&r.height>40};
      const labels=['CODIGO','MATRICULA','DIRECCION','LONGITUD','LATITUD','POTENCIA NOMINAL','VOLTAJE NOMINAL','POTENCIA MAXIMA DECLARADA','CAPACIDAD DISPONIBLE'];
      const candidates=[];
      for(const e of [...document.querySelectorAll('aside,section,div,article')]){
        if(!visible(e))continue;
        const r=e.getBoundingClientRect(), text=(e.innerText||'').trim(), nt=norm(text);
        const hits=labels.filter(x=>nt.includes(x)).length;
        if(r.left<Math.min(innerWidth*0.52,620)&&hits>=3&&text.length<12000)candidates.push({text,hits,area:r.width*r.height,left:r.left,top:r.top,width:r.width,height:r.height});
      }
      candidates.sort((a,b)=>b.hits-a.hits||a.area-b.area);
      return candidates.length?candidates[0].text:'';
    }"""
    def one(frame):
        try:
            txt=frame.evaluate(script) or ''
            if txt and re.search(r'CODIGO|MATRICULA|DIRECCION|POTENCIA\s*NOMINAL|CAPACIDAD\s*DISPONIBLE',txt,re.I): return txt
        except Exception: pass
        return ''
    txt=one(page)
    if txt:return txt
    try:
        for fr in page.frames:
            if fr==page.main_frame: continue
            txt=one(fr)
            if txt:return txt
    except Exception: pass
    return ''


def _pw_local_blink_candidate(page, x, y, radius=320):
    """After zoom, track the blinking marker around the original geographic point.
    The marker becomes larger after zoom, so this detector deliberately does not
    impose the small 15-65 px pre-zoom size restriction.
    """
    try:
        from PIL import Image
        import numpy as np, io, math
        png=page.screenshot(full_page=False)
        im=Image.open(io.BytesIO(png)).convert('RGB')
        x0=max(0,int(x-radius)); y0=max(0,int(y-radius)); x1=min(im.width,int(x+radius)); y1=min(im.height,int(y+radius))
        crop=im.crop((x0,y0,x1,y1))
        arr=np.asarray(crop)
        r,g,b=arr[:,:,0],arr[:,:,1],arr[:,:,2]
        green=(g>65)&(g>r*1.12)&(g>b*1.04)&(r<190)
        light=((r>205)&(g>205)&(b>205)&((np.maximum.reduce([r,g,b])-np.minimum.reduce([r,g,b]))<60)) | ((r>205)&(g>165)&(b<125)&(r>g*0.92))
        # Look at a compact neighborhood around the expected point and compare
        # green/light occupancy in a disk; this is robust when the icon scales.
        cx=int(x-x0); cy=int(y-y0)
        best=None
        for yy in range(max(0,cy-45),min(arr.shape[0],cy+46),5):
            for xx in range(max(0,cx-45),min(arr.shape[1],cx+46),5):
                yy0=max(0,yy-28); yy1=min(arr.shape[0],yy+29); xx0=max(0,xx-28); xx1=min(arr.shape[1],xx+29)
                gm=float(green[yy0:yy1,xx0:xx1].mean()); lm=float(light[yy0:yy1,xx0:xx1].mean())
                score=max(gm,lm)*100 - abs(xx-cx)*0.15-abs(yy-cy)*0.15
                if best is None or score>best[0]: best=(score,xx+x0,yy+y0,gm,lm)
        return {'x':float(best[1]),'y':float(best[2]),'green_score':best[3],'light_score':best[4],'score':best[0]} if best else None
    except Exception:
        return None

def _pw_detect_transition(page, clip, frames, max_age=3.0):
    """Collect transition candidates from recent screenshot pairs without clicking."""
    import io
    from PIL import Image
    png=page.screenshot(full_page=False)
    im=Image.open(io.BytesIO(png)).convert('RGB')
    x=max(0,int(clip['x'])); y=max(0,int(clip['y']))
    x2=min(im.width,int(clip['x']+clip['width'])); y2=min(im.height,int(clip['y']+clip['height']))
    if x2<=x or y2<=y:return [],None
    crop=im.crop((x,y,x2,y2)); buf=io.BytesIO(); crop.save(buf,format='PNG'); curr=buf.getvalue()
    candidates=[]
    for old_t,old_png in frames[-12:]:
        if time.time()-old_t<=max_age:
            candidates.extend(_pw_difference_triangle_candidates(old_png,curr,{'x':x,'y':y}))
            candidates.extend(_pw_transition_pairs(old_png,curr,{'x':x,'y':y}))
    frames.append((time.time(),curr))
    if len(frames)>16: del frames[:-16]
    uniq=[]
    for c in sorted(candidates,key=lambda z:z.get('score',0),reverse=True):
        if any((c['x']-u['x'])**2+(c['y']-u['y'])**2<144 for u in uniq): continue
        uniq.append(c)
    return uniq, curr


def _pw_zoom_to_marker(page, x, y, levels=3):
    """Zoom the GIS map directly around the blinking transformer."""
    page.mouse.move(float(x),float(y))
    # First give the map a real pointer-down so wheel events are owned by the GIS.
    try: page.mouse.down(); page.mouse.up()
    except Exception: pass
    for _ in range(levels):
        page.mouse.move(float(x),float(y))
        page.mouse.wheel(0,-700)
        page.wait_for_timeout(650)
    page.wait_for_timeout(1200)


def _pw_click_blinking_transformer(page, timeout=90):
    """Detect the unique blinking green↔white/yellow transformer, zoom around it,
    re-track it at the enlarged scale, click it, then verify the PUNTO panel.
    """
    deadline=time.time()+timeout; clip=None; frames=[]; diagnostic_frames=[]; last={}; initial=None
    try:
        clip=_pw_find_map_box(page)
        if not clip: raise RuntimeError('No se pudo determinar el área del mapa.')
        # Phase 1: establish the geographic target from the actual color transition.
        while time.time()<deadline and initial is None:
            candidates,curr=_pw_detect_transition(page,clip,frames,max_age=4.0)
            if curr: diagnostic_frames.append(curr)
            if candidates:
                # Prefer true temporal transition candidates over static color candidates.
                initial=sorted(candidates,key=lambda c:(1 if 'green↔white' in str(c.get('mode','')) else 0,c.get('score',0)),reverse=True)[0]
                last={'phase':'initial_detection','candidate':initial}; break
            page.wait_for_timeout(220)
        if initial is None: raise RuntimeError('No se detectó el triángulo que alterna verde↔blanco/amarillo.')

        ox,oy=float(initial['x']),float(initial['y'])
        _pw_zoom_to_marker(page,ox,oy,levels=3)

        # Phase 2: after zoom, track the same point. The enlarged icon can be >65 px,
        # therefore use a focused color-occupancy tracker rather than the pre-zoom shape filter.
        target=None; recent=[]; local_deadline=min(deadline,time.time()+28)
        while time.time()<local_deadline:
            c=_pw_local_blink_candidate(page,ox,oy,radius=340)
            if c: recent.append(c)
            # Capture several frames and look for a real green/light alternation in the focused ROI.
            png=page.screenshot(full_page=False); diagnostic_frames.append(png)
            if len(recent)>=2:
                a,b=recent[-2],recent[-1]
                if (a['green_score']>0.035 and b['light_score']>0.035) or (a['light_score']>0.035 and b['green_score']>0.035):
                    target=b; break
            if c and c['score']>3.5: target=c
            page.wait_for_timeout(220)
        if target is None: target={'x':ox,'y':oy}

        # Try the focused coordinate first, then a small cross around the detected center.
        tx,ty=float(target['x']),float(target['y'])
        attempts=[]
        for dx,dy in [(0,0),(-8,0),(8,0),(0,-8),(0,8),(-12,-12),(12,-12),(-12,12),(12,12)]:
            attempts.append((tx+dx,ty+dy))
        # Also include original cursor position because GIS wheel zoom normally keeps
        # the geographic point under the mouse stationary.
        attempts.append((ox,oy))
        seen=set(); attempts=[a for a in attempts if not ((round(a[0]),round(a[1])) in seen or seen.add((round(a[0]),round(a[1]))))]

        for px,py in attempts:
            page.mouse.move(px,py); page.wait_for_timeout(120)
            # Native click plus a JS-dispatched pointer/mouse sequence increases compatibility
            # with GIS canvases without relying on DOM marker elements.
            page.mouse.click(px,py,delay=120)
            page.wait_for_timeout(1300)
            panel=_pw_point_panel_text(page)
            if panel and re.search(r'CODIGO|MATRICULA|DIRECCION|POTENCIA\s*NOMINAL|CAPACIDAD\s*DISPONIBLE',panel,re.I):
                target.update({'x':px,'y':py,'detector':'temporal green↔white/yellow + focused zoom tracker','click_x':px,'click_y':py,'panel_verified':True,'zoom_levels':3,'panel_text':panel})
                return target
            # If the GIS needs a second event while the marker is in the alternate phase, click again.
            page.wait_for_timeout(700); page.mouse.click(px,py,delay=80); page.wait_for_timeout(1500)
            panel=_pw_point_panel_text(page)
            if panel and re.search(r'CODIGO|MATRICULA|DIRECCION|POTENCIA\s*NOMINAL|CAPACIDAD\s*DISPONIBLE',panel,re.I):
                target.update({'x':px,'y':py,'detector':'temporal green↔white/yellow + focused zoom tracker','click_x':px,'click_y':py,'panel_verified':True,'zoom_levels':3,'panel_text':panel})
                return target
        last={'phase':'clicked_but_panel_not_verified','initial':initial,'target':target,'attempts':attempts}
    except Exception as e:
        last={'phase':'detector_exception','error':str(e),'initial':initial}
    try:
        d=_or_debug_dir(); stamp=time.strftime('%Y%m%d_%H%M%S')
        for i,png in enumerate(diagnostic_frames[-12:]): (d/f'air_e_zoom_frame_{stamp}_{i}.png').write_bytes(png)
        (d/f'air_e_zoom_debug_{stamp}.json').write_text(json.dumps(last,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception: pass
    raise RuntimeError('Se identificó el transformador intermitente y se aplicó zoom dirigido, pero no apareció la ficha PUNTO después de los clics de selección. Se guardó diagnóstico del zoom en data/or_debug.')


def _pw_green_icon_components(png_bytes, clip_box, template_path=None):
    """Detect AFINIA's green transformer icon from the supplied visual reference."""
    try:
        from PIL import Image
        import numpy as np, io
        arr=np.asarray(Image.open(io.BytesIO(png_bytes)).convert('RGB'))
        r,g,b=arr[:,:,0],arr[:,:,1],arr[:,:,2]
        green=(g>70)&(g>r*1.22)&(g>b*1.08)&(r<180)&(b<180)
        green=green|np.roll(green,1,0)|np.roll(green,-1,0)|np.roll(green,1,1)|np.roll(green,-1,1)
        h,w=green.shape; seen=np.zeros(green.shape,dtype=np.uint8); comps=[]
        ys,xs=np.nonzero(green)
        for sy,sx in zip(ys,xs):
            if seen[sy,sx]: continue
            stack=[(int(sy),int(sx))]; seen[sy,sx]=1; pts=[]
            while stack:
                y,x=stack.pop(); pts.append((y,x))
                for dy,dx in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                    yy,xx=y+dy,x+dx
                    if 0<=yy<h and 0<=xx<w and green[yy,xx] and not seen[yy,xx]:
                        seen[yy,xx]=1; stack.append((yy,xx))
            if len(pts)<12: continue
            py=np.fromiter((q[0] for q in pts),dtype=np.int32); px=np.fromiter((q[1] for q in pts),dtype=np.int32)
            x0,x1=int(px.min()),int(px.max())+1; y0,y1=int(py.min()),int(py.max())+1
            bw,bh=x1-x0,y1-y0
            if not (6<=bw<=90 and 6<=bh<=90): continue
            if bw>3*bh or bh>3*bw: continue
            comps.append((x0,y0,x1,y1,px,py))
        tm32=None
        if template_path and Path(template_path).exists():
            t=np.asarray(Image.open(template_path).convert('RGB'))
            tr,tg,tb=t[:,:,0],t[:,:,1],t[:,:,2]
            tm=(tg>70)&(tg>tr*1.18)&(tg>tb*1.05)&(tr<190)&(tb<190)
            ys2,xs2=np.nonzero(tm)
            if len(xs2):
                tx0,tx1=int(xs2.min()),int(xs2.max())+1; ty0,ty1=int(ys2.min()),int(ys2.max())+1
                tm=tm[ty0:ty1,tx0:tx1]
                tm32=np.asarray(Image.fromarray((tm*255).astype('uint8')).resize((32,32),Image.Resampling.NEAREST))>127
        out=[]
        for x0,y0,x1,y1,px,py in comps:
            sub=green[y0:y1,x0:x1]; sim=0.0
            if tm32 is not None:
                sm=np.asarray(Image.fromarray((sub*255).astype('uint8')).resize((32,32),Image.Resampling.NEAREST))>127
                inter=float(np.logical_and(sm,tm32).sum()); union=float(np.logical_or(sm,tm32).sum()); sim=inter/(union+1e-9)
            area=len(px); score=sim*1000+min(1.0,area/180.0)*80
            out.append({'x':float((x0+x1)/2+clip_box['x']),'y':float((y0+y1)/2+clip_box['y']),
                        'bbox':[x0+clip_box['x'],y0+clip_box['y'],x1+clip_box['x'],y1+clip_box['y']],
                        'area':area,'template_score':sim,'score':score})
        return sorted(out,key=lambda z:z['score'],reverse=True)[:30]
    except Exception:
        return []


def _pw_visible_body_text(page):
    try: return page.locator('body').inner_text(timeout=2500) or ''
    except Exception: return ''


def _pw_visible_text_any_frame(target):
    """Collect visible text from the target page and all frames."""
    texts=[]
    for fr in target.frames:
        try:
            t=fr.locator('body').inner_text(timeout=1800) or ''
            if t.strip(): texts.append(t)
        except Exception: pass
    try:
        t=target.locator('body').inner_text(timeout=1800) or ''
        if t.strip() and t not in texts: texts.append(t)
    except Exception: pass
    return '\n'.join(texts)


def _pw_find_afinia_summary_text(target):
    """Find the actual AFINIA summary after RESUMEN, not the compact popup."""
    script=r'''()=>{
      const norm=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();
      const vis=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&parseFloat(s.opacity||'1')>0&&r.width>220&&r.height>80};
      const keys=['INFORMACION DEL PUNTO DE CONEXION','MATRICULA TRANSFORMADOR','LONGITUD','LATITUD','TENSION SECUNDARIA','PROPIEDAD','TIPO DE AREA','FACTOR DE POTENCIA','KVA APROBADOS','KVA SOLICITADOS'];
      const cand=[];
      for(const e of [...document.querySelectorAll('div,section,aside,article,dialog,mat-dialog-container,table')]){
        if(!vis(e))continue;
        const t=(e.innerText||'').trim(), n=norm(t);
        const hits=keys.filter(k=>n.includes(k)).length;
        if(hits>=3 && t.length<30000)cand.push({t,hits,area:e.getBoundingClientRect().width*e.getBoundingClientRect().height});
      }
      cand.sort((a,b)=>b.hits-a.hits||a.area-b.area);
      return cand.length?cand[0].t:'';
    }'''
    pages=[target]
    try:
        for pg in target.context.pages:
            if pg not in pages: pages.append(pg)
    except Exception: pass
    for pg in pages:
        for fr in pg.frames:
            try:
                t=fr.evaluate(script) or ''
                if t and re.search(r'MATR[ÍI]CULA\s+TRANSFORMADOR|INFORMACI[ÓO]N\s+DEL\s+PUNTO\s+DE\s+CONEXI[ÓO]N',t,re.I):
                    return t,pg
            except Exception: pass
    return '',target


def _pw_click_visible_text_in_any_frame(target, pattern):
    """Click an exact visible text/button in any page/frame."""
    rx=re.compile(pattern,re.I)
    pages=[target]
    try:
        for pg in target.context.pages:
            if pg not in pages: pages.append(pg)
    except Exception: pass
    for pg in pages:
        for fr in pg.frames:
            try:
                loc=fr.get_by_role('button',name=rx)
                if loc.count():
                    loc.last.scroll_into_view_if_needed(); loc.last.click(timeout=5000); return pg
            except Exception: pass
            try:
                loc=fr.get_by_text(rx)
                if loc.count():
                    loc.last.scroll_into_view_if_needed(); loc.last.click(timeout=5000); return pg
            except Exception: pass
    return None


def _pw_click_afinia_green_transformer(page, timeout=75):
    """AFINIA: click green icon, click RESUMEN, then read the newly opened summary dialog/page."""
    deadline=time.time()+timeout; last={}; frames=[]
    template=str(ROOT/'afinia_transformer_icon_template.png')
    clip=_pw_find_map_box(page)
    if not clip: raise RuntimeError('No se pudo determinar el área del mapa de AFINIA.')
    while time.time()<deadline:
        png=page.screenshot(full_page=False); frames.append(png)
        candidates=_pw_green_icon_components(png,clip,template)
        last={'phase':'afinia_icon_detection','candidates':candidates[:12]}
        ordered=[c for c in candidates if c['template_score']>=0.20] or candidates
        for c in ordered[:18]:
            if time.time()>=deadline: break
            x,y=c['x'],c['y']
            before=[]
            try: before=list(page.context.pages)
            except Exception: pass
            page.mouse.click(x,y,delay=120)
            page.wait_for_timeout(900)
            body=_pw_visible_text_any_frame(page)
            if not re.search(r'C[ÓO]DIGO\s+TRANSFORMADOR|POTENCIA\s+NOMINAL\s*\(KVA\)|PORCENTAJE\s+OCUPADO',body,re.I):
                try: page.keyboard.press('Escape')
                except Exception: pass
                page.wait_for_timeout(180)
                continue
            clicked_page=_pw_click_visible_text_in_any_frame(page,r'^\s*RESUMEN\s*$')
            if not clicked_page:
                page.wait_for_timeout(900)
                clicked_page=_pw_click_visible_text_in_any_frame(page,r'^\s*RESUMEN\s*$')
            if not clicked_page:
                raise RuntimeError('Se seleccionó el transformador de AFINIA, pero no se encontró el botón RESUMEN en la ventana del transformador.')
            page.wait_for_timeout(900)
            summary=''; summary_page=clicked_page
            for _ in range(16):
                # Prefer a newly opened page, otherwise the page that contains the summary dialog.
                try:
                    for pg in page.context.pages:
                        if pg not in before:
                            summary,summary_page=_pw_find_afinia_summary_text(pg)
                            if summary: break
                except Exception: pass
                if not summary:
                    summary,summary_page=_pw_find_afinia_summary_text(clicked_page)
                if summary: break
                try:
                    for pg in page.context.pages:
                        summary,summary_page=_pw_find_afinia_summary_text(pg)
                        if summary: break
                except Exception: pass
                if summary: break
                page.wait_for_timeout(450)
            last.update({'phase':'afinia_summary','x':x,'y':y,'popup_text':body[:12000],
                         'summary_found':bool(summary),'summary_page_url':getattr(summary_page,'url','')})
            if summary:
                return {'x':x,'y':y,'icon':c,'summary_text':summary,'panel_verified':True,
                        'popup_text':body,'combined_text':(summary+'\n'+body),'summary_url':getattr(summary_page,'url','')}
        page.wait_for_timeout(450)
    try:
        d=_or_debug_dir(); stamp=time.strftime('%Y%m%d_%H%M%S')
        for i,png in enumerate(frames[-10:]): (d/f'afinia_icon_frame_{stamp}_{i}.png').write_bytes(png)
        (d/f'afinia_icon_debug_{stamp}.json').write_text(json.dumps(last,ensure_ascii=False,indent=2),encoding='utf-8')
        try:
            alltxt=[]
            for pg in page.context.pages:
                alltxt.append(f'URL: {pg.url}\n{_pw_visible_text_any_frame(pg)[:20000]}')
            (d/f'afinia_pages_text_{stamp}.txt').write_text('\n\n--- PAGE ---\n\n'.join(alltxt),encoding='utf-8')
        except Exception: pass
    except Exception: pass
    raise RuntimeError('No fue posible abrir RESUMEN y leer la ventana "Resumen del transformador seleccionado" de AFINIA.')

def _pw_wait_for_result(page, timeout=20):
    deadline=time.time()+timeout; text=''
    while time.time()<deadline:
        try: text=page.locator('body').inner_text(timeout=2000)
        except Exception: text=''
        if re.search(r'POTENCIA\s*NOMINAL|CAPACIDAD\s*DISPONIBLE|POTENCIA\s*M[ÁA]XIMA',text,re.I): return text
        page.wait_for_timeout(600)
    return text


def _or_browser_query_playwright(operator,nic):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError('Playwright no está instalado. Ejecute start_local.bat para instalar la dependencia.') from e
    browser_path=_playwright_browser_path()
    if not browser_path: raise RuntimeError('No se encontró Chrome/Edge/Chromium para Playwright. Configure CHROME_PATH o instale Chrome/Edge.')
    url='https://servicios.air-e.com/CREG174/' if operator=='AIR-E' else 'https://visor.confirma.com.co/#/'
    network=[]; pw=browser=None; context=page=None
    try:
        pw=sync_playwright().start(); visible=_playwright_visible_mode()
        launch_kwargs={'headless':not visible,'args':['--no-sandbox','--disable-dev-shm-usage','--disable-popup-blocking']}
        if browser_path: launch_kwargs['executable_path']=browser_path
        browser=pw.chromium.launch(**launch_kwargs)
        context=browser.new_context(viewport={'width':1440,'height':1100},locale='es-CO')
        page=context.new_page()
        page.on('request',lambda r: network.append({'kind':'request','method':r.method,'url':r.url,'resource':r.resource_type}))
        page.on('response',lambda r: network.append({'kind':'response','method':r.request.method,'status':r.status,'url':r.url,'resource':r.request.resource_type}))
        page.goto(url,wait_until='domcontentloaded',timeout=45000); page.wait_for_timeout(2500)
        if operator=='AIR-E':
            nic_input=_pw_find_nic_input(page,'NIC de AIR-E'); nic_input.fill(str(nic)); page.wait_for_timeout(300); _pw_click_air_e_search(page,nic_input)
        else:
            _pw_choose_afinia_option(page,'Tipo','Transformadores'); page.wait_for_timeout(700)
            _pw_choose_afinia_option(page,'Consultar por','NIC'); page.wait_for_timeout(500)
            nic_input=_pw_find_nic_input(page,'Ingrese el NIC de AFINIA'); nic_input.fill(str(nic)); page.wait_for_timeout(300); _pw_click_afinia_consultar(page)
        page.wait_for_timeout(4500)
        if operator=='AIR-E':
            marker=_pw_click_blinking_transformer(page,timeout=70); text=_pw_point_panel_text(page) or _pw_wait_for_result(page,timeout=20)
        else:
            marker=_pw_click_afinia_green_transformer(page,timeout=65); text=marker.get('summary_text','') or _pw_wait_for_result(page,timeout=20)
        if not text: raise RuntimeError('El OR no devolvió la ficha PUNTO legible después de seleccionar el transformador.')
        return text,marker
    except Exception as e:
        snap=_pw_save_diagnostics(page,f'{operator.lower().replace("-","_")}_playwright_failure',network,{'operator':operator,'nic':str(nic),'url':(page.url if page else ''),'title':(page.title() if page else ''),'error':str(e)}) if page else None
        detail=f'{e}'
        if snap: detail+=f' Diagnóstico Playwright guardado en data/or_debug ({Path(snap).name}.*).'
        raise RuntimeError(detail)
    finally:
        for obj in (page,context,browser):
            try:
                if obj: obj.close()
            except Exception: pass
        try:
            if pw: pw.stop()
        except Exception: pass


def _or_browser_query(operator,nic):
    operator=str(operator or '').upper()
    if operator not in ('AIR-E','AFINIA'): raise ValueError('Operador de Red no soportado.')
    return _or_browser_query_playwright(operator,nic)

def parse_or_result_text(text):
    t=str(text or '').replace('\xa0',' ')
    def clean(v): return re.sub(r'\s+',' ',str(v or '')).strip()
    def num(v):
        v=clean(v).replace(' ','')
        if ',' in v and '.' in v: v=v.replace('.','').replace(',','.') if v.rfind(',')>v.rfind('.') else v.replace(',','')
        elif ',' in v: v=v.replace(',','.')
        m=re.search(r'-?\d+(?:\.\d+)?',v); return float(m.group(0)) if m else None
    def find(ps):
        for ptn in ps:
            m=re.search(ptn,t,re.I|re.M)
            if m:return num(m.group(1))
        return None
    def find_text(ps):
        for ptn in ps:
            m=re.search(ptn,t,re.I|re.M)
            if m:return clean(m.group(1))
        return ''
    code=find_text([
        r'(?:C[ÓO]DIGO\s+TRANSFORMADOR|C[ÓO]DIGO)\s*[:\-]?\s*\n?\s*([A-Z0-9._/-]+)',
        r'(?:C[ÓO]DIGO\s+TRANSFORMADOR|C[ÓO]DIGO)\s+([A-Z0-9._/-]+)'])
    matricula=find_text([r'(?:MATR[ÍI]CULA|MATRICULA)\s*[:\-]?\s*\n?\s*([A-Z0-9._/-]+)'])
    address=find_text([r'(?:DIRECCI[ÓO]N)\s*[:\-]?\s*\n?\s*([^\n]+)'])
    secondary=find_text([
        r'(?:VOLTAJE\s*NOMINAL\s*[-–]?\s*TENSI[ÓO]N\s*SECUNDARIA|TENSI[ÓO]N\s*SECUNDARIA)\s*(?:\(V\))?\s*[:\-]?\s*\n?\s*([^\n]+)'])
    primary=find([r'(?:VOLTAJE\s*NOMINAL\s*[-–]?\s*TENSI[ÓO]N\s*PRIMARIA|TENSI[ÓO]N\s*PRIMARIA)\s*(?:\(KV\))?\s*[:\-]?\s*\n?\s*([0-9.,]+)'])
    kva=find([r'POTENCIA\s*NOMINAL\s*\(KVA\)\s*[:\-]?\s*\n?\s*([0-9.,]+)',r'POTENCIA\s*NOMINAL\s*[:\-]?\s*\n?\s*([0-9.,]+)\s*KVA'])
    existing=find([r'POTENCIA\s*M[ÁA]XIMA\s*DECLARADA\s*\(KW\)\s*[:\-]?\s*\n?\s*([0-9.,]+)',r'POTENCIA\s*M[ÁA]XIMA\s*DECLARADA\s*[:\-]?\s*\n?\s*([0-9.,]+)\s*KW'])
    available=find([r'CAPACIDAD\s*DISPONIBLE\s*\(KW\)\s*[:\-]?\s*\n?\s*([0-9.,]+)',r'CAPACIDAD\s*DISPONIBLE\s*[:\-]?\s*\n?\s*([0-9.,]+)\s*KW'])
    longitude=find([r'LONGITUD\s*[:\-]?\s*\n?\s*(-?[0-9.,]+)'])
    latitude=find([r'LATITUD\s*[:\-]?\s*\n?\s*(-?[0-9.,]+)'])
    # AFINIA's compact popup can expose percentage occupied rather than kW existing.
    occupied=find([r'PORCENTAJE\s*OCUPADO\s*[:\-]?\s*\n?\s*([0-9.,]+)\s*%?'])
    power_factor=find([r'FACTOR\s+DE\s+POTENCIA\s*[:\-]?\s*\n?\s*([0-9.,]+)'])
    kva_approved=find([r'KVA\s+APROBADOS\s*[:\-]?\s*\n?\s*([0-9.,]+)'])
    kva_requested=find([r'KVA\s+SOLICITADOS\s*[:\-]?\s*\n?\s*([0-9.,]+)'])
    def find_text(ps):
        for ptn in ps:
            m=re.search(ptn,t,re.I|re.M)
            if m:return clean(m.group(1))
        return None
    prop=find_text([r'PROPIEDAD\s*[:\-]?\s*\n?\s*([^\n]+)', r'PROPIETARIO\s*[:\-]?\s*\n?\s*([^\n]+)'])
    area_type=find_text([r'TIPO\s+DE\s+[ÁA]REA\s*[:\-]?\s*\n?\s*([^\n]+)', r'TIPO\s+AREA\s*[:\-]?\s*\n?\s*([^\n]+)'])
    return {'transformerKva':kva,'existingKw':existing,'reportedAvailableKw':available,'primaryKv':primary,'secondaryV':num(secondary),'secondaryVText':secondary,'transformerCode':code,'transformerMatricula':matricula,'address':address,'longitude':longitude,'latitude':latitude,'occupiedPct':occupied,'powerFactor':power_factor,'kvaApproved':kva_approved,'kvaRequested':kva_requested,'property':prop,'areaType':area_type}

def or_availability(operator,nic,project_ac_kw=0):
    operator=str(operator or '').upper(); nic=str(nic or '').strip()
    if not nic: raise ValueError('NIC requerido.')
    if operator not in ('AIR-E','AFINIA'): raise ValueError('Operador de Red no soportado.')
    text,marker=_or_browser_query(operator,nic); parse_text=text
    if operator=='AFINIA' and isinstance(marker,dict) and marker.get('combined_text'): parse_text=marker.get('combined_text')
    fields=parse_or_result_text(parse_text)
    if operator=='AFINIA' and fields.get('existingKw') is None:
        if fields.get('occupiedPct') is not None and fields.get('transformerKva') is not None:
            fields['existingKw']=fields['transformerKva']*fields['occupiedPct']/100.0
        elif fields.get('kvaApproved') is not None:
            fields['existingKw']=fields['kvaApproved']
    if fields.get('transformerKva') is None and fields.get('reportedAvailableKw') is None: raise RuntimeError('El portal no devolvió los campos de disponibilidad esperados después de seleccionar el transformador titilando.')
    return {'ok':True,'operator':operator,'nic':nic,'fields':fields,'regime':'SIN','source':'Sistema oficial del OR','sourceNote':(f'Datos consultados en AIR-E: NIC diligenciado automáticamente, consulta ejecutada y transformador intermitente seleccionado automáticamente.' if operator=='AIR-E' else 'Datos consultados en AFINIA: Tipo TRANSFORMADORES, Consultar por NIC, NIC diligenciado automáticamente, CONSULTAR ejecutado, icono verde del transformador seleccionado y RESUMEN abierto automáticamente.'),'marker':marker,'raw_excerpt':text[:16000]}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def _json(self,code,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode('utf-8'); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        p=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(p.query)
        try:
            if p.path=='/api/health': return self._json(200,{'ok':True,'version':VER,'port':PORT,'python':__import__('sys').version.split()[0]})
            if p.path=='/api/publicidad/config': return self._json(200,publicidad_config_status())
            if p.path=='/api/esuna/status': return self._json(200,_esuna_status())
            if p.path=='/api/esuna/proactive':
                seed=(q.get('seed') or [None])[-1]
                raw_exclude=(q.get('exclude') or [''])[-1]
                exclude=[x for x in raw_exclude.split(',') if x]
                raw_titles=(q.get('exclude_titles') or [''])[-1]
                exclude_titles=[urllib.parse.unquote(x) for x in raw_titles.split('|') if x]
                return self._json(200,esuna_proactive(seed,exclude,exclude_titles))
            if p.path=='/api/projects': return self._json(200,{'ok':True,'version':VER,'projects':_projects_read()})
            if p.path=='/api/equipment': return self._json(200,equipment())
            if p.path=='/api/batteries': return self._json(200,{'version':VER,'batteries':batteries()})
            if p.path=='/api/meters': return self._json(200,meters())
            if p.path=='/api/costs': return self._json(200,costs())
            if p.path=='/api/supplier-prices': return self._json(200,supplier_prices())
            if p.path=='/api/budget': return self._json(200,quote_budget({k:v[-1] for k,v in q.items()}))
            if p.path=='/api/design': return self._json(200,calc_design({k:v[-1] for k,v in q.items()}))
            if p.path=='/api/divipola': return self._json(200,divipola_locations())
            if p.path=='/api/solar/locations': return self._json(200,divipola_locations())
            if p.path=='/api/solar': return self._json(200,solar_by_municipality(q.get('code',[''])[0]))
            if p.path=='/api/or-availability': return self._json(200,or_availability(q.get('operator',[''])[0],q.get('nic',[''])[0],float(q.get('project_ac_kw',['0'])[0] or 0)))
            if p.path=='/api/legacy': return self._json(200,{'version':VER,'message':'V20 usa DIVIPOLA de Datos.gov.co para ubicación y el Atlas de Radiación Solar UPME/IDEAM 2005 como referencia cartográfica mensual.'})
        except Exception as e: return self._json(400,{'error':str(e)})
        return super().do_GET()
    def do_POST(self):
        p=urllib.parse.urlparse(self.path)
        try:
            if p.path=='/api/projects':
                n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
                action=str(payload.get('action','upsert')).strip().lower()
                if action=='upsert':
                    project=payload.get('project')
                    return self._json(200,{'ok':True,'version':VER,'project':_project_upsert(project)})
                if action=='replace_all':
                    projects=payload.get('projects')
                    if not isinstance(projects,list): raise ValueError('La colección de proyectos debe ser una lista.')
                    _projects_write(projects)
                    return self._json(200,{'ok':True,'version':VER,'projects':projects})
                if action=='delete':
                    return self._json(200,{'ok':True,'version':VER,'deleted':_project_delete(payload.get('id')),'projects':_projects_read()})
                raise ValueError('Acción de proyectos no reconocida.')
            if p.path in ('/api/publicidad/config','/api/publicidad/test'):
                n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
                if p.path=='/api/publicidad/config':
                    action=str(payload.get('action','save')).strip().lower()
                    if action=='clear': _clear_openai_key()
                    else: _save_openai_key(payload.get('openai_api_key',''))
                    return self._json(200,publicidad_config_status())
                return self._json(200,publicidad_test_openai())
            if p.path in ('/api/publicidad/ideas','/api/publicidad/marketing/chat'):
                n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n).decode('utf-8'))
                if p.path=='/api/publicidad/ideas': return self._json(200,publicidad_ideas(payload.get('user',''),int(payload.get('offset',0) or 0)))
                return self._json(200,publicidad_marketing_chat(payload.get('message',''),payload.get('history',[]),payload.get('user',''),payload.get('campaign')))
            if p.path=='/api/esuna/strategy':
                n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
                opportunity=payload.get('opportunity') or {}
                if not opportunity.get('title'): raise ValueError('Oportunidad requerida.')
                opportunity.setdefault('why_now', opportunity.get('desc') or 'La oportunidad combina una necesidad comercial con señales actuales del mercado fotovoltaico.')
                opportunity.setdefault('objective', opportunity.get('objective') or 'Generar demanda calificada y fortalecer el posicionamiento de E-SUN POWER.')
                opportunity.setdefault('audience', opportunity.get('audience') or 'Tomadores de decisión con una necesidad energética identificable.')
                opportunity.setdefault('customer_problem', opportunity.get('customer_problem') or opportunity.get('desc') or '')
                opportunity.setdefault('positioning', opportunity.get('positioning') or 'No solo instalamos paneles. Diseñamos sistemas.')
                opportunity.setdefault('value_proposition', opportunity.get('value_proposition') or 'Solución fotovoltaica diseñada alrededor de la necesidad real del cliente.')
                opportunity.setdefault('offer', opportunity.get('offer') or 'Diagnóstico energético inicial.')
                opportunity.setdefault('funnel', opportunity.get('funnel') or 'Contenido → conversación → diagnóstico → propuesta → seguimiento.')
                opportunity.setdefault('content_pillars', opportunity.get('content_pillars') or ['Educación energética','Tecnología FV','Ahorro y control','Ingeniería','Confianza'])
                opportunity.setdefault('campaign_sequence', opportunity.get('campaign_sequence') or ['Captar atención','Educar','Demostrar','Vencer objeciones','Convertir'])
                opportunity.setdefault('sales_route', opportunity.get('sales_route') or 'WhatsApp Business + reunión técnico-comercial.')
                opportunity.setdefault('competitive_angle', opportunity.get('competitive_angle') or 'Competir por criterio, diseño y evidencia; no solo por precio.')
                opportunity.setdefault('cta', opportunity.get('cta') or 'Solicita un diagnóstico de tu proyecto.')
                opportunity.setdefault('kpis', opportunity.get('kpis') or 'Leads calificados, diagnósticos, propuestas y conversiones.')
                opportunity.setdefault('next_7_days', opportunity.get('next_7_days') or 'Medir resultados y preparar la siguiente iteración de campaña.')
                opportunity.setdefault('guardrails', opportunity.get('guardrails') or 'No prometer ahorros o retornos sin datos del proyecto.')
                text=' '.join(str(opportunity.get(k,'')) for k in ('title','desc','kind','audience','objective','customer_problem','positioning','value_proposition'))
                rows=_esuna_search(text,24)
                extra=[]
                for q in ('marketing estrategia campaña contenido ventas fotovoltaica','mercado fotovoltaico Colombia competencia oportunidades','BESS C&I almacenamiento energía solar','normativa fotovoltaica Colombia AGPE generación distribuida'):
                    extra.extend(_esuna_search(q,6))
                seen={r['id'] for r in rows}; rows += [r for r in extra if r['id'] not in seen]
                news=_esuna_world_news(18)
                return self._json(200,{'ok':True,'strategy':_esuna_strategy(opportunity,rows,news),'generated_at':datetime.datetime.now().astimezone().strftime('%d/%m/%Y %H:%M'),'mode':'LOCAL_KNOWLEDGE'})
            if p.path=='/api/publicidad/generate':
                n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n).decode('utf-8')); return self._json(200,publicidad_generate(payload.get('prompt',''),payload.get('title','Publicidad E-SUN POWER')))
            if p.path=='/api/publicidad/save':
                n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n).decode('utf-8')); url=str(payload.get('url',''))
                if not url.startswith('/data/publicidad_generated/'): raise ValueError('Solo se pueden guardar imágenes generadas por Esuna en esta sesión.')
                src=(ROOT/url.lstrip('/')).resolve()
                if PUBLICIDAD_DIR.resolve() not in src.parents: raise ValueError('Ruta de imagen no válida.')
                if not src.exists(): raise ValueError('La imagen ya no está disponible.')
                return self._json(200,{'ok':True,'url':url,'filename':src.name})
            if p.path=='/api/budget':
                n=int(self.headers.get('Content-Length','0')); body=self.rfile.read(n); payload=json.loads(body.decode('utf-8')); return self._json(200,quote_budget(payload))
            if p.path=='/api/ocr-rut':
                n=int(self.headers.get('Content-Length','0'))
                if n<=0 or n>28*1024*1024: raise ValueError('Carga inválida o demasiado grande.')
                body=self.rfile.read(n); payload=json.loads(body.decode('utf-8'))
                return self._json(200,ocr_rut(payload.get('data_url'),payload.get('filename','')))
            if p.path=='/api/ocr':
                n=int(self.headers.get('Content-Length','0'))
                if n<=0 or n>20*1024*1024: raise ValueError('Carga inválida o demasiado grande.')
                body=self.rfile.read(n); payload=json.loads(body.decode('utf-8'))
                return self._json(200,ocr_invoice(payload.get('data_url')))
        except Exception as e: return self._json(400,{'error':str(e)})
        self.send_error(404)


if __name__=='__main__':
    print(f'PV System Designer V{VER} — servidor en http://{HOST}:{PORT}',flush=True)
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()

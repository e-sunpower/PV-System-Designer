import base64, io, json, math, os, re, urllib.parse, urllib.request
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
VER = '63.2'
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
    area=float(payload.get('area_m2') or 0)
    savings=float(payload.get('savings_pct') or 0)
    yield_factor=float(payload.get('yield_kwh_kwp_year') or DEFAULT_YIELD_KWH_KWP_YEAR)
    losses_pct=float(payload.get('losses_pct') or DEFAULT_LOSSES_PCT)
    solar_hsp=float(payload.get('solar_hsp') or 0)
    solar_source=str(payload.get('solar_source') or 'Factor de producción manual')
    area_restriction=str(payload.get('area_restriction','true')).lower() in ('1','true','yes','si','sí','on')
    phase=str(payload.get('system_phase') or 'TRIFASICO').upper()
    if phase not in ('MONOFASICO','BIFASICO','TRIFASICO'): raise ValueError('Tipo de sistema no válido. Seleccione MONOFÁSICO, BIFÁSICO o TRIFÁSICO.')
    if annual<=0: raise ValueError('Ingrese un consumo mensual o anual válido.')
    if savings<0 or savings>100: raise ValueError('El porcentaje de ahorro debe estar entre 0 y 100 %.')
    if yield_factor<=0: raise ValueError('El factor de producción debe ser mayor que cero.')
    if losses_pct<0 or losses_pct>=100: raise ValueError('Las pérdidas deben estar entre 0 y menos de 100 %.')
    ma=module_area(m)
    if not ma: raise ValueError('El módulo seleccionado no tiene dimensiones verificadas.')
    power_w=float(m['power_w'])
    if solar_hsp>0:
        yield_factor=solar_hsp*365.0*(1-losses_pct/100.0); solar_mode=True
    else: solar_mode=False
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
        'inputs':{'consumption_monthly_kwh':monthly if monthly>0 else None,'consumption_annual_kwh':annual,'area_m2':area,'savings_pct':savings,'yield_kwh_kwp_year':yield_factor,'area_restriction':area_restriction,'losses_pct':losses_pct,'solar_hsp':solar_hsp,'solar_source':solar_source,'solar_mode':solar_mode,'system_phase':phase,'system_type':system_type,'battery_storage_hours':storage_hours if system_type=='OFF-GRID' else None},
        'module':{'index':mi,**m,'area_m2':ma},
        'target':{'target_kwh_year':target_kwh,'required_kwp':required_kwp,'required_modules':required_modules,'max_modules_area':max_modules_area},
        'area':{'available_area_m2':area,'module_area_m2':ma,'max_modules':max_modules_area,'occupied_area_m2':occupied,'remaining_area_m2':remaining,'status':'OK' if (not area_restriction or selected_modules<=max_modules_area) else 'AREA_LIMIT'},
        'system':{'modules':selected_modules,'dc_kwp':dc_kwp,'area_occupied_m2':occupied,'area_remaining_m2':remaining,'achieved_kwh_year':achieved_kwh,'achieved_savings_pct':achieved_savings,'area_limited':area_limited,'phase':phase},
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

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def _json(self,code,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode('utf-8'); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        p=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(p.query)
        try:
            if p.path=='/api/health': return self._json(200,{'ok':True,'version':VER,'port':PORT,'python':__import__('sys').version.split()[0]})
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
            if p.path=='/api/legacy': return self._json(200,{'version':VER,'message':'V20 usa DIVIPOLA de Datos.gov.co para ubicación y el Atlas de Radiación Solar UPME/IDEAM 2005 como referencia cartográfica mensual.'})
        except Exception as e: return self._json(400,{'error':str(e)})
        return super().do_GET()
    def do_POST(self):
        p=urllib.parse.urlparse(self.path)
        try:
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

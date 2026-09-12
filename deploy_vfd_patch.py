from pathlib import Path

ROOT = Path('V123')
INDEX = ROOT / 'index.html'
SERVER = ROOT / 'server.py'


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'No se encontró: {label}')
    return text.replace(old, new, 1)


# Keep the existing inverter workflow intact. The VFD mode is additive.
s = INDEX.read_text(encoding='utf-8')

old = '<section class="card"><h2>7. Inversor</h2><label class="label">Inversor técnico <span class="pill" id="phaseFilterBadge">TRIFÁSICO</span></label><select id="inverter"><option value="">Automático</option></select><div id="inverterTechCard" class="equipment-spec-grid"></div>'
new = '<section class="card"><h2>7. Inversor</h2><div id="equipmentModeBlock" class="vfd-mode-block"><label class="label" style="margin-top:0">Tipo de equipo de conversión</label><select id="equipmentMode"><option value="inverter">INVERSOR FOTOVOLTAICO — BASE EXISTENTE</option><option value="solar_vfd">VARIADOR DE FRECUENCIA SOLAR — BASE DE BOMBEO</option></select><p class="muted" style="margin-top:8px">Seleccione si el sistema utilizará el inversor fotovoltaico convencional o un variador solar con MPPT. En modo variador, la selección se dimensiona con la potencia máxima simultánea de la Matriz de Consumo.</p></div><label class="label" id="inverterTechnicalLabel">Inversor técnico <span class="pill" id="phaseFilterBadge">TRIFÁSICO</span></label><select id="inverter"><option value="">Automático</option></select><div id="inverterTechCard" class="equipment-spec-grid"></div>'
s = replace_once(s, old, new, 'sección 7')

old = 'grid_available_kw:gridAvailable,grid_dc_ac_ratio:gridDcAcRatio'
new = "grid_available_kw:gridAvailable,grid_dc_ac_ratio:gridDcAcRatio,equipment_mode:$(\'equipmentMode\')?.value||\'inverter\',solar_vfd_index:$(\'solarVfd\')?.dataset.globalIndex||\'\',solar_vfd_required_kw:$(\'solarVfdRequiredInput\')?.value||\'\'"
s = replace_once(s, old, new, 'parámetros de /api/design')

old = "if(d.inverter){const inv=d.inverter,ic=findCostForInverter(inv);rows.push(makeOrUpdate('Inversores',()=>({code:ic?.code||'',category:'Inversores',description:'Inversores',detail:`${inv.manufacturer} ${inv.model} — ${inv.ac_kw} kW c/u · ${Number(inv.quantity||1)} unidad(es) · ${d.inputs?.system_phase==='MONOFASICO'?'MONOFÁSICO':d.inputs?.system_phase==='BIFASICO'?'BIFÁSICO':'TRIFÁSICO'}`,unit:'und',qty:Number(inv.quantity||1),cost_price:ic?.price_cop||0,markup_pct:0,tax_pct:0,state:'Incluido',source:ic?`${ic.supplier} · precio público web`:'Precio de costo pendiente de cotización'})));}"
new = old + " if(d.solar_vfd?.is_solar_vfd){const v=d.solar_vfd;rows.push(makeOrUpdate('Variadores de frecuencia solar',()=>({code:'BASE-VFD-'+String(v.model).replace(/\\W+/g,'-').toUpperCase(),category:'Variadores de frecuencia solar',description:'Variador de frecuencia solar',detail:`${v.manufacturer} ${v.model} — ${v.power_kw} kW · motor ${v.motor_recommended_hp} · ${v.output_voltage}`,unit:'und',qty:Number(v.quantity||1),cost_price:Number(v.price_cop||0),markup_pct:0,tax_pct:0,state:'Incluido',source:'Base de datos de variadores de frecuencia solar suministrada por el usuario'})));}"
s = replace_once(s, old, new, 'partida automática de inversores')
s = replace_once(s, "'Módulos FV','Inversores','Medidores bidireccionales','Baterías'", "'Módulos FV','Inversores','Variadores de frecuencia solar','Medidores bidireccionales','Baterías'", 'categorías conocidas del presupuesto')

old = "$('budgetSource').innerHTML=`Sistema: <b>${fmt(d.system.dc_kwp,2)} kWp DC</b> · ${fmt(d.system.modules,0)} módulos · inversor: ${d.inverter?d.inverter.manufacturer+' '+d.inverter.model:'pendiente'}. El presupuesto se actualiza sin reiniciar las partidas existentes.`;"
new = "$('budgetSource').innerHTML=`Sistema: <b>${fmt(d.system.dc_kwp,2)} kWp DC</b> · ${fmt(d.system.modules,0)} módulos · equipo de conversión: ${d.solar_vfd?.is_solar_vfd?d.solar_vfd.manufacturer+' '+d.solar_vfd.model:(d.inverter?d.inverter.manufacturer+' '+d.inverter.model:'pendiente')}. El presupuesto se actualiza sin reiniciar las partidas existentes.`;"
s = replace_once(s, old, new, 'origen del presupuesto')

INDEX.write_text(s, encoding='utf-8')

s = SERVER.read_text(encoding='utf-8')
s = replace_once(s, "INVERTERS = DATA / 'inverters.json'\nBATTERIES = DATA / 'batteries.json'", "INVERTERS = DATA / 'inverters.json'\nSOLAR_VFDS = DATA / 'solar_vfd.json'\nBATTERIES = DATA / 'batteries.json'", 'ruta de base de datos VFD')
s = replace_once(s, "def batteries():\n    return load(BATTERIES, [])", "def batteries():\n    return load(BATTERIES, [])\n\ndef solar_vfds():\n    return load(SOLAR_VFDS, [])", 'función solar_vfds')

needle = "    phase=str(payload.get('system_phase') or 'TRIFASICO').upper()\n    if phase not in ('MONOFASICO','BIFASICO','TRIFASICO'): raise ValueError('Tipo de sistema no válido. Seleccione MONOFÁSICO, BIFÁSICO o TRIFÁSICO.')"
repl = "    phase=str(payload.get('system_phase') or 'TRIFASICO').upper()\n    equipment_mode=str(payload.get('equipment_mode') or 'inverter').lower().strip()\n    if equipment_mode not in ('inverter','solar_vfd'): equipment_mode='inverter'\n    if phase not in ('MONOFASICO','BIFASICO','TRIFASICO'): raise ValueError('Tipo de sistema no válido. Seleccione MONOFÁSICO, BIFÁSICO o TRIFÁSICO.')"
s = replace_once(s, needle, repl, 'modo de equipo en calc_design')

needle = "    phase_note=None\n    if not phase_candidates:"
repl = """    solar_vfd_result=None
    if equipment_mode=='solar_vfd':
        vfds=solar_vfds()
        candidates_vfd=[(i,v) for i,v in enumerate(vfds) if str(v.get('phase_class','')).upper()==phase]
        if not candidates_vfd:
            raise ValueError(f'La base de variadores no contiene equipos para la fase {phase}.')
        vi_raw=payload.get('solar_vfd_index')
        if vi_raw in (None,''):
            required_kw=float(payload.get('solar_vfd_required_kw') or 0)
            viable=[(float(v.get('power_kw') or 0),i,v) for i,v in candidates_vfd if float(v.get('power_kw') or 0)>=required_kw-1e-9]
            viable.sort(key=lambda x:(x[0],x[2].get('price_cop') or 0,x[1]))
            vi=viable[0][1] if viable else min(candidates_vfd,key=lambda x:float(x[1].get('power_kw') or 0))[0]
        else:
            vi=int(vi_raw)
            if vi<0 or vi>=len(vfds): raise ValueError('Variador de frecuencia solar no válido.')
            if str(vfds[vi].get('phase_class','')).upper()!=phase: raise ValueError('El variador seleccionado no corresponde a la fase del sistema.')
        v=vfds[vi]
        power_kw=float(v.get('power_kw') or 0)
        required_kw=float(payload.get('solar_vfd_required_kw') or 0)
        if power_kw<=0: raise ValueError('El variador seleccionado no tiene potencia válida.')
        if required_kw>power_kw+1e-9: raise ValueError(f'La potencia de diseño del variador ({required_kw:.2f} kW) supera la potencia disponible de {power_kw:.2f} kW en la base. Seleccione una referencia superior o revise la carga.')
        solar_vfd_result={'index':vi,**v,'quantity':1,'required_power_kw':required_kw,'selection_basis':'Potencia máxima simultánea de la Matriz de Consumo + 10 % de margen','is_solar_vfd':True}
        selected_inv=None
    phase_note=None
    if not phase_candidates:"""
s = replace_once(s, needle, repl, 'punto de inserción VFD')

needle = "    # OFF-GRID: size the battery bank automatically from daily energy demand and the selected battery database record."
repl = """    if equipment_mode=='solar_vfd' and solar_vfd_result:
        electrical={'status':'SOLAR_VFD','message':'El variador solar incorpora MPPT y reemplaza el inversor fotovoltaico convencional. La tensión, corriente, motor y configuración de bombeo deben verificarse con la ficha técnica del equipo y del motor.','power_kw':solar_vfd_result['power_kw'],'required_power_kw':solar_vfd_result['required_power_kw']}

    # OFF-GRID: size the battery bank automatically from daily energy demand and the selected battery database record."""
s = replace_once(s, needle, repl, 'bloque OFF-GRID')
s = replace_once(s, "ac_required=float(selected_inv.get('ac_kw_total') or 0) if selected_inv else 0", "ac_required=float(selected_inv.get('ac_kw_total') or 0) if selected_inv else float(solar_vfd_result.get('power_kw') or 0) if solar_vfd_result else 0", 'potencia de descarga de batería')
s = replace_once(s, "'system_type':system_type,'battery_storage_hours':storage_hours if system_type=='OFF-GRID' else None}", "'system_type':system_type,'battery_storage_hours':storage_hours if system_type=='OFF-GRID' else None,'equipment_mode':equipment_mode}", 'inputs de calc_design')
s = replace_once(s, "'inverter':selected_inv,'electrical':electrical,'phase_note':phase_note,'battery':battery_result,", "'inverter':selected_inv,'solar_vfd':solar_vfd_result,'electrical':electrical,'phase_note':phase_note,'battery':battery_result,", 'resultado solar_vfd')
SERVER.write_text(s, encoding='utf-8')

print('VFD patch aplicado correctamente.')

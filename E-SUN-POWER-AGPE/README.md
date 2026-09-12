# E-SUN POWER AGPE

Aplicación independiente para diseño y gestión de proyectos de autogeneración a pequeña escala.

## Estructura inicial

- CÁLCULO DE
  - NUEVO PROYECTO
    - SFV TRADICIONAL
    - SFV BOMBEO SOLAR
  - PROYECTOS GUARDADOS
- PROYECTOS AGPE
- CLIENTES

## Desarrollo

Esta aplicación se construye desde cero y no depende del HTML, CSS ni JavaScript de `V123`. Las bases de datos y lógica técnica del proyecto anterior se reutilizarán únicamente cuando sean incorporadas como módulos propios de AGPE.

## Render

Configurar un Web Service independiente usando:

- Root Directory: `E-SUN-POWER-AGPE`
- Build Command: `python -m py_compile server.py`
- Start Command: `python server.py`
- Health Check Path: `/api/health`

# E-SUN POWER — PV System Designer

V123 — versión online-ready del diseñador fotovoltaico.

## Despliegue en Render

El código completo de V123 está en `V123/` y el Blueprint de Render en `render.yaml` apunta a ese directorio como raíz del servicio.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/e-sunpower/PV-System-Designer)

Al crear el servicio, Render ejecutará `python -m py_compile server.py`, iniciará `python server.py` y utilizará `/api/health` como health check.

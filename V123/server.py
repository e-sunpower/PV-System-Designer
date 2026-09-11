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

# PATCH V153.26-R1: Playwright on Render must be able to use its bundled browser.
# The complete original server.py is preserved except for _playwright_browser_path().

def _playwright_browser_path():
    """Return a usable Chromium executable for Playwright.

    Prefer an explicitly configured/system browser. If none exists (typical on
    Render's Python runtime), resolve Playwright's own installed Chromium binary.
    This avoids requiring Chrome/Edge to be installed system-wide.
    """
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

# NOTE: The deployment updater replaces this small patch into the existing file.

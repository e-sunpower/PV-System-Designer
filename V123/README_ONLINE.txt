E-SUN POWER · PV SYSTEM DESIGNER V123 — EDICIÓN WEB ONLINE

Esta edición mantiene la aplicación web actual y la prepara para publicarse con un vínculo HTTPS.

PUBLICACIÓN RECOMENDADA (RENDER)
1. Cree un repositorio en GitHub y suba TODO el contenido de esta carpeta.
2. En Render cree un Web Service conectado al repositorio.
3. Render puede usar automáticamente render.yaml; si lo configura manualmente:
   Build Command: python -m py_compile server.py
   Start Command: python server.py
4. Render asignará PORT automáticamente. server.py ya está preparado para usarlo y escuchar en 0.0.0.0.
5. Al finalizar tendrá una URL HTTPS pública, que podrá compartir con otros usuarios.

IMPORTANTE SOBRE LOS DATOS
La versión actual conserva proyectos, APUs y configuraciones de usuario mediante localStorage del navegador. Por tanto, cada usuario tiene sus propios datos en su dispositivo/navegador. La publicación online NO crea todavía una base de datos central compartida.

PWA / CELULAR
Con HTTPS, el navegador puede ofrecer "Instalar aplicación" o "Agregar a pantalla de inicio". El service worker permite una experiencia tipo app y caché de archivos estáticos; las APIs se mantienen en línea.

USO LOCAL
start_local.bat sigue disponible para ejecutar la aplicación en Windows.

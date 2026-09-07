MAPA SOLAR 1 km — ADAPTADOR

Este directorio está preparado para integrar un archivo de datos del Mapa Solar de Colombia de Emergente obtenido de forma autorizada.

La página pública de Emergente describe su mapa como un producto de escala aproximada de 1 km y explica que fue construido con 369 estaciones IDEAM y fuentes secundarias (CHIRPS, MODIS-NDVI, SRTM y CLARA), desagregación espacial y krigeado con deriva externa, seguido del modelo Angstrom-Prescott para obtener GHI. El periodo metodológico publicado es 2001–2022.

No se incluye una copia de la base propietaria ni se extraen datos de la web. Para usar exactamente esa base, coloque aquí el NetCDF/GeoTIFF que tenga autorización para usar.

NetCDF recomendado:
  mapa_solar_colombia.nc

Si los nombres de variables no son estándar, edite config.json:
  variable, monthly_variables, lat_name, lon_name.

El servidor intentará usar esta fuente 1 km como prioridad. Si no existe el archivo, utilizará el fallback IDEAM ya integrado.

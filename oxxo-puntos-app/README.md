# Puntos evaluados vs. tiendas vigentes

App de Streamlit para comparar los puntos evaluados por el equipo de
Operaciones contra las tiendas que ya están **ABIERTA**, **OBRA** o
**FIRMADA**, detectar posibles duplicados por similitud de nombre, y ver el
detalle completo de cada punto (foto, contacto, link de Maps y coordenadas
en un mapa).

## ¿Qué hace?

1. **Comparación de nombres** — usa *fuzzy matching* (rapidfuzz) entre
   `Nombre del Punto` (hoja `Visitas_Operaciones`) y `NAME` de las tiendas
   vigentes (hoja `JUN` de Book.xlsx). Umbral ajustable desde la barra
   lateral; los puntos que superan el umbral se marcan como posible
   duplicado.
2. **Detalle por punto** — muestra toda la info del formulario, la(s) foto(s)
   (se extraen del texto `Foto: https://...`), el link de Maps, y un mapa
   con el punto ubicado.
3. **Coordenadas** — se obtienen en cascada:
   - Si el link ya trae `@lat,lng` (o variantes `!3d!4d`, `q=`, `ll=`), se
     extrae directo, gratis y sin llamadas externas.
   - Si es un link acortado (`maps.app.goo.gl/...`), se resuelve la
     redirección y se repite el paso anterior.
   - Si no hay coordenadas en el link (p. ej. una búsqueda de Bing Maps),
     se geocodifica la dirección con **Nominatim** (OpenStreetMap, gratis).

## Estructura

```
├── app.py                 # UI de Streamlit
├── src/
│   ├── data_loader.py      # lee Book.xlsx y Operaciones_ult_semana.xlsm
│   ├── matching.py          # fuzzy matching de nombres
│   ├── maps_utils.py        # extracción/geocodificación de coordenadas
│   └── photos_utils.py      # parseo de URLs de fotos
├── data/
│   ├── Book.xlsx
│   └── Operaciones_ult_semana.xlsm
└── requirements.txt
```

## Cómo actualizar los datos

La app lee los Excel directamente del repo (`data/Book.xlsx` y
`data/Operaciones_ult_semana.xlsm`). Para actualizar:

1. Reemplaza esos dos archivos en el repo (mismo nombre, misma hoja:
   `JUN` en Book.xlsx y `Visitas_Operaciones` en el .xlsm).
2. Haz commit y push.
3. En la app, presiona **"🔄 Recargar datos"** en la barra lateral (o
   simplemente refresca — Streamlit Cloud vuelve a desplegar solo con el
   push, pero el botón evita esperar el redeploy si solo cambiaste el dato).

No hace falta tocar código para actualizar cifras.

## Correr en local

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Desplegar gratis en Streamlit Community Cloud (recomendado)

1. Sube este proyecto a un repo de **GitHub privado** (los datos tienen
   teléfonos y correos de propietarios — no lo hagas público).
2. Entra a [share.streamlit.io](https://share.streamlit.io) con tu cuenta
   de GitHub.
3. **New app** → selecciona el repo, la rama (`main`) y el archivo
   principal (`app.py`).
4. Como el repo es privado, Streamlit Cloud te va a pedir autorizar
   acceso a ese repo específico (OAuth de GitHub) — acéptalo.
5. Deploy. La primera carga tarda ~1-2 min instalando dependencias.

La app queda con una URL tipo `https://tu-app.streamlit.app`, protegida
por el control de acceso de Streamlit Cloud (puedes restringir quién
entra desde el panel de la app, en *Settings → Sharing*).

### Alternativa: Render / Railway / servidor propio
Si prefieres no depender de Streamlit Cloud, cualquier servicio que corra
`streamlit run app.py` con Python 3.11+ sirve; solo necesitas exponer el
puerto que defina la variable de entorno `PORT` (agregar
`--server.port $PORT --server.address 0.0.0.0` al comando de arranque).

## Notas / límites

- Nominatim (geocodificación de respaldo) es gratis pero pide no golpearlo
  más de ~1 request/segundo — la app cachea cada dirección por 24h así
  que en uso normal no es problema.
- Si más adelante quieres coordenadas más precisas y sin depender de que
  el link traiga `@lat,lng`, se puede migrar a la Google Geocoding API
  (de pago, pero mucho más exacta) — el módulo `maps_utils.py` está
  aislado justo para poder cambiar esa pieza sin tocar el resto de la app.

# Panel OXXO: operaciones y estadísticas

Aplicación de Streamlit para comparar los puntos evaluados por el equipo de Operaciones contra las tiendas vigentes, detectar posibles duplicados, revisar el detalle de cada punto y consultar estadísticas de llegada diaria.

## Versión 2

La versión 2 incorpora una vista **Estadísticas** con el total de puntos recibidos, promedio diario, día de mayor llegada, acumulado, distribución por `Estado Growth`, jefe de zona, región y plaza. El periodo se puede filtrar desde la barra lateral y también se puede consultar la tabla diaria completa.

La base `Operaciones_ult_semana.xlsm` puede sincronizarse desde un vínculo compartido de OneDrive. La app conserva una copia local de respaldo si el vínculo no está configurado o si OneDrive no responde. Cada sincronización muestra la **fecha y hora local de la consulta**, además de la fecha de modificación informada por OneDrive cuando está disponible.

## Configurar OneDrive

El vínculo no se solicita dentro de la aplicación. Para un despliegue permanente, guarda el vínculo como secreto de Streamlit:

```toml
ONEDRIVE_URL = "https://tu-tenant.sharepoint.com/:x:/g/personal/..."
```

También se acepta `ONEDRIVE_OPERACIONES_URL`; ambos nombres son equivalentes. La app adapta automáticamente vínculos de `sharepoint.com` y `onedrive.live.com` agregando `download=1`, utiliza un User-Agent de navegador y prueba rutas alternativas de descarga. Una vez configurado, la barra lateral solo muestra el botón **Actualizar desde OneDrive**; el vínculo permanece oculto. El vínculo debe permitir descargar el archivo `.xlsm` y conservar la hoja `Visitas_Operaciones`.

## Método de ubicación exacta

Cada fila se procesa de manera independiente y conserva el vínculo original recibido desde OneDrive en `enlace_maps_leido`. La prioridad de fuentes es la siguiente:

1. Coordenadas explícitas del enlace real de Maps, incluyendo enlaces cortos y redirecciones.
2. Identificador de ficha de Google validado contra la respuesta pública de la misma ficha.
3. Coordenadas de `Y` (latitud) y `X` (longitud) de la hoja, sólo cuando el enlace no resolvió el pin.
4. Dirección contextual con nombre, plaza, región y restricción de país a Colombia, únicamente como respaldo.

Cuando la coordenada es válida, la aplicación genera `enlace_maps_exacto` con el formato `query=latitud,longitud`. El botón del detalle y el enlace dentro de cada marcador del mapa abren ese vínculo canónico, por lo que no vuelven a buscar una dirección ni el centro de la vista. La coordenada se conserva con ocho decimales y se muestra con su fuente para facilitar la auditoría.

Si una fuente de respaldo no devuelve un resultado dentro de Colombia, el registro no se coloca arbitrariamente: queda reportado en **Registros sin ubicación verificable**.

## Vistas disponibles

| Vista | Función |
| --- | --- |
| Estadísticas | Llegada diaria, acumulado, estados, responsables, regiones y plazas. |
| Comparación de nombres | Coincidencias difusas contra tiendas vigentes y posibles duplicados. |
| Detalle por punto | Información del formulario, fotos, mapas, cercanía e informe PDF. |

## Estructura

```text
├── app.py
├── src/
│   ├── data_loader.py
│   ├── matching.py
│   ├── maps_utils.py
│   └── ...
├── data/
│   ├── Book.xlsx
│   ├── Operaciones_ult_semana.xlsm
│   └── Puntos_Potenciales.xlsx
├── requirements.txt
└── secrets.example.toml
```

## Correr en local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Para mantener la información operativa protegida, utiliza un repositorio privado y no publiques el vínculo de OneDrive en el código fuente.

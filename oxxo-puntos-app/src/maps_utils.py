"""
Extracción de coordenadas a partir del link de Google Maps que llenan los
jefes de zona en el formulario, con estrategia en cascada:

1. Parsear el link directamente (si ya trae lat/lng en la URL).
2. Si es un link acortado (maps.app.goo.gl, goo.gl/maps), resolver la
   redirección y volver a intentar el paso 1 sobre la URL final.
3. Si no se pudo (p.ej. el link es de Bing Maps u otro buscador sin
   coordenadas), usar la dirección para geocodificar con Nominatim
   (OpenStreetMap, gratis) como respaldo.

Todo queda cacheado con st.cache_data para no golpear la red en cada rerun.
"""
import re
import requests
import streamlit as st

USER_AGENT = "oxxo-puntos-app/1.0 (contacto: equipo-expansion@oxxo.com)"

# Patrones típicos dentro de URLs de Google Maps
PATTERNS = [
    r"@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",          # .../@4.7101,-74.0721,15z
    r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)",       # pin exacto de un lugar
    r"[?&]q=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",      # ?q=4.71,-74.07
    r"[?&]ll=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",     # ?ll=4.71,-74.07
    r"[?&]destination=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",
]

SHORT_LINK_DOMAINS = ("maps.app.goo.gl", "goo.gl/maps", "goo.gl")


def _parse_coords_from_text(url: str):
    for pattern in PATTERNS:
        m = re.search(pattern, url)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    return None


def _is_short_link(url: str) -> bool:
    return any(d in url for d in SHORT_LINK_DOMAINS)


def _is_google_maps(url: str) -> bool:
    return "google.com/maps" in url or "goo.gl" in url or "maps.app.goo.gl" in url


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def resolve_short_link(url: str) -> str:
    """Sigue la redirección de un link acortado y devuelve la URL final."""
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, allow_redirects=True, timeout=8
        )
        return resp.url
    except requests.RequestException:
        return url


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def geocode_address(address: str, region_hint: str = "Colombia"):
    """Respaldo gratuito vía Nominatim (OpenStreetMap) cuando el link no
    trae coordenadas (ej. búsquedas de Bing Maps sin lat/lng en la URL)."""
    if not address or not address.strip():
        return None
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{address}, {region_hint}", "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    return None


def get_coordinates(maps_link: str, address: str = ""):
    """
    Devuelve (lat, lon, fuente) o (None, None, motivo) probando la cascada
    completa. `fuente` indica cómo se obtuvo, útil para mostrarlo en la UI.
    """
    link = (maps_link or "").strip()

    if not link:
        coords = geocode_address(address)
        if coords:
            return coords[0], coords[1], "Geocodificado por dirección (sin link)"
        return None, None, "Sin link ni dirección utilizable"

    # 1. Intento directo sobre el link tal cual
    coords = _parse_coords_from_text(link)
    if coords:
        return coords[0], coords[1], "Extraído directamente del link"

    # 2. Si es link acortado, resolver redirección y reintentar
    if _is_short_link(link):
        final_url = resolve_short_link(link)
        coords = _parse_coords_from_text(final_url)
        if coords:
            return coords[0], coords[1], "Extraído tras resolver el link corto"

    # 3. Respaldo: geocodificar por dirección
    coords = geocode_address(address)
    if coords:
        motivo = (
            "Geocodificado por dirección (el link no traía coordenadas, "
            "p. ej. búsqueda de Bing Maps)"
        )
        return coords[0], coords[1], motivo

    return None, None, "No se pudieron obtener coordenadas (ni del link ni de la dirección)"

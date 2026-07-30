La aplicación recibe enlaces que pueden ser URL completas de Google Maps,
enlaces cortos ``maps.app.goo.gl``, URLs de Bing/Waze o hipervínculos de Excel
cuyo texto visible no es la URL real. Este módulo extrae pares latitud/longitud
sin invertirlos, resuelve redirecciones cuando es necesario y deja una fuente
auditable para cada coordenada.

Formatos soportados
-------------------
- ``maps.app.goo.gl/<id>`` → redirección a URL con ``q=lat,lon`` o con ``ftid``
- ``google.com/maps/@lat,lon,zoom``
- ``google.com/maps/place/...!3d<lat>!4d<lon>``
- ``google.com/maps?q=lat,lon``
- ``google.com/maps?q=<dirección>&ftid=<id>`` → geocodificación por dirección
- ``maps.google.com/?q=lat,lon``
- ``bing.com/maps?cp=lat~lon`` y ``ppois=lat_lon_...``
- ``waze.com/ul?ll=lat,lon``
- Cualquier URL con coordenadas explícitas en query string o path
"""
from __future__ import annotations

import html as html_lib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, unquote, unquote_plus, urlparse

import requests
import streamlit as st

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = (5, 15)
GOOGLE_PREVIEW_TIMEOUT = (4, 10)
MAX_LINK_WORKERS = 6
APP_ROOT = Path(__file__).resolve().parents[1]
COORDINATE_CACHE_PATH = APP_ROOT / "data" / "maps_coordinate_cache.json"

SHORT_LINK_DOMAINS = {"maps.app.goo.gl", "goo.gl"}
MAP_HOST_HINTS = ("google.", "goo.gl", "share.google", "bing.com", "waze.com")

COORD_QUERY_KEYS = (
    "q", "query", "ll", "destination", "origin", "center", "location",
    "coords", "coordinates", "latlng", "latlon",
)


def _clean_url(value: object) -> str:
    """Normaliza una URL preservando su contenido semántico."""
    if not isinstance(value, str):
        return ""
    link = html_lib.unescape(value).replace("\u200b", "").strip()
    embedded_url = re.search(r"https?://[^\s<>\"']+", link, flags=re.IGNORECASE)
    if embedded_url:
        link = embedded_url.group(0).rstrip(".,;:)")
    if link.casefold().startswith("www."):
        link = f"https://{link}"

    try:
        parsed = urlparse(link)
        if parsed.netloc.casefold().endswith("safelinks.protection.outlook.com"):
            original_urls = parse_qs(parsed.query).get("url", [])
            if original_urls:
                link = unquote(original_urls[0]).strip()
    except ValueError:
        pass
    return link


def _valid_coordinates(lat: object, lon: object) -> tuple[float, float] | None:
    """Convierte y valida una pareja geográfica en el orden latitud,longitud."""
    try:
        latitude, longitude = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return latitude, longitude
    return None


@lru_cache(maxsize=1)
def _verified_coordinate_cache() -> dict[str, dict[str, object]]:
    """Carga coordenadas auditadas del libro actual, si el archivo existe."""
    try:
        payload = json.loads(COORDINATE_CACHE_PATH.read_text(encoding="utf-8"))
        entries = payload.get("entries", {})
        return entries if isinstance(entries, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _cached_coordinates(url: str) -> tuple[float, float, str] | None:
    """Devuelve una coordenada auditada para el mismo enlace normalizado."""
    entry = _verified_coordinate_cache().get(_clean_url(url))
    if not isinstance(entry, dict):
        return None
    coordinates = _valid_coordinates(entry.get("lat"), entry.get("lon"))
    if not coordinates:
        return None
    source = str(entry.get("source") or "Coordenada auditada del enlace")
    return coordinates[0], coordinates[1], source


def _parse_coordinate_pair(value: object) -> tuple[float, float] | None:
    """Extrae un par ``latitud,longitud`` de una cadena de consulta."""
    if not isinstance(value, str):
        return None
    text = unquote(value).strip()
    match = re.search(
        r"(?:geo:|loc:)?\s*(-?\d{1,2}(?:\.\d+)?)\s*[,~;]\s*"
        r"(-?\d{1,3}(?:\.\d+)?)",
        text,
    )
    if not match:
        return None
    return _valid_coordinates(match.group(1), match.group(2))


def _parse_coords_from_text(value: object) -> tuple[float, float] | None:
    """Obtiene coordenadas explícitas de formatos habituales de URL de mapas."""
    link = _clean_url(value)
    if not link:
        return None

    decoded = link
    for _ in range(2):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value

    patterns = (
        # Vista/resultado de Google Maps: .../@4.7101,-74.0721,15z
        r"@\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)",
        # Pin exacto de Google Maps: !3d<lat>!4d<lon>
        r"!3d(-?\d{1,2}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)",
        # Formatos observados en exportaciones y redirecciones heredadas.
        r"!1d(-?\d{1,2}(?:\.\d+)?)!2d(-?\d{1,3}(?:\.\d+)?)",
        r"!2d(-?\d{1,2}(?:\.\d+)?)!3d(-?\d{1,3}(?:\.\d+)?)",
        # Bing Maps: ppois=<lat>_<lon>_... y cp=<lat>~<lon>
        r"(?:[?&]|^)ppois=(-?\d{1,2}(?:\.\d+)?)(?:_|%5[fF])(-?\d{1,3}(?:\.\d+)?)",
        r"(?:[?&]|^)cp=(-?\d{1,2}(?:\.\d+)?)(?:~|%7[eE])(-?\d{1,3}(?:\.\d+)?)",
        # URL de Google Maps donde la coordenada aparece como parte de /place/.
        r"/place/\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)",
        # Waze: ?ll=lat,lon
        r"[?&]ll=(-?\d{1,2}(?:\.\d+)?)[,&](-?\d{1,3}(?:\.\d+)?)",
        # Google Maps share: ?q=lat,lon (sin texto, solo números)
        r"[?&]q=(-?\d{1,2}\.\d+),(-?\d{1,3}\.\d+)(?:[&\s]|$)",
        # Coordenadas en el path: /4.7101,-74.0721
        r"/(-?\d{1,2}\.\d{4,}),(-?\d{1,3}\.\d{4,})",
    )
    for pattern in patterns:
        match = re.search(pattern, decoded, flags=re.IGNORECASE)
        if match:
            coordinates = _valid_coordinates(match.group(1), match.group(2))
            if coordinates:
                return coordinates

    # Consulta estándar y URLs con query anidada.
    parsed = urlparse(decoded)
    query = parse_qs(parsed.query, keep_blank_values=False)
    for key in COORD_QUERY_KEYS:
        for candidate in query.get(key, []):
            coordinates = _parse_coordinate_pair(candidate)
            if coordinates:
                return coordinates

    key_pattern = "|".join(re.escape(key) for key in COORD_QUERY_KEYS)
    match = re.search(
        rf"(?:[?&]|\\b)(?:{key_pattern})=([^&#]+)", decoded, flags=re.IGNORECASE
    )
    if match:
        return _parse_coordinate_pair(match.group(1))
    return None


def _hostname(url: str) -> str:
    try:
        return urlparse(url).netloc.casefold().split(":", 1)[0]
    except ValueError:
        return ""


def _is_short_link(url: str) -> bool:
    host = _hostname(url)
    return host in SHORT_LINK_DOMAINS or host.endswith(".goo.gl")


def _should_follow_redirects(url: str) -> bool:
    host = _hostname(url)
    return bool(host) and any(hint in host for hint in MAP_HOST_HINTS)


def _map_query_as_address(url: str) -> str:
    """Extrae una búsqueda o dirección legible de una URL final de mapas.

    Importante: se usa la URL **sin decodificar** para el regex del path porque
    ``unquote()`` convierte ``%23`` en ``#``, y ``urlparse`` interpreta el ``#``
    como inicio de fragmento, truncando la dirección. El match se decodifica
    solo después de extraerlo.
    """
    link = _clean_url(url)
    if not link:
        return ""

    # Para los parámetros de query se puede decodificar sin riesgo porque
    # parse_qs ya maneja la decodificación internamente.
    decoded = link
    for _ in range(2):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    parsed = urlparse(decoded)
    query = parse_qs(parsed.query, keep_blank_values=False)
    for key in ("q", "query", "destination", "origin", "location", "search"):
        for candidate in query.get(key, []):
            candidate = candidate.strip()
            if not candidate or _parse_coordinate_pair(candidate):
                continue
            if candidate.casefold().startswith(("place_id:", "cid:")):
                continue
            return candidate

    # Para el path se usa la URL original (sin decodificar) para evitar que
    # %23 → # rompa el parseo de urlparse al interpretar # como fragmento.
    match = re.search(r"/(?:maps/)?place/([^/]+)", link, flags=re.IGNORECASE)
    if match:
        candidate = unquote_plus(match.group(1)).strip()
        if candidate and not _parse_coordinate_pair(candidate):
            return candidate
    return ""


def _google_place_id(url: str) -> str:
    """Extrae el identificador ``0x...:0x...`` de una ficha de Google Maps."""
    link = _clean_url(url)
    if not link:
        return ""
    decoded = unquote(link)
    parsed = urlparse(decoded)
    for candidate in parse_qs(parsed.query).get("ftid", []):
        if re.fullmatch(r"0x[0-9a-f]+:0x[0-9a-f]+", candidate, flags=re.IGNORECASE):
            return candidate
    match = re.search(r"(?:!1s|ftid=)(0x[0-9a-f]+:0x[0-9a-f]+)", decoded, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _google_preview_payload(place_id: str, label: str) -> str:
    """Construye el parámetro de vista previa usado por una ficha pública."""
    return (
        f"!1m15!1s{place_id}!2s{label[:500]}!3m12!1m3!1d100000!2d-74.0!3d4.6"
        "!2m3!1f0.0!2f0.0!3f0.0!3m2!1i1024!2i768!4f13.1"
    )


@lru_cache(maxsize=2_000)
def google_place_coordinates(url: str) -> tuple[float, float] | None:
    """Obtiene el pin principal de una ficha pública de Google Maps."""
    link = _clean_url(url)
    place_id = _google_place_id(link)
    if not link or not place_id or "google" not in _hostname(link):
        return None
    label = _map_query_as_address(link) or place_id
    response = None
    try:
        response = requests.get(
            "https://www.google.com/maps/preview/place",
            params={
                "authuser": "0",
                "hl": "es",
                "gl": "co",
                "q": label,
                "ftid": place_id,
                "pb": _google_preview_payload(place_id, label),
            },
            headers={"User-Agent": USER_AGENT},
            timeout=GOOGLE_PREVIEW_TIMEOUT,
        )
        response.raise_for_status()
        body = response.text
    except requests.RequestException:
        return None
    finally:
        if response is not None:
            response.close()

    pattern = re.compile(
        r"\[\s*null\s*,\s*null\s*,\s*"
        r"(-?\d{1,2}(?:\.\d+)?)\s*,\s*"
        r"(-?\d{1,3}(?:\.\d+)?)\s*\]\s*,\s*\""
        + re.escape(place_id)
        + r"\"",
        flags=re.IGNORECASE,
    )
    match = pattern.search(body)
    if not match:
        return None
    return _valid_coordinates(match.group(1), match.group(2))


def _extract_coords_from_html(html_body: str) -> tuple[float, float] | None:
    """Extrae coordenadas del HTML de una página de Google Maps.

    Google Maps embebe las coordenadas del pin en el HTML de la página en
    varios formatos. Este método busca los patrones más confiables para
    evitar confundir el centro de la vista con el pin real.
    """
    # Patrón 1: JSON-LD o metadatos con coordenadas explícitas
    # Formato: "center":{"lat":4.7101,"lng":-74.0721}
    match = re.search(
        r'"center"\s*:\s*\{\s*"lat"\s*:\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*"lng"\s*:\s*(-?\d{1,3}(?:\.\d+)?)',
        html_body,
    )
    if match:
        coords = _valid_coordinates(match.group(1), match.group(2))
        if coords:
            return coords

    # Patrón 2: APP_INITIALIZATION_STATE con coordenadas del pin
    # Formato: [null,null,4.7101,-74.0721]
    matches = re.findall(
        r"\[null,null,(-?\d{1,2}\.\d{4,}),(-?\d{1,3}\.\d{4,})\]",
        html_body,
    )
    for lat_str, lon_str in matches:
        coords = _valid_coordinates(lat_str, lon_str)
        if coords:
            return coords

    # Patrón 3: Coordenadas en formato de inicialización de mapa
    # Formato: @4.7101,-74.0721,
    match = re.search(
        r"@(-?\d{1,2}\.\d{4,}),(-?\d{1,3}\.\d{4,}),",
        html_body,
    )
    if match:
        coords = _valid_coordinates(match.group(1), match.group(2))
        if coords:
            return coords

    # Patrón 4: Coordenadas en meta tags o scripts
    # Formato: "lat":4.7101,"lng":-74.0721
    match = re.search(
        r'"lat"\s*:\s*(-?\d{1,2}\.\d{4,})\s*,\s*"lng"\s*:\s*(-?\d{1,3}\.\d{4,})',
        html_body,
    )
    if match:
        coords = _valid_coordinates(match.group(1), match.group(2))
        if coords:
            return coords

    # Patrón 5: Pares de coordenadas de alta precisión en el body
    # Busca el primer par de coordenadas con al menos 4 decimales
    # que esté en el rango de Colombia/Latinoamérica
    matches = re.findall(
        r"(-?\d{1,2}\.\d{5,}),(-?\d{1,3}\.\d{5,})",
        html_body,
    )
    for lat_str, lon_str in matches:
        coords = _valid_coordinates(lat_str, lon_str)
        # Filtrar coordenadas fuera de Latinoamérica para evitar falsos positivos
        if coords and -60 <= coords[0] <= 15 and -120 <= coords[1] <= -30:
            return coords

    return None


@lru_cache(maxsize=2_000)
def resolve_map_link(url: str) -> str:
    """Sigue redirecciones sin descargar el cuerpo de la página de mapas."""
    link = _clean_url(url)
    if not link or not _should_follow_redirects(link):
        return link
    response = None
    try:
        response = requests.get(
            link,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
            stream=True,
            timeout=REQUEST_TIMEOUT,
        )
        return response.url or link
    except requests.RequestException:
        return link
    finally:
        if response is not None:
            response.close()


@lru_cache(maxsize=2_000)
def _fetch_page_coordinates(url: str) -> tuple[float, float] | None:
    """Descarga el HTML de una página de Google Maps y extrae coordenadas.

    Se usa como último recurso cuando la URL final no contiene coordenadas
    explícitas pero sí apunta a un lugar concreto (fichas con ``ftid`` o
    enlaces ``/@/data=...``).
    """
    link = _clean_url(url)
    if not link or "google" not in _hostname(link):
        return None
    response = None
    try:
        response = requests.get(
            link,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        # Leer solo los primeros 50KB para no desperdiciar ancho de banda
        body = response.text[:50_000]
    except requests.RequestException:
        return None
    finally:
        if response is not None:
            response.close()

    return _extract_coords_from_html(body)


@lru_cache(maxsize=4_000)
def geocode_address(address: str, region_hint: str = "Colombia") -> tuple[float, float] | None:
    """Geocodifica una dirección sólo si el enlace no expone coordenadas.

    Intenta primero con la dirección completa. Si falla, prueba una versión
    simplificada eliminando el número de puerta (formato ``#xx-yy``), que
    Nominatim no siempre reconoce en Colombia.
    """
    normalized = (address or "").strip()
    if not normalized:
        return None

    def _query(q: str) -> tuple[float, float] | None:
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            if data:
                return _valid_coordinates(data[0].get("lat"), data[0].get("lon"))
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            pass
        return None

    # Intento 1: dirección completa
    result = _query(f"{normalized}, {region_hint}")
    if result:
        return result

    # Intento 2: eliminar el número de puerta colombiano (#xx-yy) y el
    # nombre del establecimiento si la dirección empieza con uno.
    # Ejemplo: "D1 - Ciudad La Salle, Cra. 10 #172b - 50, Bogotá"
    #       -> "Cra. 10, Bogotá"
    simplified = re.sub(r"\s*#[\w\s\-]+", "", normalized)  # quitar #xx-yy
    simplified = re.sub(r"^[^,]+,\s*", "", simplified).strip()  # quitar nombre inicial
    if simplified and simplified != normalized:
        result = _query(f"{simplified}, {region_hint}")
        if result:
            return result

    # Intento 3: solo la parte de la calle/carrera/avenida con la ciudad
    street_match = re.search(
        r"((?:Cl|Cra|Av|Calle|Carrera|Avenida|Diagonal|Transversal|Tv|Dg)\.?\s*[\d\w]+)",
        normalized,
        flags=re.IGNORECASE,
    )
    city_match = re.search(
        r",\s*([A-Zá-úÁ-ÚñÑ\s]+(?:,\s*[A-Zá-úÁ-ÚñÑ\s]+)?)\s*$",
        normalized,
        flags=re.IGNORECASE,
    )
    if street_match and city_match:
        street_city = f"{street_match.group(1).strip()}, {city_match.group(1).strip()}"
        result = _query(f"{street_city}, {region_hint}")
        if result:
            return result

    return None


def get_coordinates(maps_link: str, address: str = "") -> tuple[float | None, float | None, str]:
    """Devuelve ``(latitud, longitud, fuente)`` de un enlace o una dirección.

    Estrategia en orden de prioridad:
    1. Parseo directo de la URL original (coordenadas explícitas).
    2. Caché de coordenadas auditadas.
    3. Resolución de redirección + parseo de la URL final.
    4. Consulta de ficha de Google Maps (``ftid``/``!1s``).
    5. Descarga del HTML de la página y extracción de coordenadas.
    6. Geocodificación de la dirección extraída del enlace.
    7. Geocodificación de la dirección de respaldo de la hoja Excel.
    """
    link = _clean_url(maps_link)

    # 1. Parseo directo
    direct = _parse_coords_from_text(link)
    if direct:
        return direct[0], direct[1], "Enlace de mapa: coordenadas explícitas"

    # 2. Caché auditada
    cached = _cached_coordinates(link)
    if cached:
        return cached

    # 3. Resolución de redirección
    final_link = link
    if link and _should_follow_redirects(link):
        final_link = resolve_map_link(link)
        redirected = _parse_coords_from_text(final_link)
        if redirected:
            return redirected[0], redirected[1], "Enlace de mapa: redirección resuelta"

    # 4. Ficha de Google Maps por ftid
    google_place = google_place_coordinates(final_link)
    if google_place:
        return google_place[0], google_place[1], "Enlace de mapa: ficha de Google validada"

    # 5. Descarga del HTML de la página (para fichas y enlaces /@/data=...)
    if final_link and "google" in _hostname(final_link):
        page_coords = _fetch_page_coordinates(final_link)
        if page_coords:
            return page_coords[0], page_coords[1], "Enlace de mapa: coordenadas extraídas del HTML"

    # 6. Geocodificación por dirección del enlace
    link_address = _map_query_as_address(final_link)
    if link_address:
        coordinates = geocode_address(link_address)
        if coordinates:
            return coordinates[0], coordinates[1], "Dirección del enlace geocodificada"

    # 7. Geocodificación por dirección de respaldo de la hoja
    if address and str(address).strip():
        coordinates = geocode_address(str(address))
        if coordinates:
            return coordinates[0], coordinates[1], "Dirección geocodificada (respaldo)"

    if not link:
        return None, None, "Sin enlace ni dirección utilizable"
    return None, None, "No se obtuvieron coordenadas válidas del enlace"


def get_coordinates_batch(
    records: Iterable[tuple[object, str, str]], max_workers: int = MAX_LINK_WORKERS
) -> dict[object, tuple[float | None, float | None, str]]:
    """Resuelve varios registros de forma acotada sin bloquear la interfaz.

    Cada registro tiene la forma ``(clave, enlace, dirección)``. El número de
    trabajadores se limita para no realizar una ráfaga de solicitudes a los
    servicios de mapas ni hacer esperar al usuario por enlaces cortos uno a uno.
    """
    items = list(records)
    if not items:
        return {}

    workers = max(1, min(int(max_workers), len(items), MAX_LINK_WORKERS))
    results: dict[object, tuple[float | None, float | None, str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(get_coordinates, str(link or ""), str(address or "")): key
            for key, link, address in items
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                results[key] = (None, None, f"Error al interpretar enlace: {type(exc).__name__}")
    return results

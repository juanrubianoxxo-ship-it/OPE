"""
La columna 'Fotos del Local Revisado' viene como texto plano, con una o
varias líneas tipo 'Foto: https://...jpg'. Este módulo extrae las URLs.
"""
import re

URL_RE = re.compile(r"https?://\S+")


def parse_photo_urls(raw_text) -> list[str]:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return []
    urls = URL_RE.findall(raw_text)
    # Limpiar posibles caracteres colgados al final (comas, puntos sueltos)
    cleaned = [u.rstrip(").,;") for u in urls]
    return cleaned

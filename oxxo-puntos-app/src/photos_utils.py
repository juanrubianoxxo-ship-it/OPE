"""
La columna 'Fotos del Local Revisado' viene como texto plano, con una o
varias líneas tipo 'Foto: https://...jpg'. Este módulo extrae las URLs.
"""
import re

# Detectamos cualquier cosa que parezca una URL (incluso sin http/https)
URL_RE = re.compile(r"(?:https?://)?[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s]*)?")


def parse_photo_urls(raw_text) -> list[str]:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return []
    urls = URL_RE.findall(raw_text)
    cleaned_urls = []
    for u in urls:
        # Limpiar posibles caracteres colgados al final (comas, puntos sueltos)
        u = u.rstrip(").,;")
        # Si no tiene protocolo, se lo añadimos
        if not u.startswith('http'):
            u = 'https://' + u
        cleaned_urls.append(u)
    return cleaned_urls

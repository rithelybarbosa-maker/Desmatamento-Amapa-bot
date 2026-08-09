"""
municipalities.py — Geocodificação reversa offline para municípios do Amapá
Usa GeoJSON oficial do IBGE com fallback para centróides.
"""

import json
import logging
from typing import Optional

import requests

from config import MUNICIPIOS_GEO

logger = logging.getLogger(__name__)

# URLs para GeoJSON dos municípios do Amapá
GEODATA_BR_URL = (
    "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-16-mun.json"
)

# Nomes dos 16 municípios do Amapá com coordenadas centrais (fallback)
_CENTROIDES_AMAPA = [
    ("Macapá",                    0.0349,  -51.0694),
    ("Santana",                  -0.0583,  -51.1819),
    ("Laranjal do Jari",         -0.8000,  -52.4667),
    ("Oiapoque",                  3.8403,  -51.8339),
    ("Mazagão",                  -0.1150,  -51.2894),
    ("Porto Grande",              0.7147,  -51.4139),
    ("Tartarugalzinho",           1.5037,  -50.9098),
    ("Amapá",                     2.0527,  -50.7969),
    ("Calçoene",                  2.4975,  -50.9500),
    ("Vitória do Jari",          -0.9333,  -52.4167),
    ("Ferreira Gomes",            0.8556,  -51.1772),
    ("Cutias",                    0.9667,  -50.8000),
    ("Itaubal",                   0.6000,  -50.6833),
    ("Pracuúba",                  1.7333,  -50.7833),
    ("Serra do Navio",            0.9000,  -52.0000),
    ("Pedra Branca do Amapari",   0.7819,  -51.9486),
]

# Cache em memória dos polígonos carregados
_polygons: list = []   # lista de (nome, shapely_geometry)
_centroids: list = []  # lista de (nome, lat, lon) para fallback


def _math_dist(lat1, lon1, lat2, lon2) -> float:
    """Distância euclidiana simples (graus) para fallback de centróide."""
    return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5


def _load_geojson() -> bool:
    """Carrega o GeoJSON em memória. Retorna True se polígonos disponíveis."""
    global _polygons, _centroids

    if _polygons:
        return True

    # Popula centróides como fallback independente do GeoJSON
    _centroids = list(_CENTROIDES_AMAPA)

    if not MUNICIPIOS_GEO.exists():
        logger.info("GeoJSON não encontrado, tentando baixar...")
        _download_geojson()

    if not MUNICIPIOS_GEO.exists():
        logger.warning("GeoJSON indisponível — usando apenas centróides")
        return False

    try:
        try:
            from shapely.geometry import shape as sh_shape
            has_shapely = True
        except ImportError:
            logger.warning("Shapely não está instalado. Usando apenas centróides como fallback.")
            has_shapely = False

        with open(MUNICIPIOS_GEO, "r", encoding="utf-8") as f:
            data = json.load(f)

        loaded = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            nome = (
                props.get("NM_MUN")
                or props.get("name")
                or props.get("nome")
                or props.get("NOME")
                or "Desconhecido"
            )
            if has_shapely:
                try:
                    geom = sh_shape(feat["geometry"])
                    loaded.append((nome, geom))
                except Exception as e:
                    logger.debug(f"Falha ao carregar geometria de {nome}: {e}")

        _polygons = loaded
        if has_shapely and _polygons:
            logger.info(f"GeoJSON carregado: {len(_polygons)} municípios")
        return len(_polygons) > 0

    except Exception as e:
        logger.error(f"Erro ao ler GeoJSON: {e}")
        return False


def _download_geojson() -> None:
    """Baixa o GeoJSON dos municípios do Amapá."""
    try:
        logger.info("Baixando GeoJSON dos municípios do Amapá...")
        resp = requests.get(GEODATA_BR_URL, timeout=60)
        resp.raise_for_status()

        geojson_data = resp.json()
        features = geojson_data.get("features", [])

        if not features:
            raise ValueError("GeoJSON sem features")

        # Garante que a propriedade de nome está acessível como NM_MUN
        for feat in features:
            props = feat.setdefault("properties", {})
            if "NM_MUN" not in props:
                props["NM_MUN"] = props.get("name", props.get("description", "Desconhecido"))

        MUNICIPIOS_GEO.parent.mkdir(parents=True, exist_ok=True)
        with open(MUNICIPIOS_GEO, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, ensure_ascii=False)

        logger.info(f"GeoJSON de municípios salvo em {MUNICIPIOS_GEO}")
        return

    except Exception as e:
        logger.error(f"Falha ao baixar GeoJSON de municípios: {e}")
        _create_simplified_geojson()


def _create_simplified_geojson() -> None:
    """Fallback: cria GeoJSON simplificado usando bounding boxes aproximadas."""
    logger.warning("Criando GeoJSON de municípios simplificado como fallback...")

    mun_boxes = {
        "Macapá":                   (-51.5, -0.5,  -50.6,  0.4),
        "Santana":                  (-51.4, -0.3,  -50.9, -0.0),
        "Laranjal do Jari":         (-53.0, -1.3,  -51.8,  0.1),
        "Oiapoque":                 (-52.4,  3.2,  -51.0,  4.5),
        "Mazagão":                  (-52.0, -0.6,  -51.0,  0.3),
        "Porto Grande":             (-52.0,  0.4,  -51.0,  1.1),
        "Tartarugalzinho":          (-51.5,  1.0,  -50.5,  2.2),
        "Amapá":                    (-51.5,  1.7,  -50.2,  2.5),
        "Calçoene":                 (-51.5,  2.0,  -50.4,  3.2),
        "Vitória do Jari":          (-52.8, -1.3,  -52.0, -0.5),
        "Ferreira Gomes":           (-51.5,  0.6,  -50.9,  1.1),
        "Cutias":                   (-51.2,  0.7,  -50.6,  1.2),
        "Itaubal":                  (-50.9,  0.3,  -50.4,  0.9),
        "Pracuúba":                 (-51.2,  1.4,  -50.4,  2.0),
        "Serra do Navio":           (-52.5,  0.6,  -51.7,  1.2),
        "Pedra Branca do Amapari":  (-52.3,  0.4,  -51.5,  1.0),
    }

    features = []
    for nome, (x0, y0, x1, y1) in mun_boxes.items():
        coords = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
        features.append({
            "type": "Feature",
            "properties": {"NM_MUN": nome},
            "geometry": {"type": "Polygon", "coordinates": [coords]},
        })

    geojson = {"type": "FeatureCollection", "features": features}
    MUNICIPIOS_GEO.parent.mkdir(parents=True, exist_ok=True)
    with open(MUNICIPIOS_GEO, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    logger.info("GeoJSON de municípios simplificado criado")


def get_municipio(lat: float, lon: float) -> str:
    """
    Determina o município do Amapá para as coordenadas dadas.
    Usa polígonos reais do IBGE se disponíveis, caso contrário usa centróide mais próximo.
    """
    _load_geojson()

    # 1) Busca por polígono
    if _polygons:
        try:
            from shapely.geometry import Point
            pt = Point(lon, lat)
            for nome, geom in _polygons:
                if geom.contains(pt):
                    return nome
        except Exception as e:
            logger.debug(f"Erro na busca por polígono: {e}")

    # 2) Fallback: centróide mais próximo
    if _centroids:
        best_nome = "Amapá (indefinido)"
        best_dist = float("inf")
        for nome, clat, clon in _centroids:
            d = _math_dist(lat, lon, clat, clon)
            if d < best_dist:
                best_dist = d
                best_nome = nome
        return best_nome

    return "Amapá"


def reload_municipios() -> None:
    """Força o recarregamento do GeoJSON."""
    global _polygons, _centroids
    _polygons = []
    _centroids = []
    _load_geojson()

"""
kml_generator.py — Geração de arquivos KML para polígonos de desmatamento
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Union

import simplekml
try:
    from shapely.wkt import loads as wkt_loads
    from shapely.geometry import Polygon, MultiPolygon
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

from config import KML_DIR

logger = logging.getLogger(__name__)


def _add_polygon_to_kml(kml_obj: Union[simplekml.Kml, simplekml.Folder], name: str, geom_wkt: str, description: str) -> None:
    """Carrega uma geometria WKT e a adiciona como polígono no KML."""
    try:
        # Define estilo vermelho semi-transparente para o polígono
        poly_style = simplekml.Style()
        poly_style.polystyle.color = "500000ff"   # vermelho com transparência (AABBGGRR)
        poly_style.polystyle.outline = 1
        poly_style.linestyle.color = "ff0000ff"   # vermelho opaco para a linha externa
        poly_style.linestyle.width = 2

        if SHAPELY_AVAILABLE:
            geom = wkt_loads(geom_wkt)
            if isinstance(geom, Polygon):
                # Obtém coordenadas exteriores
                coords = [(lon, lat) for lon, lat, *_ in geom.exterior.coords]
                poly = kml_obj.newpolygon(name=name, description=description, outerboundaryis=coords)
                poly.style = poly_style
            elif isinstance(geom, MultiPolygon):
                # Para multipolígono, cria uma pasta ou adiciona cada um deles
                for i, poly_part in enumerate(geom.geoms, 1):
                    coords = [(lon, lat) for lon, lat, *_ in poly_part.exterior.coords]
                    poly = kml_obj.newpolygon(name=f"{name} (Parte {i})", description=description, outerboundaryis=coords)
                    poly.style = poly_style
            else:
                # Fallback para ponto caso não seja polígono
                lon, lat = geom.centroid.x, geom.centroid.y
                kml_obj.newpoint(name=name, description=description, coords=[(lon, lat)])
        else:
            # Fallback sem Shapely usando parsing manual simples de WKT para obter coordenadas
            import re
            # Encontra todos os pares de coordenadas (-xxx.xx -yy.yy) na string WKT
            coords_str = re.findall(r"[-+]?\d*\.\d+|\d+", geom_wkt)
            # Agrupa de 2 em 2 (lon, lat)
            coords = []
            for i in range(0, len(coords_str) - 1, 2):
                try:
                    coords.append((float(coords_str[i]), float(coords_str[i+1])))
                except ValueError:
                    continue
            
            if "POLYGON" in geom_wkt.upper() and len(coords) >= 3:
                poly = kml_obj.newpolygon(name=name, description=description, outerboundaryis=coords)
                poly.style = poly_style
            elif len(coords) >= 1:
                # Cria ponto no primeiro par
                kml_obj.newpoint(name=name, description=description, coords=[coords[0]])
            
    except Exception as e:
        logger.error(f"Erro ao converter WKT para KML: {e}")


def generate_kml_single(alerta: Dict[str, Any]) -> Optional[Path]:
    """Gera um arquivo KML para um único alerta de desmatamento."""
    gid = alerta.get("gid_deter")
    municipio = alerta.get("municipio", "Amapa")
    classe = alerta.get("classe_label", "Alerta")
    area = alerta.get("area_ha", 0.0)
    wkt = alerta.get("geometria_wkt")

    if not wkt:
        logger.warning(f"Alerta GID={gid} não possui geometria WKT para KML")
        return None

    try:
        kml = simplekml.Kml()
        name = f"Alerta {gid} — {classe}"
        desc = (
            f"Alerta DETER GID: {gid}\n"
            f"Classe: {classe}\n"
            f"Área: {area:.1f} ha\n"
            f"Município: {municipio}\n"
            f"Data: {alerta.get('data_deteccao')[:10]}"
        )
        
        _add_polygon_to_kml(kml, name, wkt, desc)

        filename = f"alerta_desmatamento_{gid}.kml"
        filepath = KML_DIR / filename
        kml.save(str(filepath))
        return filepath
    except Exception as e:
        logger.error(f"Erro ao salvar KML individual para GID={gid}: {e}")
        return None


def generate_kml_24h(alertas: List[Dict[str, Any]]) -> Optional[Path]:
    """Gera um arquivo KML consolidado com todos os alertas das últimas 24 horas."""
    try:
        kml = simplekml.Kml()
        folder = kml.newfolder(name="Alertas Desmatamento Amapá (24h)")

        for a in alertas:
            gid = a.get("gid_deter")
            municipio = a.get("municipio", "Amapa")
            classe = a.get("classe_label", "Alerta")
            area = a.get("area_ha", 0.0)
            wkt = a.get("geometria_wkt")
            
            if not wkt:
                continue

            name = f"{classe} — {municipio} ({area:.1f} ha)"
            desc = (
                f"Alerta DETER GID: {gid}\n"
                f"Classe: {classe}\n"
                f"Área: {area:.1f} ha\n"
                f"Município: {municipio}\n"
                f"Data: {a.get('data_deteccao')[:10]}"
            )
            _add_polygon_to_kml(folder, name, wkt, desc)

        filepath = KML_DIR / "desmatamento_ultimas_24h.kml"
        kml.save(str(filepath))
        return filepath
    except Exception as e:
        logger.error(f"Erro ao salvar KML consolidado: {e}")
        return None

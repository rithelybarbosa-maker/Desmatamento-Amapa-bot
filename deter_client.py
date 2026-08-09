"""
deter_client.py — Conector com a API INPE DETER (WFS / GeoServer)
Busca alertas de desmatamento, degradação e mineração no Amapá.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import requests
try:
    from shapely.geometry import shape
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False


from config import AMAPA_BBOX_STR

logger = logging.getLogger(__name__)

DETER_WFS_URL = "https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/wfs"

# Mapeamento de classes DETER para ícones e rótulos amigáveis
CLASSES_DETER = {
    "DESMATAMENTO_CR":      ("🔴", "Desmatamento com Solo Exposto"),
    "DESMATAMENTO_VEG":     ("🟠", "Desmatamento com Vegetação"),
    "DEGRADACAO":           ("🟡", "Degradação Florestal"),
    "MINERACAO":            ("⛏️", "Mineração"),
    "CS_DESORDENADO":       ("🏘️", "Corte Seletivo Desordenado"),
    "CS_GEOMETRICO":        ("📐", "Corte Seletivo Geométrico"),
    "CICATRIZ_DE_QUEIMADA": ("🔥", "Cicatriz de Queimada"),
}

def get_class_info(classname: str) -> tuple[str, str]:
    """Retorna o emoji e rótulo amigável para a classe DETER."""
    classname_upper = str(classname).upper().strip()
    return CLASSES_DETER.get(classname_upper, ("⚠️", classname))


def fetch_deter_alerts(day_range: int = 7) -> List[Dict[str, Any]]:
    """
    Busca alertas recentes do DETER via WFS (GeoJSON).
    Retorna uma lista de alertas estruturados.
    """
    since_date = (datetime.utcnow() - timedelta(days=day_range)).strftime("%Y-%m-%d")
    
    # Filtro CQL: UF Amapá e data a partir da data de corte
    cql_filter = f"uf='AMAPÁ' AND date >= '{since_date}'"
    
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "deter_public",
        "CQL_FILTER": cql_filter,
        "outputFormat": "application/json",
        "count": 100,
        "sortBy": "gid",
    }

    try:
        logger.info(f"Conectando ao INPE DETER WFS (desde {since_date})...")
        resp = requests.get(DETER_WFS_URL, params=params, timeout=45)
        resp.raise_for_status()

        data = resp.json()
        features = data.get("features", [])
        logger.info(f"DETER retornou {len(features)} feições/alertas.")

        alertas = []
        for feat in features:
            props = feat.get("properties", {})
            geom_dict = feat.get("geometry")

            if not geom_dict or not props:
                continue

            gid = props.get("gid")
            if gid is None:
                continue

            # Parse da Geometria
            try:
                if SHAPELY_AVAILABLE:
                    geom = shape(geom_dict)
                    geometria_wkt = geom.wkt
                    lon_centro = geom.centroid.x
                    lat_centro = geom.centroid.y
                else:
                    # Fallback simples se Shapely não estiver disponível:
                    # Tenta estimar centroide a partir das coordenadas do GeoJSON
                    coords_type = geom_dict.get("type", "")
                    coords = geom_dict.get("coordinates", [])
                    
                    # Extração simples das coordenadas dependendo do tipo
                    all_pts = []
                    def extract_pts(lst):
                        if not lst:
                            return
                        if isinstance(lst[0], (int, float)):
                            all_pts.append(lst)
                        else:
                            for item in lst:
                                extract_pts(item)
                    
                    extract_pts(coords)
                    if all_pts:
                        lon_centro = sum(p[0] for p in all_pts) / len(all_pts)
                        lat_centro = sum(p[1] for p in all_pts) / len(all_pts)
                    else:
                        lon_centro = -51.5
                        lat_centro = 1.5 # Centro aproximado do AP
                        
                    # Cria WKT dummy simplificado
                    geometria_wkt = f"POINT ({lon_centro} {lat_centro})"
            except Exception as e:
                logger.error(f"Erro ao processar geometria do alerta DETER GID={gid}: {e}")
                continue

            # Determinação da Área em Hectares
            # O DETER costuma retornar a área em km² (areasqkm) ou hectares (area_ha)
            areasqkm = props.get("areasqkm")
            area_ha = props.get("area_ha")
            
            if area_ha is not None:
                area_ha = float(area_ha)
            elif areasqkm is not None:
                area_ha = float(areasqkm) * 100.0  # 1 km² = 100 ha
            else:
                area_ha = 0.0

            classname = props.get("classname", "Desconhecido")
            emoji, label = get_class_info(classname)

            # Data de detecção
            raw_date = props.get("date", "")
            # O DETER retorna date no formato YYYY-MM-DD. Adicionamos a hora padrão UTC
            if raw_date:
                data_deteccao = f"{raw_date}T12:00:00"
            else:
                data_deteccao = datetime.utcnow().isoformat()

            alertas.append({
                "gid_deter":        int(gid),
                "classe":           classname,
                "classe_label":     label,
                "area_ha":          area_ha,
                "data_deteccao":    data_deteccao,
                "municipio":        props.get("municipio"),
                "uf":               props.get("uf", "AP"),
                "latitude_centro":  lat_centro,
                "longitude_centro": lon_centro,
                "geometria_wkt":    geometria_wkt,
                "satelite":         props.get("satellite", "Desconhecido"),
            })

        return alertas

    except requests.Timeout:
        logger.error("Timeout na conexão com o INPE DETER WFS")
    except Exception as e:
        logger.error(f"Erro ao buscar alertas DETER: {e}", exc_info=True)

    return []


def check_api_connection() -> tuple[bool, str]:
    """Valida se o GeoServer do INPE DETER está online."""
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetCapabilities",
    }
    try:
        resp = requests.get(DETER_WFS_URL, params=params, timeout=15)
        if resp.status_code == 200:
            return True, "Conexão com GeoServer INPE DETER OK"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)

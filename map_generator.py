"""
map_generator.py — Geração de mapas interativos Folium com polígonos de desmatamento
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

import folium
from shapely.wkt import loads as wkt_loads

from config import MAPAS_DIR

logger = logging.getLogger(__name__)


def generate_map(alertas: List[Dict[str, Any]]) -> Optional[Path]:
    """
    Gera um mapa HTML interativo contendo os polígonos de desmatamento.
    Retorna o caminho do arquivo gerado ou None.
    """
    # Coordenadas centrais aproximadas do Amapá para inicializar o mapa
    amapa_centro = [1.4, -51.8]

    try:
        # Inicializa o mapa com camada satélite (Esri World Imagery) e padrão do OpenStreetMap
        mapa = folium.Map(location=amapa_centro, zoom_start=7)

        # Adiciona camada de satélite
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="Satélite (Esri)",
            overlay=False,
            control=True
        ).add_to(mapa)

        # Mantém OpenStreetMap como alternativa
        folium.TileLayer("openstreetmap", name="Mapa Político (OSM)").add_to(mapa)

        # Grupo de camadas para os polígonos
        alertas_group = folium.FeatureGroup(name="Alertas de Desmatamento (24h)").add_to(mapa)

        poligonos_adicionados = 0

        for a in alertas:
            gid = a.get("gid_deter")
            municipio = a.get("municipio", "Amapá")
            classe = a.get("classe_label", "Alerta")
            area = a.get("area_ha", 0.0)
            wkt = a.get("geometria_wkt")
            data = a.get("data_deteccao")[:10] if a.get("data_deteccao") else ""

            if not wkt:
                continue

            try:
                geom = wkt_loads(wkt)
                
                # Monta a estrutura GeoJSON
                geojson_feature = {
                    "type": "Feature",
                    "geometry": geom.__geo_interface__,
                    "properties": {}
                }

                popup_html = (
                    f"<div style='font-family: sans-serif; font-size: 13px; min-width: 180px;'>"
                    f"<b>🌳 Alerta DETER GID:</b> {gid}<br>"
                    f"<b>📋 Classe:</b> {classe}<br>"
                    f"<b>📐 Área:</b> {area:.1f} ha<br>"
                    f"<b>📍 Município:</b> {municipio}<br>"
                    f"<b>📅 Detecção:</b> {data}"
                    f"</div>"
                )

                # Cor e estilo do polígono conforme a classe
                color_map = {
                    "Desmatamento com Solo Exposto": ("red", "darkred"),
                    "Desmatamento com Vegetação":    ("orange", "darkorange"),
                    "Degradação Florestal":          ("yellow", "gold"),
                    "Mineração":                     ("purple", "purple"),
                }
                
                fill_color, border_color = color_map.get(classe, ("red", "darkred"))

                folium.GeoJson(
                    geojson_feature,
                    name=f"Alerta {gid}",
                    style_function=lambda x, fc=fill_color, bc=border_color: {
                        "fillColor": fc,
                        "color": bc,
                        "weight": 2,
                        "fillOpacity": 0.45
                    },
                    highlight_function=lambda x: {
                        "weight": 3,
                        "fillOpacity": 0.7
                    },
                    tooltip=f"{classe} ({area:.1f} ha) em {municipio}",
                    popup=folium.Popup(popup_html, max_width=250)
                ).add_to(alertas_group)

                poligonos_adicionados += 1

            except Exception as e:
                logger.error(f"Erro ao adicionar polígono do alerta GID={gid} ao mapa: {e}")

        # Se houver elementos, ajusta o foco do mapa para abranger todos os alertas
        # (Se geopandas estiver disponível)
        if poligonos_adicionados > 0:
            folium.LayerControl().add_to(mapa)

        filepath = MAPAS_DIR / "mapa_desmatamento_24h.html"
        mapa.save(str(filepath))
        logger.info(f"Mapa interativo HTML salvo com {poligonos_adicionados} polígono(s) em {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Erro ao gerar mapa Folium: {e}", exc_info=True)
        return None

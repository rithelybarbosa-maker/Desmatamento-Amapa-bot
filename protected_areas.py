"""
protected_areas.py — Verificação offline de proximidade com áreas protegidas (UCs e TIs)
"""

import math
from typing import List, Dict, Any

import database as db

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância em quilômetros entre dois pontos usando a fórmula de Haversine."""
    R = 6371.0  # Raio da Terra em km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = (math.sin(dphi / 2) ** 2 + 
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_nearby_protected_areas(lat: float, lon: float, threshold_km: float = 10.0) -> List[Dict[str, Any]]:
    """
    Busca Unidades de Conservação (UC) ou Terras Indígenas (TI) a menos de threshold_km do centróide.
    Retorna uma lista contendo nome, tipo, categoria e distância em km.
    """
    areas = db.get_all_areas_protegidas()
    nearby = []

    for area in areas:
        dist = _haversine(lat, lon, area["latitude"], area["longitude"])
        if dist <= threshold_km:
            nearby.append({
                "nome":      area["nome"],
                "tipo":      "Unidade de Conservação" if area["tipo"] == "UC" else "Terra Indígena",
                "categoria": area["categoria"],
                "distancia": round(dist, 1),
            })
            
    # Ordena pela proximidade
    nearby.sort(key=lambda x: x["distancia"])
    return nearby

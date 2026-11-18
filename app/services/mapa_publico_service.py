"""Serialización pública del resultado ya filtrado, sin consultas adicionales."""

from datetime import datetime, timezone
from math import isfinite

from app.services.panel_service import conectividad


def coordenada_valida(valor, limite):
    try:
        numero = float(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    return numero if isfinite(numero) and -limite <= numero <= limite else None


def en_linea(contenedor, ahora):
    """Solo un booleano: no se expone ningún dato del dispositivo."""
    dispositivo = next((d for d in contenedor.dispositivos if d.activo), None)
    return conectividad(dispositivo, ahora) == "ONLINE"


def datos_mapa_publico(puntos):
    ahora = datetime.now(timezone.utc)
    datos = []
    for punto in puntos:
        latitud = coordenada_valida(punto.latitud, 90)
        longitud = coordenada_valida(punto.longitud, 180)
        if latitud is None or longitud is None:
            latitud = longitud = None
        datos.append({
            "punto_id": punto.id, "nombre": punto.nombre, "direccion": punto.direccion,
            "latitud": latitud, "longitud": longitud,
            "materiales": sorted(material.nombre for material in punto.materiales),
            "contenedores": [{
                "codigo": contenedor.codigo, "estado": contenedor.estado,
                "porcentaje_llenado": contenedor.porcentaje_llenado,
                "ultima_actualizacion": (contenedor.ultima_actualizacion.isoformat() + "Z"
                                          if contenedor.ultima_actualizacion else None),
                "en_linea": en_linea(contenedor, ahora),
            } for contenedor in sorted(punto.contenedores, key=lambda c: c.codigo) if contenedor.activo],
        })
    return datos

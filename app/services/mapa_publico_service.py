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


def minutos_desde(fecha, ahora=None):
    """Minutos transcurridos desde `fecha` (UTC), o None si no hay dato."""
    if fecha is None:
        return None
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is not None:
        ahora = ahora.astimezone(timezone.utc).replace(tzinfo=None)
    if fecha.tzinfo is not None:
        fecha = fecha.astimezone(timezone.utc).replace(tzinfo=None)
    segundos = (ahora - fecha).total_seconds()
    return int(max(segundos, 0) // 60)


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
                "conectividad": conectividad(contenedor.dispositivo_activo, ahora),
                "hace_minutos": minutos_desde(contenedor.ultima_actualizacion, ahora),
            } for contenedor in sorted(punto.contenedores, key=lambda c: c.codigo) if contenedor.activo],
        })
    return datos

"""Presentación de fechas UTC en hora local de Chile, sin alterar su origen."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ZONA_CHILE = ZoneInfo("America/Santiago")


def fecha_chile(valor, sin_fecha="Sin datos"):
    if valor is None:
        return sin_fecha
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(ZONA_CHILE).strftime("%d-%m-%Y %H:%M:%S")


def hace_tiempo(valor, sin_dato="Sin dato"):
    """Tiempo transcurrido en palabras («hace 3 min»), para la vista pública."""
    if valor is None:
        return sin_dato
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    ahora = datetime.now(timezone.utc)
    segundos = max(int((ahora - valor.astimezone(timezone.utc)).total_seconds()), 0)
    if segundos < 60:
        return "hace menos de 1 min"
    minutos = segundos // 60
    if minutos < 60:
        return f"hace {minutos} min"
    horas = minutos // 60
    if horas < 24:
        return f"hace {horas} h"
    dias = horas // 24
    return "hace 1 día" if dias == 1 else f"hace {dias} días"

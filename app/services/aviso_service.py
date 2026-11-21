"""Reportes ciudadanos anónimos (HU07): validación, límite y persistencia."""

import threading
import time
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import AvisoCiudadano

# Opciones que ve el ciudadano, con la clave que se guarda en la base.
TIPOS_AVISO = {
    "BASURA_FUERA": "Basura afuera del contenedor",
    "CONTENEDOR_DANADO": "Contenedor dañado",
    "MAL_USO": "Mal uso del punto",
}

MAX_COMENTARIO = 140
MAX_AVISOS_POR_VENTANA = 5
VENTANA_SEGUNDOS = 600

# El reporte es anónimo y no pide cuenta, por lo que el límite se aplica por IP
# en memoria. Con un solo worker (render.yaml) el control es efectivo; si algún
# día se escalara a varios workers habría que moverlo a la base de datos.
_intentos = {}
_candado = threading.Lock()


def etiqueta_tipo(tipo):
    return TIPOS_AVISO.get(tipo, tipo)


def validar_aviso(datos):
    tipo = (datos.get("tipo") or "").strip()
    comentario = (datos.get("comentario") or "").strip()
    if tipo not in TIPOS_AVISO:
        raise ValueError("Selecciona un problema válido.")
    if len(comentario) > MAX_COMENTARIO:
        raise ValueError(f"El comentario admite hasta {MAX_COMENTARIO} caracteres.")
    return {"tipo": tipo, "comentario": comentario}


def limite_excedido(ip):
    """Registrar el intento y avisar si el ciudadano ya superó el límite."""
    ahora = time.time()
    with _candado:
        recientes = [marca for marca in _intentos.get(ip, [])
                     if ahora - marca < VENTANA_SEGUNDOS]
        excedido = len(recientes) >= MAX_AVISOS_POR_VENTANA
        if not excedido:
            recientes.append(ahora)
        _intentos[ip] = recientes
        return excedido


def restablecer_limite():
    """Vaciar los intentos registrados (útil para las pruebas)."""
    with _candado:
        _intentos.clear()


def crear_aviso(punto_id, tipo, comentario):
    fecha = datetime.now(timezone.utc).replace(tzinfo=None)
    aviso = AvisoCiudadano(
        punto_id=punto_id, tipo=tipo, comentario=comentario,
        estado="NUEVO", creado_en=fecha,
    )
    db.session.add(aviso)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return aviso


def listar_avisos(estado=None):
    consulta = db.select(AvisoCiudadano).order_by(
        AvisoCiudadano.creado_en.desc(), AvisoCiudadano.id.desc())
    if estado is not None:
        consulta = consulta.where(AvisoCiudadano.estado == estado)
    return db.session.scalars(consulta).all()

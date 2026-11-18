"""Bitácora de cambios de la administración, calculada antes del commit."""

from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import inspect

from app.extensions import db
from app.models import (Bitacora, Contenedor, DispositivoIoT, Horario, Material, PuntoMaterial,
                        PuntoReciclaje, Usuario)

ENTIDADES = {
    PuntoReciclaje: "punto", Contenedor: "contenedor", Material: "material", Horario: "horario",
    Usuario: "usuario", DispositivoIoT: "dispositivo", PuntoMaterial: "punto_material",
}
# Del dispositivo solo se registran estos campos: nunca IP, BOOT, SEQ ni claves.
CAMPOS_DISPOSITIVO = ("identificador", "contenedor_id", "activo")
# El hash nunca se copia: solo se anota que hubo un cambio de contraseña.
CAMPO_PASSWORD = "password_hash"


def _campos(obj):
    if isinstance(obj, DispositivoIoT):
        return CAMPOS_DISPOSITIVO
    return [atributo.key for atributo in inspect(obj).mapper.column_attrs if atributo.key != "id"]


def _valor(valor):
    """Convertir a un valor serializable en JSON."""
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def _entidad_id(obj):
    # punto_material no tiene id propio: se identifica por el punto afectado.
    return obj.punto_id if isinstance(obj, PuntoMaterial) else obj.id


def _detalle_edicion(obj):
    estado = inspect(obj)
    detalle = {}
    for campo in _campos(obj):
        historia = estado.attrs[campo].history
        if not historia.has_changes():
            continue
        if campo == CAMPO_PASSWORD:
            detalle["contraseña"] = "contraseña cambiada"
            continue
        detalle[campo] = {
            "anterior": _valor(historia.deleted[0]) if historia.deleted else None,
            "nuevo": _valor(historia.added[0]) if historia.added else None,
        }
    return detalle


def _detalle_valores(obj, creado):
    detalle = {}
    for campo in _campos(obj):
        if campo == CAMPO_PASSWORD:
            if creado:
                detalle["contraseña"] = "contraseña asignada"
            continue
        valor = _valor(getattr(obj, campo))
        detalle[campo] = {"anterior": None, "nuevo": valor} if creado else {"anterior": valor, "nuevo": None}
    return detalle


def registrar_cambios(autor):
    """Agregar a la sesión una fila de bitácora por objeto administrado pendiente.

    Llamar antes del commit o de un flush manual: después la sesión ya no
    conserva los objetos nuevos ni el historial de los cambios. La función hace
    su propio flush para conocer los ids de los objetos creados.
    """
    pendientes = []
    # Una carga diferida no debe vaciar la sesión antes de leer los cambios.
    with db.session.no_autoflush:
        autor_id = autor.id
        for obj in list(db.session.new):
            if type(obj) in ENTIDADES:
                pendientes.append(dict(obj=obj, accion="CREAR"))
        for obj in list(db.session.dirty):
            if type(obj) in ENTIDADES:
                detalle = _detalle_edicion(obj)
                if detalle:
                    desactivado = detalle.get("activo", {}).get("nuevo") is False
                    pendientes.append(dict(obj=obj, accion="DESACTIVAR" if desactivado else "EDITAR",
                                           detalle=detalle, entidad_id=_entidad_id(obj)))
        for obj in list(db.session.deleted):
            if type(obj) in ENTIDADES:
                pendientes.append(dict(obj=obj, accion="ELIMINAR", detalle=_detalle_valores(obj, creado=False),
                                       entidad_id=_entidad_id(obj)))
    if not pendientes:
        return
    db.session.flush()
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    for pendiente in pendientes:
        obj = pendiente["obj"]
        if pendiente["accion"] == "CREAR":
            pendiente["detalle"] = _detalle_valores(obj, creado=True)
            pendiente["entidad_id"] = _entidad_id(obj)
        db.session.add(Bitacora(
            usuario_id=autor_id, accion=pendiente["accion"], entidad=ENTIDADES[type(obj)],
            entidad_id=pendiente["entidad_id"], detalle=pendiente["detalle"], creado_en=ahora))

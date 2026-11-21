"""Límite de intentos fallidos de inicio de sesión (bloqueo temporal)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import IntentoLogin

MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 600


def _limite():
    return (datetime.now(timezone.utc) - timedelta(seconds=VENTANA_SEGUNDOS)).replace(tzinfo=None)


def _contar(campo, valor):
    columna = getattr(IntentoLogin, campo)
    return db.session.scalar(db.select(db.func.count()).select_from(IntentoLogin).where(
        columna == valor, IntentoLogin.creado_en >= _limite()))


def bloqueado(ip, username):
    """Indicar si la IP o el usuario ya alcanzó el máximo de fallos recientes."""
    if _contar("ip", ip) >= MAX_INTENTOS:
        return True
    if username and _contar("username", username) >= MAX_INTENTOS:
        return True
    return False


def registrar_fallo(ip, username):
    fecha = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.add(IntentoLogin(ip=ip, username=username, creado_en=fecha))
    try:
        db.session.commit()
    except SQLAlchemyError:
        # Un fallo al registrar el intento no debe tumbar el inicio de sesión.
        db.session.rollback()


def limpiar_exitoso(username):
    """Olvidar los fallos previos de un usuario que acaba de ingresar bien."""
    if not username:
        return
    db.session.execute(db.delete(IntentoLogin).where(IntentoLogin.username == username))
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()

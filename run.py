import logging
import time

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app import create_app
from app.extensions import db

logger = logging.getLogger(__name__)

app = create_app()


def _agregar_calibracion_dispositivo(engine):
    """Agregar columnas de calibración a bases existentes (idempotente).

    create_all no agrega columnas a tablas ya creadas; Render no ofrece Shell,
    por lo que esta migración aditiva corre al arrancar.
    """
    with engine.begin() as conexion:
        columnas = {c["name"] for c in inspect(conexion).get_columns("dispositivo_iot")}
        tipo = "DOUBLE PRECISION" if engine.dialect.name == "postgresql" else "FLOAT"
        if "distancia_vacio_cm" not in columnas:
            conexion.execute(text(
                f"ALTER TABLE dispositivo_iot ADD COLUMN distancia_vacio_cm {tipo} "
                "NOT NULL DEFAULT 175.0"))
        if "distancia_lleno_cm" not in columnas:
            conexion.execute(text(
                f"ALTER TABLE dispositivo_iot ADD COLUMN distancia_lleno_cm {tipo} "
                "NOT NULL DEFAULT 25.0"))


def _relajar_modo_compuerta(engine):
    """Permitir lecturas solo de sensores: modo/compuerta pasan a ser opcionales.

    Solo aplica a PostgreSQL (bases existentes); SQLite se recrea con create_all.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conexion:
        for columna in ("modo", "compuerta"):
            conexion.execute(text(
                f"ALTER TABLE medicion ALTER COLUMN {columna} DROP NOT NULL"))


def _inicializar():
    """Crear tablas y cargar datos de demostración (idempotente).

    En Render el plan gratuito no ofrece Shell, por lo que la aplicación se
    inicializa sola al arrancar: crea el esquema si falta y agrega solo los
    registros de demostración ausentes.
    """
    with app.app_context():
        db.create_all()
        _agregar_calibracion_dispositivo(db.engine)
        _relajar_modo_compuerta(db.engine)
        from seed import cargar_datos  # import tardío: no ejecuta el main de seed.py
        cargar_datos()
        from seed import cargar_dispositivos
        cargar_dispositivos()


for intento in range(10):
    try:
        _inicializar()
    except OperationalError:
        if intento == 9:
            raise
        logger.warning("Base de datos no disponible; reintentando en 3 s...")
        time.sleep(3)
    else:
        break

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

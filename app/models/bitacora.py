from app.extensions import db

ACCIONES = ("CREAR", "EDITAR", "DESACTIVAR", "ELIMINAR")
ENTIDADES = ("punto", "contenedor", "material", "horario", "usuario", "dispositivo", "punto_material")


class Bitacora(db.Model):
    """Registro de solo lectura de los cambios hechos desde la administración."""

    __tablename__ = "bitacora"
    __table_args__ = (
        db.CheckConstraint("accion IN ('CREAR', 'EDITAR', 'DESACTIVAR', 'ELIMINAR')", name="ck_bitacora_accion"),
        db.CheckConstraint(
            "entidad IN ('punto', 'contenedor', 'material', 'horario', 'usuario', 'dispositivo', 'punto_material')",
            name="ck_bitacora_entidad"),
    )

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    accion = db.Column(db.String(20), nullable=False)
    entidad = db.Column(db.String(30), nullable=False)
    # En punto_material, que no tiene id propio, guarda el punto afectado.
    entidad_id = db.Column(db.Integer, nullable=False)
    # Campos cambiados: {"campo": {"anterior": ..., "nuevo": ...}}. Nunca secretos.
    detalle = db.Column(db.JSON, nullable=False)
    creado_en = db.Column(db.DateTime, nullable=False)

    usuario = db.relationship("Usuario")

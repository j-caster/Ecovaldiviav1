from app.extensions import db


class AvisoCiudadano(db.Model):
    """Reporte anónimo de un ciudadano sobre una incidencia en un punto."""

    __tablename__ = "aviso_ciudadano"
    __table_args__ = (
        db.CheckConstraint(
            "tipo IN ('BASURA_FUERA', 'CONTENEDOR_DANADO', 'MAL_USO')",
            name="ck_aviso_ciudadano_tipo",
        ),
        db.CheckConstraint(
            "estado IN ('NUEVO', 'ATENDIDO')", name="ck_aviso_ciudadano_estado"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    punto_id = db.Column(db.Integer, db.ForeignKey("punto_reciclaje.id"), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    comentario = db.Column(db.String(140), nullable=False, default="")
    estado = db.Column(db.String(20), nullable=False, default="NUEVO")
    creado_en = db.Column(db.DateTime, nullable=False)
    # Foto opcional del reporte; solo la ve el operador/administrador.
    foto = db.Column(db.LargeBinary)
    foto_mime = db.Column(db.String(50))

    punto = db.relationship("PuntoReciclaje", back_populates="avisos")

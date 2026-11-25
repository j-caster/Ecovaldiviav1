from app.extensions import db


class DispositivoIoT(db.Model):
    __tablename__ = "dispositivo_iot"
    __table_args__ = (
        db.CheckConstraint("contador_lleno BETWEEN 0 AND 3", name="ck_dispositivo_contador_lleno"),
        db.Index(
            "uq_dispositivo_activo_contenedor", "contenedor_id", unique=True,
            sqlite_where=db.text("activo = true"),
            postgresql_where=db.text("activo = true"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    identificador = db.Column(db.String(100), nullable=False, unique=True)
    contenedor_id = db.Column(db.Integer, db.ForeignKey("contenedor.id"), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    modo_actual = db.Column(db.String(10))
    compuerta_actual = db.Column(db.String(10))
    ultima_ip = db.Column(db.String(45))
    ultimo_boot = db.Column(db.String(100))
    ultimo_seq = db.Column(db.BigInteger)
    ultima_actualizacion = db.Column(db.DateTime)
    contador_lleno = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    boot_confirmacion = db.Column(db.String(100))
    # Calibración del contenedor físico: distancia (cm) al fondo cuando está
    # vacío y cuando está lleno. Cada contenedor puede tener la suya.
    distancia_vacio_cm = db.Column(db.Float, nullable=False, default=175.0)
    distancia_lleno_cm = db.Column(db.Float, nullable=False, default=25.0)

    contenedor = db.relationship("Contenedor", back_populates="dispositivos")
    mediciones = db.relationship("Medicion", back_populates="dispositivo")

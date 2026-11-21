from app.extensions import db


class IntentoLogin(db.Model):
    """Intento fallido de inicio de sesión, para limitar fuerza bruta."""

    __tablename__ = "intento_login"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), nullable=False)
    username = db.Column(db.String(100), nullable=False, default="")
    creado_en = db.Column(db.DateTime, nullable=False)

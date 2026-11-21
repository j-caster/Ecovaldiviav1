from flask import Flask

from config import Config
from app.extensions import db, login_manager
from app.services.security import csrf_token
from app.services.fecha_service import fecha_chile, hace_tiempo
from app.services.panel_service import conectividad


def create_app(config_class=Config):
    """Crear y configurar una instancia de EcoValdivia."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager.init_app(app)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["conectividad"] = conectividad
    app.jinja_env.filters["fecha_chile"] = fecha_chile
    app.jinja_env.filters["hace_tiempo"] = hace_tiempo

    from app import models

    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.operacion import operacion_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(operacion_bp)
    return app

from io import BytesIO

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy import case
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Alerta, AvisoCiudadano, Contenedor, EventoOperacional
from app.services.aviso_service import etiqueta_tipo
from app.services.operacion_service import registrar_vaciado
from app.services.security import roles_required, validar_csrf

operacion_bp = Blueprint("operacion", __name__, url_prefix="/operacion")


@operacion_bp.before_request
@roles_required("operador", "administrador")
def proteger_operacion():
    if request.method == "POST":
        validar_csrf()


@operacion_bp.get("/alertas")
def alertas():
    filtro = request.args.get("estado", "todas")
    if filtro not in ("todas", "activas"):
        abort(400, description="Filtro de alertas inválido.")
    total_activas = db.session.scalar(db.select(db.func.count()).select_from(Alerta).where(Alerta.activa.is_(True)))
    consulta = db.select(Alerta).options(
        joinedload(Alerta.contenedor).joinedload(Contenedor.punto)).order_by(
        Alerta.activa.desc(), Alerta.creada_en.desc(), Alerta.id.desc())
    if filtro == "activas":
        consulta = consulta.where(Alerta.activa.is_(True))
    pagina = db.paginate(consulta, per_page=50)
    contenedores = db.session.scalars(db.select(Contenedor).where(
        Contenedor.activo.is_(True)).order_by(Contenedor.codigo)).all()
    return render_template("operacion/alertas.html", pagina=pagina, contenedores=contenedores,
                           total_activas=total_activas, filtro=filtro)


@operacion_bp.post("/contenedores/<int:contenedor_id>/vaciado")
def vaciado(contenedor_id):
    db.get_or_404(Contenedor, contenedor_id)
    try:
        registrar_vaciado(contenedor_id, current_user.id)
    except ValueError as error:
        flash(str(error), "danger")
    except SQLAlchemyError:
        flash("No se pudo registrar el vaciado. Intenta nuevamente.", "danger")
    else:
        flash("Vaciado registrado. Alertas cerradas; pendiente de nueva lectura.", "success")
    return redirect(url_for("operacion.alertas"))


@operacion_bp.get("/historial")
def historial():
    pagina = db.paginate(db.select(EventoOperacional).options(
        joinedload(EventoOperacional.contenedor), joinedload(EventoOperacional.usuario)).order_by(
        EventoOperacional.creado_en.desc(), EventoOperacional.id.desc()), per_page=50)
    return render_template("operacion/historial.html", pagina=pagina)


@operacion_bp.get("/avisos")
def avisos():
    """Reportes ciudadanos: primero los nuevos, luego los atendidos."""
    consulta = db.select(AvisoCiudadano).options(
        joinedload(AvisoCiudadano.punto)).order_by(
        case((AvisoCiudadano.estado == "NUEVO", 0), else_=1),
        AvisoCiudadano.creado_en.desc(), AvisoCiudadano.id.desc())
    pagina = db.paginate(consulta, per_page=50)
    total_nuevos = db.session.scalar(db.select(db.func.count()).select_from(
        AvisoCiudadano).where(AvisoCiudadano.estado == "NUEVO"))
    return render_template("operacion/avisos.html", pagina=pagina, total_nuevos=total_nuevos,
                           etiqueta_tipo=etiqueta_tipo)


@operacion_bp.post("/avisos/<int:aviso_id>/atendido")
def aviso_atendido(aviso_id):
    aviso = db.get_or_404(AvisoCiudadano, aviso_id)
    aviso.estado = "ATENDIDO"
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("No se pudo actualizar el aviso. Intenta nuevamente.", "danger")
    else:
        flash("Aviso marcado como atendido.", "success")
    return redirect(url_for("operacion.avisos"))


@operacion_bp.get("/avisos/<int:aviso_id>/foto")
def aviso_foto(aviso_id):
    """Foto adjunta a un reporte, visible solo para operador y administrador."""
    aviso = db.get_or_404(AvisoCiudadano, aviso_id)
    if not aviso.foto:
        abort(404)
    return send_file(
        BytesIO(aviso.foto),
        mimetype=aviso.foto_mime or "image/jpeg",
        as_attachment=False,
        max_age=0,
    )

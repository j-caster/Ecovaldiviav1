from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Contenedor, Material, PuntoReciclaje
from app.services.mapa_publico_service import datos_mapa_publico
from app.services.aviso_service import crear_aviso, limite_excedido, validar_aviso

public_bp = Blueprint("public", __name__)


def consultar_puntos_publicos():
    """Compartir exactamente el filtro entre HTML y actualización JSON."""
    materiales = db.session.scalars(db.select(Material).order_by(Material.nombre)).all()
    valor = request.args.get("material", "").strip()
    material_id = None
    error_filtro = None
    if valor:
        try:
            material_id = int(valor)
        except ValueError:
            error_filtro = "El material seleccionado no es válido."
        else:
            if material_id not in {material.id for material in materiales}:
                error_filtro = "El material seleccionado no existe."

    consulta = db.select(PuntoReciclaje).where(PuntoReciclaje.activo.is_(True)).options(
        selectinload(PuntoReciclaje.materiales),
        selectinload(PuntoReciclaje.horarios),
        selectinload(PuntoReciclaje.contenedores).selectinload(Contenedor.dispositivos),
    ).order_by(PuntoReciclaje.nombre)
    if material_id is not None:
        consulta = consulta.where(PuntoReciclaje.materiales.any(Material.id == material_id))
    puntos = [] if error_filtro else db.session.scalars(consulta).all()
    return puntos, materiales, material_id, error_filtro


@public_bp.route("/")
def index():
    puntos, materiales, material_id, error_filtro = consultar_puntos_publicos()
    return render_template(
        "index.html", puntos=puntos, materiales=materiales, puntos_mapa=datos_mapa_publico(puntos),
        material_id=material_id, error_filtro=error_filtro,
        dias_semana=("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"),
    )


@public_bp.get("/salud")
def salud():
    """Comprobación de vida para el hosting: no consulta la base de datos."""
    return jsonify(estado="ok")


@public_bp.get("/public/datos")
def datos():
    puntos, _, _, _ = consultar_puntos_publicos()
    respuesta = jsonify(puntos=datos_mapa_publico(puntos))
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@public_bp.post("/public/avisos")
def reportar_aviso():
    """Recibir un reporte ciudadano anónimo sobre un punto de reciclaje."""
    if limite_excedido(request.remote_addr or "desconocida"):
        return jsonify(ok=False, error="Límite de avisos alcanzado. Intenta más tarde."), 429

    datos = request.get_json(silent=True) or request.form
    try:
        punto_id = int(datos.get("punto_id", ""))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Selecciona un punto válido."), 400

    punto = db.session.get(PuntoReciclaje, punto_id)
    if punto is None or not punto.activo:
        return jsonify(ok=False, error="El punto seleccionado no está disponible."), 404

    try:
        valores = validar_aviso(datos)
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 400

    try:
        aviso = crear_aviso(punto.id, valores["tipo"], valores["comentario"])
    except SQLAlchemyError:
        return jsonify(ok=False, error="No pudimos guardar el aviso. Intenta nuevamente."), 500

    return jsonify(ok=True, aviso_id=aviso.id,
                   mensaje="Gracias. El operador verá tu aviso en su panel."), 201

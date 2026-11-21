"""Reporte ciudadano anónimo (HU07): validación, límite y atención en el panel."""

import io
import unittest

from app import create_app
from app.extensions import db
from app.models import AvisoCiudadano, PuntoReciclaje
from app.services import aviso_service
from app.services.aviso_service import MAX_AVISOS_POR_VENTANA, restablecer_limite
from config import Config
from seed import cargar_datos


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class AvisosCiudadanosTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.contexto = self.app.app_context()
        self.contexto.push()
        db.create_all()
        cargar_datos()
        restablecer_limite()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.contexto.pop()

    def token(self):
        self.client.get("/login")
        with self.client.session_transaction() as sesion:
            return sesion["csrf_token"]

    def login(self, username, password):
        return self.client.post("/login", data={
            "username": username, "password": password, "csrf_token": self.token(),
        })

    def punto(self):
        return db.session.scalar(db.select(PuntoReciclaje).where(PuntoReciclaje.activo.is_(True)))

    def enviar(self, punto_id=None, tipo="BASURA_FUERA", comentario=""):
        punto_id = self.punto().id if punto_id is None else punto_id
        return self.client.post("/public/avisos", json={
            "punto_id": punto_id, "tipo": tipo, "comentario": comentario,
        })

    def test_vista_publica_muestra_boton_y_modal(self):
        respuesta = self.client.get("/")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn("btn-avisar-problema", html)
        self.assertIn('id="modal-aviso"', html)
        self.assertIn("js/aviso_ciudadano.js", html)
        self.assertIn("Tu aviso es anónimo", html)

    def test_envio_anomino_valido(self):
        punto = self.punto()
        porcentaje = next(c.porcentaje_llenado for c in punto.contenedores if c.activo)
        respuesta = self.enviar(punto.id, "BASURA_FUERA", "Hay sacos al lado del contenedor.")
        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(respuesta.json["ok"])
        aviso = db.session.scalar(db.select(AvisoCiudadano))
        self.assertEqual(aviso.punto_id, punto.id)
        self.assertEqual(aviso.tipo, "BASURA_FUERA")
        self.assertEqual(aviso.estado, "NUEVO")
        # El aviso no altera la medición del sensor.
        self.assertEqual(next(c.porcentaje_llenado for c in punto.contenedores if c.activo), porcentaje)

    def test_tipo_faltante_o_invalido_rechazado(self):
        punto = self.punto()
        self.assertEqual(self.enviar(punto.id, tipo="").status_code, 400)
        self.assertEqual(self.enviar(punto.id, tipo="OTRO").status_code, 400)
        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(AvisoCiudadano)), 0)

    def test_comentario_largo_rechazado(self):
        respuesta = self.enviar(comentario="x" * 141)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("140", respuesta.json["error"])

    def test_punto_inexistente_o_inactivo_rechazado(self):
        punto = self.punto()
        self.assertEqual(self.enviar(punto_id=999999).status_code, 404)
        punto.activo = False
        db.session.commit()
        self.assertEqual(self.enviar(punto_id=punto.id).status_code, 404)

    def test_limite_anomimo_por_ip(self):
        punto = self.punto()
        for _ in range(MAX_AVISOS_POR_VENTANA):
            self.assertEqual(self.enviar(punto.id).status_code, 201)
        respuesta = self.enviar(punto.id)
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("Límite", respuesta.json["error"])

    def test_anonimo_no_accede_al_listado_operador(self):
        respuesta = self.client.get("/operacion/avisos")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.location)

    def test_operador_ve_aviso_y_lo_marca_atendido(self):
        punto = self.punto()
        self.enviar(punto.id, "CONTENEDOR_DANADO", "Puerta rota.")
        self.assertEqual(self.login("operador", "Operador123!").status_code, 302)
        respuesta = self.client.get("/operacion/avisos")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Contenedor dañado", respuesta.get_data(as_text=True))
        aviso = db.session.scalar(db.select(AvisoCiudadano))
        self.assertEqual(aviso.estado, "NUEVO")
        # Marcar atendido exige el token CSRF de la sesión.
        self.assertEqual(self.client.post(f"/operacion/avisos/{aviso.id}/atendido").status_code, 400)
        respuesta = self.client.post(
            f"/operacion/avisos/{aviso.id}/atendido", data={"csrf_token": self.token()})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(db.session.get(AvisoCiudadano, aviso.id).estado, "ATENDIDO")

    def test_envio_con_foto_opcional(self):
        punto = self.punto()
        contenido = b"imagen-de-prueba"
        respuesta = self.client.post("/public/avisos", data={
            "punto_id": str(punto.id), "tipo": "BASURA_FUERA", "comentario": "Con foto.",
            "foto": (io.BytesIO(contenido), "foto.png"),
        }, content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 201)
        aviso = db.session.scalar(db.select(AvisoCiudadano))
        self.assertEqual(aviso.foto, contenido)
        self.assertEqual(aviso.foto_mime, "image/png")
        # Solo el operador puede ver la foto adjunta.
        self.assertEqual(self.client.get(f"/operacion/avisos/{aviso.id}/foto").status_code, 302)
        self.login("operador", "Operador123!")
        respuesta_foto = self.client.get(f"/operacion/avisos/{aviso.id}/foto")
        self.assertEqual(respuesta_foto.status_code, 200)
        self.assertEqual(respuesta_foto.data, contenido)

    def test_foto_tipo_no_permitido_rechazada(self):
        punto = self.punto()
        respuesta = self.client.post("/public/avisos", data={
            "punto_id": str(punto.id), "tipo": "BASURA_FUERA", "comentario": "",
            "foto": (io.BytesIO(b"no-es-imagen"), "nota.txt"),
        }, content_type="multipart/form-data")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("JPG, PNG o WebP", respuesta.json["error"])

    def test_foto_grande_rechazada(self):
        punto = self.punto()
        original = aviso_service.MAX_FOTO_BYTES
        aviso_service.MAX_FOTO_BYTES = 10
        try:
            respuesta = self.client.post("/public/avisos", data={
                "punto_id": str(punto.id), "tipo": "BASURA_FUERA", "comentario": "",
                "foto": (io.BytesIO(b"x" * 20), "foto.png"),
            }, content_type="multipart/form-data")
        finally:
            aviso_service.MAX_FOTO_BYTES = original
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("5 MB", respuesta.json["error"])


if __name__ == "__main__":
    unittest.main()

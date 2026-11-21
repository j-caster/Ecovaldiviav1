"""Endpoint de cámara: roles y no exposición de la URL RTSP (M1/M2)."""

import os
import unittest

from app import create_app
from app.extensions import db
from app.models import PuntoReciclaje
from app.services.camara_service import PUNTO_CON_CAMARA
from config import Config
from seed import cargar_datos


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class CamaraTests(unittest.TestCase):
    def setUp(self):
        os.environ["ECOV_CAMARA_RTSP_URL"] = "rtsp://usuario:clave@192.168.1.26/live0"
        self.app = create_app(TestConfig)
        self.contexto = self.app.app_context()
        self.contexto.push()
        db.create_all()
        cargar_datos()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.contexto.pop()
        os.environ.pop("ECOV_CAMARA_RTSP_URL", None)

    def token(self):
        self.client.get("/login")
        with self.client.session_transaction() as sesion:
            return sesion["csrf_token"]

    def login(self, username, password):
        return self.client.post("/login", data={
            "username": username, "password": password, "csrf_token": self.token(),
        })

    def punto_camara(self):
        return db.session.scalar(db.select(PuntoReciclaje).where(
            PuntoReciclaje.nombre == PUNTO_CON_CAMARA))

    def punto_sin_camara(self):
        return db.session.scalar(db.select(PuntoReciclaje).where(
            PuntoReciclaje.nombre != PUNTO_CON_CAMARA))

    def test_anonimo_recibe_redireccion(self):
        respuesta = self.client.get(f"/api/camara/{self.punto_camara().id}")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.location)

    def test_operador_recibe_camara_sin_rtsp_url(self):
        self.login("operador", "Operador123!")
        respuesta = self.client.get(f"/api/camara/{self.punto_camara().id}")
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json
        self.assertTrue(datos["ok"])
        self.assertNotIn("rtsp_url", datos)
        self.assertIn("stream_src", datos)
        self.assertIn("stream_host", datos)

    def test_punto_sin_camara_responde_404(self):
        self.login("operador", "Operador123!")
        respuesta = self.client.get(f"/api/camara/{self.punto_sin_camara().id}")
        self.assertEqual(respuesta.status_code, 404)

    def test_sin_rtsp_configurada_no_hay_camara(self):
        os.environ.pop("ECOV_CAMARA_RTSP_URL", None)
        self.login("operador", "Operador123!")
        respuesta = self.client.get(f"/api/camara/{self.punto_camara().id}")
        self.assertEqual(respuesta.status_code, 404)


if __name__ == "__main__":
    unittest.main()

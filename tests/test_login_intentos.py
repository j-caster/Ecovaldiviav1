"""Límite de intentos fallidos de inicio de sesión (M4)."""

import unittest

from app import create_app
from app.extensions import db
from app.models import IntentoLogin
from config import Config
from seed import cargar_datos


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class LoginIntentosTests(unittest.TestCase):
    def setUp(self):
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

    def token(self):
        self.client.get("/login")
        with self.client.session_transaction() as sesion:
            return sesion["csrf_token"]

    def login(self, username, password):
        return self.client.post("/login", data={
            "username": username, "password": password, "csrf_token": self.token(),
        })

    def test_bloqueo_tras_cinco_fallos(self):
        for _ in range(5):
            self.login("admin", "incorrecta")
        respuesta = self.login("admin", "Admin123!")
        self.assertIn(b"Demasiados intentos", respuesta.data)
        self.assertEqual(self.client.get("/panel").status_code, 302)

    def test_bloqueo_por_ip_afecta_a_otros_usuarios(self):
        for _ in range(5):
            self.login("admin", "incorrecta")
        respuesta = self.login("operador", "Operador123!")
        self.assertIn(b"Demasiados intentos", respuesta.data)
        self.assertEqual(self.client.get("/panel").status_code, 302)

    def test_exito_funciona_con_menos_de_cinco_fallos(self):
        for _ in range(2):
            self.login("admin", "incorrecta")
        self.assertEqual(self.login("admin", "Admin123!").status_code, 302)
        self.assertEqual(self.client.get("/panel").status_code, 200)

    def test_cada_fallo_queda_registrado(self):
        self.login("admin", "incorrecta")
        self.assertEqual(db.session.scalar(db.select(db.func.count()).select_from(IntentoLogin)), 1)
        intento = db.session.scalar(db.select(IntentoLogin))
        self.assertEqual(intento.username, "admin")
        self.assertIn(intento.ip, ("127.0.0.1", "test"))


if __name__ == "__main__":
    unittest.main()

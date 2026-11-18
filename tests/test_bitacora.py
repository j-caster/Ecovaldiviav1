"""Bitácora de la administración: registro, secretos excluidos y acceso por rol."""

import json
import unittest
from datetime import time

from flask import g

from app import create_app
from app.extensions import db
from app.models import Bitacora, Contenedor, DispositivoIoT, Horario, PuntoReciclaje, Usuario
from config import Config
from seed import cargar_datos


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class BitacoraTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        cargar_datos()
        self.admin = db.session.scalar(db.select(Usuario).where(Usuario.username == "admin"))
        self.client = self.app.test_client()
        self.login(self.client, "admin", "Admin123!")

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def post(self, path, datos=None, client=None):
        client = client or self.client
        g.pop("_login_user", None)
        client.get("/login", follow_redirects=True)
        with client.session_transaction() as session:
            token = session["csrf_token"]
        respuesta = client.post(path, data={**(datos or {}), "csrf_token": token})
        g.pop("_login_user", None)
        return respuesta

    def login(self, client, username, password):
        return self.post("/login", {"username": username, "password": password}, client)

    def filas(self):
        return db.session.scalars(db.select(Bitacora).order_by(Bitacora.id)).all()

    def test_editar_punto_crea_una_fila(self):
        punto = db.session.scalar(db.select(PuntoReciclaje))
        nombre_original = punto.nombre
        respuesta = self.post(f"/admin/puntos/{punto.id}/editar", {
            "nombre": "Nombre editado", "direccion": punto.direccion, "activo": "1" if punto.activo else "",
            "latitud": str(punto.latitud), "longitud": str(punto.longitud)})
        self.assertEqual(respuesta.status_code, 302)
        filas = self.filas()
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual((fila.accion, fila.entidad, fila.entidad_id, fila.usuario_id),
                         ("EDITAR", "punto", punto.id, self.admin.id))
        self.assertEqual(fila.detalle, {"nombre": {"anterior": nombre_original, "nuevo": "Nombre editado"}})
        self.assertIn("Nombre editado", self.client.get("/admin/bitacora").get_data(as_text=True))

    def test_desactivar_punto_registra_desactivar(self):
        punto = db.session.scalar(db.select(PuntoReciclaje).where(PuntoReciclaje.activo.is_(True)))
        self.post(f"/admin/puntos/{punto.id}/estado")
        fila = self.filas()[-1]
        self.assertEqual(fila.accion, "DESACTIVAR")
        self.assertEqual(fila.detalle["activo"], {"anterior": True, "nuevo": False})

    def test_cambio_de_contrasena_no_guarda_el_hash(self):
        usuario = db.session.scalar(db.select(Usuario).where(Usuario.username == "operador"))
        hash_anterior = usuario.password_hash
        respuesta = self.post(f"/admin/usuarios/{usuario.id}/editar", {
            "nombre": usuario.nombre, "username": usuario.username, "rol": usuario.rol, "activo": "1",
            "password": "OtraClave123!", "password_confirmacion": "OtraClave123!"})
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotEqual(usuario.password_hash, hash_anterior)
        fila = self.filas()[-1]
        self.assertEqual((fila.accion, fila.entidad, fila.entidad_id), ("EDITAR", "usuario", usuario.id))
        self.assertEqual(fila.detalle, {"contraseña": "contraseña cambiada"})
        texto = json.dumps(fila.detalle, ensure_ascii=False)
        for secreto in (hash_anterior, usuario.password_hash, "OtraClave123!", "password_hash"):
            self.assertNotIn(secreto, texto)
        html = self.client.get("/admin/bitacora").get_data(as_text=True)
        self.assertNotIn(usuario.password_hash, html)

    def test_crear_usuario_anota_contrasena_asignada(self):
        self.post("/admin/usuarios/nuevo", {"nombre": "Nuevo", "username": "nuevo", "rol": "operador",
            "activo": "1", "password": "Clave123!", "password_confirmacion": "Clave123!"})
        fila = self.filas()[-1]
        self.assertEqual(fila.accion, "CREAR")
        self.assertEqual(fila.detalle["contraseña"], "contraseña asignada")
        self.assertNotIn("password_hash", fila.detalle)

    def test_eliminar_horario_guarda_valores_anteriores(self):
        horario = db.session.scalar(db.select(Horario))
        horario_id, punto_id, dia = horario.id, horario.punto_id, horario.dia_semana
        inicio, fin = horario.hora_inicio, horario.hora_fin
        self.assertEqual(self.post(f"/admin/puntos/{punto_id}/horarios/{horario_id}/eliminar").status_code, 302)
        self.assertIsNone(db.session.get(Horario, horario_id))
        filas = self.filas()
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual((fila.accion, fila.entidad, fila.entidad_id), ("ELIMINAR", "horario", horario_id))
        self.assertEqual(fila.detalle, {
            "punto_id": {"anterior": punto_id, "nuevo": None},
            "dia_semana": {"anterior": dia, "nuevo": None},
            "hora_inicio": {"anterior": inicio.isoformat(), "nuevo": None},
            "hora_fin": {"anterior": fin.isoformat(), "nuevo": None},
        })
        self.assertIsInstance(inicio, time)

    def test_crear_contenedor_con_dispositivo_genera_dos_filas_crear(self):
        punto = db.session.scalar(db.select(PuntoReciclaje))
        respuesta = self.post(f"/admin/puntos/{punto.id}/contenedores", {
            "codigo": "BITACORA-01", "identificador": "BITACORA-IOT-01", "activo": "1"})
        self.assertEqual(respuesta.status_code, 302)
        contenedor = db.session.scalar(db.select(Contenedor).where(Contenedor.codigo == "BITACORA-01"))
        dispositivo = db.session.scalar(db.select(DispositivoIoT).where(
            DispositivoIoT.identificador == "BITACORA-IOT-01"))
        filas = self.filas()
        self.assertEqual(sorted((f.accion, f.entidad, f.entidad_id) for f in filas), [
            ("CREAR", "contenedor", contenedor.id), ("CREAR", "dispositivo", dispositivo.id)])
        detalle_dispositivo = next(f.detalle for f in filas if f.entidad == "dispositivo")
        self.assertEqual(set(detalle_dispositivo), {"identificador", "contenedor_id", "activo"})

    def test_operador_recibe_403(self):
        operador = self.app.test_client()
        self.login(operador, "operador", "Operador123!")
        g.pop("_login_user", None)
        self.assertEqual(operador.get("/admin/bitacora").status_code, 403)

    def test_anonimo_redirigido_al_login(self):
        respuesta = self.app.test_client().get("/admin/bitacora")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login", respuesta.headers["Location"])

    def test_bitacora_sin_rutas_de_edicion_ni_borrado(self):
        reglas = [r for r in self.app.url_map.iter_rules() if "bitacora" in r.rule]
        self.assertEqual([r.rule for r in reglas], ["/admin/bitacora"])
        self.assertEqual(reglas[0].methods - {"HEAD", "OPTIONS"}, {"GET"})


if __name__ == "__main__":
    unittest.main()

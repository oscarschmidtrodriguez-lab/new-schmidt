import re

import pytest
from werkzeug.security import generate_password_hash

from rsjdr import create_app
from rsjdr.db import get_db


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "DATABASE": str(tmp_path / "test.db"),
        "BACKUPS_DIR": str(tmp_path / "backups"),
    })
    with app.app_context():
        get_db().execute(
            "INSERT INTO usuarios (email, password_hash) VALUES (?, ?)",
            ("oscar@rsjdr.es", generate_password_hash("contraseña-segura")),
        )
        get_db().commit()
    return app


class Cliente:
    """Cliente de pruebas que rellena el token CSRF automáticamente."""

    def __init__(self, flask_client):
        self.c = flask_client
        self.token = None

    def get(self, *a, **kw):
        r = self.c.get(*a, **kw)
        m = re.search(rb'name="_csrf" value="([^"]+)"', r.data)
        if m:
            self.token = m.group(1).decode()
        return r

    def post(self, url, data=None, **kw):
        if self.token is None:
            self.get("/login")
        data = dict(data or {})
        data.setdefault("_csrf", self.token)
        return self.c.post(url, data=data, **kw)


@pytest.fixture
def anon(app):
    return Cliente(app.test_client())


@pytest.fixture
def client(anon):
    r = anon.post("/login", data={"email": "oscar@rsjdr.es", "password": "contraseña-segura"})
    assert r.status_code == 302
    anon.get("/")  # el login renueva la sesión y con ella el token CSRF
    return anon


@pytest.fixture
def crear(app):
    """Atajos para crear datos directamente en la base de datos."""
    class Crear:
        def vehiculo(self, nombre="KTM X-BOW", estado="operativo", tarifa=900):
            with app.app_context():
                db = get_db()
                cur = db.execute(
                    "INSERT INTO vehiculos (nombre, estado, tarifa_dia) VALUES (?, ?, ?)",
                    (nombre, estado, tarifa),
                )
                db.commit()
                return cur.lastrowid

        def evento(self, nombre, inicio, fin, estado="presupuesto"):
            with app.app_context():
                db = get_db()
                cur = db.execute(
                    "INSERT INTO eventos (nombre, fecha_inicio, fecha_fin, estado) VALUES (?, ?, ?, ?)",
                    (nombre, inicio, fin, estado),
                )
                db.commit()
                return cur.lastrowid

        def reservas(self, evento_id):
            with app.app_context():
                return get_db().execute(
                    "SELECT * FROM evento_vehiculos WHERE evento_id = ?", (evento_id,)
                ).fetchall()

        def estado(self, evento_id):
            with app.app_context():
                return get_db().execute(
                    "SELECT estado FROM eventos WHERE id = ?", (evento_id,)
                ).fetchone()[0]

    return Crear()

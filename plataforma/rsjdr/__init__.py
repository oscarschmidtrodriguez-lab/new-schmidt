"""RSJdR Luxury — plataforma de operaciones de flota y eventos."""
import os
import secrets
from datetime import timedelta

from flask import Flask

from . import auth, db


def _secret_key(instance_path):
    """SECRET_KEY del entorno o, si no hay, una aleatoria guardada en instance/."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = os.path.join(instance_path, "secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
        os.chmod(path, 0o600)
    with open(path) as f:
        return f.read().strip()


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.update(
        DATABASE=os.path.join(app.instance_path, "rsjdr.db"),
        BACKUPS_DIR=os.path.join(app.instance_path, "backups"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("HTTPS", "") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    )
    if config:
        app.config.update(config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _secret_key(app.instance_path)

    db.migrate(app.config["DATABASE"], app.config["BACKUPS_DIR"])
    app.teardown_appcontext(db.close_db)
    db.register_cli(app)
    auth.init_app(app)

    if not app.config.get("TESTING"):
        @app.before_request
        def _backup():
            db.backup_diario_si_toca(app)

    from . import ajustes, clientes, demo, eventos, filtros, flota, panel, presupuestos

    filtros.init_app(app)
    demo.register(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(panel.bp)
    app.register_blueprint(flota.bp)
    app.register_blueprint(clientes.bp)
    app.register_blueprint(eventos.bp)
    app.register_blueprint(presupuestos.bp)
    app.register_blueprint(ajustes.bp)
    return app

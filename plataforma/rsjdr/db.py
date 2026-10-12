"""Conexión SQLite, migraciones versionadas y copias de seguridad."""
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import click
from flask import current_app, g

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
BACKUPS_A_CONSERVAR = 30


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def backup(db_path, backups_dir, etiqueta="diaria"):
    """Copia consistente de la base de datos (válida aunque esté en uso)."""
    if not os.path.exists(db_path):
        return None
    os.makedirs(backups_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = os.path.join(backups_dir, f"rsjdr-{stamp}-{etiqueta}.db")
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(destino)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    copias = sorted(Path(backups_dir).glob("rsjdr-*.db"))
    for vieja in copias[:-BACKUPS_A_CONSERVAR]:
        vieja.unlink()
    return destino


def migrate(db_path, backups_dir):
    """Aplica en orden las migraciones pendientes. Nunca borra datos.

    Si la base de datos ya existía, hace una copia antes de tocarla.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    existia = os.path.exists(db_path)
    conn = _connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    aplicadas = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    pendientes = [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.stem not in aplicadas]

    if pendientes and existia:
        conn.close()
        backup(db_path, backups_dir, etiqueta="pre-migracion")
        conn = _connect(db_path)

    for path in pendientes:
        with conn:
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (path.stem, datetime.now().isoformat(timespec="seconds")),
            )
    conn.close()
    return [p.stem for p in pendientes]


_ultimo_backup = {"dia": None}


def backup_diario_si_toca(app):
    """Una copia al día, hecha en la primera petición del día."""
    hoy = date.today()
    if _ultimo_backup["dia"] == hoy:
        return
    _ultimo_backup["dia"] = hoy
    backups_dir = app.config["BACKUPS_DIR"]
    prefijo = f"rsjdr-{hoy.strftime('%Y%m%d')}-"
    if os.path.isdir(backups_dir) and any(
        n.startswith(prefijo) for n in os.listdir(backups_dir)
    ):
        return
    backup(app.config["DATABASE"], backups_dir)


def register_cli(app):
    @app.cli.command("backup")
    def backup_command():
        """Hace una copia de seguridad de la base de datos ahora."""
        destino = backup(app.config["DATABASE"], app.config["BACKUPS_DIR"], etiqueta="manual")
        click.echo(f"Copia guardada en {destino}" if destino else "No hay base de datos todavía.")

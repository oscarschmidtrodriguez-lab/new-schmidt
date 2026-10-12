"""Acceso solo por invitación: no hay registro público.

Los usuarios se crean desde la terminal con `flask --app rsjdr crear-usuario`.
Incluye protección CSRF para todos los formularios.
"""
import functools
import hmac
import secrets
import sqlite3

import click
from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def init_app(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def cargar_usuario_y_validar_csrf():
        uid = session.get("user_id")
        g.user = None
        if uid is not None:
            g.user = get_db().execute(
                "SELECT * FROM usuarios WHERE id = ? AND activo = 1", (uid,)
            ).fetchone()
            if g.user is None:
                session.clear()

        if request.method == "POST":
            enviado = request.form.get("_csrf", "")
            esperado = session.get("_csrf", "")
            if not esperado or not hmac.compare_digest(enviado, esperado):
                abort(400, "Formulario caducado. Recarga la página e inténtalo de nuevo.")

    @app.cli.command("crear-usuario")
    @click.argument("email")
    @click.option("--nombre", default="")
    @click.password_option(prompt="Contraseña")
    def crear_usuario(email, nombre, password):
        """Da acceso a una persona (solo quien tú crees puede entrar)."""
        if len(password) < 10:
            raise click.ClickException("La contraseña debe tener al menos 10 caracteres.")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO usuarios (email, nombre, password_hash) VALUES (?, ?, ?)",
                (email.strip().lower(), nombre or None, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            raise click.ClickException(f"Ya existe un usuario {email}.")
        click.echo(f"Usuario {email} creado.")

    @app.cli.command("desactivar-usuario")
    @click.argument("email")
    def desactivar_usuario(email):
        """Quita el acceso a una persona sin borrar su historial."""
        db = get_db()
        cur = db.execute(
            "UPDATE usuarios SET activo = 0 WHERE email = ?", (email.strip().lower(),)
        )
        db.commit()
        click.echo("Usuario desactivado." if cur.rowcount else "No existe ese usuario.")


def _destino_seguro(next_url):
    # Solo rutas internas, para no redirigir a webs externas.
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for("panel.inicio")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM usuarios WHERE email = ? AND activo = 1", (email,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(_destino_seguro(request.args.get("next")))
        flash("Email o contraseña incorrectos.", "error")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

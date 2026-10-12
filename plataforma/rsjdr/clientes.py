from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db

bp = Blueprint("clientes", __name__, url_prefix="/clientes")

CAMPOS = ("nombre", "empresa", "cif", "email", "telefono", "notas")


def _form():
    return {c: (request.form.get(c) or "").strip() or None for c in CAMPOS}


@bp.route("/")
@login_required
def lista():
    clientes = get_db().execute(
        """
        SELECT c.*, COUNT(e.id) AS num_eventos, MAX(e.fecha_inicio) AS ultimo_evento
        FROM clientes c LEFT JOIN eventos e ON e.cliente_id = c.id
        GROUP BY c.id ORDER BY c.nombre
        """
    ).fetchall()
    return render_template("clientes/lista.html", clientes=clientes)


@bp.route("/nuevo", methods=["GET", "POST"])
@bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
@login_required
def formulario(cliente_id=None):
    db = get_db()
    cliente = None
    if cliente_id is not None:
        cliente = db.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
        if cliente is None:
            abort(404)

    if request.method == "POST":
        datos = _form()
        if not datos["nombre"]:
            flash("El nombre es obligatorio.", "error")
            return render_template("clientes/form.html", cliente=datos)
        if cliente is None:
            db.execute(
                f"INSERT INTO clientes ({', '.join(CAMPOS)}) VALUES ({', '.join('?' * len(CAMPOS))})",
                [datos[c] for c in CAMPOS],
            )
            flash(f"Cliente «{datos['nombre']}» creado.", "ok")
        else:
            db.execute(
                f"UPDATE clientes SET {', '.join(c + ' = ?' for c in CAMPOS)} WHERE id = ?",
                [datos[c] for c in CAMPOS] + [cliente_id],
            )
            flash("Cliente actualizado.", "ok")
        db.commit()
        return redirect(url_for("clientes.lista"))

    return render_template("clientes/form.html", cliente=cliente)

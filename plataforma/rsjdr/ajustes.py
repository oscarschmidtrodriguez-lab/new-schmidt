"""Pantalla de tarifas y datos de la empresa."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db
from .numeros import leer_numero
from .tarifas import NUMERICOS, ROLES, guardar_ajustes, leer_ajustes, tarifas_personal

bp = Blueprint("ajustes", __name__, url_prefix="/tarifas")

TEXTOS = ("empresa_nombre", "empresa_cif", "empresa_email", "empresa_telefono",
          "empresa_web", "base_ciudad", "condiciones")


def _num(valor, tipo):
    n = leer_numero(valor, tipo, None)
    return n if n is not None and n >= 0 else None


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    db = get_db()
    if request.method == "POST":
        f = request.form
        valores = {c: (f.get(c) or "").strip() for c in TEXTOS}
        errores = []
        for clave, tipo in NUMERICOS.items():
            n = _num(f.get(clave), tipo)
            if n is None:
                errores.append(f"«{clave.replace('_', ' ')}» no es un número válido.")
            valores[clave] = n
        if valores.get("coches_por_camion") == 0:
            errores.append("Un camión lleva al menos 1 coche.")
        personal = {}
        for rol in ROLES:
            precio = _num(f.get(f"precio_{rol}"), float)
            coste = _num(f.get(f"coste_{rol}"), float)
            if precio is None or coste is None:
                errores.append(f"Tarifa de {ROLES[rol].lower()} no válida.")
            personal[rol] = (precio, coste)
        if errores:
            for e in errores:
                flash(e, "error")
            return redirect(url_for("ajustes.index"))

        guardar_ajustes(db, valores)
        for rol, (precio, coste) in personal.items():
            db.execute(
                "INSERT INTO tarifas_personal (rol, precio_jornada, coste_jornada) VALUES (?, ?, ?)"
                " ON CONFLICT(rol) DO UPDATE SET precio_jornada = excluded.precio_jornada,"
                " coste_jornada = excluded.coste_jornada",
                (rol, precio, coste),
            )
        for ciudad in f.getlist("borrar_distancia"):
            db.execute("DELETE FROM distancias WHERE ciudad = ?", (ciudad,))
        db.commit()
        flash("Tarifas guardadas. Se aplican a los presupuestos nuevos.", "ok")
        return redirect(url_for("ajustes.index"))

    return render_template(
        "ajustes.html", a=leer_ajustes(db), tarifas=tarifas_personal(db), ROLES=ROLES,
        distancias=db.execute("SELECT * FROM distancias ORDER BY ciudad").fetchall(),
    )

from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db
from .disponibilidad import comprobar_evento, comprobar_reserva, ventana
from .filtros import ESTADO_EVENTO, TIPO_EVENTO

bp = Blueprint("eventos", __name__, url_prefix="/eventos")

MARGEN_DEFECTO = 1  # días de transporte/montaje antes y de recogida después


def _get_evento(db, evento_id):
    e = db.execute(
        """
        SELECT e.*, c.nombre AS cliente_nombre, c.empresa AS cliente_empresa
        FROM eventos e LEFT JOIN clientes c ON c.id = e.cliente_id
        WHERE e.id = ?
        """,
        (evento_id,),
    ).fetchone()
    if e is None:
        abort(404)
    return e


def _flash_todos(mensajes, categoria):
    for m in mensajes:
        flash(m, categoria)


@bp.route("/")
@login_required
def lista():
    vista = request.args.get("vista", "proximos")
    hoy = date.today().isoformat()
    sql = """
        SELECT e.*, c.nombre AS cliente_nombre,
               (SELECT COUNT(*) FROM evento_vehiculos r WHERE r.evento_id = e.id) AS num_coches
        FROM eventos e LEFT JOIN clientes c ON c.id = e.cliente_id
    """
    if vista == "pasados":
        sql += " WHERE e.fecha_fin < ? ORDER BY e.fecha_inicio DESC"
    else:
        vista = "proximos"
        sql += " WHERE e.fecha_fin >= ? ORDER BY e.fecha_inicio"
    eventos = get_db().execute(sql, (hoy,)).fetchall()
    return render_template("eventos/lista.html", eventos=eventos, vista=vista)


def _datos_form():
    f = request.form
    cliente_id = f.get("cliente_id")
    return {
        "nombre": (f.get("nombre") or "").strip(),
        "cliente_id": int(cliente_id) if cliente_id and cliente_id.isdigit() else None,
        "tipo": f.get("tipo"),
        "venue": (f.get("venue") or "").strip() or None,
        "ciudad": (f.get("ciudad") or "").strip() or None,
        "fecha_inicio": f.get("fecha_inicio") or "",
        "fecha_fin": f.get("fecha_fin") or f.get("fecha_inicio") or "",
        "estado": f.get("estado") or "presupuesto",
        "notas": (f.get("notas") or "").strip() or None,
    }


def _validar(datos):
    errores = []
    if not datos["nombre"]:
        errores.append("El nombre del evento es obligatorio.")
    if datos["tipo"] not in TIPO_EVENTO:
        errores.append("Tipo de evento no válido.")
    if datos["estado"] not in ESTADO_EVENTO:
        errores.append("Estado no válido.")
    try:
        ini = date.fromisoformat(datos["fecha_inicio"])
        fin = date.fromisoformat(datos["fecha_fin"])
        if fin < ini:
            errores.append("La fecha de fin no puede ser anterior a la de inicio.")
    except ValueError:
        errores.append("Fechas no válidas.")
    return errores


@bp.route("/nuevo", methods=["GET", "POST"])
@bp.route("/<int:evento_id>/editar", methods=["GET", "POST"])
@login_required
def formulario(evento_id=None):
    db = get_db()
    evento = _get_evento(db, evento_id) if evento_id is not None else None
    clientes = db.execute("SELECT id, nombre, empresa FROM clientes ORDER BY nombre").fetchall()

    if request.method == "POST":
        datos = _datos_form()
        errores = _validar(datos)
        avisos = []
        if not errores and evento is not None:
            # Cambiar fechas o estado mueve también los coches: revalidar.
            bloqueos, avisos = comprobar_evento(
                db, evento_id, datos["estado"], datos["fecha_inicio"], datos["fecha_fin"]
            )
            errores += bloqueos
        if errores:
            _flash_todos(errores, "error")
            return render_template(
                "eventos/form.html", evento=datos, evento_id=evento_id, clientes=clientes
            )

        cols = list(datos)
        if evento is None:
            cur = db.execute(
                f"INSERT INTO eventos ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                [datos[c] for c in cols],
            )
            evento_id = cur.lastrowid
            flash("Evento creado. Ahora añade los coches.", "ok")
        else:
            db.execute(
                f"UPDATE eventos SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?",
                [datos[c] for c in cols] + [evento_id],
            )
            flash("Evento actualizado.", "ok")
            _flash_todos(avisos, "aviso")
        db.commit()
        return redirect(url_for("eventos.detalle", evento_id=evento_id))

    return render_template(
        "eventos/form.html", evento=evento, evento_id=evento_id, clientes=clientes
    )


@bp.route("/<int:evento_id>")
@login_required
def detalle(evento_id):
    db = get_db()
    evento = _get_evento(db, evento_id)
    reservas = db.execute(
        """
        SELECT r.*, v.nombre, v.matricula, v.tarifa_dia, v.estado AS vehiculo_estado
        FROM evento_vehiculos r JOIN vehiculos v ON v.id = r.vehiculo_id
        WHERE r.evento_id = ? ORDER BY v.nombre
        """,
        (evento_id,),
    ).fetchall()
    filas = []
    for r in reservas:
        salida, regreso = ventana(
            evento["fecha_inicio"], evento["fecha_fin"], r["dias_antes"], r["dias_despues"]
        )
        filas.append({"r": r, "salida": salida, "regreso": regreso})
    bloqueos, avisos = comprobar_evento(
        db, evento_id, evento["estado"], evento["fecha_inicio"], evento["fecha_fin"]
    )

    # Selector de coches: cómo quedaría cada uno con el margen por defecto.
    ya = {r["vehiculo_id"] for r in reservas}
    candidatos = []
    for v in db.execute("SELECT * FROM vehiculos WHERE estado != 'baja' ORDER BY nombre"):
        if v["id"] in ya:
            continue
        b, a = comprobar_reserva(
            db, v, evento_id, evento["estado"], evento["fecha_inicio"], evento["fecha_fin"],
            MARGEN_DEFECTO, MARGEN_DEFECTO,
        )
        candidatos.append({"v": v, "bloqueos": b, "avisos": a})
    candidatos.sort(key=lambda c: (bool(c["bloqueos"]), bool(c["avisos"]), c["v"]["nombre"]))

    dias = (date.fromisoformat(evento["fecha_fin"]) - date.fromisoformat(evento["fecha_inicio"])).days + 1
    return render_template(
        "eventos/detalle.html", evento=evento, filas=filas, candidatos=candidatos,
        bloqueos=bloqueos, avisos=avisos, dias=dias, margen=MARGEN_DEFECTO,
    )


def _entero(valor, defecto):
    try:
        n = int(valor)
        return n if 0 <= n <= 30 else defecto
    except (TypeError, ValueError):
        return defecto


@bp.route("/<int:evento_id>/coches", methods=["POST"])
@login_required
def anadir_coche(evento_id):
    db = get_db()
    evento = _get_evento(db, evento_id)
    vehiculo = db.execute(
        "SELECT * FROM vehiculos WHERE id = ?", (request.form.get("vehiculo_id"),)
    ).fetchone()
    if vehiculo is None:
        flash("Elige un coche.", "error")
        return redirect(url_for("eventos.detalle", evento_id=evento_id))

    antes = _entero(request.form.get("dias_antes"), MARGEN_DEFECTO)
    despues = _entero(request.form.get("dias_despues"), MARGEN_DEFECTO)
    bloqueos, avisos = comprobar_reserva(
        db, vehiculo, evento_id, evento["estado"], evento["fecha_inicio"], evento["fecha_fin"],
        antes, despues,
    )
    if bloqueos:
        _flash_todos(bloqueos, "error")
        return redirect(url_for("eventos.detalle", evento_id=evento_id))

    existe = db.execute(
        "SELECT 1 FROM evento_vehiculos WHERE evento_id = ? AND vehiculo_id = ?",
        (evento_id, vehiculo["id"]),
    ).fetchone()
    if existe:
        flash(f"{vehiculo['nombre']} ya está en este evento.", "error")
        return redirect(url_for("eventos.detalle", evento_id=evento_id))

    db.execute(
        "INSERT INTO evento_vehiculos (evento_id, vehiculo_id, dias_antes, dias_despues)"
        " VALUES (?, ?, ?, ?)",
        (evento_id, vehiculo["id"], antes, despues),
    )
    db.commit()
    flash(f"{vehiculo['nombre']} reservado.", "ok")
    _flash_todos(avisos, "aviso")
    return redirect(url_for("eventos.detalle", evento_id=evento_id))


@bp.route("/<int:evento_id>/coches/<int:reserva_id>/quitar", methods=["POST"])
@login_required
def quitar_coche(evento_id, reserva_id):
    db = get_db()
    db.execute(
        "DELETE FROM evento_vehiculos WHERE id = ? AND evento_id = ?", (reserva_id, evento_id)
    )
    db.commit()
    flash("Coche liberado.", "ok")
    return redirect(url_for("eventos.detalle", evento_id=evento_id))


@bp.route("/<int:evento_id>/estado", methods=["POST"])
@login_required
def cambiar_estado(evento_id):
    db = get_db()
    evento = _get_evento(db, evento_id)
    nuevo = request.form.get("estado")
    if nuevo not in ESTADO_EVENTO:
        abort(400)
    bloqueos, avisos = comprobar_evento(
        db, evento_id, nuevo, evento["fecha_inicio"], evento["fecha_fin"]
    )
    if bloqueos:
        flash(f"No se puede pasar a «{ESTADO_EVENTO[nuevo]}»:", "error")
        _flash_todos(bloqueos, "error")
    else:
        db.execute("UPDATE eventos SET estado = ? WHERE id = ?", (nuevo, evento_id))
        db.commit()
        flash(f"Estado cambiado a «{ESTADO_EVENTO[nuevo]}».", "ok")
        _flash_todos(avisos, "aviso")
    return redirect(url_for("eventos.detalle", evento_id=evento_id))

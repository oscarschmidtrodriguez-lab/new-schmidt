from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db
from .disponibilidad import comprobar_evento
from .numeros import leer_numero as _num
from .tarifas import (
    ROLES, camiones_necesarios, dias_evento, generar_lineas, km_conocidos, leer_ajustes,
    recordar_km, siguiente_numero, tarifas_personal, totales,
)

bp = Blueprint("presupuestos", __name__, url_prefix="/presupuestos")

ESTADOS = {
    "borrador": "Borrador",
    "enviado": "Enviado",
    "aceptado": "Aceptado",
    "rechazado": "Rechazado",
}


def _evento(db, evento_id):
    e = db.execute(
        """
        SELECT e.*, c.nombre AS cliente_nombre, c.empresa AS cliente_empresa,
               c.email AS cliente_email, c.cif AS cliente_cif
        FROM eventos e LEFT JOIN clientes c ON c.id = e.cliente_id WHERE e.id = ?
        """,
        (evento_id,),
    ).fetchone()
    if e is None:
        abort(404)
    return e


def _vehiculos_evento(db, evento_id):
    return db.execute(
        """
        SELECT v.* FROM evento_vehiculos r JOIN vehiculos v ON v.id = r.vehiculo_id
        WHERE r.evento_id = ? ORDER BY v.nombre
        """,
        (evento_id,),
    ).fetchall()


def cargar(db, presupuesto_id):
    p = db.execute("SELECT * FROM presupuestos WHERE id = ?", (presupuesto_id,)).fetchone()
    if p is None:
        abort(404)
    lineas = db.execute(
        "SELECT * FROM presupuesto_lineas WHERE presupuesto_id = ? ORDER BY orden, id",
        (presupuesto_id,),
    ).fetchall()
    return p, lineas, totales(lineas, p["descuento_pct"], p["iva_pct"])


def resumen_por_evento(db, evento_id):
    filas = db.execute(
        "SELECT id FROM presupuestos WHERE evento_id = ? ORDER BY id DESC", (evento_id,)
    ).fetchall()
    resumen = []
    for f in filas:
        p, _, t = cargar(db, f["id"])
        resumen.append({"p": p, "t": t})
    return resumen


@bp.route("/")
@login_required
def lista():
    db = get_db()
    filtro = request.args.get("estado", "")
    sql = """
        SELECT p.id FROM presupuestos p JOIN eventos e ON e.id = p.evento_id
        {} ORDER BY p.id DESC
    """.format("WHERE p.estado = ?" if filtro in ESTADOS else "")
    ids = db.execute(sql, (filtro,) if filtro in ESTADOS else ()).fetchall()
    filas = []
    for r in ids:
        p, _, t = cargar(db, r["id"])
        filas.append({"p": p, "t": t, "e": _evento(db, p["evento_id"])})
    return render_template(
        "presupuestos/lista.html", filas=filas, filtro=filtro, ESTADOS=ESTADOS
    )


@bp.route("/nuevo/<int:evento_id>", methods=["GET", "POST"])
@login_required
def nuevo(evento_id):
    db = get_db()
    evento = _evento(db, evento_id)
    vehiculos = _vehiculos_evento(db, evento_id)
    ajustes = leer_ajustes(db)
    tarifas = tarifas_personal(db)
    dias = dias_evento(evento)

    if request.method == "POST":
        f = request.form
        km_ida = _num(f.get("km_ida"), float)
        camiones = _num(f.get("camiones"), int)
        personal = {
            rol: (_num(f.get(f"n_{rol}"), int), _num(f.get(f"j_{rol}"), float, dias))
            for rol in ROLES
        }
        if km_ida is None or km_ida < 0 or camiones is None or camiones < 0 or any(
            n is None or j is None or n < 0 or j < 0 for n, j in personal.values()
        ):
            flash("Revisa los números: hay algún valor que no es válido.", "error")
            return redirect(url_for("presupuestos.nuevo", evento_id=evento_id))

        lineas = generar_lineas(evento, vehiculos, ajustes, tarifas, km_ida, camiones, personal)
        cur = db.execute(
            "INSERT INTO presupuestos (evento_id, numero, iva_pct, validez_dias) VALUES (?, ?, ?, ?)",
            (evento_id, siguiente_numero(db, date.today().year), ajustes["iva_pct"], ajustes["validez_dias"]),
        )
        pid = cur.lastrowid
        for i, l in enumerate(lineas):
            db.execute(
                "INSERT INTO presupuesto_lineas (presupuesto_id, tipo, concepto, cantidad, precio, coste, orden)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pid, l["tipo"], l["concepto"], l["cantidad"], l["precio"], l["coste"], i),
            )
        recordar_km(db, evento["ciudad"], km_ida)
        db.commit()
        flash("Presupuesto generado. Revisa las líneas y ajusta lo que necesites.", "ok")
        if not km_ida and vehiculos:
            flash("No has puesto kilómetros: el transporte no está incluido.", "aviso")
        return redirect(url_for("presupuestos.detalle", presupuesto_id=pid))

    km = km_conocidos(db, evento["ciudad"])
    return render_template(
        "presupuestos/nuevo.html", evento=evento, vehiculos=vehiculos, dias=dias,
        km_ida=km, km_recordado=km is not None, ajustes=ajustes, tarifas=tarifas, ROLES=ROLES,
        camiones=camiones_necesarios(len(vehiculos), ajustes["coches_por_camion"]),
    )


@bp.route("/<int:presupuesto_id>")
@login_required
def detalle(presupuesto_id):
    db = get_db()
    p, lineas, t = cargar(db, presupuesto_id)
    evento = _evento(db, p["evento_id"])
    fianzas = sum(v["fianza"] for v in _vehiculos_evento(db, evento["id"]))
    sin_coste = [l for l in lineas if l["tipo"] == "vehiculo" and not l["coste"]]
    # ¿Podríamos cumplir si el cliente dice que sí? Simula la confirmación.
    no_cumplible = []
    if p["estado"] in ("borrador", "enviado") and evento["estado"] == "presupuesto":
        no_cumplible, _ = comprobar_evento(
            db, evento["id"], "confirmado", evento["fecha_inicio"], evento["fecha_fin"]
        )
    return render_template(
        "presupuestos/detalle.html", p=p, lineas=lineas, t=t, evento=evento,
        fianzas=fianzas, ESTADOS=ESTADOS, editable=p["estado"] != "aceptado",
        sin_coste=sin_coste, no_cumplible=no_cumplible,
    )


@bp.route("/<int:presupuesto_id>/guardar", methods=["POST"])
@login_required
def guardar(presupuesto_id):
    db = get_db()
    p, lineas, _ = cargar(db, presupuesto_id)
    volver = redirect(url_for("presupuestos.detalle", presupuesto_id=presupuesto_id))
    if p["estado"] == "aceptado":
        flash("Un presupuesto aceptado no se puede modificar.", "error")
        return volver

    f = request.form
    descuento = _num(f.get("descuento_pct"))
    iva = _num(f.get("iva_pct"))
    validez = _num(f.get("validez_dias"), int)
    if descuento is None or not 0 <= descuento <= 100 or iva is None or iva < 0 or validez is None:
        flash("Descuento, IVA o validez no válidos.", "error")
        return volver

    borrar = set(f.getlist("borrar"))
    cambios = []
    for l in lineas:
        lid = str(l["id"])
        if lid in borrar:
            cambios.append(("borrar", l["id"], None))
            continue
        concepto = (f.get(f"concepto_{lid}") or "").strip()
        cantidad = _num(f.get(f"cantidad_{lid}"))
        precio = _num(f.get(f"precio_{lid}"))
        coste = _num(f.get(f"coste_{lid}"))
        if not concepto or cantidad is None or cantidad < 0 or precio is None or coste is None:
            flash(f"Línea «{l['concepto']}»: revisa concepto, cantidad y precios.", "error")
            return volver
        cambios.append(("actualizar", l["id"], (concepto, cantidad, precio, coste)))

    nuevo_concepto = (f.get("nuevo_concepto") or "").strip()
    nueva = None
    if nuevo_concepto:
        cantidad = _num(f.get("nuevo_cantidad"), float, 1)
        precio = _num(f.get("nuevo_precio"))
        coste = _num(f.get("nuevo_coste"))
        if cantidad is None or cantidad < 0 or precio is None or coste is None:
            flash("La línea nueva tiene números no válidos.", "error")
            return volver
        nueva = (nuevo_concepto, cantidad, precio, coste)

    for accion, lid, datos in cambios:
        if accion == "borrar":
            db.execute("DELETE FROM presupuesto_lineas WHERE id = ?", (lid,))
        else:
            db.execute(
                "UPDATE presupuesto_lineas SET concepto = ?, cantidad = ?, precio = ?, coste = ? WHERE id = ?",
                (*datos, lid),
            )
    if nueva:
        orden = db.execute(
            "SELECT COALESCE(MAX(orden), 0) + 1 FROM presupuesto_lineas WHERE presupuesto_id = ?",
            (presupuesto_id,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO presupuesto_lineas (presupuesto_id, tipo, concepto, cantidad, precio, coste, orden)"
            " VALUES (?, 'extra', ?, ?, ?, ?, ?)",
            (presupuesto_id, *nueva, orden),
        )
    db.execute(
        "UPDATE presupuestos SET descuento_pct = ?, iva_pct = ?, validez_dias = ?, notas = ? WHERE id = ?",
        (descuento, iva, validez, (f.get("notas") or "").strip() or None, presupuesto_id),
    )
    db.commit()
    flash("Presupuesto guardado.", "ok")
    return volver


@bp.route("/<int:presupuesto_id>/estado", methods=["POST"])
@login_required
def cambiar_estado(presupuesto_id):
    db = get_db()
    p, _, _ = cargar(db, presupuesto_id)
    nuevo = request.form.get("estado")
    if nuevo not in ESTADOS:
        abort(400)
    enviado_at = p["enviado_at"]
    if nuevo == "enviado" and not enviado_at:
        enviado_at = datetime.now().isoformat(timespec="seconds")
    db.execute(
        "UPDATE presupuestos SET estado = ?, enviado_at = ? WHERE id = ?",
        (nuevo, enviado_at, presupuesto_id),
    )
    flash(f"Presupuesto {p['numero']} marcado como «{ESTADOS[nuevo]}».", "ok")

    if nuevo == "aceptado":
        evento = _evento(db, p["evento_id"])
        if evento["estado"] == "presupuesto":
            bloqueos, _ = comprobar_evento(
                db, evento["id"], "confirmado", evento["fecha_inicio"], evento["fecha_fin"]
            )
            if bloqueos:
                flash("El evento sigue sin confirmar porque hay coches comprometidos en otro evento:", "error")
                for b in bloqueos:
                    flash(b, "error")
            else:
                db.execute("UPDATE eventos SET estado = 'confirmado' WHERE id = ?", (evento["id"],))
                flash("Evento confirmado y coches bloqueados en firme.", "ok")
    db.commit()
    return redirect(url_for("presupuestos.detalle", presupuesto_id=presupuesto_id))


@bp.route("/<int:presupuesto_id>/eliminar", methods=["POST"])
@login_required
def eliminar(presupuesto_id):
    db = get_db()
    p, _, _ = cargar(db, presupuesto_id)
    if p["estado"] != "borrador":
        flash("Solo se pueden eliminar borradores.", "error")
        return redirect(url_for("presupuestos.detalle", presupuesto_id=presupuesto_id))
    db.execute("DELETE FROM presupuestos WHERE id = ?", (presupuesto_id,))
    db.commit()
    flash(f"Borrador {p['numero']} eliminado.", "ok")
    return redirect(url_for("eventos.detalle", evento_id=p["evento_id"]))


@bp.route("/<int:presupuesto_id>/propuesta")
@login_required
def propuesta(presupuesto_id):
    db = get_db()
    p, lineas, t = cargar(db, presupuesto_id)
    evento = _evento(db, p["evento_id"])
    vehiculos = _vehiculos_evento(db, evento["id"])
    emitido = date.fromisoformat((p["enviado_at"] or p["created_at"])[:10])
    return render_template(
        "presupuestos/propuesta.html", p=p, lineas=lineas, t=t, evento=evento,
        vehiculos=vehiculos, ajustes=leer_ajustes(db),
        emitido=emitido, valido_hasta=emitido + timedelta(days=p["validez_dias"]),
        fianzas=sum(v["fianza"] for v in vehiculos),
    )

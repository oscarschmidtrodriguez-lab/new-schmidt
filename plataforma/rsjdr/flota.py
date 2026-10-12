import calendar
from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db
from .disponibilidad import ESTADOS_FIRMES, eventos_afectados_por_vehiculo, reservas_entre
from .filtros import CATEGORIA_VEHICULO, ESTADO_VEHICULO

bp = Blueprint("flota", __name__, url_prefix="/flota")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _get_vehiculo(db, vehiculo_id):
    v = db.execute("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,)).fetchone()
    if v is None:
        abort(404)
    return v


def _numero(valor, tipo, defecto=0):
    try:
        return tipo((valor or "").replace(",", ".")) if valor not in (None, "") else defecto
    except ValueError:
        return None


@bp.route("/")
@login_required
def lista():
    db = get_db()
    vehiculos = db.execute("SELECT * FROM vehiculos ORDER BY estado = 'baja', nombre").fetchall()
    hoy = date.today().isoformat()
    proxima = {}
    for v in vehiculos:
        siguientes = reservas_entre(db, hoy, "9999-12-31", v["id"])
        proxima[v["id"]] = siguientes[0] if siguientes else None
    return render_template("flota/lista.html", vehiculos=vehiculos, proxima=proxima)


@bp.route("/nuevo", methods=["GET", "POST"])
@bp.route("/<int:vehiculo_id>/editar", methods=["GET", "POST"])
@login_required
def formulario(vehiculo_id=None):
    db = get_db()
    vehiculo = _get_vehiculo(db, vehiculo_id) if vehiculo_id is not None else None

    if request.method == "POST":
        f = request.form
        datos = {
            "nombre": (f.get("nombre") or "").strip(),
            "matricula": (f.get("matricula") or "").strip().upper() or None,
            "categoria": f.get("categoria"),
            "tarifa_dia": _numero(f.get("tarifa_dia"), float),
            "fianza": _numero(f.get("fianza"), float),
            "km_actuales": _numero(f.get("km_actuales"), int),
            "estado": f.get("estado"),
            "notas": (f.get("notas") or "").strip() or None,
        }
        errores = []
        if not datos["nombre"]:
            errores.append("El nombre del coche es obligatorio.")
        if datos["categoria"] not in CATEGORIA_VEHICULO:
            errores.append("Categoría no válida.")
        if datos["estado"] not in ESTADO_VEHICULO:
            errores.append("Estado no válido.")
        for campo in ("tarifa_dia", "fianza", "km_actuales"):
            if datos[campo] is None or datos[campo] < 0:
                errores.append(f"«{campo.replace('_', ' ')}» debe ser un número positivo.")
        if datos["matricula"]:
            dup = db.execute(
                "SELECT id FROM vehiculos WHERE matricula = ? AND id != ?",
                (datos["matricula"], vehiculo_id or 0),
            ).fetchone()
            if dup:
                errores.append(f"Ya hay un coche con la matrícula {datos['matricula']}.")
        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("flota/form.html", vehiculo=datos, vehiculo_id=vehiculo_id)

        cols = list(datos)
        if vehiculo is None:
            cur = db.execute(
                f"INSERT INTO vehiculos ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                [datos[c] for c in cols],
            )
            vehiculo_id = cur.lastrowid
            flash(f"{datos['nombre']} añadido a la flota.", "ok")
        else:
            db.execute(
                f"UPDATE vehiculos SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?",
                [datos[c] for c in cols] + [vehiculo_id],
            )
            flash("Coche actualizado.", "ok")
        db.commit()

        if datos["estado"] != "operativo":
            for r in eventos_afectados_por_vehiculo(db, vehiculo_id):
                flash(
                    f"Atención: {datos['nombre']} está reservado para «{r['evento_nombre']}» "
                    f"(sale el {date.fromisoformat(r['salida']).strftime('%d/%m')}). "
                    "Busca sustituto o cambia el coche en ese evento.",
                    "error",
                )
        return redirect(url_for("flota.detalle", vehiculo_id=vehiculo_id))

    return render_template("flota/form.html", vehiculo=vehiculo, vehiculo_id=vehiculo_id)


@bp.route("/<int:vehiculo_id>")
@login_required
def detalle(vehiculo_id):
    db = get_db()
    vehiculo = _get_vehiculo(db, vehiculo_id)
    reservas = reservas_entre(db, "0000-01-01", "9999-12-31", vehiculo_id)
    hoy = date.today().isoformat()
    proximas = [r for r in reservas if r["regreso"] >= hoy]
    pasadas = [r for r in reservas if r["regreso"] < hoy][::-1]
    return render_template(
        "flota/detalle.html", vehiculo=vehiculo, proximas=proximas, pasadas=pasadas,
    )


def _mes_param():
    try:
        y, m = (int(x) for x in request.args.get("mes", "").split("-"))
        return date(y, m, 1)
    except ValueError:
        return date.today().replace(day=1)


def ocupacion_mes(db, primero):
    """Rejilla coches × días del mes y % de ocupación firme de la flota operativa."""
    ultimo = primero.replace(day=calendar.monthrange(primero.year, primero.month)[1])
    dias = [primero + timedelta(days=i) for i in range((ultimo - primero).days + 1)]
    vehiculos = db.execute(
        "SELECT * FROM vehiculos WHERE estado != 'baja' ORDER BY nombre"
    ).fetchall()
    reservas = reservas_entre(db, primero.isoformat(), ultimo.isoformat())

    filas = []
    dias_ocupados = dias_disponibles = 0
    for v in vehiculos:
        propias = [r for r in reservas if r["vehiculo_id"] == v["id"]]
        celdas = []
        for d in dias:
            iso = d.isoformat()
            en_dia = [r for r in propias if r["salida"] <= iso <= r["regreso"]]
            if len(en_dia) > 1:
                clase = "conflicto"
            elif en_dia:
                r = en_dia[0]
                clase = "firme" if r["estado"] in ESTADOS_FIRMES else "provisional"
                if not (r["fecha_inicio"] <= iso <= r["fecha_fin"]):
                    clase += " logistica"
            elif v["estado"] != "operativo":
                clase = "taller"
            else:
                clase = "libre"
            celdas.append({"clase": clase, "reservas": en_dia, "dia": d})
            if v["estado"] == "operativo":
                dias_disponibles += 1
                if any(r["estado"] in ESTADOS_FIRMES for r in en_dia):
                    dias_ocupados += 1
        filas.append({"vehiculo": v, "celdas": celdas})

    pct = round(100 * dias_ocupados / dias_disponibles) if dias_disponibles else 0
    return dias, filas, pct


@bp.route("/calendario")
@login_required
def calendario():
    primero = _mes_param()
    dias, filas, ocupacion = ocupacion_mes(get_db(), primero)
    anterior = (primero - timedelta(days=1)).replace(day=1)
    siguiente = (primero + timedelta(days=32)).replace(day=1)
    return render_template(
        "flota/calendario.html",
        dias=dias, filas=filas, ocupacion=ocupacion,
        titulo=f"{MESES[primero.month - 1].capitalize()} {primero.year}",
        anterior=anterior.strftime("%Y-%m"), siguiente=siguiente.strftime("%Y-%m"),
        hoy=date.today(),
    )

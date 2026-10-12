"""Portada: lo que requiere tu atención hoy."""
from datetime import date, timedelta

from flask import Blueprint, render_template

from .auth import login_required
from .db import get_db
from .disponibilidad import ESTADOS_ACTIVOS, comprobar_evento
from .flota import ocupacion_mes
from .presupuestos import cargar

bp = Blueprint("panel", __name__)


@bp.route("/")
@login_required
def inicio():
    db = get_db()
    hoy = date.today()
    proximos = db.execute(
        """
        SELECT e.*, c.nombre AS cliente_nombre,
               (SELECT COUNT(*) FROM evento_vehiculos r WHERE r.evento_id = e.id) AS num_coches
        FROM eventos e LEFT JOIN clientes c ON c.id = e.cliente_id
        WHERE e.fecha_fin >= ? AND e.fecha_inicio <= ? AND e.estado != 'cancelado'
        ORDER BY e.fecha_inicio
        """,
        (hoy.isoformat(), (hoy + timedelta(days=45)).isoformat()),
    ).fetchall()

    alertas = []
    activos = db.execute(
        f"SELECT * FROM eventos WHERE fecha_fin >= ? AND estado IN ({','.join('?' * len(ESTADOS_ACTIVOS))})"
        " ORDER BY fecha_inicio",
        (hoy.isoformat(), *ESTADOS_ACTIVOS),
    ).fetchall()
    for e in activos:
        bloqueos, avisos = comprobar_evento(db, e["id"], e["estado"], e["fecha_inicio"], e["fecha_fin"])
        for m in bloqueos:
            alertas.append({"evento": e, "texto": m, "nivel": "error"})
        for m in avisos:
            alertas.append({"evento": e, "texto": m, "nivel": "aviso"})
        if e["estado"] == "confirmado":
            sin_coches = not db.execute(
                "SELECT 1 FROM evento_vehiculos WHERE evento_id = ?", (e["id"],)
            ).fetchone()
            if sin_coches:
                alertas.append({"evento": e, "texto": "Confirmado y sin coches asignados.", "nivel": "aviso"})

    pendientes = [
        cargar(db, r["id"])
        for r in db.execute("SELECT id FROM presupuestos WHERE estado = 'enviado'")
    ]
    pendientes_total = sum(t["base"] for _, _, t in pendientes)

    _, _, ocupacion = ocupacion_mes(db, hoy.replace(day=1))
    flota = db.execute(
        "SELECT estado, COUNT(*) AS n FROM vehiculos GROUP BY estado"
    ).fetchall()
    return render_template(
        "panel.html", proximos=proximos, alertas=alertas, ocupacion=ocupacion,
        flota={r["estado"]: r["n"] for r in flota},
        num_pendientes=len(pendientes), pendientes_total=pendientes_total,
    )

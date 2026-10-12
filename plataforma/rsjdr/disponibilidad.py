"""Reglas de disponibilidad de la flota.

Un coche reservado ocupa su ventana completa: los días del evento más los
días de transporte/montaje antes y de recogida después.

- Evento firme (confirmado / en curso / finalizado) contra otro firme en las
  mismas fechas  -> BLOQUEO: no se permite, el coche no puede estar en dos sitios.
- Si uno de los dos es solo un presupuesto -> AVISO: se permite como reserva
  provisional, pero sale marcada para que decidas quién se lo queda.
- Coche en taller o de baja para un evento activo -> BLOQUEO.
"""
from datetime import date, timedelta

ESTADOS_FIRMES = ("confirmado", "en_curso", "finalizado")
ESTADOS_ACTIVOS = ("presupuesto", "confirmado", "en_curso")


def ventana(fecha_inicio, fecha_fin, dias_antes, dias_despues):
    salida = date.fromisoformat(fecha_inicio) - timedelta(days=dias_antes)
    regreso = date.fromisoformat(fecha_fin) + timedelta(days=dias_despues)
    return salida.isoformat(), regreso.isoformat()


_RESERVAS_SQL = """
    SELECT * FROM (
        SELECT r.id AS reserva_id, r.vehiculo_id, r.dias_antes, r.dias_despues,
               e.id AS evento_id, e.nombre AS evento_nombre, e.estado,
               e.fecha_inicio, e.fecha_fin,
               date(e.fecha_inicio, printf('-%d days', r.dias_antes)) AS salida,
               date(e.fecha_fin, printf('+%d days', r.dias_despues)) AS regreso
        FROM evento_vehiculos r
        JOIN eventos e ON e.id = r.evento_id
        WHERE e.estado != 'cancelado'
    )
"""


def reservas_entre(db, desde, hasta, vehiculo_id=None):
    """Reservas no canceladas cuya ventana toca el intervalo [desde, hasta]."""
    sql = _RESERVAS_SQL + " WHERE salida <= ? AND regreso >= ?"
    params = [hasta, desde]
    if vehiculo_id is not None:
        sql += " AND vehiculo_id = ?"
        params.append(vehiculo_id)
    return db.execute(sql + " ORDER BY salida", params).fetchall()


def _fmt(d):
    return date.fromisoformat(d).strftime("%d/%m/%Y")


def comprobar_reserva(db, vehiculo, evento_id, estado, fecha_inicio, fecha_fin,
                      dias_antes, dias_despues):
    """Devuelve (bloqueos, avisos) para tener `vehiculo` en ese evento."""
    bloqueos, avisos = [], []
    if estado not in ESTADOS_ACTIVOS:
        return bloqueos, avisos

    if vehiculo["estado"] != "operativo":
        bloqueos.append(
            f"{vehiculo['nombre']} está en estado «{vehiculo['estado']}» y no puede ir a eventos."
        )

    salida, regreso = ventana(fecha_inicio, fecha_fin, dias_antes, dias_despues)
    for otra in reservas_entre(db, salida, regreso, vehiculo["id"]):
        if otra["evento_id"] == evento_id:
            continue
        texto = (
            f"{vehiculo['nombre']} ya está reservado para «{otra['evento_nombre']}» "
            f"({otra['estado']}) del {_fmt(otra['salida'])} al {_fmt(otra['regreso'])}"
        )
        if estado in ESTADOS_FIRMES and otra["estado"] in ESTADOS_FIRMES:
            bloqueos.append(texto + ".")
        else:
            avisos.append(texto + " — reserva provisional, decide quién se lo queda.")
    return bloqueos, avisos


def comprobar_evento(db, evento_id, estado, fecha_inicio, fecha_fin):
    """Revalida todos los coches de un evento con unas fechas/estado dados.

    Se usa al editar fechas o cambiar el estado, y para mostrar alertas.
    """
    bloqueos, avisos = [], []
    filas = db.execute(
        """
        SELECT v.*, r.dias_antes, r.dias_despues
        FROM evento_vehiculos r JOIN vehiculos v ON v.id = r.vehiculo_id
        WHERE r.evento_id = ?
        """,
        (evento_id,),
    ).fetchall()
    for v in filas:
        b, a = comprobar_reserva(
            db, v, evento_id, estado, fecha_inicio, fecha_fin, v["dias_antes"], v["dias_despues"]
        )
        bloqueos += b
        avisos += a
    return bloqueos, avisos


def eventos_afectados_por_vehiculo(db, vehiculo_id):
    """Eventos activos desde hoy que tienen este coche reservado."""
    hoy = date.today().isoformat()
    return [
        r for r in reservas_entre(db, hoy, "9999-12-31", vehiculo_id)
        if r["estado"] in ESTADOS_ACTIVOS
    ]

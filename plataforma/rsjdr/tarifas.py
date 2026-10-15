"""Motor de precios: ajustes, generación de líneas y totales de un presupuesto."""
import math
from datetime import date

ROLES = {
    "conductor": "Conductor/a",
    "azafata": "Azafata / azafato",
    "camarero": "Camarero/a",
    "tecnico": "Técnico/a",
}
NUMERICOS = {
    "transporte_precio_km": float,
    "transporte_coste_km": float,
    "coches_por_camion": int,
    "iva_pct": float,
    "validez_dias": int,
}


def leer_ajustes(db):
    datos = {r["clave"]: r["valor"] for r in db.execute("SELECT clave, valor FROM ajustes")}
    for clave, tipo in NUMERICOS.items():
        try:
            datos[clave] = tipo(datos.get(clave, 0))
        except ValueError:
            datos[clave] = tipo(0)
    datos["coches_por_camion"] = max(1, datos["coches_por_camion"])
    return datos


def guardar_ajustes(db, valores):
    for clave, valor in valores.items():
        db.execute(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?)"
            " ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, str(valor)),
        )


def tarifas_personal(db):
    return {r["rol"]: r for r in db.execute("SELECT * FROM tarifas_personal")}


def km_conocidos(db, ciudad):
    if not ciudad:
        return None
    fila = db.execute("SELECT km_ida FROM distancias WHERE ciudad = ?", (ciudad.strip(),)).fetchone()
    return fila["km_ida"] if fila else None


def recordar_km(db, ciudad, km_ida):
    if ciudad and km_ida:
        db.execute(
            "INSERT INTO distancias (ciudad, km_ida) VALUES (?, ?)"
            " ON CONFLICT(ciudad) DO UPDATE SET km_ida = excluded.km_ida",
            (ciudad.strip(), km_ida),
        )


def dias_evento(evento):
    return (date.fromisoformat(evento["fecha_fin"]) - date.fromisoformat(evento["fecha_inicio"])).days + 1


def camiones_necesarios(num_coches, coches_por_camion):
    return math.ceil(num_coches / coches_por_camion) if num_coches else 0


def _plural(n, singular, plural):
    return f"{n:g} {singular if n == 1 else plural}"


def generar_lineas(evento, vehiculos, ajustes, tarifas, km_ida, camiones, personal):
    """Líneas de un presupuesto nuevo.

    vehiculos: coches reservados para el evento.
    personal:  {rol: (personas, jornadas)}.
    Devuelve una lista de dicts (tipo, concepto, cantidad, precio, coste).
    """
    dias = dias_evento(evento)
    lineas = []
    for v in vehiculos:
        lineas.append({
            "tipo": "vehiculo",
            "concepto": f"{v['nombre']} — alquiler {_plural(dias, 'día', 'días')} de evento",
            "cantidad": dias,
            "precio": v["tarifa_dia"],
            "coste": v["coste_dia"],
        })

    if km_ida and camiones:
        destino = evento["ciudad"] or evento["venue"] or "destino"
        km_total = km_ida * 2 * camiones
        lineas.append({
            "tipo": "transporte",
            "concepto": (
                f"Transporte en camión portavehículos {ajustes.get('base_ciudad') or 'base'} → {destino}, "
                f"ida y vuelta ({_plural(camiones, 'camión', 'camiones')} × 2 × {km_ida:g} km)"
            ),
            "cantidad": km_total,
            "precio": ajustes["transporte_precio_km"],
            "coste": ajustes["transporte_coste_km"],
        })

    for rol, (personas, jornadas) in personal.items():
        if personas <= 0 or jornadas <= 0 or rol not in tarifas:
            continue
        t = tarifas[rol]
        lineas.append({
            "tipo": "personal",
            "concepto": (
                f"{ROLES[rol]} — {_plural(personas, 'persona', 'personas')} × "
                f"{_plural(jornadas, 'jornada', 'jornadas')}"
            ),
            "cantidad": personas * jornadas,
            "precio": t["precio_jornada"],
            "coste": t["coste_jornada"],
        })
    return lineas


def totales(lineas, descuento_pct, iva_pct):
    """Totales al cliente y margen interno.

    El descuento se aplica sobre el subtotal; el margen se calcula sobre la base
    (ya con descuento) menos los costes conocidos.
    """
    subtotal = round(sum(l["cantidad"] * l["precio"] for l in lineas), 2)
    descuento = round(subtotal * descuento_pct / 100, 2)
    base = round(subtotal - descuento, 2)
    iva = round(base * iva_pct / 100, 2)
    coste = round(sum(l["cantidad"] * l["coste"] for l in lineas), 2)
    margen = round(base - coste, 2)
    return {
        "subtotal": subtotal,
        "descuento": descuento,
        "base": base,
        "iva": iva,
        "total": round(base + iva, 2),
        "coste": coste,
        "margen": margen,
        "margen_pct": round(100 * margen / base, 1) if base else 0,
    }


def siguiente_numero(db, anio):
    prefijo = f"P-{anio}-"
    ultimo = db.execute(
        "SELECT numero FROM presupuestos WHERE numero LIKE ? ORDER BY numero DESC LIMIT 1",
        (prefijo + "%",),
    ).fetchone()
    n = int(ultimo["numero"].rsplit("-", 1)[1]) + 1 if ultimo else 1
    return f"{prefijo}{n:04d}"

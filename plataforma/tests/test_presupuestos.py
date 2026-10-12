import re

from rsjdr.db import get_db


def _reservar(client, evento_id, vehiculo_id):
    client.post(f"/eventos/{evento_id}/coches", data={"vehiculo_id": vehiculo_id, "dias_antes": 1, "dias_despues": 1})


def _crear_presupuesto(client, evento_id, km="600", camiones="1", azafatas="2"):
    data = {"km_ida": km, "camiones": camiones}
    for rol in ("conductor", "azafata", "camarero", "tecnico"):
        data[f"n_{rol}"] = azafatas if rol == "azafata" else "0"
        data[f"j_{rol}"] = "3"
    r = client.post(f"/presupuestos/nuevo/{evento_id}", data=data)
    assert r.status_code == 302, r.get_data(as_text=True)
    return int(re.search(r"/presupuestos/(\d+)", r.headers["Location"]).group(1))


def _q(app, sql, *args):
    with app.app_context():
        return get_db().execute(sql, args).fetchall()


def test_flujo_completo(client, crear, app):
    v = crear.vehiculo("KTM X-BOW GT", tarifa=1000)
    e = crear.evento("Salón BCN", "2026-11-10", "2026-11-12")
    with app.app_context():
        get_db().execute("UPDATE eventos SET ciudad = 'Barcelona' WHERE id = ?", (e,))
        get_db().commit()
    _reservar(client, e, v)
    pid = _crear_presupuesto(client, e)

    p = _q(app, "SELECT * FROM presupuestos WHERE id = ?", pid)[0]
    assert p["numero"].startswith("P-") and p["numero"].endswith("-0001")
    tipos = sorted(l["tipo"] for l in _q(app, "SELECT tipo FROM presupuesto_lineas WHERE presupuesto_id = ?", pid))
    assert tipos == ["personal", "transporte", "vehiculo"]

    # La distancia se recuerda para el siguiente presupuesto en Barcelona.
    assert _q(app, "SELECT km_ida FROM distancias WHERE ciudad = 'barcelona'")[0][0] == 600
    assert 'value="600"' in client.get(f"/presupuestos/nuevo/{e}").get_data(as_text=True)

    html = client.get(f"/presupuestos/{pid}").get_data(as_text=True)
    assert "P-" in html and "margen" in html

    propuesta = client.get(f"/presupuestos/{pid}/propuesta").get_data(as_text=True)
    assert "KTM X-BOW GT" in propuesta
    assert "Coste" not in propuesta  # el coste interno nunca sale al cliente

    client.post(f"/presupuestos/{pid}/estado", data={"estado": "enviado"})
    assert "pendientes de respuesta" in client.get("/").get_data(as_text=True)

    client.post(f"/presupuestos/{pid}/estado", data={"estado": "aceptado"})
    assert crear.estado(e) == "confirmado"


def test_editar_lineas_descuento_y_extra(client, crear, app):
    v = crear.vehiculo(tarifa=1000)
    e = crear.evento("Ev", "2026-11-10", "2026-11-10")
    _reservar(client, e, v)
    pid = _crear_presupuesto(client, e, km="", azafatas="0")
    linea = _q(app, "SELECT * FROM presupuesto_lineas WHERE presupuesto_id = ?", pid)[0]

    r = client.post(f"/presupuestos/{pid}/guardar", data={
        f"concepto_{linea['id']}": "KTM — día de feria",
        f"cantidad_{linea['id']}": "1",
        f"precio_{linea['id']}": "1.100",       # formato español: mil cien
        f"coste_{linea['id']}": "0",
        "nuevo_concepto": "Vinilado con logo del cliente",
        "nuevo_cantidad": "1", "nuevo_precio": "350", "nuevo_coste": "200",
        "descuento_pct": "10", "iva_pct": "21", "validez_dias": "15", "notas": "Incluye seguro",
    })
    assert r.status_code == 302
    lineas = _q(app, "SELECT * FROM presupuesto_lineas WHERE presupuesto_id = ? ORDER BY orden", pid)
    assert [l["precio"] for l in lineas] == [1100, 350]
    assert _q(app, "SELECT descuento_pct FROM presupuestos WHERE id = ?", pid)[0][0] == 10
    html = client.get(f"/presupuestos/{pid}/propuesta").get_data(as_text=True)
    assert "1.579,05 €" in html   # (1100 + 350) × 0,9 = 1305 de base + 21 % de IVA


def test_avisa_si_el_presupuesto_no_se_podria_cumplir(client, crear):
    v = crear.vehiculo("KTM X-BOW GT")
    firme = crear.evento("Ya confirmado", "2026-11-10", "2026-11-12", "confirmado")
    nuevo = crear.evento("Cliente nuevo", "2026-11-11", "2026-11-11")
    _reservar(client, firme, v)
    _reservar(client, nuevo, v)
    pid = _crear_presupuesto(client, nuevo, km="", azafatas="0")
    html = client.get(f"/presupuestos/{pid}").get_data(as_text=True)
    assert "no podrías confirmar el evento" in html
    # Y si aun así el cliente acepta, el evento no se confirma solo.
    client.post(f"/presupuestos/{pid}/estado", data={"estado": "aceptado"})
    assert crear.estado(nuevo) == "presupuesto"

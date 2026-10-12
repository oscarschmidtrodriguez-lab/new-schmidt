"""Reglas de negocio: un coche no puede estar en dos eventos firmes a la vez."""


def reservar(client, evento_id, vehiculo_id, antes=1, despues=1):
    return client.post(
        f"/eventos/{evento_id}/coches",
        data={"vehiculo_id": vehiculo_id, "dias_antes": antes, "dias_despues": despues},
        follow_redirects=True,
    )


def test_reserva_libre(client, crear):
    v = crear.vehiculo()
    e = crear.evento("Salón Madrid", "2026-11-10", "2026-11-12", "confirmado")
    r = reservar(client, e, v)
    assert "reservado" in r.get_data(as_text=True)
    assert len(crear.reservas(e)) == 1


def test_dos_confirmados_mismas_fechas_bloquea(client, crear):
    v = crear.vehiculo("Corvette C8")
    a = crear.evento("Feria A", "2026-11-10", "2026-11-12", "confirmado")
    b = crear.evento("Feria B", "2026-11-11", "2026-11-11", "confirmado")
    reservar(client, a, v)
    r = reservar(client, b, v)
    assert "ya está reservado" in r.get_data(as_text=True)
    assert crear.reservas(b) == []


def test_margen_de_transporte_cuenta_como_ocupado(client, crear):
    # A acaba el 12 y el coche vuelve el 13; B empieza el 14 pero sale el 13.
    v = crear.vehiculo()
    a = crear.evento("Feria A", "2026-11-10", "2026-11-12", "confirmado")
    b = crear.evento("Feria B", "2026-11-14", "2026-11-15", "confirmado")
    reservar(client, a, v)
    reservar(client, b, v)
    assert crear.reservas(b) == []
    # Sin margen de salida, sí cabe.
    reservar(client, b, v, antes=0)
    assert len(crear.reservas(b)) == 1


def test_presupuesto_solapado_se_permite_con_aviso(client, crear):
    v = crear.vehiculo()
    a = crear.evento("Confirmado", "2026-11-10", "2026-11-12", "confirmado")
    b = crear.evento("Solo presupuesto", "2026-11-11", "2026-11-11", "presupuesto")
    reservar(client, a, v)
    r = reservar(client, b, v)
    assert "provisional" in r.get_data(as_text=True)
    assert len(crear.reservas(b)) == 1


def test_no_se_puede_confirmar_si_el_coche_ya_esta_comprometido(client, crear):
    v = crear.vehiculo()
    a = crear.evento("Confirmado", "2026-11-10", "2026-11-12", "confirmado")
    b = crear.evento("Presupuesto", "2026-11-11", "2026-11-11", "presupuesto")
    reservar(client, a, v)
    reservar(client, b, v)
    r = client.post(f"/eventos/{b}/estado", data={"estado": "confirmado"}, follow_redirects=True)
    assert "No se puede pasar" in r.get_data(as_text=True)
    assert crear.estado(b) == "presupuesto"


def test_cancelar_libera_el_coche(client, crear):
    v = crear.vehiculo()
    a = crear.evento("A", "2026-11-10", "2026-11-12", "confirmado")
    b = crear.evento("B", "2026-11-11", "2026-11-11", "presupuesto")
    reservar(client, a, v)
    reservar(client, b, v)
    client.post(f"/eventos/{a}/estado", data={"estado": "cancelado"})
    client.post(f"/eventos/{b}/estado", data={"estado": "confirmado"})
    assert crear.estado(b) == "confirmado"


def test_coche_en_taller_no_se_reserva(client, crear):
    v = crear.vehiculo("Honda NSX", estado="taller")
    e = crear.evento("Feria", "2026-11-10", "2026-11-12")
    r = reservar(client, e, v)
    assert "taller" in r.get_data(as_text=True)
    assert crear.reservas(e) == []


def test_mover_fechas_que_crea_solape_se_bloquea(client, crear):
    v = crear.vehiculo()
    a = crear.evento("A", "2026-11-10", "2026-11-12", "confirmado")
    b = crear.evento("B", "2026-11-20", "2026-11-21", "confirmado")
    reservar(client, a, v)
    reservar(client, b, v)
    r = client.post(f"/eventos/{b}/editar", data={
        "nombre": "B", "tipo": "feria", "estado": "confirmado",
        "fecha_inicio": "2026-11-12", "fecha_fin": "2026-11-13",
    }, follow_redirects=True)
    assert "ya está reservado" in r.get_data(as_text=True)


def test_panel_muestra_alerta_si_coche_pasa_a_taller(client, crear, app):
    v = crear.vehiculo("CUPRA DTM")
    e = crear.evento("Feria", "2099-01-10", "2099-01-12", "confirmado")
    reservar(client, e, v)
    r = client.post(f"/flota/{v}/editar", data={
        "nombre": "CUPRA DTM", "categoria": "competicion", "estado": "taller",
        "tarifa_dia": "1200", "fianza": "5000", "km_actuales": "15000",
    }, follow_redirects=True)
    assert "Busca sustituto" in r.get_data(as_text=True)
    panel = client.get("/").get_data(as_text=True)
    assert "taller" in panel and "Feria" in panel


def test_calendario_marca_solape(client, crear):
    v = crear.vehiculo()
    a = crear.evento("A", "2026-11-10", "2026-11-12", "confirmado")
    b = crear.evento("B", "2026-11-11", "2026-11-11", "presupuesto")
    reservar(client, a, v)
    reservar(client, b, v)
    html = client.get("/flota/calendario?mes=2026-11").get_data(as_text=True)
    assert 'class="conflicto' in html

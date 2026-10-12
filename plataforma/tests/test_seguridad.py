def test_sin_login_redirige(anon):
    for url in ("/", "/flota/", "/eventos/", "/clientes/", "/flota/calendario"):
        r = anon.get(url)
        assert r.status_code == 302 and "/login" in r.headers["Location"], url


def test_no_hay_registro_publico(anon):
    assert anon.get("/registro").status_code == 404


def test_login_incorrecto(anon):
    r = anon.post("/login", data={"email": "oscar@rsjdr.es", "password": "mala"})
    assert r.status_code == 200
    assert "incorrectos" in r.get_data(as_text=True)


def test_post_sin_csrf_rechazado(client):
    r = client.c.post("/clientes/nuevo", data={"nombre": "Sin token"})
    assert r.status_code == 400


def test_login_no_redirige_fuera(anon):
    r = anon.post(
        "/login?next=//evil.com",
        data={"email": "oscar@rsjdr.es", "password": "contraseña-segura"},
    )
    assert r.headers["Location"] == "/"


def test_paginas_cargan(client, crear):
    v = crear.vehiculo()
    e = crear.evento("Feria", "2026-11-10", "2026-11-12")
    for url in ("/", "/flota/", f"/flota/{v}", "/flota/calendario?mes=2026-11",
                "/eventos/", f"/eventos/{e}", "/clientes/", "/clientes/nuevo",
                "/eventos/nuevo", "/flota/nuevo"):
        assert client.get(url).status_code == 200, url

"""Datos de ejemplo para probar la plataforma (`flask --app rsjdr demo`)."""
from datetime import date, timedelta

import click

from .db import get_db

COCHES = [
    ("KTM X-BOW GT", "competicion", 1100, 6000, 18400, 320),
    ("Chevrolet Corvette C8", "deportivo", 850, 4000, 32150, 240),
    ("Honda NSX", "exotico", 950, 5000, 27800, 280),
    ("CUPRA León DTM", "competicion", 1200, 6000, 9600, 380),
]


def register(app):
    @app.cli.command("demo")
    def demo():
        """Carga una flota y eventos de ejemplo (solo si la base está vacía)."""
        db = get_db()
        if db.execute("SELECT COUNT(*) FROM vehiculos").fetchone()[0]:
            raise click.ClickException("Ya hay coches en la base de datos; no cargo la demo.")

        ids = []
        for nombre, cat, tarifa, fianza, km, coste in COCHES:
            cur = db.execute(
                "INSERT INTO vehiculos (nombre, categoria, tarifa_dia, fianza, km_actuales, coste_dia)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (nombre, cat, tarifa, fianza, km, coste),
            )
            ids.append(cur.lastrowid)
        cli = db.execute(
            "INSERT INTO clientes (nombre, empresa, email) VALUES (?, ?, ?)",
            ("Laura Gómez", "Agencia Eventia", "laura@eventia.example"),
        ).lastrowid

        hoy = date.today()

        def evento(nombre, desde, dias, estado, venue, ciudad, coches):
            ini = hoy + timedelta(days=desde)
            fin = ini + timedelta(days=dias - 1)
            eid = db.execute(
                "INSERT INTO eventos (nombre, cliente_id, tipo, venue, ciudad, fecha_inicio,"
                " fecha_fin, estado) VALUES (?, ?, 'feria', ?, ?, ?, ?, ?)",
                (nombre, cli, venue, ciudad, ini.isoformat(), fin.isoformat(), estado),
            ).lastrowid
            for i in coches:
                db.execute(
                    "INSERT INTO evento_vehiculos (evento_id, vehiculo_id) VALUES (?, ?)",
                    (eid, ids[i]),
                )

        evento("Salón del Motor — stand Cupra", 5, 4, "confirmado", "IFEMA", "Madrid", [0, 3])
        evento("Convención farmacéutica", 7, 2, "presupuesto", "Fira Gran Via", "Barcelona", [0, 1])
        evento("Lanzamiento relojería", 16, 1, "confirmado", "Hotel Puente Romano", "Marbella", [2])
        db.commit()
        click.echo("Demo cargada: 4 coches, 1 cliente y 3 eventos (uno con un solape provisional).")

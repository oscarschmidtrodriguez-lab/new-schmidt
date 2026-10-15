import pytest

from rsjdr.numeros import leer_numero, para_input
from rsjdr.tarifas import camiones_necesarios, generar_lineas, totales


@pytest.mark.parametrize("texto,esperado", [
    ("1.100", 1100), ("1100", 1100), ("2,5", 2.5), ("1.234,50", 1234.5),
    ("2.20", 2.2), ("900 €", 900), ("", 0), ("abc", None),
])
def test_leer_numero_formato_espanol(texto, esperado):
    assert leer_numero(texto) == esperado


def test_leer_entero_rechaza_decimales():
    assert leer_numero("18.400", int) == 18400
    assert leer_numero("2,5", int) is None


def test_para_input_es_reversible():
    for n in (1100, 2.2, 1234.5, 0):
        assert leer_numero(para_input(n)) == n


def test_camiones():
    assert camiones_necesarios(0, 2) == 0
    assert camiones_necesarios(1, 2) == 1
    assert camiones_necesarios(3, 2) == 2


AJUSTES = {"base_ciudad": "Madrid", "transporte_precio_km": 2.0, "transporte_coste_km": 1.5}
TARIFAS = {"azafata": {"precio_jornada": 200, "coste_jornada": 120}}
EVENTO = {"fecha_inicio": "2026-11-10", "fecha_fin": "2026-11-12", "ciudad": "Barcelona", "venue": None}
COCHES = [{"nombre": "KTM X-BOW GT", "tarifa_dia": 1000, "coste_dia": 300}, {"nombre": "Honda NSX", "tarifa_dia": 900, "coste_dia": 0}]


def test_generar_lineas_completo():
    lineas = generar_lineas(EVENTO, COCHES, AJUSTES, TARIFAS, km_ida=600, camiones=1,
                            personal={"azafata": (2, 3)})
    por_tipo = {l["tipo"]: l for l in lineas}
    assert [l["cantidad"] for l in lineas if l["tipo"] == "vehiculo"] == [3, 3]
    assert por_tipo["transporte"]["cantidad"] == 1200          # 600 km × ida y vuelta × 1 camión
    assert "Madrid → Barcelona" in por_tipo["transporte"]["concepto"]
    assert por_tipo["personal"]["cantidad"] == 6               # 2 azafatas × 3 jornadas
    t = totales(lineas, descuento_pct=0, iva_pct=21)
    # 3×1000 + 3×900 + 1200×2 + 6×200
    assert t["base"] == 3000 + 2700 + 2400 + 1200
    assert t["coste"] == 3 * 300 + 1200 * 1.5 + 6 * 120
    assert t["total"] == round(t["base"] * 1.21, 2)


def test_sin_km_no_hay_transporte_y_personal_a_cero_se_omite():
    lineas = generar_lineas(EVENTO, COCHES, AJUSTES, TARIFAS, km_ida=0, camiones=1,
                            personal={"azafata": (0, 3)})
    assert {l["tipo"] for l in lineas} == {"vehiculo"}


def test_descuento_y_margen():
    lineas = [{"cantidad": 1, "precio": 1000, "coste": 400}]
    t = totales(lineas, descuento_pct=10, iva_pct=21)
    assert t["descuento"] == 100
    assert t["base"] == 900
    assert t["iva"] == 189
    assert t["total"] == 1089
    assert t["margen"] == 500
    assert t["margen_pct"] == pytest.approx(55.6)

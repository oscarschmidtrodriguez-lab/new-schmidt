"""Etiquetas y formatos para las plantillas."""
from datetime import date

from jinja2 import Undefined

from .numeros import para_input

ESTADO_EVENTO = {
    "presupuesto": "Presupuesto",
    "confirmado": "Confirmado",
    "en_curso": "En curso",
    "finalizado": "Finalizado",
    "cancelado": "Cancelado",
}
TIPO_EVENTO = {
    "feria": "Feria",
    "corporativo": "Corporativo",
    "presentacion": "Presentación de producto",
    "rodaje": "Rodaje / sesión de fotos",
    "privado": "Privado",
    "otro": "Otro",
}
ESTADO_VEHICULO = {"operativo": "Operativo", "taller": "En taller", "baja": "De baja"}
CATEGORIA_VEHICULO = {
    "deportivo": "Deportivo",
    "exotico": "Exótico",
    "competicion": "Competición",
    "clasico": "Clásico",
    "apoyo": "Apoyo / transporte",
}


def fecha(valor):
    if not valor:
        return ""
    return date.fromisoformat(valor[:10]).strftime("%d/%m/%Y")


def euros(valor):
    if valor is None:
        return ""
    texto = f"{valor:,.0f}".replace(",", ".")
    return f"{texto} €"


def euros2(valor):
    """1234.5 -> «1.234,50 €»"""
    if valor is None:
        return ""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{texto} €"


def numero(valor):
    """Cantidades: sin decimales si es entero, con coma decimal si no."""
    if valor is None:
        return ""
    if float(valor).is_integer():
        return f"{int(valor):,}".replace(",", ".")
    return f"{valor:g}".replace(".", ",")


def km(valor):
    return f"{valor or 0:,}".replace(",", ".") + " km"


def init_app(app):
    app.jinja_env.filters.update(
        fecha=fecha,
        euros=euros,
        euros2=euros2,
        numero=numero,
        input_num=lambda v: "" if isinstance(v, Undefined) else para_input(v),
        km=km,
        estado_evento=lambda v: ESTADO_EVENTO.get(v, v),
        tipo_evento=lambda v: TIPO_EVENTO.get(v, v),
        estado_vehiculo=lambda v: ESTADO_VEHICULO.get(v, v),
        categoria_vehiculo=lambda v: CATEGORIA_VEHICULO.get(v, v),
    )
    app.jinja_env.globals.update(
        ESTADO_EVENTO=ESTADO_EVENTO,
        TIPO_EVENTO=TIPO_EVENTO,
        ESTADO_VEHICULO=ESTADO_VEHICULO,
        CATEGORIA_VEHICULO=CATEGORIA_VEHICULO,
    )

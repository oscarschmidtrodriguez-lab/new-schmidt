"""Etiquetas y formatos para las plantillas."""
from datetime import date

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


def km(valor):
    return f"{valor or 0:,}".replace(",", ".") + " km"


def init_app(app):
    app.jinja_env.filters.update(
        fecha=fecha,
        euros=euros,
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

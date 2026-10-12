"""Lectura de números escritos al estilo español («1.100», «2,5», «1.234,50»)."""
import re

_MILES = re.compile(r"^-?\d{1,3}(\.\d{3})+$")


def leer_numero(valor, tipo=float, defecto=0):
    """Convierte texto a número. Devuelve `defecto` si está vacío y None si no es válido."""
    if valor is None:
        return defecto
    texto = str(valor).strip().replace(" ", "").replace("€", "")
    if not texto:
        return defecto
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")   # 1.234,50 -> 1234.50
    elif _MILES.match(texto):
        texto = texto.replace(".", "")                     # 1.100 -> 1100
    try:
        n = float(texto)
    except ValueError:
        return None
    if tipo is int:
        return int(n) if n.is_integer() else None
    return n


def para_input(valor):
    """Número para rellenar un campo de formulario: sin separador de miles, coma decimal."""
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return ""  # campo vacío (formulario nuevo o valor no válido)
    if n.is_integer():
        return str(int(n))
    return f"{n:.4f}".rstrip("0").replace(".", ",")

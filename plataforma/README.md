# RSJdR Luxury — plataforma de operaciones

Gestión de flota de coches exóticos y deportivos para ferias y eventos corporativos.

## Qué hace (fase 1: flota sin solapes)

- **Flota**: ficha de cada coche (tarifa/día, fianza, km, estado operativo / taller / baja)
  con sus próximas reservas e historial.
- **Eventos y clientes**: cada evento tiene cliente, venue, fechas y estado
  (presupuesto → confirmado → en curso → finalizado / cancelado).
- **Reservas de coches con control de solapes**. Un coche ocupa los días del evento
  **más** los días de transporte/montaje antes y de recogida después (1 por defecto,
  ajustable por reserva).
  - Dos eventos **firmes** (confirmado/en curso/finalizado) con el mismo coche y fechas
    que se pisan → **bloqueado**.
  - Si uno de los dos es solo **presupuesto** → se permite como **reserva provisional**
    con aviso, para poder presupuestar sin perder ventas. Al confirmar, se vuelve a
    comprobar: no puedes confirmar un evento con un coche ya comprometido.
  - Coches en taller o de baja no se pueden reservar; si un coche reservado pasa a
    taller, la app te avisa de los eventos afectados.
  - Cambiar las fechas de un evento revalida todos sus coches.
- **Calendario de flota**: coches × días del mes, con confirmados, provisionales,
  días de logística, solapes en rojo y coches en taller. Muestra el % de ocupación firme.
- **Panel**: alertas abiertas y eventos de los próximos 45 días.

## Seguridad y datos

- Acceso **solo por invitación** (no hay registro público). Protección CSRF en todos
  los formularios y cookies de sesión `HttpOnly`.
- **Copia de seguridad automática** diaria en `instance/backups/` (se conservan 30)
  y otra antes de aplicar cualquier migración.
- Las migraciones (`rsjdr/migrations/`) solo añaden; nunca borran tablas.

## Puesta en marcha

```bash
cd plataforma
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

flask --app rsjdr crear-usuario tu@email.com --nombre "Tu nombre"   # pide contraseña
flask --app rsjdr demo        # opcional: 4 coches y 3 eventos de ejemplo
flask --app rsjdr run
```

Abre http://127.0.0.1:5000.

Otros comandos:

```bash
flask --app rsjdr backup                       # copia de seguridad manual
flask --app rsjdr desactivar-usuario email     # quitar acceso
```

Si la publicas en internet, ponla detrás de HTTPS y define `HTTPS=1` y `SECRET_KEY`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

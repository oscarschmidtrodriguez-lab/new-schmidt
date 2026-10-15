-- Presupuestos: ajustes de la empresa, tarifas, distancias aprendidas,
-- presupuestos y sus líneas.

-- Lo que te cuesta cada día de alquiler de un coche (seguro, amortización,
-- preparación). Solo se usa para calcular el margen; el cliente no lo ve.
ALTER TABLE vehiculos ADD COLUMN coste_dia REAL NOT NULL DEFAULT 0;

CREATE TABLE ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

-- Valores de ejemplo: se cambian en la pantalla «Tarifas».
INSERT INTO ajustes (clave, valor) VALUES
    ('empresa_nombre', 'RSJdR Luxury'),
    ('empresa_cif', ''),
    ('empresa_email', ''),
    ('empresa_telefono', ''),
    ('empresa_web', ''),
    ('base_ciudad', 'Madrid'),
    ('transporte_precio_km', '2.20'),
    ('transporte_coste_km', '1.40'),
    ('coches_por_camion', '2'),
    ('iva_pct', '21'),
    ('validez_dias', '15'),
    ('condiciones', 'Reserva en firme con la aceptación de esta propuesta y el pago del 50 %. Resto antes del evento. Fianza por vehículo reembolsable a la devolución sin daños. Seguro a todo riesgo incluido; franquicia según condiciones de póliza.');

CREATE TABLE tarifas_personal (
    rol TEXT PRIMARY KEY CHECK(rol IN ('conductor', 'azafata', 'camarero', 'tecnico')),
    precio_jornada REAL NOT NULL,   -- lo que cobras al cliente
    coste_jornada REAL NOT NULL     -- lo que te cuesta a ti
);

INSERT INTO tarifas_personal (rol, precio_jornada, coste_jornada) VALUES
    ('conductor', 250, 150),
    ('azafata', 220, 130),
    ('camarero', 180, 110),
    ('tecnico', 300, 180);

-- Kilómetros (solo ida) desde la base a cada ciudad. Se recuerdan solos
-- la primera vez que presupuestas un evento en esa ciudad.
CREATE TABLE distancias (
    ciudad TEXT PRIMARY KEY COLLATE NOCASE,
    km_ida INTEGER NOT NULL CHECK(km_ida >= 0)
);

CREATE TABLE presupuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id INTEGER NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
    numero TEXT UNIQUE NOT NULL,                 -- P-2026-0001
    estado TEXT NOT NULL DEFAULT 'borrador'
        CHECK(estado IN ('borrador', 'enviado', 'aceptado', 'rechazado')),
    descuento_pct REAL NOT NULL DEFAULT 0 CHECK(descuento_pct >= 0 AND descuento_pct <= 100),
    iva_pct REAL NOT NULL DEFAULT 21,
    validez_dias INTEGER NOT NULL DEFAULT 15,
    notas TEXT,                                   -- aparecen en la propuesta al cliente
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    enviado_at TEXT
);

CREATE TABLE presupuesto_lineas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    presupuesto_id INTEGER NOT NULL REFERENCES presupuestos(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK(tipo IN ('vehiculo', 'transporte', 'personal', 'extra')),
    concepto TEXT NOT NULL,
    cantidad REAL NOT NULL DEFAULT 1,
    precio REAL NOT NULL DEFAULT 0,               -- precio unitario al cliente
    coste REAL NOT NULL DEFAULT 0,                -- coste unitario interno (no sale en la propuesta)
    orden INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_presupuestos_evento ON presupuestos(evento_id);
CREATE INDEX idx_lineas_presupuesto ON presupuesto_lineas(presupuesto_id);

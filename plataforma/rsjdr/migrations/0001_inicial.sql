-- Esquema inicial: usuarios, clientes, flota, eventos y reservas de vehículos.
-- Las migraciones solo añaden; nunca se borran tablas con datos.

CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    nombre TEXT,
    password_hash TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    empresa TEXT,
    cif TEXT,
    email TEXT,
    telefono TEXT,
    notas TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE vehiculos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,              -- p. ej. "KTM X-BOW GT"
    matricula TEXT UNIQUE,
    categoria TEXT NOT NULL DEFAULT 'deportivo'
        CHECK(categoria IN ('deportivo', 'exotico', 'competicion', 'clasico', 'apoyo')),
    tarifa_dia REAL NOT NULL DEFAULT 0,
    fianza REAL NOT NULL DEFAULT 0,
    km_actuales INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'operativo'
        CHECK(estado IN ('operativo', 'taller', 'baja')),
    notas TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    cliente_id INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
    tipo TEXT NOT NULL DEFAULT 'feria'
        CHECK(tipo IN ('feria', 'corporativo', 'presentacion', 'rodaje', 'privado', 'otro')),
    venue TEXT,
    ciudad TEXT,
    fecha_inicio TEXT NOT NULL,
    fecha_fin TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'presupuesto'
        CHECK(estado IN ('presupuesto', 'confirmado', 'en_curso', 'finalizado', 'cancelado')),
    notas TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK(fecha_fin >= fecha_inicio)
);

-- Un coche reservado para un evento. Ocupa desde
-- fecha_inicio - dias_antes (transporte/montaje) hasta fecha_fin + dias_despues.
CREATE TABLE evento_vehiculos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id INTEGER NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
    vehiculo_id INTEGER NOT NULL REFERENCES vehiculos(id) ON DELETE RESTRICT,
    dias_antes INTEGER NOT NULL DEFAULT 1 CHECK(dias_antes >= 0),
    dias_despues INTEGER NOT NULL DEFAULT 1 CHECK(dias_despues >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(evento_id, vehiculo_id)
);

CREATE INDEX idx_evento_vehiculos_vehiculo ON evento_vehiculos(vehiculo_id);
CREATE INDEX idx_eventos_fechas ON eventos(fecha_inicio, fecha_fin);

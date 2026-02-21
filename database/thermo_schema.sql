CREATE TABLE IF NOT EXISTS thermo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    temperature REAL NOT NULL,
    humidity REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_thermo_created ON thermo(created);
CREATE INDEX IF NOT EXISTS idx_thermo_device ON thermo(device_id);

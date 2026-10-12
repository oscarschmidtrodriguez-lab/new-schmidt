import os

from rsjdr.db import backup, migrate


def test_migraciones_idempotentes_y_con_copia(tmp_path):
    db_path = str(tmp_path / "x.db")
    backups = str(tmp_path / "b")
    assert migrate(db_path, backups) == ["0001_inicial"]
    assert migrate(db_path, backups) == []
    assert not os.path.exists(backups)  # nada pendiente: no hace falta copia


def test_backup_rota(tmp_path):
    db_path = str(tmp_path / "x.db")
    backups = str(tmp_path / "b")
    migrate(db_path, backups)
    destino = backup(db_path, backups, etiqueta="manual")
    assert os.path.exists(destino)

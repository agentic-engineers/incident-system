"""Importador mensual del sistema viejo (Nagios + planillas).

Corre el dia 1 de cada mes desde 2023, a mano, desde la maquina de Marcos:

    python scripts/legacy_import.py export_mensual.csv

Inserta DIRECTO en la tabla incidents (no pasa por la API a proposito: el
export trae miles de filas y la API los deduplicaria "mal": aca las
recurrencias mensuales SE INSERTAN DE NUEVO, asi lo pide compliance para
el historico).

OJO: por esto mismo la tabla incidents NO puede tener unique en fingerprint.
Se intento en 2023 y este script murio a mitad de un import (quedo el
historico cojo un mes entero). Hablar con Marcos antes de cambiar nada.
"""
import csv
import datetime
import sys

from sqlalchemy import create_engine, text

from app.db import DATABASE_URL
from app.domain.models import compute_fingerprint

INSERT = text(
    "INSERT INTO incidents (fingerprint, source, title, body, status, created_at) "
    "VALUES (:fingerprint, :source, :title, :body, :status, :created_at)"
)


def main(path: str) -> int:
    engine = create_engine(DATABASE_URL)
    insertados = 0
    with engine.begin() as conn, open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            # El export trae recurrencias del mismo incidente en meses distintos:
            # mismo fingerprint, filas nuevas. Es intencional (historico compliance).
            conn.execute(
                INSERT,
                {
                    "fingerprint": compute_fingerprint(row["source"], row["title"]),
                    "source": row["source"],
                    "title": row["title"],
                    "body": row.get("body", ""),
                    "status": row.get("status", "done"),
                    "created_at": datetime.datetime.fromisoformat(row["fecha"]),
                },
            )
            insertados += 1
    print(f"importadas {insertados} filas")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: python scripts/legacy_import.py <export.csv>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))

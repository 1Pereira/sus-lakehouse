"""Aplicacao do DDL versionado das camadas via Trino."""

import logging
import os

import trino

from sus_sih import config

logger = logging.getLogger(__name__)

ARQUIVOS_BRONZE = ("bronze/sih_aih_schema.sql", "bronze/sih_aih.sql")
ARQUIVOS_SILVER = ("silver/sih_aih_schema.sql", "silver/sih_aih.sql")


def conectar():
    return trino.dbapi.connect(
        host=os.environ.get("TRINO_HOST", "localhost"),
        port=int(os.environ.get("TRINO_PORT", "8080")),
        user=os.environ.get("TRINO_USER", "airflow"),
    )


def ler_sql(relativo: str) -> str:
    caminho = os.path.join(config.DIR_SQL, relativo)
    return open(caminho, encoding="utf-8").read().strip().rstrip(";")


def executar(cursor, relativo: str, params: tuple | None = None):
    sql = ler_sql(relativo)
    if params:
        cursor.execute(sql, params=params)
    else:
        cursor.execute(sql)
    resultado = cursor.fetchall()
    logger.info("aplicado %s", relativo)
    return resultado


def garantir(arquivos: tuple[str, ...]) -> None:
    with conectar() as conexao:
        cursor = conexao.cursor()
        for relativo in arquivos:
            executar(cursor, relativo)


def garantir_tabela() -> None:
    """Namespace e tabela da bronze."""
    garantir(ARQUIVOS_BRONZE)

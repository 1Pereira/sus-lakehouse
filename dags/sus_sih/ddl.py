"""Aplicacao do DDL versionado da camada bronze via Trino."""

import logging
import os

import trino

from sus_sih import config

logger = logging.getLogger(__name__)

ARQUIVOS_BRONZE = ("bronze/sih_aih_schema.sql", "bronze/sih_aih.sql")


def conectar():
    return trino.dbapi.connect(
        host=os.environ.get("TRINO_HOST", "localhost"),
        port=int(os.environ.get("TRINO_PORT", "8080")),
        user=os.environ.get("TRINO_USER", "airflow"),
    )


def executar_arquivo(cursor, caminho: str) -> None:
    sentenca = open(caminho, encoding="utf-8").read().strip().rstrip(";")
    cursor.execute(sentenca)
    cursor.fetchall()
    logger.info("aplicado %s", caminho)


def garantir_tabela() -> None:
    """Cria namespace e tabela bronze se ainda nao existirem."""
    with conectar() as conexao:
        cursor = conexao.cursor()
        for relativo in ARQUIVOS_BRONZE:
            executar_arquivo(cursor, os.path.join(config.DIR_SQL, relativo))

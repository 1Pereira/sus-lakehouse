"""Carga da camada silver do SIH a partir da bronze."""

import logging

from sus_sih import ddl
from sus_sih.download import validar_competencia

logger = logging.getLogger(__name__)

CARGA = "silver/sih_aih_carga.sql"


def garantir_tabela() -> None:
    ddl.garantir(ddl.ARQUIVOS_SILVER)


def carregar(competencia: str) -> int:
    """Roda o merge de uma competencia e devolve as linhas afetadas.

    A competencia entra como parametro do Trino, nunca interpolada na string,
    e o SQL vive em sql/silver para nao virar literal no meio da DAG.
    """
    competencia = validar_competencia(competencia)
    with ddl.conectar() as conexao:
        cursor = conexao.cursor()
        resultado = ddl.executar(cursor, CARGA, params=(competencia,))
    afetadas = resultado[0][0] if resultado and resultado[0] else 0
    logger.info("silver recebeu %s linhas da competencia %s", afetadas, competencia)
    return afetadas

"""Gravacao da tabela bronze do SIH no catalogo Iceberg.

A tabela e criada pelos arquivos em sql/bronze, unico lugar onde o DDL vive.
Aqui so acontece a escrita de dados e a evolucao de schema quando uma
competencia traz campos que ainda nao existem na tabela.
"""

import logging
import os

import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.expressions import EqualTo

from sus_sih import config
from sus_sih.conversao import COLUNA_ARQUIVO

logger = logging.getLogger(__name__)

IDENTIFICADOR = (config.NAMESPACE_BRONZE, config.TABELA_BRONZE)


def carregar_catalogo() -> RestCatalog:
    return RestCatalog(
        "rest",
        **{
            "uri": config.iceberg_rest_uri(),
            "s3.endpoint": config.s3_endpoint(),
            "s3.access-key-id": os.environ.get("AWS_ACCESS_KEY_ID", ""),
            "s3.secret-access-key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        },
    )


def alinhar_ao_schema(tabela: pa.Table, alvo: pa.Schema) -> pa.Table:
    """Reordena as colunas na ordem do alvo e preenche com nulo o que faltar.

    Competencias antigas nao tem todos os campos das recentes, e o Iceberg
    exige que o lote escrito case com o schema da tabela.
    """
    colunas = []
    for campo in alvo:
        if campo.name in tabela.column_names:
            colunas.append(tabela.column(campo.name).cast(campo.type))
        else:
            colunas.append(pa.nulls(tabela.num_rows, type=campo.type))
    return pa.Table.from_arrays(colunas, schema=alvo)


def evoluir_schema(tabela_iceberg, tabela: pa.Table) -> None:
    """Absorve campos que a competencia trouxe e a tabela ainda nao tem."""
    existentes = set(tabela_iceberg.schema().as_arrow().names)
    novos = [nome for nome in tabela.column_names if nome not in existentes]
    if not novos:
        return
    logger.info("evoluindo schema da bronze com os campos %s", novos)
    with tabela_iceberg.update_schema() as evolucao:
        evolucao.union_by_name(tabela.schema)


def gravar(tabela: pa.Table, nome_arquivo: str, catalogo=None) -> int:
    """Substitui a fatia da tabela que veio deste arquivo e devolve as linhas escritas.

    A idempotencia vem do overwrite filtrado por _source_file. Reprocessar a
    mesma UF e competencia troca a fatia em vez de acumular, e o filtro e por
    arquivo, nao por competencia, porque uma competencia agrega as 27 UFs e
    reprocessar uma nao pode apagar as outras.
    """
    catalogo = catalogo or carregar_catalogo()
    tabela_iceberg = catalogo.load_table(IDENTIFICADOR)

    evoluir_schema(tabela_iceberg, tabela)
    tabela_iceberg.refresh()

    alinhada = alinhar_ao_schema(tabela, tabela_iceberg.schema().as_arrow())
    tabela_iceberg.overwrite(
        alinhada,
        overwrite_filter=EqualTo(COLUNA_ARQUIVO, nome_arquivo),
    )

    logger.info("gravadas %s linhas de %s na bronze", alinhada.num_rows, nome_arquivo)
    return alinhada.num_rows

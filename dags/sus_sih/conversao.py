"""Conversao dos arquivos .dbc do DATASUS para tabelas Arrow.

O .dbc e um .dbf comprimido com PKWare DCL implode. A descompressao usa
pyreaddbc, que empacota o blast em C com wheel para a versao de Python da
imagem. A leitura do .dbf resultante e feita em modo raw para que nenhum
campo seja tipado nesta camada: bronze guarda a origem como veio.
"""

import datetime as dt
import logging
import os
import tempfile

import pyarrow as pa
import pyreaddbc
from dbfread import DBF

from sus_sih import config

logger = logging.getLogger(__name__)

COLUNA_INGESTAO = "_ingested_at"
COLUNA_ARQUIVO = "_source_file"
COLUNA_COMPETENCIA = "_competencia"
COLUNAS_AUDITORIA = (COLUNA_INGESTAO, COLUNA_ARQUIVO, COLUNA_COMPETENCIA)


def dbc_para_dbf(origem: str, destino: str) -> str:
    pyreaddbc.dbc2dbf(origem, destino)
    return destino


def _texto(bruto: bytes, encoding: str) -> str | None:
    """Decodifica um campo do DBF preservando o conteudo.

    O DBF preenche os campos com espacos ate a largura declarada, entao o
    strip remove padding de formato, nao informacao. Campo vazio vira nulo.
    """
    valor = bruto.decode(encoding, errors="replace").strip()
    return valor or None


def dbf_para_arrow(caminho: str, encoding: str = config.ENCODING_DBF) -> pa.Table:
    """Le um .dbf com todos os campos como string, na ordem original."""
    leitor = DBF(caminho, raw=True, encoding=encoding, char_decode_errors="replace")
    nomes = [campo.name for campo in leitor.fields]
    colunas: dict[str, list] = {nome: [] for nome in nomes}

    total = 0
    for registro in leitor:
        total += 1
        for nome in nomes:
            colunas[nome].append(_texto(registro[nome], encoding))

    logger.info("lidos %s registros e %s campos de %s", total, len(nomes), caminho)
    return pa.table(
        {nome.lower(): pa.array(colunas[nome], type=pa.string()) for nome in nomes}
    )


def dbc_para_arrow(caminho: str, encoding: str = config.ENCODING_DBF) -> pa.Table:
    with tempfile.TemporaryDirectory() as pasta:
        dbf = os.path.join(pasta, os.path.basename(caminho) + ".dbf")
        dbc_para_dbf(caminho, dbf)
        return dbf_para_arrow(dbf, encoding=encoding)


def adicionar_auditoria(
    tabela: pa.Table,
    nome_arquivo: str,
    competencia: str,
    ingerido_em: dt.datetime | None = None,
) -> pa.Table:
    """Anexa as colunas de auditoria ao final da tabela."""
    ingerido_em = ingerido_em or dt.datetime.now(dt.timezone.utc)
    linhas = tabela.num_rows
    return (
        tabela.append_column(
            COLUNA_INGESTAO,
            pa.array([ingerido_em] * linhas, type=pa.timestamp("us", tz="UTC")),
        )
        .append_column(COLUNA_ARQUIVO, pa.array([nome_arquivo] * linhas, type=pa.string()))
        .append_column(COLUNA_COMPETENCIA, pa.array([competencia] * linhas, type=pa.string()))
    )

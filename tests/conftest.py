import os
import struct
import sys
from ftplib import FTP
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "dags"))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AMOSTRA_DBC = "RDAC2401.dbc"


def escrever_dbf(caminho: Path, campos: list[tuple[str, int]], registros: list[list[str]]) -> Path:
    """Gera um .dbf dBase III minimo, sem depender de rede ou de arquivo binario no repo.

    Todos os campos saem como tipo C, que e como o DATASUS publica a maioria
    dos campos da AIH, e o valor e preenchido com espacos ate a largura.
    """
    tamanho_registro = 1 + sum(largura for _, largura in campos)
    tamanho_cabecalho = 32 + 32 * len(campos) + 1

    cabecalho = struct.pack(
        "<BBBBIHH20x",
        0x03,
        24,
        1,
        1,
        len(registros),
        tamanho_cabecalho,
        tamanho_registro,
    )

    descritores = b""
    for nome, largura in campos:
        descritores += struct.pack(
            "<11sc4xBB14x", nome.encode("ascii").ljust(11, b"\x00"), b"C", largura, 0
        )

    corpo = b""
    for registro in registros:
        corpo += b" "
        for valor, (_, largura) in zip(registro, campos):
            corpo += valor.encode("iso-8859-1").ljust(largura)[:largura]

    caminho.write_bytes(cabecalho + descritores + b"\x0d" + corpo + b"\x1a")
    return caminho


@pytest.fixture
def dbf_sintetico(tmp_path):
    return escrever_dbf(
        tmp_path / "amostra.dbf",
        [("N_AIH", 13), ("UF_ZI", 6), ("VAL_TOT", 10), ("VAZIO", 4)],
        [
            ["1224100061118", "120000", "1234.56", "    "],
            ["1224100061239", "120060", "0.00", "abcd"],
        ],
    )


@pytest.fixture(scope="session")
def dbc_real():
    """Arquivo real de AC/202401, cacheado em tests/fixtures e fora do git."""
    FIXTURES.mkdir(exist_ok=True)
    alvo = FIXTURES / AMOSTRA_DBC
    if not alvo.exists():
        try:
            with FTP("ftp.datasus.gov.br", timeout=120) as ftp:
                ftp.login()
                ftp.cwd("/dissemin/publicos/SIHSUS/200801_/Dados")
                with open(alvo, "wb") as saida:
                    ftp.retrbinary(f"RETR {AMOSTRA_DBC}", saida.write)
        except OSError as erro:
            if alvo.exists():
                os.remove(alvo)
            pytest.skip(f"sem acesso ao FTP do DATASUS: {erro}")
    return alvo

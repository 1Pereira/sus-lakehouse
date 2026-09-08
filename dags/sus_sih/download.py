"""Download dos arquivos de AIH reduzida do DATASUS para o bucket landing.

O DATASUS publica os arquivos em HTTP, HTTPS e FTP, mas de dentro da rede do
compose apenas a porta 21 responde, entao o acesso aqui e sempre por FTP anonimo.
"""

import logging
import os
import tempfile
from ftplib import FTP, error_perm

from sus_sih import config

logger = logging.getLogger(__name__)

TIMEOUT_FTP = 120


class ArquivoIndisponivel(Exception):
    """A competencia pedida nao existe no servidor do DATASUS."""


def validar_uf(uf: str) -> str:
    normalizada = (uf or "").strip().upper()
    if normalizada not in config.UFS:
        raise ValueError(f"UF invalida: {uf!r}")
    return normalizada


def validar_competencia(competencia: str) -> str:
    normalizada = (competencia or "").strip()
    if len(normalizada) != 6 or not normalizada.isdigit():
        raise ValueError(f"competencia deve estar no formato AAAAMM, recebido {competencia!r}")
    if not "01" <= normalizada[4:] <= "12":
        raise ValueError(f"mes invalido na competencia {competencia!r}")
    if normalizada < config.COMPETENCIA_MINIMA:
        raise ValueError(
            f"a serie do SIH comeca em {config.COMPETENCIA_MINIMA}, recebido {competencia!r}"
        )
    return normalizada


def nome_arquivo(uf: str, competencia: str) -> str:
    """Nome do arquivo no DATASUS, no padrao RD<UF><AA><MM>.dbc."""
    uf = validar_uf(uf)
    competencia = validar_competencia(competencia)
    return f"RD{uf}{competencia[2:]}.dbc"


def chave_landing(uf: str, competencia: str) -> str:
    uf = validar_uf(uf)
    competencia = validar_competencia(competencia)
    return (
        f"{config.BUCKET_LANDING}/{config.PREFIXO_LANDING}"
        f"/uf={uf}/competencia={competencia}/{nome_arquivo(uf, competencia)}"
    )


def tamanho_remoto(nome: str) -> int:
    """Bytes do arquivo no servidor do DATASUS."""
    with FTP(config.FTP_HOST, timeout=TIMEOUT_FTP) as ftp:
        ftp.login()
        ftp.cwd(config.FTP_DIR)
        try:
            tamanho = ftp.size(nome)
        except error_perm as erro:
            raise ArquivoIndisponivel(f"{nome} nao esta disponivel no DATASUS") from erro
    if tamanho is None:
        raise ArquivoIndisponivel(f"{nome} nao esta disponivel no DATASUS")
    return tamanho


def baixar_para_arquivo(nome: str, destino: str) -> int:
    """Baixa por FTP em streaming e devolve o numero de bytes gravados."""
    with FTP(config.FTP_HOST, timeout=TIMEOUT_FTP) as ftp:
        ftp.login()
        ftp.cwd(config.FTP_DIR)
        with open(destino, "wb") as saida:
            try:
                ftp.retrbinary(f"RETR {nome}", saida.write)
            except error_perm as erro:
                raise ArquivoIndisponivel(f"{nome} nao esta disponivel no DATASUS") from erro
    return os.path.getsize(destino)


def baixar_para_landing(uf: str, competencia: str, *, forcar: bool = False, fs=None) -> dict:
    """Grava o arquivo bruto no landing sem alterar o conteudo.

    Se o objeto ja existe com o mesmo tamanho do servidor, o download e pulado,
    o que torna a task barata em reprocessamento.
    """
    uf = validar_uf(uf)
    competencia = validar_competencia(competencia)
    nome = nome_arquivo(uf, competencia)
    chave = chave_landing(uf, competencia)
    fs = fs or config.sistema_arquivos()

    esperado = tamanho_remoto(nome)

    if not forcar and fs.exists(chave) and fs.info(chave)["size"] == esperado:
        logger.info("landing ja tem %s com %s bytes, download pulado", chave, esperado)
        return {
            "uri": f"s3://{chave}",
            "nome_arquivo": nome,
            "tamanho": esperado,
            "pulado": True,
        }

    with tempfile.TemporaryDirectory() as pasta:
        local = os.path.join(pasta, nome)
        baixado = baixar_para_arquivo(nome, local)
        if baixado != esperado:
            raise IOError(
                f"download incompleto de {nome}: esperado {esperado} bytes, recebido {baixado}"
            )
        fs.put(local, chave)

    logger.info("gravado %s com %s bytes", chave, esperado)
    return {
        "uri": f"s3://{chave}",
        "nome_arquivo": nome,
        "tamanho": esperado,
        "pulado": False,
    }

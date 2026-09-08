"""Configuracao de ambiente da ingestao do SIH."""

import os

FTP_HOST = "ftp.datasus.gov.br"
FTP_DIR = "/dissemin/publicos/SIHSUS/200801_/Dados"

BUCKET_LANDING = os.environ.get("BUCKET_LANDING", "landing")
PREFIXO_LANDING = "sih/aih_rd"

NAMESPACE_BRONZE = "bronze"
TABELA_BRONZE = "sih_aih"

COMPETENCIA_MINIMA = "200801"

DIR_SQL = os.environ.get("SUS_SQL_DIR", "/opt/airflow/sql")

ENCODING_DBF = "iso-8859-1"

UFS = frozenset(
    """AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN
    RO RR RS SC SE SP TO""".split()
)


def s3_endpoint() -> str:
    return os.environ.get("S3_ENDPOINT", "http://localhost:9000")


def iceberg_rest_uri() -> str:
    return os.environ.get("ICEBERG_REST_URI", "http://localhost:8181")


def sistema_arquivos():
    """Cliente s3fs apontado para o MinIO, com credenciais vindas do ambiente."""
    import s3fs

    return s3fs.S3FileSystem(
        key=os.environ.get("AWS_ACCESS_KEY_ID"),
        secret=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        client_kwargs={"endpoint_url": s3_endpoint()},
    )

"""Ingestao bronze do SIH/SUS por UF e competencia.

Baixa a AIH reduzida do DATASUS para o landing, converte o .dbc e grava na
tabela iceberg.bronze.sih_aih. Rodar a mesma UF e competencia duas vezes
substitui a fatia correspondente em vez de duplicar linhas.
"""

import datetime as dt
import os
import tempfile

from airflow.sdk import Param, dag, get_current_context, task

from sus_sih import config, conversao, ddl, download, escrita


@dag(
    dag_id="ingest_sih_bronze",
    description="Ingestao bronze da AIH reduzida do SIH/SUS por UF e competencia",
    schedule=None,
    catchup=False,
    start_date=dt.datetime(2024, 1, 1),
    max_active_runs=1,
    tags=["bronze", "sih", "datasus"],
    params={
        "uf": Param(
            "AC",
            type="string",
            enum=sorted(config.UFS),
            title="UF",
            description="Unidade da federacao do arquivo de AIH",
        ),
        "competencia": Param(
            "202401",
            type="string",
            pattern=r"^\d{4}(0[1-9]|1[0-2])$",
            title="Competencia",
            description="Competencia no formato AAAAMM, a partir de 200801",
        ),
        "forcar_download": Param(
            False,
            type="boolean",
            title="Forcar download",
            description="Rebaixa do DATASUS mesmo que o landing ja tenha o arquivo",
        ),
    },
)
def ingest_sih_bronze():
    @task
    def garantir_tabela() -> None:
        ddl.garantir_tabela()

    @task
    def baixar() -> dict:
        parametros = get_current_context()["params"]
        return download.baixar_para_landing(
            parametros["uf"],
            parametros["competencia"],
            forcar=parametros["forcar_download"],
        )

    @task
    def converter_e_gravar(info: dict) -> int:
        competencia = get_current_context()["params"]["competencia"]
        fs = config.sistema_arquivos()
        with tempfile.TemporaryDirectory() as pasta:
            local = os.path.join(pasta, info["nome_arquivo"])
            fs.get(info["uri"].removeprefix("s3://"), local)
            tabela = conversao.dbc_para_arrow(local)
        tabela = conversao.adicionar_auditoria(tabela, info["nome_arquivo"], competencia)
        return escrita.gravar(tabela, info["nome_arquivo"])

    garantir_tabela() >> converter_e_gravar(baixar())


ingest_sih_bronze()

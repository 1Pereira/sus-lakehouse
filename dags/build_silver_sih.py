"""Carga da camada silver do SIH por competencia.

Le iceberg.bronze.sih_aih, tipa os campos, deduplica por numero de AIH e
grava em iceberg.silver.sih_aih. Rodar a mesma competencia duas vezes
atualiza as linhas em vez de duplicar.
"""

import datetime as dt

from airflow.sdk import Param, dag, get_current_context, task

from sus_sih import silver


@dag(
    dag_id="build_silver_sih",
    description="Tipagem e deduplicacao da AIH da bronze para a silver",
    schedule=None,
    catchup=False,
    start_date=dt.datetime(2024, 1, 1),
    max_active_runs=1,
    tags=["silver", "sih", "datasus"],
    params={
        "competencia": Param(
            "202401",
            type="string",
            pattern=r"^\d{4}(0[1-9]|1[0-2])$",
            title="Competencia",
            description="Competencia no formato AAAAMM, a partir de 200801",
        ),
    },
)
def build_silver_sih():
    @task
    def garantir_tabela() -> None:
        silver.garantir_tabela()

    @task
    def carregar() -> int:
        competencia = get_current_context()["params"]["competencia"]
        return silver.carregar(competencia)

    garantir_tabela() >> carregar()


build_silver_sih()

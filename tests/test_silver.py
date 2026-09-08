"""Testes da camada silver.

Os testes de unidade rodam offline. Os de integracao exigem o Trino no ar e
sao pulados quando ele nao responde, para que a suite continue util em
maquina sem os containers.
"""

import pytest

from sus_sih import ddl, silver


def test_carga_valida_competencia():
    with pytest.raises(ValueError):
        silver.carregar("2024")
    with pytest.raises(ValueError):
        silver.carregar("202413")


def test_sql_da_carga_usa_parametro_e_nao_interpolacao():
    sql = ddl.ler_sql(silver.CARGA)
    assert "?" in sql, "a competencia deve entrar como parametro do Trino"
    assert "202401" not in sql, "nenhuma competencia pode estar fixa no SQL"


def test_sql_da_carga_deduplica_por_n_aih():
    sql = ddl.ler_sql(silver.CARGA)
    assert "row_number() OVER" in sql
    assert "PARTITION BY n_aih" in sql
    assert "ON destino.n_aih = origem.n_aih" in sql


def test_sql_da_carga_protege_contra_ordem_de_execucao():
    sql = ddl.ler_sql(silver.CARGA)
    assert 'WHEN MATCHED AND origem."_competencia" >= destino."_competencia"' in sql


def test_ddl_da_silver_particiona_por_mes_de_internacao():
    sql = ddl.ler_sql("silver/sih_aih.sql")
    assert "partitioning = ARRAY['month(dt_inter)']" in sql


def test_ddl_da_silver_preserva_codigos_com_zero_a_esquerda():
    sql = ddl.ler_sql("silver/sih_aih.sql")
    for campo in ["proc_rea", "proc_solic", "cep", "espec", "cgc_hosp", "raca_cor", "financ"]:
        assert f"    {campo} varchar" in sql, f"{campo} nao pode virar numero"


def test_ddl_da_silver_tipa_datas_valores_e_contadores():
    sql = ddl.ler_sql("silver/sih_aih.sql")
    for campo in ["dt_inter", "dt_saida", "nasc"]:
        assert f"    {campo} date" in sql
    for campo in ["val_tot", "val_uti", "val_sh"]:
        assert f"    {campo} decimal(12,2)" in sql
    for campo in ["dias_perm", "qt_diarias", "idade"]:
        assert f"    {campo} integer" in sql
    assert "    morte boolean" in sql


@pytest.mark.integracao
def test_carga_e_idempotente(trino_cursor, competencia_carregada):
    trino_cursor.execute("SELECT count(*) FROM iceberg.silver.sih_aih")
    antes = trino_cursor.fetchone()[0]

    silver.carregar(competencia_carregada)

    trino_cursor.execute("SELECT count(*) FROM iceberg.silver.sih_aih")
    assert trino_cursor.fetchone()[0] == antes


@pytest.mark.integracao
def test_silver_nao_tem_aih_repetida(trino_cursor):
    trino_cursor.execute(
        "SELECT count(*), count(DISTINCT n_aih) FROM iceberg.silver.sih_aih"
    )
    linhas, distintas = trino_cursor.fetchone()
    assert linhas == distintas


@pytest.mark.integracao
def test_tipagem_chegou_na_tabela(trino_cursor):
    trino_cursor.execute("""
        SELECT column_name, data_type FROM iceberg.information_schema.columns
        WHERE table_schema = 'silver' AND table_name = 'sih_aih'
          AND column_name IN ('dt_inter','val_tot','dias_perm','morte','proc_rea')
        ORDER BY column_name""")
    assert dict(trino_cursor.fetchall()) == {
        "dt_inter": "date",
        "val_tot": "decimal(12,2)",
        "dias_perm": "integer",
        "morte": "boolean",
        "proc_rea": "varchar",
    }

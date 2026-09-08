import datetime as dt

import pyarrow as pa
import pytest

from sus_sih import conversao, download


def test_dbf_vira_tudo_string(dbf_sintetico):
    tabela = conversao.dbf_para_arrow(str(dbf_sintetico))
    assert all(campo.type == pa.string() for campo in tabela.schema)


def test_nomes_de_campo_viram_minusculo_na_ordem_de_origem(dbf_sintetico):
    tabela = conversao.dbf_para_arrow(str(dbf_sintetico))
    assert tabela.column_names == ["n_aih", "uf_zi", "val_tot", "vazio"]


def test_padding_do_dbf_e_removido_e_campo_vazio_vira_nulo(dbf_sintetico):
    tabela = conversao.dbf_para_arrow(str(dbf_sintetico))
    assert tabela.column("n_aih").to_pylist() == ["1224100061118", "1224100061239"]
    assert tabela.column("val_tot").to_pylist() == ["1234.56", "0.00"]
    assert tabela.column("vazio").to_pylist() == [None, "abcd"]


def test_auditoria_anexa_as_tres_colunas_no_final(dbf_sintetico):
    tabela = conversao.dbf_para_arrow(str(dbf_sintetico))
    momento = dt.datetime(2024, 3, 1, 12, 0, tzinfo=dt.timezone.utc)
    com_auditoria = conversao.adicionar_auditoria(tabela, "RDAC2401.dbc", "202401", momento)

    assert com_auditoria.column_names[-3:] == list(conversao.COLUNAS_AUDITORIA)
    assert com_auditoria.num_rows == tabela.num_rows
    assert com_auditoria.column("_source_file").to_pylist() == ["RDAC2401.dbc"] * 2
    assert com_auditoria.column("_competencia").to_pylist() == ["202401"] * 2
    assert com_auditoria.column("_ingested_at").to_pylist() == [momento] * 2


def test_auditoria_nao_altera_campos_de_origem(dbf_sintetico):
    tabela = conversao.dbf_para_arrow(str(dbf_sintetico))
    com_auditoria = conversao.adicionar_auditoria(tabela, "RDAC2401.dbc", "202401")
    for coluna in tabela.column_names:
        assert com_auditoria.column(coluna).to_pylist() == tabela.column(coluna).to_pylist()


def test_ingested_at_e_timestamp_com_fuso(dbf_sintetico):
    tabela = conversao.dbf_para_arrow(str(dbf_sintetico))
    com_auditoria = conversao.adicionar_auditoria(tabela, "RDAC2401.dbc", "202401")
    assert com_auditoria.schema.field("_ingested_at").type == pa.timestamp("us", tz="UTC")


def test_dbc_real_do_datasus_e_descomprimido_e_lido(dbc_real):
    tabela = conversao.dbc_para_arrow(str(dbc_real))
    assert tabela.num_rows > 0
    assert {"n_aih", "uf_zi", "dt_inter", "dt_saida"} <= set(tabela.column_names)
    assert all(campo.type == pa.string() for campo in tabela.schema)


def test_dbc_real_preserva_datas_como_texto_de_origem(dbc_real):
    tabela = conversao.dbc_para_arrow(str(dbc_real))
    datas = [d for d in tabela.column("dt_inter").to_pylist() if d]
    assert datas, "esperado ao menos uma data de internacao preenchida"
    assert all(len(d) == 8 and d.isdigit() for d in datas[:100])


@pytest.mark.parametrize(
    "uf,competencia,esperado",
    [("AC", "202401", "RDAC2401.dbc"), ("sp", "201312", "RDSP1312.dbc")],
)
def test_nome_do_arquivo_segue_o_padrao_do_datasus(uf, competencia, esperado):
    assert download.nome_arquivo(uf, competencia) == esperado


@pytest.mark.parametrize(
    "uf,competencia",
    [("XX", "202401"), ("AC", "2024"), ("AC", "202413"), ("AC", "200712"), ("AC", "abcdef")],
)
def test_parametros_invalidos_sao_rejeitados(uf, competencia):
    with pytest.raises(ValueError):
        download.nome_arquivo(uf, competencia)

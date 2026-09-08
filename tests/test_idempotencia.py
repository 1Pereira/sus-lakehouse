import pyarrow as pa
import pytest
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.transforms import IdentityTransform

from sus_sih import conversao, escrita

NAMESPACE = "bronze"
TABELA = "sih_aih"


def _amostra(dbf, nome_arquivo, competencia="202401"):
    return conversao.adicionar_auditoria(
        conversao.dbf_para_arrow(str(dbf)), nome_arquivo, competencia
    )


@pytest.fixture
def catalogo(tmp_path, dbf_sintetico, monkeypatch):
    """Catalogo Iceberg local, espelhando o particionamento do DDL de producao."""
    armazem = tmp_path / "warehouse"
    armazem.mkdir()
    catalogo = SqlCatalog(
        "teste",
        **{
            "uri": f"sqlite:///{tmp_path / 'catalogo.db'}",
            "warehouse": f"file://{armazem.as_posix()}",
        },
    )
    catalogo.create_namespace(NAMESPACE)
    tabela = catalogo.create_table(
        (NAMESPACE, TABELA), schema=_amostra(dbf_sintetico, "seed.dbc").schema
    )
    with tabela.update_spec() as spec:
        spec.add_field(conversao.COLUNA_COMPETENCIA, IdentityTransform())
    monkeypatch.setattr(escrita, "IDENTIFICADOR", (NAMESPACE, TABELA))
    return catalogo


def _linhas(catalogo):
    return catalogo.load_table((NAMESPACE, TABELA)).scan().to_arrow().num_rows


def _por_arquivo(catalogo, nome):
    tabela = catalogo.load_table((NAMESPACE, TABELA)).scan().to_arrow()
    return tabela.filter(pa.compute.equal(tabela.column("_source_file"), nome))


def test_reingestao_da_mesma_competencia_nao_duplica(catalogo, dbf_sintetico):
    lote = _amostra(dbf_sintetico, "RDAC2401.dbc")

    escrita.gravar(lote, "RDAC2401.dbc", catalogo=catalogo)
    depois_da_primeira = _linhas(catalogo)
    escrita.gravar(lote, "RDAC2401.dbc", catalogo=catalogo)

    assert depois_da_primeira == lote.num_rows
    assert _linhas(catalogo) == lote.num_rows


def test_reingestao_substitui_a_fatia_em_vez_de_acumular(catalogo, dbf_sintetico):
    escrita.gravar(_amostra(dbf_sintetico, "RDAC2401.dbc"), "RDAC2401.dbc", catalogo=catalogo)
    primeira = _por_arquivo(catalogo, "RDAC2401.dbc").column("_ingested_at").to_pylist()

    escrita.gravar(_amostra(dbf_sintetico, "RDAC2401.dbc"), "RDAC2401.dbc", catalogo=catalogo)
    segunda = _por_arquivo(catalogo, "RDAC2401.dbc").column("_ingested_at").to_pylist()

    assert len(set(segunda)) == 1
    assert set(segunda) != set(primeira)


def test_reprocessar_uma_uf_nao_apaga_as_outras_da_competencia(catalogo, dbf_sintetico):
    escrita.gravar(_amostra(dbf_sintetico, "RDAC2401.dbc"), "RDAC2401.dbc", catalogo=catalogo)
    escrita.gravar(_amostra(dbf_sintetico, "RDRR2401.dbc"), "RDRR2401.dbc", catalogo=catalogo)
    total = _linhas(catalogo)

    escrita.gravar(_amostra(dbf_sintetico, "RDAC2401.dbc"), "RDAC2401.dbc", catalogo=catalogo)

    assert _linhas(catalogo) == total
    assert _por_arquivo(catalogo, "RDRR2401.dbc").num_rows > 0


def test_competencias_diferentes_convivem(catalogo, dbf_sintetico):
    escrita.gravar(_amostra(dbf_sintetico, "RDAC2401.dbc"), "RDAC2401.dbc", catalogo=catalogo)
    lote = _amostra(dbf_sintetico, "RDAC2402.dbc", competencia="202402")
    escrita.gravar(lote, "RDAC2402.dbc", catalogo=catalogo)

    assert _linhas(catalogo) == lote.num_rows * 2


def test_campo_ausente_na_competencia_antiga_e_preenchido_com_nulo(catalogo, dbf_sintetico):
    lote = _amostra(dbf_sintetico, "RDAC2401.dbc")
    sem_coluna = lote.drop_columns(["val_tot"])

    escrita.gravar(sem_coluna, "RDAC2401.dbc", catalogo=catalogo)

    gravado = _por_arquivo(catalogo, "RDAC2401.dbc")
    assert "val_tot" in gravado.column_names
    assert gravado.column("val_tot").to_pylist() == [None] * lote.num_rows


def test_campo_novo_entra_por_evolucao_de_schema(catalogo, dbf_sintetico):
    lote = _amostra(dbf_sintetico, "RDAC2401.dbc")
    com_novo = lote.append_column(
        "campo_novo", pa.array(["x"] * lote.num_rows, type=pa.string())
    )

    escrita.gravar(com_novo, "RDAC2401.dbc", catalogo=catalogo)

    gravado = _por_arquivo(catalogo, "RDAC2401.dbc")
    assert gravado.column("campo_novo").to_pylist() == ["x"] * lote.num_rows

# sus-lakehouse

Lakehouse de internações hospitalares do SUS com arquitetura de medalhão, orquestração em Airflow, armazenamento em Apache Iceberg sobre MinIO e consulta federada via Trino.

## Fontes

| Fonte | Origem | Papel |
|---|---|---|
| SIH/SUS | DATASUS, arquivos de AIH | Fato principal de internações |
| CNES | DATASUS, cadastro de estabelecimentos | Dimensão de unidades e leitos |
| Postgres OLTP | Banco local com dados sintéticos | Fonte relacional para consulta federada |

## Camadas

* **Bronze**: ingestão bruta com colunas de auditoria, sem transformação de negócio.
* **Silver**: tipagem, deduplicação por chave de AIH e conformidade de dimensões.
* **Gold**: agregados por competência, município e especialidade, mais a tabela de features.

## Subindo o ambiente

Crie o ambiente virtual e instale as dependências de desenvolvimento:

```bash
py -3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

O Python precisa ser 3.13, mesma versao da imagem do Airflow. O `pyreaddbc`,
que descomprime os arquivos `.dbc` do DATASUS, publica wheel ate cp313, e em
3.14 o pip cai para compilacao de fonte.

No Windows o comando de ativação é `.venv\Scripts\activate`.

Copie o arquivo de variáveis e gere as duas chaves do Airflow:

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
openssl rand -hex 32
```

Preencha `AIRFLOW_FERNET_KEY` com a saída do primeiro comando e `AIRFLOW_JWT_SECRET` com a do segundo, depois:

```bash
make up
```

| Serviço | URL |
|---|---|
| Airflow | http://localhost:8082 |
| Trino | http://localhost:8081 |
| MinIO Console | http://localhost:9001 |
| Postgres OLTP | localhost:5433 |

No primeiro start o Airflow gera a senha do usuário admin no arquivo `simple_auth_manager_passwords.json.generated` dentro do container do api-server:

```bash
docker compose exec airflow-apiserver cat simple_auth_manager_passwords.json.generated
```

## Validando

```bash
docker compose exec trino trino --execute "SHOW CATALOGS"
docker compose exec trino trino --execute "SELECT count(*) FROM postgresql.public.agendamento"
```

## Ingestão bronze do SIH

A DAG `ingest_sih_bronze` baixa a AIH reduzida do DATASUS por UF e competência,
grava o arquivo bruto no bucket `landing` e carrega `iceberg.bronze.sih_aih`.

Dispare pela interface do Airflow preenchendo os parâmetros `uf` e
`competencia`, ou pela linha de comando:

```bash
docker compose exec airflow-scheduler   airflow dags test ingest_sih_bronze   --conf '{"uf":"AC","competencia":"202401"}'
```

Rodar a mesma UF e competência de novo substitui a fatia correspondente em vez
de duplicar linhas. O acesso ao DATASUS é por FTP, já que as portas 80 e 443 de
`ftp.datasus.gov.br` não respondem de dentro da rede do compose.

Testes:

```bash
.venv/Scripts/python.exe -m pytest tests -q
```

Os testes marcados com `integracao` exigem os containers no ar e sao pulados
automaticamente quando o Trino nao responde.

## Camada silver do SIH

A DAG `build_silver_sih` le a bronze, tipa os campos e deduplica por numero de
AIH, gravando em `iceberg.silver.sih_aih`.

```bash
docker compose exec airflow-scheduler   airflow dags test build_silver_sih --conf '{"competencia":"202401"}'
```

Dos 113 campos de origem, 19 viram `decimal(12,2)`, 15 viram `integer`, 3 viram
`date` e `morte` vira `boolean`. Os outros 75 seguem `varchar`, incluindo os 29
que tem valores comecando em zero, como `proc_rea` e `cep`, onde o zero a
esquerda e informacao.

A tabela e particionada por `month(dt_inter)` e nao por competencia. Competencia
e o mes de faturamento, e a fatura de janeiro traz internacoes de meses
anteriores, entao analise de ocupacao filtra por data de internacao.

A carga usa `MERGE INTO` por `n_aih`, entao rodar a mesma competencia duas vezes
atualiza as linhas em vez de duplicar, e carregar uma competencia antiga depois
de uma recente nao sobrescreve a versao mais nova.

## Fluxo de trabalho

Uma branch por entrega, commits pequenos e descritivos, merge via pull request.

```bash
git switch -c feat/nome-da-entrega
git commit -m "feat: descricao curta"
git push -u origin feat/nome-da-entrega
```

## Desenvolvimento local

O projeto abre como Dev Container no VS Code com as extensões já configuradas e as dependências instaladas no `postCreateCommand`. Nesse caso o ambiente virtual do passo anterior não é necessário, o container já isola tudo.

Com o `.venv` ativo, aponte o interpretador do VS Code para ele em `Python: Select Interpreter`.

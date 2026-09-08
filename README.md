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
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

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
| Airflow | http://localhost:8080 |
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

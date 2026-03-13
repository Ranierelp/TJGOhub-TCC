# TJGO Playwright Hub — Backend

Sistema interno para centralização e gestão de resultados de testes automatizados E2E (Playwright) do Tribunal de Justiça do Estado de Goiás (TJGO).

---

## Sobre o Projeto

O **TJGO Playwright Hub** é uma plataforma desenvolvida em Django para receber, armazenar e visualizar resultados de testes automatizados end-to-end (E2E) executados com Playwright. O sistema funciona como um hub central de qualidade de software, oferecendo:

- **Centralização de resultados**: Recebimento de relatórios via upload de JSON (Playwright Hub Reporter)
- **Armazenamento de evidências**: Screenshots, vídeos, traces e logs de execução
- **Histórico por projeto e ambiente**: Rastreamento de execuções ao longo do tempo
- **Análise de instabilidade (Flakiness)**: Identificação e marcação de testes instáveis
- **Visão de falhas recorrentes**: Filtros e métricas por status

### Contexto

Este projeto foi desenvolvido como Trabalho de Conclusão de Curso (TCC), com escopo de MVP viável para implementação por um único desenvolvedor. O sistema foi arquitetado para funcionar em **modo de upload manual/API de relatórios**, com caminho claro para evolução futura via integração com GitLab CI quando houver Runner disponível na infraestrutura.

---

## Funcionalidades

### MVP

- [x] CRUD de casos de teste
- [x] Upload de relatórios JSON via API (`POST /runs/upload-report/`)
- [x] Armazenamento de evidências (screenshots, vídeos, traces) — modelo `Artifact`
- [x] Dashboard de visualização de resultados — consumido pelo frontend Next.js
- [x] Histórico de execuções por projeto e ambiente
- [x] Filtros por ambiente, status, branch e projeto
- [x] Identificação de testes com falhas recorrentes (`failed_tests` agregado por run)
- [x] Detecção de flakiness — status `FLAKY`, campo `flaky_tests`, ação `mark-as-flaky`
- [x] Autenticação e controle de acesso (JWT)
- [x] API REST com documentação OpenAPI (Swagger + ReDoc)

### Evolução Futura

- [ ] Integração automática com GitLab CI/CD (runner)
- [ ] Webhooks para notificação de falhas
- [ ] Relatórios exportáveis (PDF, Excel)
- [ ] Comparação entre execuções
- [ ] Métricas de cobertura de testes
- [ ] Integração com sistemas de gestão de defeitos

---

## Stack Tecnológica

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| Python | 3.11+ | Linguagem principal |
| Django | 5.0 | Framework web |
| Django REST Framework | 3.16 | API REST |
| drf-spectacular | 0.29 | OpenAPI / Swagger / ReDoc |
| SimpleJWT | 5.5 | Autenticação JWT |
| PostgreSQL | 15+ | Banco de dados |
| Docker | 24+ | Containerização |
| Docker Compose | 2.x | Orquestração local |
| django-storages + boto3 | - | Storage S3 para artefatos |
| django-admin-interface | 0.32 | Admin customizado |

---

## Estrutura de Apps

```
apps/
├── users/          # Usuários (email-based, sem campo username)
├── projects/       # Projetos — agrupam ambientes, casos e execuções
├── cases/          # Casos de teste documentados (vinculáveis a resultados)
├── environments/   # Ambientes por projeto (dev, staging, produção)
├── runs/           # Execuções de teste — agrega métricas dos resultados
├── results/        # Resultados individuais — read-only via API, criados pelo parser
├── artifacts/      # Evidências: screenshots, vídeos, traces, logs
├── tags/           # Tags coloridas globais para categorizar execuções
├── metrics/        # Placeholder para futuras métricas agregadas
├── commons/        # BaseModel com soft delete + rastreabilidade completa
└── honeypot/       # Segurança anti-bot: rastreia tentativas de login suspeitas
```

### Conceitos do `commons`

**Soft Delete** — registros não são removidos fisicamente:
```python
objeto.delete()       # soft delete (marca como inativo)
objeto.hard_delete()  # remoção permanente
Model.objects.all()       # só ativos (padrão)
Model.all_objects.all()   # todos, incluindo inativos
```

**Rastreabilidade** — todos os models registram automaticamente:
`created_at`, `created_by`, `updated_at`, `updated_by`, `deleted_at`, `deleted_by`

---

## Endpoints da API

Base URL: `/api/v1/`

### Autenticação e Usuários

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/user/token/` | Login — retorna `access` + `refresh` JWT |
| POST | `/user/token/refresh/` | Renova o access token |
| POST | `/user/register/` | Cadastra novo usuário |
| POST | `/user/request-password-reset/` | Solicita reset de senha |
| POST | `/user/password-reset/` | Confirma reset de senha |
| GET/PUT | `/user/user/` | Perfil do usuário autenticado |

### Projetos

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET/POST | `/projects/` | Lista / cria projetos |
| GET/PUT/DELETE | `/projects/{id}/` | Detalha / edita / arquiva projeto |

### Ambientes

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET/POST | `/environments/` | Lista / cria ambientes |
| GET/PUT/DELETE | `/environments/{id}/` | Detalha / edita / arquiva ambiente |

### Casos de Teste

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET/POST | `/test-cases/` | Lista / cria casos |
| GET/PUT/DELETE | `/test-cases/{id}/` | Detalha / edita / arquiva caso |
| POST | `/test-cases/{id}/change-status/` | Altera status do caso |

### Execuções (Runs)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET/POST | `/runs/` | Lista / cria execuções |
| GET/PUT/DELETE | `/runs/{id}/` | Detalha / edita / arquiva execução |
| POST | `/runs/{id}/start/` | PENDING → RUNNING |
| POST | `/runs/{id}/complete/` | RUNNING → COMPLETED (recalcula métricas) |
| POST | `/runs/{id}/fail/` | Marca como FAILED |
| POST | `/runs/{id}/cancel/` | Cancela a execução |
| POST | `/runs/{id}/recalculate-metrics/` | Força recálculo das métricas |
| GET | `/runs/by-project/{project_id}/` | Execuções de um projeto |
| GET | `/runs/by-environment/{env_id}/` | Execuções de um ambiente |
| GET | `/runs/{id}/results/` | Resultados da execução (paginado, `?status=PASSED\|FAILED\|SKIPPED\|FLAKY`) |
| POST | `/runs/upload-report/` | **Upload atômico** de relatório JSON — cria TestRun + TestResults |

### Resultados (read-only, criados pelo parser)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/results/` | Lista resultados (com filtros) |
| GET | `/results/{id}/` | Detalha resultado (com error_message + stack_trace) |
| POST | `/results/{id}/mark-as-flaky/` | Marca como FLAKY e recalcula métricas da run pai |
| GET | `/results/{id}/artifacts/` | Lista artefatos deste resultado |

### Tags

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET/POST | `/tags/` | Lista / cria tags |
| GET/PUT/DELETE | `/tags/{id}/` | Detalha / edita / remove tag |

### Utilitários

| Endpoint | Descrição |
|----------|-----------|
| `GET /health/` | Health check |
| `GET /api/schema/` | Schema OpenAPI (JSON/YAML) |
| `GET /api/docs/swagger/` | Swagger UI interativo |
| `GET /api/docs/redoc/` | ReDoc |

---

## Requisitos

### Para Desenvolvimento (Docker)

- [Docker Engine](https://docs.docker.com/get-docker/) 24.0+
- [Docker Compose](https://docs.docker.com/compose/install/) 2.0+
- [GNU Make](https://www.gnu.org/software/make/) (opcional, mas recomendado)
- [Git](https://git-scm.com/)

### Sem Docker

- Python 3.11+
- PostgreSQL 15+

---

## Instalação e Configuração

### 1. Clone o Repositório

```bash
git clone <url-do-repositorio>
cd tjgo-playwright-hub
```

### 2. Configure as Variáveis de Ambiente

```bash
cp .envs/.local/.django.example .envs/.local/.django
cp .envs/.local/.postgres.example .envs/.local/.postgres
```

### 3. Inicie os Containers

```bash
make build
make up
# ou sem Make:
docker-compose build && docker-compose up -d
```

### 4. Crie um Superusuário

```bash
make createsuperuser
# ou:
docker-compose exec api python manage.py createsuperuser
```

### 5. Acesse o Sistema

| Serviço | URL |
|---------|-----|
| Admin Django | http://localhost:8000/admin/ |
| Swagger UI | http://localhost:8000/api/docs/swagger/ |
| ReDoc | http://localhost:8000/api/docs/redoc/ |
| Schema OpenAPI | http://localhost:8000/api/schema/ |

**Credenciais padrão de desenvolvimento:**
- Email: `admin@exemple.com.br`
- Senha: `admin@123`

> **Importante:** Altere as credenciais em ambiente de produção!

---

## Comandos Úteis (Makefile)

```bash
# Containers
make build          # Constrói as imagens Docker
make up             # Inicia todos os serviços
make down           # Para todos os serviços
make restart        # Reinicia os serviços
make logs           # Logs em tempo real (todos)
make logs-api       # Logs só da API Django
make status         # Status dos containers

# Banco de Dados
make migrate        # Executa migrações
make makemigrations # Cria novas migrações
make setup-database # Cria schema + migra

# Desenvolvimento
make shell          # Shell do container Django
make dbshell        # Shell do PostgreSQL
make collectstatic  # Coleta arquivos estáticos
make createsuperuser

# Qualidade de Código
make test           # Executa os testes
make test-coverage  # Testes com cobertura
make ruff           # Lint + fix (ruff)
make ruff-check     # Lint check only
make quality-check  # Todos os checks de qualidade
```

---

## Padrão de Desenvolvimento

### Criar novo app

```bash
docker-compose exec api python manage.py startapp nome_do_app apps/nome_do_app
```

### Modelo (herdar de BaseModel)

```python
from apps.commons.models import BaseModel

class MeuModel(BaseModel):
    class Meta(BaseModel.Meta):
        verbose_name = "Meu Model"
        verbose_name_plural = "Meus Models"

    nome = models.CharField(max_length=255)
```

### ViewSet (herdar de BaseViewSet)

```python
from apps.commons.api.v1.viewsets import BaseViewSet

class MeuModelViewSet(BaseViewSet):
    queryset = MeuModel.objects.all()
    serializer_class = MeuModelSerializer
```

---

## Deploy em Produção

### Variáveis de Ambiente Obrigatórias

```bash
DJANGO_SECRET_KEY=sua-chave-secreta-muito-longa-e-aleatoria
DJANGO_ALLOWED_HOSTS=seu-dominio.tjgo.jus.br
DJANGO_SETTINGS_MODULE=tjgohub.settings.production

POSTGRES_HOST=seu-host-postgres
POSTGRES_DB=tjgohub_prod
POSTGRES_USER=tjgohub_user
POSTGRES_PASSWORD=senha-muito-forte
```

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Roadmap

### Fase 1 — MVP
- [x] Estrutura base do projeto Django
- [x] Autenticação JWT
- [x] BaseModel com soft delete e rastreabilidade
- [x] CRUD de projetos, ambientes, casos de teste
- [x] Upload de relatório JSON (`upload-report`)
- [x] Armazenamento de evidências (Artifact model)
- [x] Dashboard de resultados (consumido pelo frontend)
- [x] Detecção e marcação de flakiness

### Fase 2 — Análise
- [ ] Relatório de falhas recorrentes (ranking de testes mais instáveis)
- [ ] Filtros avançados e exportação

### Fase 3 — Integração
- [ ] API para GitLab CI (runner automático)
- [ ] Webhooks de notificação de falhas
- [ ] Integração com sistemas TJGO

---

## Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<p align="center">Desenvolvido como TCC para o TJGO</p>

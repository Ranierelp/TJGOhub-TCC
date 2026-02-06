# TJGO Playwright Hub

Sistema interno para centralização e gestão de resultados de testes automatizados E2E (Playwright) do Tribunal de Justiça do Estado de Goiás (TJGO).

---

## Sobre o Projeto

O **TJGO Playwright Hub** é uma plataforma desenvolvida em Django para receber, armazenar e visualizar resultados de testes automatizados end-to-end (E2E) executados com Playwright. O sistema foi projetado para funcionar como um hub central de qualidade de software, oferecendo:

- **Centralização de resultados**: Recebimento de relatórios em formato JUnit XML
- **Armazenamento de evidências**: Screenshots, vídeos e traces de execução
- **Histórico por projeto e ambiente**: Rastreamento de execuções ao longo do tempo
- **Análise de instabilidade (Flakiness)**: Identificação de testes instáveis
- **Visão de falhas recorrentes**: Dashboard com padrões de falhas

### Contexto

Este projeto foi desenvolvido como Trabalho de Conclusão de Curso (TCC), com escopo de MVP viável para implementação por um único desenvolvedor. O sistema foi arquitetado para funcionar em **modo de upload manual** de relatórios, com caminho claro para evolução futura via integração com GitLab CI quando houver Runner disponível na infraestrutura.

---

## Funcionalidades

### MVP (Escopo Inicial)

- [ ] Upload manual de relatórios JUnit XML
- [ ] Armazenamento de evidências (screenshots, vídeos, traces do Playwright)
- [ ] Dashboard de visualização de resultados
- [ ] Histórico de execuções por projeto
- [ ] Filtros por ambiente (desenvolvimento, homologação, produção)
- [ ] Identificação de testes com falhas recorrentes
- [ ] Detecção de flakiness (testes instáveis)
- [ ] Autenticação e controle de acesso (JWT)
- [ ] API REST para integração

### Evolução Futura

- [ ] Integração automática com GitLab CI/CD
- [ ] Webhooks para notificação de falhas
- [ ] Relatórios exportáveis (PDF, Excel)
- [ ] Comparação entre execuções
- [ ] Métricas de cobertura de testes
- [ ] Integração com sistemas de gestão de defeitos

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TJGO Playwright Hub                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │   Frontend   │    │   API REST   │    │   Processamento de   │  │
│  │   (Admin)    │◄──►│   (DRF)      │◄──►│   Relatórios XML     │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│                             │                       │               │
│                             ▼                       ▼               │
│                      ┌──────────────┐    ┌──────────────────────┐  │
│                      │  PostgreSQL  │    │   Storage            │  │
│                      │  (Dados)     │    │   (Evidências)       │  │
│                      └──────────────┘    └──────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Fluxo de Dados:
1. Upload de relatório JUnit XML (manual ou via API)
2. Parser processa o XML e extrai resultados
3. Evidências são armazenadas no storage
4. Dados são persistidos no PostgreSQL
5. Dashboard exibe resultados e métricas
```

---

## Stack Tecnológica

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| Python | 3.11+ | Linguagem principal |
| Django | 5.x | Framework web |
| Django REST Framework | 3.x | API REST |
| PostgreSQL | 15+ | Banco de dados |
| Docker | 24+ | Containerização |
| Docker Compose | 2.x | Orquestração local |
| Celery | 5.x | Tarefas assíncronas |
| Redis | 7.x | Broker/Cache |
| JWT (Simple JWT) | - | Autenticação |

---

## Estrutura do Projeto

```
tjgo-playwright-hub/
│
├── apps/                           # Aplicações Django
│   ├── commons/                    # Modelos e utilitários base
│   │   ├── models.py               # BaseModel com soft delete
│   │   ├── admin.py                # Admin base customizado
│   │   └── api/v1/                 # Endpoints comuns
│   │
│   ├── core/                       # Núcleo do sistema
│   │   ├── models.py               # Modelos de exemplo
│   │   └── api/v1/                 # Endpoints core
│   │
│   ├── users/                      # Gestão de usuários
│   │   ├── models.py               # Modelo de usuário customizado
│   │   └── api/v1/                 # Endpoints de autenticação
│   │
│   └── honeypot/                   # Segurança anti-bot
│
├── tjgohub/                        # Configurações do projeto
│   ├── settings/                   # Configurações por ambiente
│   │   ├── base.py                 # Configurações base
│   │   ├── local.py                # Desenvolvimento
│   │   └── production.py           # Produção
│   ├── router/                     # Roteamento de APIs
│   ├── urls.py                     # URLs principais
│   ├── celery.py                   # Configuração Celery
│   └── storage_backends.py         # Storage customizado
│
├── docker/                         # Configurações Docker
│   ├── local/                      # Ambiente de desenvolvimento
│   │   ├── django/                 # Dockerfile Django
│   │   └── postgres/               # Dockerfile PostgreSQL
│   └── production/                 # Ambiente de produção
│       ├── django/                 # Dockerfile Django prod
│       ├── nginx/                  # Configurações Nginx
│       └── redis/                  # Configurações Redis
│
├── requirements/                   # Dependências Python
│   ├── base.txt                    # Dependências base
│   ├── local.txt                   # Dependências desenvolvimento
│   └── production.txt              # Dependências produção
│
├── .envs/                          # Variáveis de ambiente
│   ├── .local/                     # Variáveis locais
│   └── .production/                # Variáveis produção
│
├── diagramas/                      # Diagramas do projeto
├── tools/                          # Scripts utilitários
├── docker-compose.yml              # Compose desenvolvimento
├── docker-compose.prod.yml         # Compose produção
├── Makefile                        # Comandos úteis
├── manage.py                       # CLI Django
└── README.md                       # Este arquivo
```

---

## Requisitos

### Para Desenvolvimento

- [Docker Engine](https://docs.docker.com/get-docker/) (24.0+)
- [Docker Compose](https://docs.docker.com/compose/install/) (2.0+)
- [GNU Make](https://www.gnu.org/software/make/) (opcional, mas recomendado)
- [Git](https://git-scm.com/)

### Para Execução sem Docker

- Python 3.11+
- PostgreSQL 15+
- Redis 7+

---

## Instalação e Configuração

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/tjgo-playwright-hub.git
cd tjgo-playwright-hub
```

### 2. Configure as Variáveis de Ambiente

Copie os arquivos de exemplo e ajuste conforme necessário:

```bash
# Crie o arquivo .env na raiz (se não existir)
cp .envs/.local/.django.example .envs/.local/.django
cp .envs/.local/.postgres.example .envs/.local/.postgres
```

### 3. Inicie os Containers

```bash
# Construa as imagens
make build

# Inicie os serviços
make up
```

Ou sem Make:

```bash
docker-compose build
docker-compose up -d
```

### 4. Crie um Superusuário (Primeiro Acesso)

```bash
make createsuperuser
```

Ou:

```bash
docker-compose exec api python manage.py createsuperuser
```

### 5. Acesse o Sistema

| Serviço | URL | Descrição |
|---------|-----|-----------|
| Admin Django | http://localhost:8000/admin/ | Painel administrativo |
| API Docs (Swagger) | http://localhost:8000/api/schema/ | Documentação interativa |
| API Docs (CoreAPI) | http://localhost:8000/api/docs/ | Documentação alternativa |

**Credenciais padrão de desenvolvimento:**
- Email: `admin@exemple.com.br`
- Senha: `admin@123`

> **Importante:** Altere as credenciais em ambiente de produção!

---

## Comandos Úteis (Makefile)

```bash
# Gerenciamento de Containers
make build          # Constrói as imagens Docker
make up             # Inicia todos os serviços
make down           # Para todos os serviços
make restart        # Reinicia os serviços
make logs           # Exibe logs em tempo real

# Desenvolvimento
make shell          # Acessa o shell do container Django
make dbshell        # Acessa o shell do PostgreSQL
make migrate        # Executa migrações do banco
make makemigrations # Cria novas migrações
make collectstatic  # Coleta arquivos estáticos

# Testes e Qualidade
make test           # Executa os testes
make lint           # Verifica estilo de código
make format         # Formata o código

# Utilitários
make createsuperuser # Cria um superusuário
make flush           # Limpa o banco de dados
```

---

## API REST

A API REST permite integração programática com o sistema. Todos os endpoints requerem autenticação JWT.

### Autenticação

```bash
# Obter token de acesso
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "seu@email.com", "password": "sua_senha"}'

# Resposta
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}

# Usar o token nas requisições
curl -X GET http://localhost:8000/api/v1/endpoint/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

### Endpoints Principais (Planejados)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/v1/reports/upload/` | Upload de relatório JUnit XML |
| GET | `/api/v1/reports/` | Lista relatórios |
| GET | `/api/v1/reports/{id}/` | Detalhes de um relatório |
| GET | `/api/v1/projects/` | Lista projetos |
| GET | `/api/v1/test-cases/` | Lista casos de teste |
| GET | `/api/v1/test-cases/{id}/history/` | Histórico de um teste |
| GET | `/api/v1/metrics/flakiness/` | Métricas de flakiness |

### Coleção Postman

Uma coleção Postman está disponível para facilitar os testes da API:

```bash
# Importe o arquivo no Postman
postman_collection.json
```

---

## Conceitos Importantes

### Soft Delete

Todos os modelos do sistema implementam **soft delete**, ou seja, registros não são removidos fisicamente do banco de dados. Em vez disso, são marcados como inativos:

```python
# Soft delete (marca como inativo)
objeto.delete()

# Hard delete (remoção permanente - use com cuidado!)
objeto.hard_delete()

# Consultar apenas ativos (padrão)
Model.objects.all()

# Consultar todos (incluindo inativos)
Model.all_objects.all()
```

### Rastreabilidade

Todos os modelos registram automaticamente:
- `created_at` / `created_by`: Data e usuário de criação
- `updated_at` / `updated_by`: Data e usuário da última atualização
- `deleted_at` / `deleted_by`: Data e usuário da remoção (soft delete)

### Flakiness (Testes Instáveis)

O sistema identifica testes "flaky" - aqueles que alternam entre sucesso e falha sem alterações no código. A detecção é baseada em:

- Taxa de falha em um período
- Alternância de status entre execuções consecutivas
- Padrões de falha não-determinísticos

---

## Desenvolvimento

### Estrutura de Apps

Cada nova funcionalidade deve ser criada como um app Django separado:

```bash
# Criar novo app
docker-compose exec api python manage.py startapp nome_do_app apps/nome_do_app
```

### Padrão de Models

Todos os models devem herdar de `BaseModel`:

```python
from apps.commons.models import BaseModel

class MeuModel(BaseModel):
    class Meta(BaseModel.Meta):
        verbose_name = "Meu Model"
        verbose_name_plural = "Meus Models"

    # seus campos aqui
    nome = models.CharField(max_length=255)
```

### Padrão de APIs

Utilize os serializers e viewsets base:

```python
# serializers.py
from apps.commons.api.v1.serializers import BaseSerializer

class MeuModelSerializer(BaseSerializer):
    class Meta:
        model = MeuModel
        fields = '__all__'

# viewsets.py
from apps.commons.api.v1.viewsets import BaseViewSet

class MeuModelViewSet(BaseViewSet):
    queryset = MeuModel.objects.all()
    serializer_class = MeuModelSerializer
```

---

## Deploy em Produção

### Variáveis de Ambiente Obrigatórias

```bash
# Django
DJANGO_SECRET_KEY=sua-chave-secreta-muito-longa-e-aleatoria
DJANGO_ALLOWED_HOSTS=seu-dominio.tjgo.jus.br
DJANGO_SETTINGS_MODULE=tjgohub.settings.production

# Banco de Dados
POSTGRES_HOST=seu-host-postgres
POSTGRES_DB=tjgohub_prod
POSTGRES_USER=tjgohub_user
POSTGRES_PASSWORD=senha-muito-forte

# Redis
REDIS_URL=redis://seu-host-redis:6379/0
```

### Executar em Produção

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Roadmap

### Fase 1 - MVP (Em Desenvolvimento)
- [x] Estrutura base do projeto Django
- [x] Autenticação JWT
- [x] Models base com soft delete
- [ ] Parser de relatórios JUnit XML
- [ ] Upload e armazenamento de evidências
- [ ] Dashboard básico de resultados

### Fase 2 - Análise
- [ ] Detecção de flakiness
- [ ] Relatório de falhas recorrentes
- [ ] Filtros avançados

### Fase 3 - Integração
- [ ] API para GitLab CI
- [ ] Webhooks de notificação
- [ ] Integração com sistemas TJGO

---

## Contribuindo

1. Faça um Fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

---

## Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## Contato

**Tribunal de Justiça do Estado de Goiás - TJGO**

- Website: [https://www.tjgo.jus.br](https://www.tjgo.jus.br)

---

<p align="center">
  Desenvolvido como TCC para o TJGO
</p>

# Detectar sistema operacional
ifeq ($(OS),Windows_NT)
	DETECTED_OS := Windows
	SHELL := powershell.exe
	.SHELLFLAGS := -NoProfile -Command
	DATE_CMD := Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
	CAT_CMD := Get-Content
	MKDIR_CMD := New-Item -ItemType Directory -Force -Path
	NULL_DEVICE := $$null
	PATH_SEP := \\
	GREP_CMD := Select-String
	PWD_CMD := Get-Location | Select-Object -ExpandProperty Path
	USER_CMD := $$env:USERNAME
else
	DETECTED_OS := $(shell uname -s)
	SHELL := /bin/bash
	DATE_CMD := date +%Y-%m-%d_%H-%M-%S
	CAT_CMD := cat
	MKDIR_CMD := mkdir -p
	NULL_DEVICE := /dev/null
	PATH_SEP := /
	GREP_CMD := grep
	PWD_CMD := pwd
	USER_CMD := whoami
endif

.PHONY: help build start up stop deploy rollback status test test-coverage \
				pre-commit-install pre-commit-all pre-commit-update ruff ruff-check ruff-format \
				quality-check lint-auto lint-check lint-file lint fix check format migrate \
				makemigrations collectstatic createsuperuser checkdeploy logs logs-api logs-worker \
				down-v reload-api reload-worker install-deps install-prod \
				install-test deps-check deps-update deps-test-retry

# --- CONFIGURAÇÕES DE VERSIONAMENTO ---
# Lendo a versão do arquivo VERSION. Se não existir, assume 1.0.0.
# Isso torna a versão disponível para todos os comandos do Makefile.
IMAGE_NAME := tjgohub-api

ifeq ($(OS),Windows_NT)
	CURRENT_VERSION := $(shell if (Test-Path "VERSION") { $(CAT_CMD) VERSION } else { "1.0.0" })
	CURRENT_DIR := $(shell $(PWD_CMD))
	USER := $(shell $(USER_CMD))
	TIMESTAMP := $(shell $(DATE_CMD))
else
	CURRENT_VERSION := $(shell $(CAT_CMD) VERSION 2>$(NULL_DEVICE) || echo "1.0.0")
	CURRENT_DIR := $(shell $(PWD_CMD))
	USER := $(shell $(USER_CMD))
	TIMESTAMP := $(shell $(DATE_CMD))
endif

export COMPOSE_CMD := docker compose
# export COMPOSE_CMD := /usr/local/bin/docker-compose
yml := docker-compose.yml

# when running for the first time in new environment you can simply run "make build"
# you will need the build commands only when there are changes in any container
# all build commands usually takes more time than a run command

# Variável para passar a versão manualmente (ex: make deploy V=1.2)
V :=

# --- COMANDOS PRINCIPAIS DE DESENVOLVIMENTO ---

# Mostrar ajuda com todos os comandos disponíveis
help:
ifeq ($(OS),Windows_NT)
	@echo "tjgohub API - Comandos Disponiveis:"
	@echo ""
	@echo "DESENVOLVIMENTO:"
	@echo "  build              - Constroi todos os servicos"
	@echo "  start/up           - Inicia todos os containers"
	@echo "  stop               - Para todos os containers"
	@echo "  down-v             - Para containers e remove volumes"
	@echo ""
	@echo "SERVICOS:"
	@echo "  reload-api         - Reconstroi e reinicia apenas a API"
	@echo "  logs               - Mostra logs de todos os servicos"
	@echo "  logs-api           - Mostra logs apenas da API"
	@echo "  logs-worker        - Mostra logs apenas dos workers"
	@echo ""
	@echo "BANCO DE DADOS:"
	@echo "  migrate            - Executa migracoes"
	@echo "  makemigrations     - Cria novas migracoes"
	@echo ""
	@echo "TESTES E QUALIDADE:"
	@echo "  test               - Executa todos os testes"
	@echo "  test-coverage      - Executa testes com cobertura"
	@echo "  ruff               - Linting com correcao automatica"
	@echo "  ruff-check         - Linting apenas verificacao"
	@echo "  ruff-format        - Formatacao de codigo"
	@echo "  quality-check      - Executa todas verificacoes"
	@echo "  pre-commit-install - Instala hooks do pre-commit"
	@echo "  pre-commit-all     - Executa pre-commit em tudo"
	@echo ""
	@echo "LINT HIBRIDO:"
	@echo "  lint-auto          - Lint + correcoes automaticas"
	@echo "  lint-check         - Verificacao apenas (sem correcao)"
	@echo "  lint-file FILE=... - Processa arquivo especifico"
	@echo ""
	@echo "DEPENDENCIAS:"
	@echo "  install-deps       - Instala dependencias locais"
	@echo "  install-prod       - Instala dependencias de producao"
	@echo "  install-test       - Instala dependencias de teste"
	@echo "  deps-check         - Verifica conflitos de dependencias"
	@echo "  deps-update        - Atualiza requirements.txt com versoes atuais"
	@echo ""
	@echo "ALIASES RAPIDOS:"
	@echo "  lint/fix/format    - Alias para lint-auto"
	@echo "  check              - Alias para lint-check"
	@echo ""
	@echo "DEPLOY:"
	@echo "  deploy             - Executa deploy"
	@echo "  rollback           - Faz rollback da ultima versao"
	@echo "  status             - Mostra status dos containers"
	@echo ""
	@echo "DJANGO:"
	@echo "  collectstatic      - Coleta arquivos estaticos"
	@echo "  createsuperuser    - Cria superusuario"
	@echo "  checkdeploy        - Verifica configuracao para deploy"
else
	@echo "tjgohub API - Comandos Disponíveis:"
	@echo ""
	@echo "DESENVOLVIMENTO:"
	@echo "  build              - Constrói todos os serviços"
	@echo "  start/up           - Inicia todos os containers"
	@echo "  stop               - Para todos os containers"
	@echo "  down-v             - Para containers e remove volumes"
	@echo ""
	@echo "SERVIÇOS:"
	@echo "  reload-api         - Reconstrói e reinicia apenas a API"
	@echo "  logs               - Mostra logs de todos os serviços"
	@echo "  logs-api           - Mostra logs apenas da API"
	@echo "  logs-worker        - Mostra logs apenas dos workers"
	@echo ""
	@echo "BANCO DE DADOS:"
	@echo "  migrate            - Executa migrações"
	@echo "  makemigrations     - Cria novas migrações"
	@echo ""
	@echo "TESTES E QUALIDADE:"
	@echo "  test               - Executa todos os testes"
	@echo "  test-coverage      - Executa testes com cobertura"
	@echo "  ruff               - Linting com correção automática"
	@echo "  ruff-check         - Linting apenas verificação"
	@echo "  ruff-format        - Formatação de código"
	@echo "  quality-check      - Executa todas verificações"
	@echo "  pre-commit-install - Instala hooks do pre-commit"
	@echo "  pre-commit-all     - Executa pre-commit em tudo"
	@echo ""
	@echo "LINT HÍBRIDO (FUNCIONA EM QUALQUER AMBIENTE):"
	@echo "  lint-auto          - Lint + correções automáticas"
	@echo "  lint-check         - Verificação apenas (sem correção)"
	@echo "  lint-file FILE=... - Processa arquivo específico"
	@echo ""
	@echo "DEPENDÊNCIAS:"
	@echo "  install-deps       - Instala dependências locais"
	@echo "  install-prod       - Instala dependências de produção"
	@echo "  install-test       - Instala dependências de teste"
	@echo "  deps-check         - Verifica conflitos de dependências"
	@echo "  deps-update        - Atualiza requirements.txt com versões atuais"
	@echo ""
	@echo "ALIASES RÁPIDOS:"
	@echo "  lint/fix/format    - Alias para lint-auto"
	@echo "  check              - Alias para lint-check"
	@echo ""
	@echo "DEPLOY:"
	@echo "  deploy             - Executa deploy"
	@echo "  rollback           - Faz rollback da última versão"
	@echo "  status             - Mostra status dos containers"
	@echo ""
	@echo "DJANGO:"
	@echo "  collectstatic      - Coleta arquivos estáticos"
	@echo "  createsuperuser    - Cria superusuário"
	@echo "  checkdeploy        - Verifica configuração para deploy"
endif

# Comando padrão quando executar apenas 'make'
.DEFAULT_GOAL := help

# --- COMANDOS PRINCIPAIS DE DESENVOLVIMENTO ---

# Garante que a rede tjgohub exista para conectar com serviços externos
create-network:
ifeq ($(OS),Windows_NT)
	@echo "Verificando e criando rede tjgohub..."
	@powershell -Command "if (-not (docker network ls | Select-String 'tjgohub')) { docker network create tjgohub; Write-Host 'Rede tjgohub criada para conectar aos servicos externos' }"
	@echo "Rede tjgohub disponivel"
else
	@echo "Verificando e criando rede tjgohub..."
	@docker network ls | $(GREP_CMD) -q "tjgohub" || (docker network create tjgohub && echo "Rede 'tjgohub' criada para conectar aos servicos externos")
	@echo "Rede tjgohub disponivel"
endif

# Gera um .env na raiz com BASE_URL extraída do ./.envs/.local/.django
prepare-env: create-network
ifeq ($(OS),Windows_NT)
	@powershell -Command "if (-not (Test-Path '.env')) { Write-Host 'Criando arquivo .env...'; Get-Content '.\.envs\.local\.django' | Select-String '^BASE_URL=' | Out-File -FilePath '.env' -Encoding utf8; Add-Content -Path '.env' -Value 'API_IMAGE_NAME=$(IMAGE_NAME)'; Add-Content -Path '.env' -Value 'API_IMAGE_TAG=$(CURRENT_VERSION)'; Write-Host 'Arquivo .env criado.' } else { Write-Host 'Arquivo .env ja existe.' }"
else
	@if [ ! -f .env ]; then \
		echo "Arquivo .env nao encontrado. Criando um novo com valores padrao..."; \
		$(GREP_CMD) '^BASE_URL=' ./.envs/.local/.django > .env; \
		echo "API_IMAGE_NAME=$(IMAGE_NAME)" >> .env; \
		echo "API_IMAGE_TAG=$(CURRENT_VERSION)" >> .env; \
		echo "Arquivo .env criado com sucesso."; \
	else \
		echo "Arquivo .env ja existe. Nenhuma acao foi tomada."; \
	fi
endif

# Constrói ou reconstrói TODOS os serviços, garantindo que a API use a tag de versão correta
build: prepare-env
ifeq ($(OS),Windows_NT)
	@echo "Construindo/recriando todos os servicos..."
	@echo "A API usara a imagem: $(IMAGE_NAME):$(CURRENT_VERSION)"
	@docker compose -f $(yml) up --build -d --remove-orphans
else
	@echo "Construindo/recriando todos os servicos..."
	@echo "A API usara a imagem: $(IMAGE_NAME):$(CURRENT_VERSION)"
	@export API_IMAGE_NAME=$(IMAGE_NAME); \
	export API_IMAGE_TAG=$(CURRENT_VERSION); \
	$(COMPOSE_CMD) -f $(yml) up --build -d --remove-orphans
endif

# Setup completo para primeira execução (build + schema + migrations)
first-run: build setup-database
	@echo "Setup inicial completo!"
	@echo "- Containers construidos e iniciados"
	@echo "- Schema especifico criado"
	@echo "- Migracoes aplicadas"
	@echo ""
	@echo "Proximos passos opcionais:"
	@echo "make createsuperuser  # Criar usuario admin"
	@echo "make collectstatic    # Coletar arquivos estaticos"

# Inicia TODOS os containers, garantindo que a API use a imagem com a versão correta
start: prepare-env
ifeq ($(OS),Windows_NT)
	@echo "Iniciando todos os containers..."
	@echo "A API usara a imagem: $(IMAGE_NAME):$(CURRENT_VERSION)"
	@docker compose -f $(yml) up -d
else
	@echo "Iniciando todos os containers..."
	@echo "A API usara a imagem: $(IMAGE_NAME):$(CURRENT_VERSION)"
	@export API_IMAGE_NAME=$(IMAGE_NAME); \
	export API_IMAGE_TAG=$(CURRENT_VERSION); \
	$(COMPOSE_CMD) -f $(yml) up -d
endif

# Alias para start
up: start

# Para TODOS os containers
stop:
ifeq ($(OS),Windows_NT)
	@echo "Parando todos os containers..."
	@docker compose -f $(yml) down
else
	@echo "Parando todos os containers..."
	@export API_IMAGE_NAME=$(IMAGE_NAME); \
	export API_IMAGE_TAG=$(CURRENT_VERSION); \
	$(COMPOSE_CMD) -f $(yml) down
endif

# Alias para stop
down: stop

restart: stop start ## Reinicia todos os containers

# Comando para visualizar o status
status:
ifeq ($(OS),Windows_NT)
	@echo "Container em execucao:"
	@powershell -Command "docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | Select-String 'tjgohub'"
else
	@echo "Container em execucao:"
	@docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | $(GREP_CMD) tjgohub
endif

reload-api:
	${COMPOSE_CMD} -f ${yml} up -d --no-deps --build api

# Comando para ver os logs de TODOS os containers em tempo real
logs:
	@echo "Mostrando logs de TODOS os servicos em tempo real... (Pressione Ctrl+C para sair)"
	@$(COMPOSE_CMD) -f $(yml) logs -f

# Comando para ver os logs APENAS da API em tempo real
logs-api:
	@echo "Mostrando logs do container da API em tempo real... (Pressione Ctrl+C para sair)"
	@$(COMPOSE_CMD) -f $(yml) logs -f api

# Command to run the django migrate script
migrate:
	${COMPOSE_CMD} -f ${yml} run --rm api python3 manage.py migrate

# Command to create database schema for this API instance
create-schema:
	@echo "Criando schema especifico para esta API..."
	${COMPOSE_CMD} -f ${yml} run --rm api python3 manage.py create_schema

# Complete database setup (schema + migrations)
setup-database: create-schema migrate
	@echo "Database setup concluido! Schema criado e migracoes aplicadas."

# Command to run the django makemigrations script
makemigrations:
	${COMPOSE_CMD} -f ${yml} run --rm api python3 manage.py makemigrations

# Command to run the django collectstatic script
collectstatic:
	${COMPOSE_CMD} -f ${yml} run --rm api python3 manage.py collectstatic --no-input --clear

# Command to run the django createsuperuse script
createsuperuser:
	${COMPOSE_CMD} -f ${yml} run --rm api python3 manage.py createsuperuser

# Command to run the django test script
test:
	${COMPOSE_CMD} -f ${yml} run --rm api python3 manage.py test

# Comando para executar testes com cobertura
test-coverage:
	${COMPOSE_CMD} -f ${yml} run --rm api coverage run --source='.' manage.py test
	${COMPOSE_CMD} -f ${yml} run --rm api coverage report
	${COMPOSE_CMD} -f ${yml} run --rm api coverage html

# Comando para instalar e configurar pre-commit hooks
pre-commit-install:
	pre-commit install

# Comando para executar pre-commit em todos os arquivos
pre-commit-all:
	pre-commit run --all-files

# Comando para atualizar pre-commit hooks
pre-commit-update:
	pre-commit autoupdate

# Command to stop the docker container and remove the named volume
down-v:
	${COMPOSE_CMD} -f ${yml} down -v

# --- FERRAMENTAS DE QUALIDADE DE CÓDIGO ---
# Ruff: linter e formatter moderno (substitui flake8, isort e black)
ruff:
	${COMPOSE_CMD} -f ${yml} exec api ruff check --fix .

# Ruff check apenas (sem correção automática)
ruff-check:
	${COMPOSE_CMD} -f ${yml} exec api ruff check .

# Ruff format (formatação de código)
ruff-format:
	${COMPOSE_CMD} -f ${yml} exec api ruff format .

# Executar todas as verificações de qualidade
quality-check: ruff-check ruff-format

# --- COMANDOS HÍBRIDOS (FUNCIONAM DENTRO E FORA DO CONTAINER) ---

# Detecta se está no container ou fora e executa o comando apropriado
lint-auto:
ifeq ($(OS),Windows_NT)
	@powershell -Command "if (Test-Path '/.dockerenv') { Write-Host 'Executando dentro do container...'; ruff check --fix --unsafe-fixes .; ruff format . } elseif (Get-Command docker -ErrorAction SilentlyContinue) { Write-Host 'Executando via Docker Compose...'; docker compose -f docker-compose.yml exec api ruff check --fix --unsafe-fixes .; docker compose -f docker-compose.yml exec api ruff format . } elseif (Test-Path './venv/Scripts/ruff.exe') { Write-Host 'Executando no ambiente virtual local...'; ./venv/Scripts/ruff.exe check --fix --unsafe-fixes .; ./venv/Scripts/ruff.exe format . } else { Write-Host 'ERRO: Nenhum ambiente encontrado!'; Write-Host 'Instale as dependências ou inicie o container'; exit 1 }"
else
	@if [ -f /.dockerenv ]; then \
		echo "Executando dentro do container..."; \
		ruff check --fix --unsafe-fixes . && ruff format .; \
	elif command -v docker-compose >$(NULL_DEVICE) 2>&1 && ${COMPOSE_CMD} -f ${yml} ps api | $(GREP_CMD) -q "Up"; then \
		echo "Executando via Docker Compose..."; \
		${COMPOSE_CMD} -f ${yml} exec api ruff check --fix --unsafe-fixes . && \
		${COMPOSE_CMD} -f ${yml} exec api ruff format .; \
	elif [ -f "./venv/bin/ruff" ]; then \
		echo "Executando no ambiente virtual local..."; \
		./venv/bin/ruff check --fix --unsafe-fixes . && ./venv/bin/ruff format . && ./venv/bin/black . --line-length 79; \
	else \
		echo "ERRO: Nenhum ambiente encontrado!"; \
		echo "Instale as dependências ou inicie o container"; \
		exit 1; \
	fi
endif

# Verificação apenas (sem correção) - funciona em qualquer ambiente
lint-check:
ifeq ($(OS),Windows_NT)
	@powershell -Command "if (Test-Path '/.dockerenv') { Write-Host 'Verificando código dentro do container...'; ruff check . } elseif (Get-Command docker -ErrorAction SilentlyContinue) { Write-Host 'Verificando código via Docker Compose...'; docker compose -f docker-compose.yml exec api ruff check . } elseif (Test-Path './venv/Scripts/ruff.exe') { Write-Host 'Verificando código no ambiente virtual local...'; ./venv/Scripts/ruff.exe check . } else { Write-Host 'ERRO: Nenhum ambiente encontrado!'; Write-Host 'Instale as dependências ou inicie o container'; exit 1 }"
else
	@if [ -f /.dockerenv ]; then \
		echo "Verificando código dentro do container..."; \
		ruff check .; \
	elif command -v docker-compose >$(NULL_DEVICE) 2>&1 && ${COMPOSE_CMD} -f ${yml} ps api | $(GREP_CMD) -q "Up"; then \
		echo "Verificando código via Docker Compose..."; \
		${COMPOSE_CMD} -f ${yml} exec api ruff check .; \
	elif [ -f "./venv/bin/ruff" ]; then \
		echo "Verificando código no ambiente virtual local..."; \
		./venv/bin/ruff check . && ./venv/bin/mypy . --ignore-missing-imports; \
	else \
		echo "ERRO: Nenhum ambiente encontrado!"; \
		echo "Instale as dependências ou inicie o container"; \
		exit 1; \
	fi
endif

# Comando para arquivo específico - funciona em qualquer ambiente
lint-file:
ifeq ($(OS),Windows_NT)
	@powershell -Command "if (-not $$env:FILE) { Write-Host 'ERRO: Especifique o arquivo com FILE=caminho/arquivo.py'; Write-Host 'Exemplo: make lint-file FILE=tools/utils.py'; exit 1 }; try { ruff check --fix --unsafe-fixes $$env:FILE; ruff format $$env:FILE } catch { docker compose -f docker-compose.yml exec api ruff check --fix --unsafe-fixes $$env:FILE; docker compose -f docker-compose.yml exec api ruff format $$env:FILE }"
else
	@if [ -z "$(FILE)" ]; then \
		echo "Erro: Especifique o arquivo com FILE=caminho/arquivo.py"; \
		echo "Exemplo: make lint-file FILE=tools/utils.py"; \
		exit 1; \
	fi; \
	if [ -f /.dockerenv ]; then \
		echo "Processando $(FILE) dentro do container..."; \
		ruff check --fix --unsafe-fixes $(FILE) && ruff format $(FILE); \
	elif command -v docker-compose >$(NULL_DEVICE) 2>&1 && ${COMPOSE_CMD} -f ${yml} ps api | $(GREP_CMD) -q "Up"; then \
		echo "Processando $(FILE) via Docker Compose..."; \
		${COMPOSE_CMD} -f ${yml} exec api ruff check --fix --unsafe-fixes $(FILE) && \
		${COMPOSE_CMD} -f ${yml} exec api ruff format $(FILE); \
	elif [ -f "./venv/bin/ruff" ]; then \
		echo "Processando $(FILE) no ambiente virtual local..."; \
		./venv/bin/ruff check --fix --unsafe-fixes $(FILE) && ./venv/bin/ruff format $(FILE) && ./venv/bin/black $(FILE) --line-length 79; \
	else \
		echo "Erro: Nenhum ambiente encontrado!"; \
		echo "Instale as dependências ou inicie o container"; \
		exit 1; \
	fi
endif

# --- COMANDOS DE DEPENDÊNCIAS ---

# Instalar dependências para desenvolvimento local
install-deps:
	@echo "Instalando dependências para desenvolvimento..."
	@./scripts/install-requirements.sh local

# Instalar dependências para produção
install-prod:
	@echo "Instalando dependências para produção..."
	@./scripts/install-requirements.sh production

# Instalar dependências para testes
install-test:
	@echo "Instalando dependências para testes..."
	@./scripts/install-requirements.sh test

# Verificar conflitos de dependências
deps-check:
	@echo "Verificando conflitos de dependencias..."
ifeq ($(OS),Windows_NT)
	@powershell -Command "try { pip check } catch { docker compose -f docker-compose.yml exec api pip check }"
else
	@if command -v pip >$(NULL_DEVICE) 2>&1; then \
		pip check; \
	elif [ -f "/.dockerenv" ] || [ -n "$$DOCKER_CONTAINER" ]; then \
		${COMPOSE_CMD} -f ${yml} exec api pip check; \
	else \
		echo "Pip não encontrado e não está em container"; \
		exit 1; \
	fi
endif

# Atualizar requirements.txt com versões instaladas
deps-update:
	@echo "Atualizando requirements com versoes atuais..."
ifeq ($(OS),Windows_NT)
	@powershell -Command "try { pip freeze > requirements\\current-freeze.txt; Write-Host 'Versões atuais salvas em requirements\\current-freeze.txt' } catch { docker compose -f docker-compose.yml exec api pip freeze > requirements\\current-freeze.txt; Write-Host 'Versões atuais salvas em requirements\\current-freeze.txt' }"
else
	@if command -v pip >$(NULL_DEVICE) 2>&1; then \
		pip freeze > requirements$(PATH_SEP)current-freeze.txt; \
		echo "Versões atuais salvas em requirements$(PATH_SEP)current-freeze.txt"; \
	elif [ -f "/.dockerenv" ] || [ -n "$$DOCKER_CONTAINER" ]; then \
		${COMPOSE_CMD} -f ${yml} exec api pip freeze > requirements$(PATH_SEP)current-freeze.txt; \
		echo "Versões atuais salvas em requirements$(PATH_SEP)current-freeze.txt"; \
	else \
		echo "Pip não encontrado e não está em container"; \
		exit 1; \
	fi
endif

# Verificar se retry service está funcionando
deps-test-retry:
	@echo "Testando retry service..."
ifeq ($(OS),Windows_NT)
	@powershell -Command "try { python -c 'from tools.retry_service import CEPService, retry_metrics; print(\"Retry service funcionando!\")' } catch { docker compose -f docker-compose.yml exec api python -c 'from tools.retry_service import CEPService, retry_metrics; print(\"Retry service funcionando!\")' }"
else
	@if command -v python >$(NULL_DEVICE) 2>&1; then \
		python -c "from tools.retry_service import CEPService, retry_metrics; print('Retry service funcionando!')"; \
	elif [ -f "/.dockerenv" ] || [ -n "$$DOCKER_CONTAINER" ]; then \
		${COMPOSE_CMD} -f ${yml} exec api python -c "from tools.retry_service import CEPService, retry_metrics; print('Retry service funcionando!')"; \
	else \
		echo "Python não encontrado e não está em container"; \
		exit 1; \
	fi
endif

# --- ALIASES PARA CONVENIÊNCIA ---
# Aliases para os comandos mais usados
lint: lint-auto
fix: lint-auto
check: lint-check
format: lint-auto


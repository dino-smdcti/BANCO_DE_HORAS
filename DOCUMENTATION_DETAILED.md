# Banco de Horas - Documentação Técnica

Este documento descreve as funcionalidades, arquitetura e regras de negócio do sistema de Banco de Horas.

## 1. Arquitetura
O sistema segue os princípios da **Arquitetura em Camadas** e **Domain-Driven Design (DDD)** simplificado:
- **Domain (`src/domain/`)**: Contém as entidades de negócio (`User`, `DailyPonto`), enums e lógica pura de cálculo (como saldo de horas).
- **Adapters (`src/adapters/`)**: Implementa a persistência (SQLAlchemy/Repository Pattern).
- **Service Layer (`src/service_layer/`)**: Orquestra os casos de uso (registro de ponto, correções, processamento de faltas).
- **Entrypoints (`src/entrypoints/`)**: Interface com o usuário (Flask App e CLI Scripts).

## 2. Funcionalidades Principais

### 2.1 Gestão de Usuários e Perfis
- **Registro e Login**: Autenticação segura com `Werkzeug`.
- **Perfis Detalhados**: Armazena matrícula, CPF, departamento, cargo e secretaria.
- **Hierarquia**: Papéis de `ADMIN` (Secretário), `MANAGER` (Diretor) e `EMPLOYEE` (Funcionário).
- **Data de Início de Análise**: Define a partir de quando o saldo de horas começa a ser calculado para cada usuário.

### 2.2 Controle de Jornada (Ponto)
- **Registro em 4 Estágios**: Chegada, Saída Almoço, Retorno Almoço e Fim de Jornada.
- **Geolocalização**: Captura a localização no momento do registro (via navegador).
- **Detecção Automática de Anomalias**:
    - **Atraso na Chegada**: Comparado com o horário previsto + tolerância.
    - **Saída Antecipada**: Saída antes do horário previsto - tolerância.
    - **Anomalias de Almoço**: Saídas ou retornos fora da janela prevista.
- **Ponto Incompleto**: Registros que não possuem todos os estágios preenchidos são penalizados no saldo diário.

### 2.3 Sistema de Faltas Automáticas (`absence_processor.py`)
- **Identificação de Ausências**: Verifica diariamente se o usuário possui registro de ponto.
- **Lógica Otimizada**:
    - Em dias comuns, verifica o dia anterior.
    - Nas segundas-feiras, verifica sexta, sábado e domingo.
- **Criação de Registro `FALTANTE`**: Se não houver registro em dia útil (e não for feriado/férias), cria um ponto com status "Faltante".
- **Abono de Faltas**: Gestores podem clicar no badge vermelho "! Abonar Falta" em registros faltantes para remover a penalidade, útil para casos de atestados médicos ou folgas não programadas.
- **Penalização**: Faltas não abonadas subtraem a jornada integral do saldo de horas.

### 2.4 Cálculos de Saldo (Time Balance)
- **Saldo Diário**: `Minutos Trabalhados - Minutos Previstos`.
- **Saldo Total**: Somatório dos saldos diários desde a `start_analysis_date`.
- **Regras de Abono**:
    - Anomalias aprovadas ou justificadas pelo gestor utilizam o tempo previsto (neutralizam o atraso).
    - Status `DISMISSED` (Dispensado) ou `JUSTIFIED` (Justificado) não geram débito.
    - Status `REJECTED` (Rejeitado) ou `MISSING` (Faltante) geram débito total da jornada.

### 2.5 Gestão Administrativa
- **Aprovação de Anomalias**: Administradores podem aprovar atrasos individualmente.
- **Correções Manuais**: Gestores podem corrigir horários de subordinados.
- **Solicitações de Correção**: Funcionários podem solicitar ajustes que precisam de aprovação.
- **Relatórios**: Geração de relatórios em Excel (`openpyxl`) com formatação profissional.
- **Feriados e Férias**: Cadastro de datas que isentam o registro de ponto.

## 3. Fluxos de Loop e Processamento
- **Processamento de Faltas**: Executado via `run_daily_auto_log.py` (idealmente via CRON diário).
- **Cálculo de Saldo**: Realizado dinamicamente na entidade `User` ao acessar o dashboard, garantindo dados sempre atualizados.

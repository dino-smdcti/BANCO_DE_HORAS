# Banco de Horas — Workforce Expansion (Gestão)

Este documento define a expansão do aplicativo de ponto eletrônico em uma plataforma integrada de **gestão de equipes e trabalho**. É o plano mestre (arquitetura, verticals, decisões, e o objetivo final).

---

## 0. TL;DR — Objetivo final

Transformar o "Banco de Horas" (um app de ponto) em um **portal único de gestão de trabalho**, mantendo a autenticação, o modelo de organização (Times + Secretaria) e o banco de dados atuais — estendendo-os *in place* (Opção A).

Entrega **quatro verticals complementares**, construídas uma a uma sobre uma **base compartilhada de organização e atribuição (assignment)**:

1. **Tarefas & Checklists internos** — atribuição, prazos e status.
2. **Conquistas de equipe com períodos** — registro e vitrine do que cada time entrega.
3. **Quadro de Ideias / KAIZEN** — brainstorming colaborativo com votação (categoria `kaizen` + status `implemented` para melhoria contínua).
4. **Painéis de equipe** — dashboards operacionais por time (funcionários, tarefas abertas, ideias, conquistas).

**Módulos complementares (cultura / filosofia de trabalho):**
- **5S por setor** — checklist periódico de auditoria + pontuação por time.
- **Wiki interna** — base de conhecimento colaborativa.
- **Eventos** — eventos marcados no calendário; tarefas podem vincularse a um evento (objetivo ligado à entrega do evento).
- **Kudos (reconhecimento entre pares)** — elogios simples.
- **Calendário de eventos / oficinas** — agenda interna.
- **A7 — Dashboard executivo de Indicadores (KPIs)** — visão consolidada da secretaria.
- **A6 — Patch notes / release board interno** — **removido** na reorganização: o changelog ("Notas") não era função de negócio e foi eliminado do código (rota, template, service, modelo, repositório). A tabela `changelog_notes` em produção permanece intacta (sem DROP); bases novas não a criam mais.

Mais um **"magic button" (botão mágico)**: uma chave de **modo visual** que faz o lado de gestão parecer *outra coisa* distinta do mundo do ponto — mesmo dentro do mesmo site e banco de dados.

**Princípios fundamentais:**
- **Mesmo site, mesmo banco** — nenhum silo, nenhum DB separado/sincronizado.
- **Base org compartilhada** — toda nova entidade referencia `team_id`; o **Time é a unidade** (sem entidade Departamento nova).
- **Todos participam** — funcionários postam/votam em ideias e veem conquistas; gestores criam tarefas e aprovam conquistas.
- **`metadata.create_all`** cria as tabelas novas automaticamente em todos os ambientes (SQLite e Postgres), via `scripts/run_migrations.py` — tabelas novas não precisam de ALTER migration.

---

## 1. Decisões de arquitetura confirmadas

| Tema | Decisão | Justificativa |
|---|---|---|
| Extensão | **Opção A — in place** (mesmo site, mesmo DB) | Base org + assignment comum pressupoe um único DB; zero sincronismo |
| Unidade organizacional | **Time** (reuso de `Team` + `User.team_id` + `User.profile.secretariat`) | Modelo atual já resolve; nada de entidade Departamento |
| Participação | **Todos** (funcionários view/post/vote; gestores create/approve) | Cultura colaborativa; sem silos |
| "Botão mágico" | **Modo visual via paleta CSS** `[data-app-mode]` + toggle | Puro apresentacional; dados unificados |
| Escopo de acesso | Reuso de `ensure_managed_user` / papéis `MANAGEMENT_ROLES`/`ADMIN_ROLES` | IDOR já modelado; admin/gestor see-all, manager só seu time |
| Persistência | Tabela SQLAlchemy em `orm.py` + `metadata.create_all` | Auto-criado em todo deploy; sem ALTER manual |

### Papéis atuais (reuso)
- `ADMIN` (Secretário) e `GESTOR`: todas as equipes.
- `MANAGER` (Diretor): apenas a própria `team_id`.
- `EMPLOYEE` (Funcionário): participação em conteúdo do seu time + colaboração.
- `MANAGEMENT_ROLES = ADMIN + MANAGER + GESTOR`; `ADMIN_ROLES = ADMIN + GESTOR`.

---

## 2. Base compartilhada (construída primeiro — Fase F0)

Antes das verticals, uma fundação única evita duplicar a lógica de IDOR e escopo:

- **`managed_team_ids(uow, actor)`** — helper de escrita/criação em `service_layer`:
  - `ADMIN`/`GESTOR` → todas as `team_id`.
  - `MANAGER` → `[actor.team_id]` (vazio se sem time).
  - Outros → levanta `PermissionError`.
- **`scoped_team_ids(uow, actor)`** — helper de leitura:
  - `ADMIN`/`GESTOR` → todas as `team_id`.
  - `MANAGER` → `[actor.team_id]`.
  - `EMPLOYEE` → próprio time (leitura).
- **`Team.lead_user_id` (ORIGINALMENTE em F0, MOVIDO para Fase D):** adicionar coluna à tabela `teams` existente em prod exige ALTER Postgres; F0 mantém-se **sem ALTER** (regra de segurança). Fresh DBs recebem via `create_all`; prod recebe via ALTER idempotente na Fase D, validado em staging.
- **Auditoria** (`record_action`) e **notificações** (reuso de `add_notification`) para toda mutação relevante.

Test parity: `tests/unit/test_assignment_base.py`.

---

## 3. Vertical A — Tarefas & Checklists internos

**Objetivo:** to-dos atribuíveis a uma pessoa, com prazo e status, por time.

- **Modelos:**
  - `TeamTask`: `team_id`, `title`, `description`, `assignee_id`, `due_date`, `status` (todo/in_progress/done/cancelled), `created_by`, `created_at`.
  - `TaskChecklistItem`: `task_id`, `label`, `done` (sub-checklist).
  - "Base de assignment" — o primeiro consumidor de `scoped_team_ids`.
- **Regras:**
  - Gestores criam/atribuem para o seu escopo.
  - Funcionários veem tarefas do time + as suas atribuídas; podem marcar o próprio status/subitens.
  - Notificação ao `assignee` quando atribuído.
- **Rotas:** novas ("work/tasks", sub-rotas POST com CSRF), rotas `@manager_required` para create/assign e `@login_required` para auto-status.
- **Test parity:** CRUD, escopo de assignee, toggle de checklist, transições de status, auditoria.

---

## 4. Vertical B — Conquistas de equipe com períodos

**Objetivo:** registrar e exibir o que cada time entrega em um intervalo de datas, visível na organização inteira.

- **Modelos:**
  - `Accomplishment`: `team_id`, `title`, `description`, `start_date`, `end_date` (opcional → "em andamento"), `achieved_by_user_id`, `created_by`.
- **Regras:**
  - Gestores criam para seu escopo; todos visualizam.
  - `end_date >= start_date`; período aberto permitido (**default**).
  - Auditoria em criação/edição.
- **Test parity:** validação de período, escopo por time, guarda de sobreposição.

---

## 5. Vertical C — Quadro de Ideias / KAIZEN (brainstorming)

**Objetivo:** funcionários postam ideias (gerais ou de melhoria contínua/KAIZEN); todos votam (up/down); gestores triam status. **Importante: KAIZEN NÃO é um módulo separado** — é uma categoria + status do mesmo quadro de ideias, evitando duplicar um vertical para um rótulo (decisão de compactação).

- **Modelos:**
  - `Idea`: `author_id`, `title`, `description`, `category` (idea/kaizen), `created_at`, `status` (open/under_review/implemented/declined).
  - `IdeaVote`: `idea_id`, `voter_id`, `value` (+1/−1), `UNIQUE(idea_id, voter_id)`.
  - Campo opcional `review_date`/`review_owner` para cadência PDCA (sem virar feature separada).
- **Regras:**
  - Qualquer pessoa posta e vota; **1 voto por usuário por ideia**.
  - Gestores mudam status (**`done` → `implemented`**); notificação ao autor em mudança.
  - KAIZEN = `category="kaizen"` + transição para `implemented` quando aplicado.
  - **Default:** drivers de status = gestores; qualquer pessoa posta/vota.
- **Test parity:** postagem, voto único, alternância de voto, transições de status (incluindo `implemented`), filtro por categoria kaizen.

---

## 6. Vertical D — Painéis de equipe (management expansion)

**Objetivo:** aprofundar os atuais `teams.html`/`management_panel()` em dashboards operacionais por time.

- **Escopo:** renomear time, definir `lead_user_id`; roll-ups por time:
  - nº de membros, tarefas abertas/criadas, ideias abertas, conquistas/trimestre.
- **Visibilidade:**
  - Manager vê seu time; admin/gestor veem todos.
  - **Default:** funcionários veem dashboard **read-only do próprio time**.
- **Test parity:** atribuição de lead, contagem de membros, dados do dashboard com escopo.

---

## 6b. Módulo B-extra — 5S por setor (filosofia de trabalho)

**Objetivo:** operacionalizar a filosofia **5S** (Seiri, Seiton, Seiso, Seiketsu, Shitsuke) como **auditoria periódica por setor**, com pontuação — reaproveitando a Vertical A (tasks/checklists).

- **Mecânica:** cada setor/team tem um **checklist 5S** (lista de itens verificáveis por etapa); uma auditoria gera uma instância com data, responsável e **score** (% itens marcados).
- **Modelos (leves, sobre a base de A):** `S5Audit` (`team_id`, `auditor_id`, `date`, `total_items`, `passed_items`, `score`, `notes`) e os itens padrão por setor (`S5Item`). Reusa `TeamTask` infra se viável; senão tabela fina própria.
- **Regras:** auditorias apenas por gestores/auditores do escopo; todos visualizam os scores do próprio time; histórico mensal.
- **Test parity:** criação de auditoria, cálculo de score, escopo por time, histórico.

# 6c. Módulo C-extra — Cultura colaborativa (Wiki, Kudos, Eventos)

Agrupamento de funcionalidades leves de cultura/colaboração, cada uma uma tabela fina:

- **`WikiArticle` — Wiki interna:** `team_id` (ou pública), `author_id`, `title`, `body`, `updated_at`. Qualquer pessoa escreve/edita no escopo. O corpo suporta **Markdown** com sanitização; a listagem mostra snippets.
- **`Kudos` — Reconhecimento entre pares:** `giver_id`, `receiver_id`, `message`, `created_at`. Qualquer pessoa doa; feed visível no time.
- **`TeamEvent` — Calendário/eventos/oficinas:** `team_id`, `title`, `date`, `description`. Reusa notificações. Uma tarefa pode vincularse a um evento via `team_tasks.event_id`.
- **`Mentorship` — REMOVIDO:** a mentoria (pareamento 1:1) foi retirada end-to-end; a tabela prod fica intacta (sem DROP).
- **Test parity:** CRUD por entidade + escopo + auditoria.

## 6d. Módulo A7 — Dashboard executivo de Indicadores (KPIs)

**Objetivo:** visão consolidada da secretaria, consumindo os roll-ups da Vertical D (e qualquer dado derivado) em cards/gráficos **transversais a times**.

- **Exemplos de KPIs:** nº de membros por time, tarefas abertas/vencidas, ideias abertas/implementadas, conquistas no período, score 5S médio, kudos emitidos.
- **Visibilidade:** `ADMIN`/`GESTOR` (todos); `MANAGER` só seu time; `EMPLOYEE` read-only do próprio time.
- **Test parity:** agregação correta por escopo; dados coerentes com as fontes (D/B/C/5S).

## 6e. Módulo A6 — Patch notes / release board interno

**Status: REMOVIDO** na reorganização ("Workforce Expansion 2"). O changelog era meta-affordance, não função de negócio, e foi eliminado do código: rotas `work_changelog*`, template `work_changelog.html`, `changelog_service.py`, a classe `ChangeLogNote` no modelo, a tabela `changelog_notes` e seus mappers/repos, re-exports em `services.py`, o link "Notas" na nav e os testes correspondentes. MySQL/Postgres de produção **não recebem DROP** — a tabela existente fica intacta; bases novas simplesmente não a criam (`changelog_notes` não está mais no `metadata`).

---

## 7. Cross-cutting — "Magic button" (modo visual)

**Objetivo:** o lado de gestão *parece outra coisa* do mundo do ponto, sem separar dados.

**Mecânica (puramente apresentacional):**
- **Duas paletas** em `style.css`: paleta padrão (`:root`) = mundo do ponto; paleta override sob `[data-app-mode="work"]` = mundo gestão (troca as custom properties de marca — accent, primary, bg, etc.). A paleta de gestão usa **navy/slate corporativo** (navbar `#1F2A44`, primary `#2E5C8A`) — nitidamente distinta do verde do ponto, mantendo ares profissional.
- **Duas navegações isoladas** num único `base.html`, chaveadas por `data_app_mode` (contexto injetado em `flask_app` a partir do `request.path`): páginas `/work/*` mostram **apenas** a nav de workforce, agora **agrupada em dropdowns** para reduzir poluição — **Painel** (top-level), **Atividade** (Tarefas/Conquistas/Ideias/5S), **Estrutura** (Equipes), **Cultura** (Wiki/Kudos/Eventos), **Gestão** (Relatórios/Executivo); páginas de ponto mostram **apenas** a nav do relógio (Ponto/Gestão/Auditoria/Times/Dados). Sem mix/crowding.
- **Auto-deteção por rota (sempre aplicada):** `request.path.startswith("/work")` decide a nav + paleta; **visitar diretamente um link de `/work/*` sempre renderiza a paleta/nav correta**, independente de preferência salva (removido o override por localStorage que tornava a troca invisível).
- **Switch no navbar (estilo day/night, `.app-mode-switch`)** no lugar do botão flutuante: é um **toggle switch de verdade** — trilho + tecla deslizante (ligado/desligado) que reflete o modo ativo por `data-mode`, com rótulo ao lado; na nav de clock, "Workforce" (antes de Dados); na nav de gestão, "Voltar ao Ponto" (antes de Dados). Renderizado **somente quando `WORKFORCE_ENABLED`** (install puramente de clock nunca o vê).
- **Sem dados duplicados:** é apenas a identidade visual + nav; o modelo de dados continua unificado.

> **Default confirmado:** auto-deteção por rota + **switch no navbar** (não mais botão flutuante). A troca é comandada por rota/URL — paleta e navegação sempre correspondem ao caminho. (Alternativa descartada: um toggle global JS único, que adicionaria estado sem o "feeling" de lugar distinto.)

---

## 8. Fases & sequência de commits

Disciplina de trabalho: commits atômicos, teste por unidade, push **só no fim de cada fase**.

| Fase | Conteúdo | Nota |
|---|---|---|
| **F0** | `managed_team_ids` + `scoped_team_ids` + testes | Fundação de escopo; **sem ALTER** (lead_user_id movido a D) |
| **A** | Tarefas & checklists (modelo + service + rotas + templates + nav) | Base de assignment consumida |
| **B** | Conquistas com períodos | Reusa escopo F0 |
| **C** | Quadro de ideias **+ KAIZEN (categoria `kaizen` + status `implemented` + review PDCA opcional)** | Escopo + notificações |
| **D** | Painéis de equipe (roll-ups, lead) — inclui `Team.lead_user_id` (coluna `create_all` + ALTER Postgres idempotente) | Aprofunda `management_panel`; alimenta A7 |
| **B-extra** | 5S por setor (auditoria periódica + score) | Instância de A |
| **C-extra** | Wiki interna, Kudos, Calendário/eventos | Tabelas finas de cultura |
| **A7** | Dashboard executivo de KPIs (cross-team) | Consome roll-ups de D/B/C/5S |
| **W** | Mode-switch (paleta `[data-app-mode]` + toggle + aplicação nas templates de gestão) | Botão mágico |
| **A6** | Patch notes / release board interno | Último; descartável |

**Sequência recomendada de entrega (F0 → A → B → C → D), depois B-extra/C-extra/A7, e só então W; A6 por último.**

Cada fase altera: `src/domain/model.py`, `src/adapters/orm.py` (tabela nova), `src/service_layer/<novo>.py`, re-export no `services.py`, `src/entrypoints/<novo>_routes.py`, template que estende `base.html`, link de nav gated por papel, e `tests/`.

Tabelas novas em `orm.py` → criadas por `metadata.create_all` em `run_migrations.py` (SQLite e Postgres). Nenhuma ALTER manual necessária para tabelas novas.

---

## 9. Topologia de rotas (previsão)

- `/work` — **landing/dashboard** (novo painel de resumo do workforce sobre os times no escopo).
- `/work/tasks/*` — Vertical A (CRUD tarefas; checklist).
- `/work/accomplishments/*` — Vertical B (conquistas).
- `/work/ideas/*` — Vertical C (quadro ideal/kaiizen + voto).
- `/work/teams/*` — Vertical D (painéis de equipe).
- `/work/5s/*` — B-extra (auditorias 5S).
- `/work/culture/*` — C-extra (wiki, kudos, eventos).
- `/work/reports*` — **relatórios HTML** (filtro por período/team; seções de tarefas/conquistas/ideias/5S/kudos/eventos/wiki; exportável para impressão).
- `/work/exec/*` — A7 (dashboard executivo de KPIs).
- Prefixo `/work` carrega `data-app-mode="work"` → o "magic button" reconhece instantaneamente.

---

## 10. Padrões de implementação (reuso obrigatório)

- Rotas: `@login_required` + `@manager_required`/`@admin_required` + `@handle_errors`; `new_uow()`, `flash_redirect`, `record_action` (auditoria), `csrf_token()` em todo POST.
- Repositório: acesso via `AbstractRepository`/`SqlAlchemyRepository` exposto no `uow` (ex.: `uow.tasks`, `uow.ideas`) — padrão `uow.users`.
- `services.py` é a fachada: qualquer pastagem de `services.py` verifica se há plug de dead-code.
- Notificações: `add_notification` (in-app) + hooks Brevo/SMTP existentes.
- Templates: estendem `base.html`; a nav é dividida por modo (`data_app_mode`) — páginas de gestão com a nav dedicada de workforce, páginas de ponto com a nav do relógio; persistência de papel por escopo via `MANAGEMENT_ROLES`/`ADMIN_ROLES`.

---

## 11. Semântica padrão de estado

| Entidade | Estados |
|---|---|
| `TeamTask` | `todo` → `in_progress` → `done`; ramo `cancelled` |
| `Idea` | `open` → `under_review` → `implemented`/`declined` (KAIZEN = `category=kaizen` aplicado em `implemented`) |
| `Accomplishment` | `planned` → `achieved` (com `end_date` opcional) |
| `S5Audit` | `open` → `scored` (com `score` %) |

Nomes de índice seg. convenção `ix_*` já usada.

---

## 11b. Segurança para produção (prod = Postgres, dev = SQLite)

Estratégia **não-invasiva**: nenhuma mudança pode afetar o sistema de ponto já em produção.

**Garantias estruturais (gratuitas do design atual):**
- Todas as entidades novas = **tabelas novas**; **nunca `ALTER`** tabelas existentes (só leitura de `teams`/`users`).
- Tabelas novas criadas por `metadata.create_all` (`CREATE TABLE IF NOT EXISTS`) em `run_migrations.py` — idempotente em SQLite e Postgres; não dropa/altera nada existente.
- Rotas novas em `/work/*` e módulos novos — **aditivo**, rotas existentes não são modificadas.
- Suite de regressão (279 tests) verde é **gate obrigatório antes de cada push de fase**.

**Áreas de risco e mitigação:**
1. **`services.py` (fachada)** — apenas **append** de re-exports; nunca reescrever funções existentes (verificar plug de dead-code).
2. **Migração em prod (Postgres)** — só tabelas novas, sem índice novo em tabela pré-existente e sem `run_base_migrations`/`run_index_migrations` adicionais que toquem tabelas antigas.
3. **nav/base.html** — links novos **gated por papel**; páginas existentes inalteradas.
4. **Mode-switch (W)** — único change cross-página; mitigação: paleta override estritamente sob `[data-app-mode="work"]`, páginas de ponto sem atributo renderizam idênticas; **flag `WORKFORCE_ENABLED`** (false por default) para *soft-launch* e rollback instantâneo.

**Release gate por fase (aceito):**
- (a) Deploy zero-downtime: push fase → `run_migrations.py` contra prod (Postgres) → smoke-test `/work/*` → prod continua no ar.
- (b) Staging clone do prod DB antes do deploy real.
- (c) Backup/snapshot do banco de prod **antes de cada** migração (rollback).
- Validação com staging + suite verde como pré-requisito antes de cada push de fase.

**Rollback:** cada feature vive em tabela/rota própria → fase ruim é isolada; desabilitável via nav-link / não deployar sua migração sem tocar no ponto.

---

## 12. Visão final (destination statement)

Ao concluir as 6 fases, o "Banco de Horas" deixa de ser só ponto eletrônico e passa a ser um **portal de gestão de trabalho integrado**:

- Os mesmos usuários, times e autenticação.
- O mesmo banco (tabelas novas convivem com `daily_pontos`/`audit_logs`).
- Gestores gerenciam **tarefas, conquistas, painéis e KPIs executivos**; todos **participam com ideias/KAIZEN, wiki, kudos e eventos**, e **auditam 5S por setor**.
- A filosofia de trabalho (**5S**) e a cultura colaborativa (**KAIZEN, kudos, wiki, eventos**) são entregues **sobre a mesma base compartilhada** — sem duplicar sistema ou dados.
- O **"magic button"** separa visualmente as duas experiências — ponto vs gestão — mesmo dentro de um único site.

Resultado: um produto único e coeso onde **bater ponto, gerir o trabalho e cultivar a melhoria contínua são faces da mesma organização**, sem duplicação de dados nem ferramentas paralelas.
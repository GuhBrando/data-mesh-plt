# data_mesh_plt

Plataforma de Data Mesh para gestão de **Data Contracts** e **Data Products** em arquitetura distribuída por domínios, com classificação por **tiers** e modelo híbrido de armazenamento (catálogo central de contratos + repositórios de código por domínio).

A plataforma serve como camada de orquestração, descoberta e governança sobre uma malha de produtos de dados descentralizados, mantendo o equilíbrio entre **autonomia dos times** (cada domínio é dono de seu código) e **descoberta global** (contratos são públicos por design).

---

## Sumário

- [Visão Geral](#visão-geral)
- [Conceitos Fundamentais](#conceitos-fundamentais)
  - [Data Contract](#data-contract)
  - [Data Product](#data-product)
  - [Como os Dois se Relacionam](#como-os-dois-se-relacionam)
- [Arquitetura Híbrida de Armazenamento](#arquitetura-híbrida-de-armazenamento)
  - [Por que Híbrido](#por-que-híbrido)
  - [Repositório Central de Contratos](#repositório-central-de-contratos)
  - [Repositórios de Produtos por Domínio](#repositórios-de-produtos-por-domínio)
  - [Papel do Postgres na Plataforma](#papel-do-postgres-na-plataforma)
- [Sistema de Tiers](#sistema-de-tiers)
  - [Por que Tiers Existem](#por-que-tiers-existem)
  - [Definição dos Tiers](#definição-dos-tiers)
  - [Como Classificar um Produto](#como-classificar-um-produto)
- [Fluxo de Criação de um Data Product](#fluxo-de-criação-de-um-data-product)
- [Estrutura do Repositório da Plataforma](#estrutura-do-repositório-da-plataforma)
- [Política de Evolução](#política-de-evolução)
- [Decisões de Design e Trade-offs](#decisões-de-design-e-trade-offs)
- [Referências](#referências)

---

## Visão Geral

Esta plataforma orquestra três entidades principais que vivem em locais diferentes mas trabalham em conjunto:

1. **Os contratos** vivem em um **repositório central** de catálogo, em formato YAML padronizado (ODCS). Servem como interfaces públicas dos produtos de dados — descobríveis por qualquer time, modificáveis apenas pelos owners do domínio correspondente.

2. **O código dos produtos** (pipelines de transformação, testes, infraestrutura específica) vive em **repositórios separados por domínio**, garantindo isolamento de acesso e autonomia dos times.

3. **A plataforma** (este repositório) é a camada de orquestração: indexa os contratos em Postgres para queries ricas, oferece UI para criação e gestão, gerencia fluxos de aprovação, valida conformidade, e expõe APIs.

A separação entre "contrato como interface pública" e "código como implementação privada" é a mesma que existe entre uma especificação OpenAPI e o código que implementa a API. Aplicada a dados, essa separação é o que permite que Data Mesh funcione em escala.

---

## Conceitos Fundamentais

### Data Contract

Um **Data Contract** é uma especificação formal, versionada e legível por máquina que define a interface pela qual um conjunto de dados é exposto. Não é apenas um schema; é um acordo completo que cobre estrutura, semântica, qualidade, garantias de serviço e regras de evolução.

Pense em um Data Contract como o equivalente de uma especificação OpenAPI para APIs, mas aplicado a dados.

Um contrato típico contém:

- **Schema** — estrutura, tipos, constraints de cada campo
- **Semântica** — o que cada campo significa no domínio do negócio (não apenas seu tipo de dado)
- **Regras de qualidade** — completude, unicidade, distribuições aceitáveis, integridade referencial
- **SLAs** — frescor dos dados, disponibilidade, latência, RTO/RPO
- **Ownership** — quem é responsável técnico, de produto e de negócio
- **Política de evolução** — como o contrato pode mudar sem quebrar consumidores
- **Governança** — classificação, retenção, controle de acesso, lineage

### Data Product

Um **Data Product** é a unidade autocontida que entrega valor analítico a partir de dados. Ele é maior que um contrato: o contrato é uma das interfaces do produto, mas o produto inclui também o código de transformação, a infraestrutura, a documentação, os testes e o processo operacional.

Um Data Product tem características que o aproximam de um produto de software:

- **Donos identificáveis** — pessoas reais, não times genéricos
- **Usuários (consumidores) registrados** — quem depende do produto está documentado
- **Ciclo de vida** — criação, evolução, deprecation, retirement
- **Métricas de adoção e qualidade** — uso real é monitorado
- **Múltiplas formas de consumo (output ports)** — o mesmo dado lógico pode ser exposto via tabela SQL, API REST, eventos, arquivos, com contratos específicos para cada forma

Um Data Product geralmente declara:

- **Input ports** — quais contratos de outros produtos ele consome
- **Output ports** — quais contratos ele expõe (um para cada forma de consumo)
- **Código de transformação** — pipeline que transforma inputs em outputs
- **Metadados de governança** — domínio, criticidade, classificação

### Como os Dois se Relacionam

A confusão mais comum é tratar Data Contract e Data Product como sinônimos ou alternativas. Eles operam em níveis diferentes e são complementares.

```
┌─────────────────────────────────────────────────────────────┐
│                       DATA PRODUCT                          │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Input Ports  │───▶│ Transformação│───▶│ Output Ports │   │
│  │ (contratos   │    │   (código)   │    │  (contratos  │   │
│  │  de upstream)│    │              │    │   expostos)  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                             │
│  + Ownership, Documentação, Métricas, Ciclo de Vida         │
└─────────────────────────────────────────────────────────────┘
```

Em outras palavras: um Data Product é uma máquina que transforma um conjunto de contratos de entrada em um conjunto de contratos de saída, somada a tudo que é necessário para que essa máquina seja operável, evoluível e confiável ao longo do tempo.

Sem contratos, um Data Product não tem como ser confiável. Sem mentalidade de produto, contratos viram apenas burocracia técnica.

---

## Arquitetura Híbrida de Armazenamento

### Por que Híbrido

A escolha entre monorepo e multi-repo para gestão de Data Products é frequentemente apresentada como binária, mas ambos os extremos têm problemas. Monorepo único mistura código de domínios distintos e dificulta isolamento de acesso. Multi-repo total fragmenta a descoberta — um consumidor procurando dados precisa adivinhar em qual de N repositórios procurar.

A solução adotada nesta plataforma é **híbrida e baseada em uma distinção conceitual**: contratos são interfaces públicas, código é implementação privada. Cada um vive onde sua natureza pede.

### Repositório Central de Contratos

Um repositório dedicado armazena **todos os contratos da organização** em formato YAML (padrão ODCS), organizados por domínio:

```
data-contracts/
├── domains/
│   ├── risco/
│   │   ├── exposicao-credito.yaml
│   │   └── default-prediction.yaml
│   ├── comunicacao-interna/
│   │   └── engajamento-comunicados.yaml
│   └── marketing/
│       └── attribution.yaml
├── CODEOWNERS
└── README.md
```

Características:

- **Visível para todos os times da organização** — qualquer pessoa pode descobrir contratos existentes, ler especificações, propor consumo
- **Modificável apenas pelos owners de cada domínio** — o arquivo `CODEOWNERS` garante que mudanças em `domains/risco/` só são aprovadas pelo time de Risco
- **Versionado e auditável** — todo o histórico de mudanças nos contratos é preservado pelo Git
- **Source of truth dos contratos** — a plataforma sincroniza a partir daqui, não o contrário

### Repositórios de Produtos por Domínio

Cada domínio tem seu próprio repositório contendo o **código** dos seus Data Products:

```
risco-data-products/
├── exposicao-credito/
│   ├── pipeline/         # Código de transformação
│   ├── tests/            # Testes específicos
│   ├── infrastructure/   # IaC se aplicável
│   └── README.md
└── default-prediction/
    ├── pipeline/
    └── tests/
```

Características:

- **Acesso restrito aos times do domínio** — outros times não leem nem modificam o código alheio
- **Ciclo de vida independente** — releases, CI/CD e versionamento próprios
- **Referencia contratos do repositório central** — o pipeline declara qual contrato e qual versão ele cumpre
- **Autonomia de implementação** — o time de Risco escolhe sua stack (Spark, dbt, Airflow) sem afetar outros domínios

### Papel do Postgres na Plataforma

O repositório central de contratos é o source of truth, mas Git é um meio ruim para queries ricas, dashboards e UI. A plataforma resolve isso indexando o conteúdo dos contratos em **Postgres**, que serve como camada de leitura performática.

Modelo de dados conceitual:

```
- domains              (id, name, owner, ...)
- data_products        (id, name, domain_id, tier, owner, code_repo_url, ...)
- data_contracts       (id, product_id, version, tier, yaml_content, status, ...)
- contract_versions    (id, contract_id, version, yaml_content, created_at, ...)
- input_ports          (id, product_id, references_contract_id, ...)
- output_ports         (id, product_id, contract_id, port_type, ...)
- consumers            (id, contract_id, consumer_name, registered_at, ...)
- approvals            (id, contract_id, version, approver, status, ...)
- quality_violations   (id, contract_id, rule_name, occurred_at, ...)
```

Sincronização é bidirecional:

- **Quando um contrato é criado/editado pela UI**, a plataforma escreve no Postgres e abre PR no repositório central de contratos
- **Quando um contrato é editado diretamente via Git**, um webhook notifica a plataforma, que reindexa o Postgres

O Git permanece como source of truth; o Postgres é cache indexado para a aplicação.

---

## Sistema de Tiers

### Por que Tiers Existem

A tentação inicial é definir um padrão único de contrato e aplicar a tudo. Isso falha por dois motivos opostos: aplicar rigor máximo a tudo cria overhead que mata adoção; aplicar rigor mínimo a tudo deixa dados críticos sem proteção.

A solução é classificar Data Products em **tiers** com expectativas explicitamente diferentes de rigor, processo e governança. Tier não é uma pasta física no repositório — é um **atributo** que governa o comportamento da plataforma para aquele produto: quais campos são obrigatórios no contrato, quem precisa aprovar mudanças, quais SLAs mínimos são exigidos, qual janela de notificação para mudanças breaking.

### Definição dos Tiers

| Tier | Nome | Critério Principal |
|------|------|--------------------|
| **1** | Critical / Regulated | Erro pode causar consequência legal, regulatória ou financeira material |
| **2** | Business Important | Erro pode levar a decisão de negócio errada relevante, sem implicação regulatória |
| **3** | Operational / Internal | Erro tem impacto limitado, gerenciável via processo informal |
| **4** | Experimental / Sandbox | Em fase de descoberta; não permite consumidores em produção |

Cada tier define progressivamente menos requisitos:

**Tier 1 — Critical / Regulated**

- Schema fortemente tipado e validado em runtime
- Regras de qualidade exaustivas (não apenas estruturais; também estatísticas e de reconciliação)
- SLA com penalidades formais e janelas de detecção/correção curtas
- Janela de deprecation longa (180+ dias)
- Aprovação multi-stakeholder obrigatória para qualquer mudança
- Lineage rastreável de ponta a ponta
- Auditoria completa de mudanças
- Versionamento imutável (reprodutibilidade histórica)

**Tier 2 — Business Important**

- Schema bem definido com validações principais
- Regras de qualidade moderadas (foco em campos críticos para negócio)
- SLA monitorado mas sem penalidades formais
- Janela de deprecation média (60-90 dias)
- Aprovação por owner mais um stakeholder relevante
- Lineage documentado para os principais campos
- Retention de médio prazo

**Tier 3 — Operational / Internal**

- Schema com validações básicas (não-nulos, tipos)
- Regras de qualidade mínimas (campos críticos não-nulos, ranges óbvios)
- SLA "best effort" documentado
- Janela de deprecation curta (30 dias) ou nenhuma para mudanças aditivas
- Aprovação simples (owner do produto)
- Sem auditoria formal
- Retention curta

**Tier 4 — Experimental / Sandbox**

- Schema opcional ou em rascunho
- Regras de qualidade não-obrigatórias
- Sem SLA formal
- Mudanças livres
- Sem aprovação formal
- **Regra dura**: produtos Tier 4 não podem ter consumidores em produção

### Como Classificar um Produto

A classificação não é decidida por preferência técnica, mas pelo impacto de erros. A plataforma guia o usuário com perguntas de negócio durante a criação:

1. **Um erro neste dado pode resultar em consequência regulatória, multa ou processo legal?**\
   Se sim → **Tier 1**

2. **Um erro neste dado pode levar a uma decisão de negócio errada com impacto financeiro mensurável?**\
   Se sim → **Tier 2**

3. **Um erro neste dado é detectável e corrigível com processo informal, sem dano material?**\
   Se sim → **Tier 3**

4. **Este dado existe para exploração ou validação de hipótese, sem dependentes em produção?**\
   Se sim → **Tier 4**

Um produto sobe de tier conforme ganha consumidores críticos, e essa transição deve ser explícita — não silenciosa. A plataforma registra mudanças de classificação e exige re-aprovação quando relevante.

---

## Fluxo de Criação de um Data Product

O fluxo abaixo descreve como um usuário de uma área (por exemplo, Marketing) cria um novo Data Product na plataforma. Note que o usuário **não interage diretamente com Git** na maior parte do fluxo — a plataforma abstrai a complexidade.

**1. Iniciação**\
O usuário acessa a plataforma e seleciona "Criar novo Data Product". Preenche metadados básicos (nome, propósito, contexto de negócio) e identifica o domínio (Marketing).

**2. Classificação por tier**\
A plataforma faz perguntas de negócio que classificam o tier automaticamente. O usuário pode questionar a classificação, mas a sugestão é baseada em impacto, não preferência.

**3. Definição do contrato (output ports)**\
A UI guia o usuário pela definição de schema, regras de qualidade, SLA e demais campos exigidos pelo tier. Para cada output port (forma de exposição — tabela Delta, API, evento), um contrato específico é gerado. O YAML é renderizado em tempo real.

**4. Declaração de input ports**\
O usuário busca, no catálogo da plataforma, contratos de outros produtos que serão consumidos. A plataforma registra essas dependências formalmente — o que automaticamente inclui o novo produto na lista de consumidores notificados de futuras mudanças nos produtos upstream.

**5. Submissão**\
Ao submeter, a plataforma realiza duas operações coordenadas:
- Cria um **PR no repositório central de contratos** (`data-contracts/domains/marketing/`) com os YAMLs gerados
- Cria (ou prepara) **estrutura no repositório de produtos do domínio** (`marketing-data-products/`) para receber o código

**6. Aprovação**\
O PR no repositório central segue o fluxo de aprovação correspondente ao tier. Para Tier 1, owners do domínio + governance + compliance precisam aprovar. Para Tier 3, apenas o owner do produto. A plataforma gerencia notificações e SLA de aprovação.

**7. Implementação**\
Após aprovação do contrato, um engenheiro do domínio implementa o pipeline no repositório de produtos do domínio. O código declara qual contrato e qual versão cumpre. A plataforma valida em CI que o pipeline efetivamente cumpre o contrato declarado.

**8. Publicação e descoberta**\
Quando o pipeline está funcional e validações passam, o produto é publicado. A partir desse momento, **outros times veem o produto no catálogo** da plataforma — podem ler o contrato (estrutura, semântica, SLA), podem se registrar como consumidores, mas **não veem o código**.

**9. Operação contínua**\
Em produção, dados são validados continuamente contra as regras de qualidade do contrato. Violações geram alertas conforme severidade e tier. Mudanças no contrato seguem a política de evolução do tier correspondente.

---

## Estrutura do Repositório da Plataforma

Este repositório (`data_mesh_plt`) contém o **código da plataforma**, não os contratos ou produtos em si:

```
.
├── backend/              # API e lógica da plataforma
├── frontend/             # Interface web
├── database/             # Migrations e schema do Postgres
├── scripts/              # Scripts auxiliares
├── tests/                # Testes da plataforma
├── docs/                 # Documentação técnica
├── .github/workflows/    # CI/CD da plataforma
├── docker-compose.yml    # Orquestração local
├── dockerfile            # Build da plataforma
└── README.md             # Este arquivo
```

Os contratos e produtos vivem em **repositórios separados**, gerenciados pela plataforma:

- `data-contracts` (repositório central de contratos)
- `<dominio>-data-products` (um repositório por domínio para o código)

---

## Política de Evolução

Toda mudança em um contrato cai em uma de três categorias:

**Mudanças não-breaking (aditivas)**\
Adicionar coluna com default, adicionar valor a enum opcional, relaxar constraint, aumentar tamanho de campo. Incrementam a versão **MINOR**.

**Mudanças breaking (incompatíveis)**\
Renomear ou remover coluna, mudar tipo, tornar campo opcional em obrigatório, mudar significado semântico. Incrementam a versão **MAJOR**.

**Mudanças semânticas silenciosas**\
Schema igual, significado diferente. Tecnicamente o contrato não é violado, mas o comportamento esperado mudou. **Proibido** em qualquer tier — toda mudança semântica deve ser refletida no contrato.

A política específica de cada tier (janelas de notificação, deprecation, aprovações) é aplicada automaticamente pela plataforma com base no atributo `tier` do produto.

---

## Decisões de Design e Trade-offs

Algumas escolhas merecem registro explícito porque envolvem trade-offs reais:

**Por que armazenamento híbrido (Git central de contratos + Git por domínio para código + Postgres como cache)?**\
Cada elemento serve um propósito distinto. Git central permite descoberta e versionamento auditável dos contratos enquanto interfaces públicas. Git por domínio garante isolamento e autonomia do código. Postgres viabiliza queries ricas e UI performática que Git sozinho não oferece. Tentar usar uma única ferramenta para os três papéis sacrifica algo importante.

**Por que tiers como atributos e não como pastas?**\
Tiers governam comportamento (regras, aprovações, SLAs), não localização física. Implementar como atributo permite mudança de classificação sem mover arquivos, queries por tier no Postgres, e aplicação consistente das regras independentemente da estrutura de pastas.

**Por que ODCS e não um formato customizado?**\
Padrões abertos têm ecossistema (ferramentas, validadores, exemplos) que economiza meses de trabalho. Customização incremental é viável; reinvenção total raramente compensa.

**Por que YAML e não JSON Schema puro?**\
YAML é mais legível para humanos e suporta comentários. Como contratos são lidos por humanos durante revisões, YAML ganha. Validação interna ainda usa JSON Schema sob o capô.

**Por que contratos são públicos mas código é privado?**\
Contratos são interfaces — sua proposta de valor é serem descobríveis. Esconder contratos derrota o propósito do Data Mesh. Código é implementação — sua proposta de valor é autonomia do time dono. Misturar os dois é o erro mais comum em arquiteturas de dados distribuídos.

**Por que a plataforma como camada de orquestração e não como source of truth?**\
A plataforma facilita, mas não deve ser indispensável. Engenheiros avançados precisam poder operar via Git diretamente quando faz sentido (CI/CD de pipelines, automações). Tornar a plataforma o único caminho cria atrito desnecessário e leva a workarounds que ela não consegue governar.

---

## Referências

Conceitos, padrões e implementações que informaram este projeto:

- **Open Data Contract Standard (ODCS)** — [bitol-io.github.io/open-data-contract-standard](https://bitol-io.github.io/open-data-contract-standard/)
- **Data Mesh: Delivering Data-Driven Value at Scale** — Zhamak Dehghani (O'Reilly, 2022)
- **Data Contracts: Developing Production-Grade Data Pipelines** — Chad Sanderson, Mark Freeman, B.E. Schmidt (O'Reilly, 2025)
- **Driving Data Quality with Data Contracts** — Andrew Jones (Packt)
- **An Engineer's Guide to Data Contracts** — Chad Sanderson e Adrian Kreuziger
- **Data Mesh Principles and Logical Architecture** — Zhamak Dehghani (martinfowler.com)

---

_Este projeto é uma implementação de referência para fins de aprendizado e demonstração. Os conceitos são aplicáveis em contextos corporativos com adaptações de escala e governança._

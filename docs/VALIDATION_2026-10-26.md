# Validação do Harness no Databricks — 26/10/2026

## Escopo da evidência

Execução **manual e somente leitura**, no Databricks Free Edition, dos módulos
`harness.core`, `harness.databricks` e `harness.coverage_v2` e de uma
checagem de linhagem por hashes e contrato. Os resultados desta página são
**saídas do workspace informadas pelo operador** e preservadas aqui para
rastreabilidade; o GitHub Actions não acessou esse workspace para reproduzi-los.

- Repositório: `AlexandreSantosRodrigues/oil-gas-production-lakehouse`.
- Escopo publicado: `historico_anp_v2`.
- Contrato de leitura: `aea99472-c0f7-4fb7-b8b6-e2336f272fc4`.
- Check estrutural: `6629c509-a338-4933-8e97-e0ad5c2bb98c`.
- Check de cobertura original: `e31b28e1-fdd1-439a-92ea-b42e24197bad`.
- Reconciliação Silver: `5186fc62-65c2-473d-af27-d294b08cbb78`.
- Check de escopo Gold: `e6a5a17b-62b0-4458-9afb-7b73dc60ed2d`.
- Lote de ingestão estrutural: `1eddf192-e8eb-42eb-b26c-b6227916c739`.

## 1. Harness original: alertas preservados

| Auditoria Ops | Aprovadas | Pendentes | Total |
| --- | ---: | ---: | ---: |
| Estrutura dos CSVs | 14 | 1 | 15 |
| Cobertura Bronze (regra original) | 10 | 3 | 13 |
| Reconciliação Bronze/CSV ↔ Silver | 169 | 0 | 169 |
| Verificações de publicação Gold | 3 | 0 | 3 |
| **Total** | **196** | **4** | **200** |

O `export_snapshot(...)` e o `evaluate(...)` retornaram:

```text
Status: BLOCK
checked_rows: {structure: 15, coverage: 13, silver: 169, published: 3}
issues: 4
```

As quatro pendências são **REVIEW** (nenhuma linha da tabela Silver de
reconciliação foi reportada como FAIL):

1. `producao_por_poco_terra_2025_4_trim.csv`: layout diferente do piloto.
2. Mesmo arquivo: 30.123 competências rejeitadas pelo parser **antigo**,
   apesar de 30.123/30.123 registros encontrados.
3. `producao_por_poco_terra_2026_1_trim.csv`: 657 chaves classificadas
   como incompletas, com 20.389/20.389 registros encontrados.
4. `producao_por_poco_terra_2026_2_trim.csv`: 459 chaves classificadas
   como incompletas, com 15.486/15.486 registros encontrados.

A auditoria antiga só aceitava meses em `MM/AAAA` e considerava
`instalacao` obrigatória. A Silver v2 aceita também meses abreviados em
português (`out/2025`, `nov/2025`, `dez/2025`) e preserva a instalação
ausente com `status_instalacao = AUSENTE`. Portanto, essas regras não são
equivalentes. **Os REVIEW históricos não foram modificados nem apagados.**

## 2. Auditoria corretiva de cobertura Bronze

Foi executado no workspace:

```python
from harness.coverage_v2 import audit_bronze

report = audit_bronze(
    spark,
    contract_run_id="aea99472-c0f7-4fb7-b8b6-e2336f272fc4",
    expected_files=13,
    expected_missing_installation=1116,
)
```

Saída relatada:

```text
STATUS: PASS
ARQUIVOS: 13
INSTALAÇÕES AUSENTES: 1116
PROBLEMAS: []
```

Todos os 13 arquivos de produção passaram, somando **315.356 registros**:
43.919 marítimos e 271.437 terrestres. Foram identificadas 657 instalações
ausentes no 1º trimestre de 2026 e 459 no 2º trimestre de 2026, totalizando
1.116 registros preservados, sem imputação de valores nem exclusão de linhas.

O arquivo `producao_por_poco_terra_2025_4_trim.csv` passou com seus
30.123 registros na auditoria corrigida; a execução não reportou competências
inválidas ou identificadores essenciais ausentes.

**Interpretação:** `PASS` nesta auditoria significa que os 13 arquivos
contratados atendem às condições de cobertura implementadas na v2.
Não modifica os resultados da auditoria antiga e não autoriza, isoladamente,
publicação ou alteração de dados.

## 3. Correspondência de hashes, layout e escopo publicado

Uma célula independente, somente leitura, comparou
`source_file_read_contracts`,
`source_file_structure_checks` e
`analytical_scope_sources` por pares `(dataset, source_file_sha256)`,
usando os IDs explícitos acima. Também validou as listas de colunas
normalizadas, a ordem do layout, `regra_alinhamento`, os identificadores
de check e ingestão e as sinalizações básicas de integridade estrutural.

```text
Contratos: 15
Auditorias estruturais: 15
Fontes no escopo publicado: 16
Hashes contrato × estrutura: True
Hashes contrato × Gold: True
Arquivos com ordem diferente:
  ['producao_por_poco_terra_2025_4_trim.csv']
Problemas: []
STATUS FINAL: PASS
```

O escopo `historico_anp_v2` contém 15 arquivos correspondentes ao contrato
(produção e intervenções) e **um** snapshot cadastral
`situacao_pocos`, totalizando 16. A alteração do arquivo de 2025/Q4
foi identificada como uma mudança de **ordem**, mantendo o conjunto de
nomes normalizados e a regra de alinhamento por nome.

**Interpretação:** a composição do contrato coincide com a lista de
conteúdos do escopo Gold; a auditoria manual não foi concebida para
demonstrar equivalência linha a linha entre todos os estágios nem para
substituir reconciliações independentes.

## 4. Testes automatizados do código

O workflow de GitHub Actions **Read-only Harness Quality Checks**
executou 27 testes offline com dados sintéticos e concluiu com sucesso:

- [Execução do CI](https://github.com/AlexandreSantosRodrigues/oil-gas-production-lakehouse/actions/runs/40333571887).
- [Implementação da auditoria v2 — PR #2](https://github.com/AlexandreSantosRodrigues/oil-gas-production-lakehouse/pull/2).

Essa execução de CI verifica o código do harness, **não** as tabelas reais
do Databricks. A execução real foi realizada manualmente e reportada acima.

## 5. Encerramento da versão

**Aceitação desta versão:** a auditoria corretiva Bronze v2 e a verificação
manual de hashes/layout produziram `PASS`, as 169 reconciliações Silver
e as três verificações Gold estavam `PASS` no conjunto de auditorias
selecionado, e os testes automatizados passaram.

**Ressalvas preservadas:** o Quality Gate original permanece em `BLOCK`
ao avaliar os `REVIEW` históricos. A aprovação da auditoria corrigida
não é um mecanismo de waiver automático, nem prova reprodução integral
do pipeline em um workspace limpo, orquestração em produção ou autonomia
do agente para corrigir/publicar dados.

Nenhum notebook existente, dado bruto, tabela Delta ou view foi alterado
pelos testes descritos aqui. Futuras mudanças de escopo exigem uma nova
base de comparação; os limites de 13 arquivos e 1.116 instalações ausentes
se aplicam ao histórico verificado, não a novas coletas.

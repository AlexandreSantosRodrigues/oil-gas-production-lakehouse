# Próximo teste: repetibilidade da evidência histórica com IDs fixos

Base analisada: main em d42c449e2edad46e5395be9912d0156b9b81e70e (PR #3).

## Decisão por impacto e esforço

1. **Agora, baixo esforço:** executar duas leituras das auditorias Ops fixadas,
   com cardinalidades explícitas, avaliação independente do gate e cobertura
   Bronze v2. Detecta evidência faltante, alteração entre leituras e regressão
   das regras sem reexecutar ingestão. O resultado esperado é diagnóstico PASS
   coexistindo com gate histórico BLOCK. Não resolve nem substitui os REVIEW.
2. **Depois, esforço médio:** transformar a célula manual de linhagem em módulo
   testável, verificando contrato × estrutura × escopo por multiconjuntos de
   (dataset, SHA-256), os 15 contratos, 16 fontes (uma cadastral), ausência de
   duplicações, IDs de ingestão/check, permutação de cabeçalhos normalizados
   sem nomes repetidos e alinhamento por nome. Testar hash trocado, fonte
   faltante/duplicada e coluna removida. O PR #3 documenta a saída da célula,
   mas não inclui essa implementação reutilizável. Não inventar seus detalhes
   de schema: inspecionar os contratos reais antes de implementá-la.
3. **Depois, esforço alto:** reprodução integral em workspace isolado e vazio.
   Isso exige escrita e está fora desta etapa. Em somente leitura, podemos
   identificar dependências, mas não provar a recriação de tabelas/views.

A leitura dos notebooks mostrou seleção de contrato por data mais recente,
IDs históricos fixos e dependências de variáveis de células anteriores. O README
já reconhece essas restrições. Rodar novamente apenas o CI sintético não testa
essas dependências; executar os notebooks inteiros violaria o escopo read-only.

## Execução autorizável somente leitura (ainda não executada no workspace)

Pré-condições: repo disponível em um Git folder Databricks, Python compatível,
Spark ativo, acesso SELECT aos quatro conjuntos Ops, contratos e duas tabelas
Bronze usadas por `audit_bronze`. Sem permissões de escrita para esta execução.
Escolher uma janela sem alterações concorrentes; duas leituras iguais não são
uma transação consistente entre múltiplas tabelas. Se necessário, definir antes
versões Delta explícitas por tabela; o bridge atual não fixa essas versões.

Em uma sessão Python existente, com a raiz do repo no sys.path, executar:

```python
import json
from scripts.verify_historical_readonly import verify
receipt = verify(spark)
print(json.dumps(receipt, indent=2, ensure_ascii=False))
```

O código usa os cinco IDs documentados em VALIDATION_2026-10-26.md, não MAX(data).
Não executar os notebooks 01/02 nem células de criação ou publicação. O script
não grava tabelas, arquivos ou recibos: imprime o resultado. Preservar a saída
manualmente no registro da execução junto com commit Git e runtime utilizados.
Não enviar metadados Ops ao GitHub automaticamente.

Critérios desta etapa:

- 15/13/169/3 linhas de auditoria; quatro REVIEW (1 estrutural, 3 cobertura).
- Gate histórico BLOCK, sem outros erros; cobertura v2 PASS, 13 arquivos,
  1.116 instalações ausentes no contrato fixado.
- Mesmo hash canônico das duas extrações Ops; a ordem do collect é irrelevante,
  mas multiplicidade e conteúdo das linhas são preservados.
- `publication_allowed=false` e `clean_workspace_replay_proven=false`.
- Qualquer divergência interrompe o diagnóstico. Investigar; não reclassificar
  status nem baixar limites para obter verde.

Limites: o teste compara categorias/contagens dos REVIEW, não suas identidades
históricas completas. Não reabre CSVs brutos para conferir hashes, não reconcilia
linha a linha a Silver e não fixa versões Delta. A cobertura Bronze é lida uma
vez. Essas lacunas permanecem explícitas; não há aprovação geral de publicação.

## Arquivos

Nesta etapa: `scripts/verify_historical_readonly.py` (diagnóstico),
`tests/test_historical_readonly.py` (regressões sintéticas), este roteiro,
`docs/HARNESS.md` (referência) e `.github/workflows/harness-quality.yml`
(gatilhos e compilação incluindo scripts). Nenhum notebook/dado é modificado.

Próxima implementação, apenas proposta: `harness/lineage.py`,
`tests/test_lineage.py`, extensão do script e documentação das colunas/versões
fixadas. Para reprodução limpa futura: primeiro especificar configuração única
para catálogo/schema/Volume, manifesto imutável de fontes e hashes, contrato e
escopo, runtime/dependências e ordem de execução; só depois revisar os notebooks
01/02. Critério futuro: duas execuções isoladas com as mesmas entradas e igualdade
de contagens, chaves, nulos, zeros e totais por medida, sem duplicação no rerun.

O verde do GitHub significa aprovação dos testes offline, inclusive a proteção
do BLOCK histórico. Não significa que o Databricks foi acessado pelo CI.

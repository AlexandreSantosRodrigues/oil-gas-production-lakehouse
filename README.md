# Oil & Gas Production Lakehouse — ANP

**Status: projeto em desenvolvimento.** As funcionalidades abaixo representam o escopo planejado; os pipelines e indicadores ainda não foram implementados ou validados.

Lakehouse analítico de produção de petróleo e gás natural no Brasil, desenvolvido no Databricks com dados públicos da Agência Nacional do Petróleo, Gás Natural e Biocombustíveis (ANP).

## Objetivo

Investigar a evolução da produção, a contribuição dos poços para os resultados dos campos e o comportamento observado antes e depois de intervenções. Comparações temporais não demonstram, isoladamente, relação de causa e efeito.

## Escopo planejado

- Ingestão de arquivos históricos e cadastrais com rastreabilidade de origem e execução.
- Camadas Bronze, Silver e Gold em Delta Lake.
- Padronização de unidades, tipos, identificadores e granularidades.
- Tratamento de duplicidades, registros rejeitados e revisões da fonte.
- Data warehouse dimensional com fatos de produção, intervenções e atividade de sondas.
- Dimensões de tempo, poço, campo, bacia, operador e localização, conforme os dados disponíveis.
- Histórico cadastral a partir das alterações observadas nas coletas; sem presumir histórico anterior não publicado.
- Validações de qualidade, reconciliação de totais e execução incremental idempotente.
- Dashboards para análise de produção, concentração, variações e qualidade dos dados.

## Stack planejada

Databricks Free Edition, Python, PySpark, SQL, Delta Lake, Unity Catalog, Lakeflow Jobs e visualizações no Databricks. A compatibilidade dos recursos será validada no workspace durante a implementação.

O projeto será desenvolvido pelo navegador, respeitando as cotas do ambiente gratuito. O acesso direto às URLs da fonte será verificado antes da definição do mecanismo definitivo de ingestão.

## Fonte oficial

[ANP — Fase de Desenvolvimento e Produção](https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/fase-de-desenvolvimento-e-producao)

A cobertura temporal, a periodicidade e as chaves de cada conjunto serão documentadas após a inspeção dos arquivos e metadados.

## Etapas

- [x] Criação do repositório e definição inicial do escopo.
- [ ] Diagnóstico do ambiente Databricks.
- [ ] Inventário das fontes e inspeção dos metadados.
- [ ] Prova de ingestão e definição das granularidades.
- [ ] Implementação Bronze e controles de ingestão.
- [ ] Implementação Silver e regras de qualidade.
- [ ] Modelagem dimensional Gold.
- [ ] Análises, dashboards e orquestração.
- [ ] Documentação dos resultados e limitações.

Os notebooks serão construídos e validados progressivamente, uma célula por vez.

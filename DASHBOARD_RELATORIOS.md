# Dashboard e relatório mensal

O painel fica na página inicial após o login. Administradores e operadores
consultam os mesmos dados da organização. Escolha o mês pelo campo de referência
ou pelas setas. O endereço também aceita `/?mes=2026-11`.

## O que cada número significa

- **Saldo acumulado:** saldo inicial das contas ativas mais todos os seus
  lançamentos realizados. Não muda ao selecionar outro mês. Não é um saldo
  histórico de fechamento; a data de um registro marcado como realizado não
  impede que ele componha esse saldo.
- **Receitas, despesas e resultado:** apenas lançamentos realizados no mês
  selecionado, incluindo contas desativadas para preservar o histórico.
  Transferências ficam fora dessas métricas.
- **A receber e a pagar:** lançamentos previstos para o mês selecionado,
  ainda não realizados. Não são somados ao resultado realizado.
- **Maiores despesas:** cinco categorias com maior gasto realizado no mês,
  com o número de lançamentos de cada grupo. Sem categoria também é um grupo.
  Subcategorias aparecem separadamente; o valor não é somado novamente no pai.
- **Evolução:** mês selecionado e os cinco anteriores. Meses sem movimento
  aparecem zerados. Transferências e valores previstos ficam fora.
- **Orçamentos:** limites e gastos realizados do mês, compartilhados pela equipe.
- **Últimos lançamentos:** oito registros mais recentes do mês selecionado,
  incluindo previstos e transferências devidamente identificados.

Todas as consultas começam pelo filtro da organização. O ranking e a evolução
usam agregações no banco (`Sum`, `Count`, `TruncMonth`), sem consultar cada mês
separadamente. As regras das métricas ficam em `finance/reports.py`; o resumo
mensal existente continua em `finance/services.py`.

## Exportação CSV

Use **Exportar mês (CSV)** no painel. A rota é
`/lancamentos/exportar/?mes=2026-11`, exige login e perfil válido e aceita GET.

O arquivo contém todos os lançamentos da organização naquele mês, em ordem de
data e ID. Inclui realizados, previstos e as duas movimentações de transferências,
com colunas para diferenciá-los. Receitas têm valor positivo; despesas, negativo.
Para reproduzir o resumo do painel, filtre `Situação = Realizado` e
`Transferência = Não` antes de somar.

O CSV usa ponto e vírgula, decimal com vírgula e UTF-8 com BOM para preservar
acentos no Excel. Textos que poderiam iniciar fórmulas recebem um apóstrofo.
Essa proteção só altera o arquivo exportado, não os dados salvos.
Se a planilha pedir opções de importação, selecione UTF-8 e separador `;`.

Não há alteração de models, dependências ou migrações neste bloco.

## Conferência manual

1. Faça login e selecione um mês com lançamentos.
2. Registre uma despesa realizada e confira resumo, ranking e evolução.
3. Registre uma despesa prevista e confira apenas o valor a pagar.
4. Faça uma transferência: ela altera saldos por conta, mas não receitas/despesas.
5. Troque de mês: resumo, ranking, pendências, orçamentos e últimos lançamentos mudam;
   saldo acumulado permanece igual.
6. Exporte o mês e compare registros e valores com a tela.
7. Entre com outro membro da mesma organização: os números são compartilhados.
   Com usuário de outra organização, os registros anteriores não aparecem.

Teste automatizado específico: `python manage.py test finance.test_reports`.
Suíte completa: `python manage.py test`.

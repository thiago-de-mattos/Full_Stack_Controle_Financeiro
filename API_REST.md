# API REST financeira

## Acesso e permissões

Faça login pela aplicação ou por `/api-auth/login/`. A API usa a sessão do Django.
No navegador, use a interface do DRF em `/api/contas/`, `/api/categorias/`,
`/api/lancamentos/` e `/api/orcamentos/`. Requisições de escrita autenticadas
por sessão exigem CSRF; os formulários da interface do DRF já o enviam.

Administrador e operador consultam, cadastram e editam. Somente administrador
exclui. Todas as consultas e escolhas de relacionamentos são limitadas à
organização do perfil. O criador é preservado ao editar o registro.
O papel de administrador da organização não concede acesso ao Django Admin.

## Endpoints

| Recurso | Lista e criação | Detalhe, edição e exclusão |
| --- | --- | --- |
| Contas | GET/POST `/api/contas/` | GET/PUT/PATCH/DELETE `/api/contas/<id>/` |
| Categorias | GET/POST `/api/categorias/` | GET/PUT/PATCH/DELETE `/api/categorias/<id>/` |
| Lançamentos | GET/POST `/api/lancamentos/` | GET/PUT/PATCH/DELETE `/api/lancamentos/<id>/` |
| Orçamentos | GET/POST `/api/orcamentos/` | GET/PUT/PATCH/DELETE `/api/orcamentos/<id>/` |
| Transferências | POST `/api/transferencias/` | Consulte as movimentações em `/api/lancamentos/` |

As listas retornam arrays JSON, sem paginação nesta etapa. Use PATCH para
alterar alguns campos; PUT exige os campos obrigatórios do recurso.
Os relacionamentos usam IDs. Substitua os IDs de exemplo pelos retornados
pela API da sua organização.

## Exemplos de criação

Categoria (`POST /api/categorias/`):

```json
{"name":"Transporte","kind":"expense","parent":null,"is_active":true}
```

Lançamento (`POST /api/lancamentos/`):

```json
{
  "account": 1,
  "category": 2,
  "kind": "expense",
  "amount": "25.00",
  "date": "2026-11-25",
  "description": "Transporte",
  "notes": "",
  "is_settled": true
}
```

Orçamento (`POST /api/orcamentos/`):

```json
{"category":2,"month":"2026-11","limit_amount":"300.00"}
```

O mês também aceita uma data completa e é normalizado para o primeiro dia.
O retorno desse recurso contém os campos cadastrados; as métricas de gasto
continuam sendo calculadas no dashboard.

Transferência (`POST /api/transferencias/`):

```json
{
  "from_account": 1,
  "to_account": 3,
  "amount": "50.00",
  "date": "2026-11-25",
  "description": "Transferência entre contas"
}
```

A resposta 201 contém `saida` e `entrada`, cada uma com os dados e o ID de seu
lançamento. O saldo total não muda. As duas movimentações são gravadas na
mesma transação: uma falha impede que fique apenas uma delas.

Para excluir a transferência, um administrador envia DELETE para o endpoint
de qualquer uma de suas movimentações, `/api/lancamentos/<id>/`.
O serviço remove as duas. PUT/PATCH de uma movimentação de transferência
retorna 400; para corrigir, exclua a transferência e registre novamente.

## Validação

- Nomes de contas e categorias não podem se repetir na mesma organização;
  categorias distinguem receita e despesa. Maiúsculas e minúsculas são ignoradas.
- Categoria pai precisa pertencer à organização e ter o mesmo tipo.
  Não é permitido criar ciclos na hierarquia.
- Alterar o tipo de categoria não pode invalidar subcategorias, lançamentos ou orçamentos.
- Valor de lançamento, transferência e limite do orçamento devem ser positivos.
- Categoria do lançamento precisa corresponder ao tipo receita/despesa.
- Orçamento exige categoria de despesa e não pode repetir categoria e mês na organização.
- Contas e categorias inativas não podem ser escolhidas para novos lançamentos.
  Vínculos antigos podem ser mantidos durante a edição de registros históricos.
- Contas e categorias com lançamentos vinculados não podem ser excluídas.
- `user`, `organization`, `role`, `transfer_group` e outros campos internos não são editáveis.

Formulários e serializers compartilham as regras em `finance/validators.py`
e `budget/validators.py`. O filtro de organização e o tratamento dos erros
de gravação ficam em `core/api.py`; as permissões continuam em `finance/permissions.py`.

## Respostas

| Status | Significado |
| --- | --- |
| 200 | Consulta ou atualização concluída |
| 201 | Registro criado |
| 204 | Registro excluído, sem corpo de resposta |
| 400 | Dados inválidos, exclusão protegida ou conflito de gravação |
| 403 | Sem autenticação/perfil válido ou sem permissão para a operação |
| 404 | Registro inexistente ou fora da organização |
| 405 | Método não disponível no endpoint |

Para executar as verificações:

```bash
python manage.py check
python manage.py test
```

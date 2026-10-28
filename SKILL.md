---
name: rca-incidentes
description: >-
  Análise de causa raiz (RCA) de incidente, sem culpados. Coleta a evidência somente em leitura
  (alarmes do CloudWatch, CloudTrail, AWS Health, Logs Insights, Activity Log da Azure), monta a
  linha do tempo com a fonte de cada evento, calcula o tempo até detectar, mitigar e resolver,
  conduz os porquês até a causa sistêmica e gera um documento HTML autocontido, a figura SVG do
  caminho da falha e o backlog de ações com dono e prazo. Só usa a biblioteca padrão do Python.
  Use quando pedirem RCA, post-mortem, pós-incidente, análise de causa raiz, relatório de
  incidente, ou quiserem entender por que algo caiu, atrasou ou perdeu dado em produção.
---

# rca-incidentes

Transforma um incidente em um documento de causa raiz auditável: cada evento da linha do tempo
tem fonte, cada ação tem dono e prazo, e a causa raiz é sistêmica, nunca uma pessoa.

## O fluxo

### 1. Recorte

Confirme com o usuário: qual incidente, ambiente, janela (do primeiro sinal até a resolução, com
folga de algumas horas antes) e quem tem as informações que não estão em log (chamado, canal do
incidente, nota de versão de fornecedor).

### 2. Evidência, somente em leitura

```bash
python <skill>/scripts/coleta_aws.py --perfil <perfil> --regiao sa-east-1 \
  --inicio 2026-10-19T12:00 --fim 2026-10-22T14:00 --saida coleta/ \
  --log-group /aws-glue/jobs/error --consulta "fields @timestamp, @message | filter @message like /ERROR/"
python <skill>/scripts/coleta_azure.py --assinatura <id> --grupo <rg> --inicio ... --fim ... --saida coleta/
```

Rode antes com `--dry-run`, que apenas imprime os comandos. O que não puder ser lido vira lacuna
e entra no documento. Nunca rode comando de escrita no ambiente durante um RCA. Detalhes e
permissões em `references/coleta.md`.

### 3. O incidente.json

Escreva o `incidente.json` na pasta do projeto, partindo de
`examples/empresa-exemplo/incidente.json`. Os campos e o método estão em `references/metodo.md`.
O essencial:

- `marcos`: início do impacto, detecção, reconhecimento, mitigação e resolução. Horário sem fuso
  é lido como horário de Brasília; o campo `fuso` (por exemplo `"Europe/Lisbon"`) troca o padrão.
- `linha_do_tempo`: apenas os eventos que explicam o incidente, cada um com `fonte`. Evento de
  coleta entra pelo `ref`; o documento não é despejo de log.
- `porques`: do sintoma até a causa sistêmica. Se a resposta for uma pessoa, pergunte por que o
  sistema permitiu.
- `acoes`: tipo `prevenir`, `detectar`, `mitigar` ou `processo`, prioridade P1 a P4, dono e prazo.
- `caminho_falha`: lista de `passos` do gatilho ao impacto, cada um `{"tipo": "no", "titulo",
  "sub", "nota", "alerta"}` ou `{"tipo": "seta", "rotulo", "alerta"}`. `alerta` (verdadeiro ou um
  texto curto) marca em vermelho o ponto em que o fluxo falhou.

### 4. Validar e montar

```bash
python <skill>/scripts/valida_incidente.py incidente.json
python <skill>/scripts/monta_rca.py incidente.json --saida out
```

O validador barra marco fora de ordem, evento sem fonte, ação sem dono ou prazo, causa raiz que
para em "erro humano", passo inválido no caminho da falha e travessão; avisa sobre linguagem de
culpa e sobre detecção lenta sem ação de detecção. O montador grava em `out/`:

| Arquivo | Conteúdo |
|---|---|
| `rca.html` | o documento, página única autocontida, com tema claro e escuro e versão para impressão |
| `caminho_falha.svg` | a figura do caminho da falha, também embutida no HTML |
| `linha_do_tempo.json` | a linha do tempo consolidada e ordenada |
| `backlog.json` | as ações com identificador, dono, prazo e status |

### 5. Conferir e entregar

Abra o `rca.html` no navegador e confira cada horário e número contra a evidência. Para PDF, use
imprimir no navegador. Entregue o documento, as métricas (tempo até detectar, mitigar, duração),
a causa raiz em uma frase e o backlog.

## Regras

1. Sem culpados. O documento fala de sistema, processo e decisão, nunca de quem errou.
2. Todo evento e todo número com fonte. O que não tem fonte é lacuna ou `[A CONFIRMAR]`.
3. Coleta somente em leitura. Correção não faz parte do RCA.
4. O incidente real fica na pasta do projeto, nunca neste repositório. O exemplo usa empresa
   fictícia.
5. Sem travessão: o validador recusa.

## Dependências

Python 3.8+ (só biblioteca padrão) e, para a coleta, AWS CLI ou Azure CLI autenticadas.

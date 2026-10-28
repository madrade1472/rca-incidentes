# Método

## Sem culpados

O RCA explica por que o sistema permitiu a falha. "O analista rodou o script errado" é o começo
da análise, não o fim: por que o script errado estava disponível, por que nada bloqueou, por que
ninguém percebeu. O validador recusa causa raiz que para em "erro humano" e avisa quando o texto
procura culpado.

## Severidade

| Nível | Quando |
|---|---|
| SEV1 | Indisponibilidade total ou perda de dado em produção, com impacto direto no negócio |
| SEV2 | Degradação severa ou funcionalidade crítica fora do ar para parte dos usuários |
| SEV3 | Degradação parcial com contorno disponível |
| SEV4 | Impacto mínimo, sem efeito percebido pelo usuário final |

## Marcos e métricas

| Marco | Quando é |
|---|---|
| `inicio_impacto` | o primeiro instante em que alguém foi afetado, mesmo sem saber |
| `deteccao` | alguém (ou um alarme) percebeu |
| `reconhecimento` | alguém assumiu o incidente |
| `mitigacao` | o impacto parou de crescer ou foi contornado |
| `resolucao` | o serviço voltou ao normal, inclusive com o dado reprocessado |

O montador calcula o tempo até detectar, até reconhecer, até mitigar e a duração do impacto. Um
tempo até detectar grande quase sempre pede ação do tipo `detectar`, e o validador avisa quando
ela falta. Marco que cai no mesmo minuto de um evento da linha do tempo vira prefixo dele, sem
linha repetida.

## Os porquês

Comece pelo sintoma que o usuário viu e pergunte por quê até chegar a algo que, corrigido,
impede a repetição de toda a classe do problema. Cinco é referência, não regra. Quando houver
duas cadeias (por que aconteceu e por que demorou para perceber), escreva as duas: a causa raiz
pode ter duas partes.

## Ações

| Tipo | Responde |
|---|---|
| `prevenir` | como impedir que aconteça de novo |
| `detectar` | como perceber em minutos, antes do usuário |
| `mitigar` | como reduzir o impacto quando acontecer |
| `processo` | runbook, plantão, comunicação, contrato com fornecedor |

Prioridade: P1 para o que fecha o risco imediato, P2 para o que impede a repetição, P3 e P4 para
melhorias. Toda ação tem dono (área ou papel) e prazo em data no formato dd/mm/aaaa. Status
aceitos: `aberta`, `em_andamento`, `concluida` e `cancelada`.

## Caminho da falha

Fluxo vertical do gatilho ao impacto percebido, sem ícones de provedores:

```json
"caminho_falha": {
  "passos": [
    { "tipo": "no", "titulo": "Origem", "sub": "o que mudou ali", "nota": "19/10 17:30" },
    { "tipo": "seta", "rotulo": "carga diária" },
    { "tipo": "seta", "rotulo": "job de transformação", "alerta": "FALHA" },
    { "tipo": "no", "titulo": "Destino", "sub": "o que o usuário viu", "alerta": true }
  ]
}
```

`no` é uma caixa com título e subtítulo; `nota` aparece ao lado dela. `seta` liga a caixa anterior
à seguinte, com `rotulo` ao lado. `alerta` marca em vermelho o ponto em que o fluxo falhou: com
`true`, a etiqueta é padrão; com um texto curto, ele vira a etiqueta. O texto longo quebra em
linhas automaticamente. `titulo` opcional dá nome à figura no arquivo SVG avulso.

## Campos do incidente.json

| Campo | Obrigatório | Conteúdo |
|---|---|---|
| `id`, `titulo`, `severidade`, `resumo` | sim | identificação e o resumo de um parágrafo |
| `marcos` | sim | ver acima; início, detecção e resolução obrigatórios |
| `impacto` | não | `descricao` e `numeros: [{rotulo, valor}]` |
| `linha_do_tempo` | não | `[{quando, fonte, evento, tipo, ref?}]` |
| `coleta` | não | pasta com a saída dos coletores, relativa ao incidente.json |
| `porques`, `causa_raiz` | sim | a cadeia e a conclusão |
| `fatores`, `funcionou`, `nao_funcionou`, `licoes` | não | listas de frases |
| `acoes` | sim | `[{titulo, tipo, prioridade, dono, prazo, status?, detalhe?}]` |
| `caminho_falha` | não | `{titulo?, passos: [...]}`, ver acima |
| `evidencias`, `lacunas` | não | `[{rotulo, ref}]` e lista de frases |
| `ambiente`, `autor`, `versao`, `data_documento`, `classificacao` | não | metadados do documento |
| `fuso`, `fuso_rotulo` | não | fuso IANA dos horários sem fuso (padrão `America/Sao_Paulo`) e como citá-lo no texto |

# Coleta de evidência

Tudo em leitura. Os coletores chamam a AWS CLI ou a Azure CLI com o perfil de quem executa e
gravam um JSON por fonte, já no formato de evento da linha do tempo (`quando`, `fonte`, `evento`,
`tipo`, `ref`). Rode sempre com `--dry-run` primeiro para ver os comandos.

## AWS (`coleta_aws.py`)

| Arquivo | Fonte | Permissão |
|---|---|---|
| `alarmes.json` | mudanças de estado dos alarmes do CloudWatch | `cloudwatch:DescribeAlarmHistory` |
| `cloudtrail.json` | chamadas de API de escrita no período | `cloudtrail:LookupEvents` |
| `health.json` | eventos do AWS Health | `health:DescribeEvents`, exige plano Business ou superior |
| `logs.json` | resultado de uma consulta do Logs Insights | `logs:StartQuery`, `logs:GetQueryResults` |

A política gerenciada `ReadOnlyAccess` cobre tudo. O `LookupEvents` do CloudTrail alcança apenas
90 dias e devolve no máximo `--max-cloudtrail` eventos; para janelas longas, estreite a janela.

## Azure (`coleta_azure.py`)

`activity_log.json` com as operações de escrita, as falhas e os alertas do Activity Log (inclusive
Service Health e Resource Health), no escopo da assinatura ou de um resource group. Papel `Reader`,
depois de `az login`.

## Lacunas

O que um coletor não consegue ler vai para `lacunas.json` na mesma pasta. O montador junta essas
lacunas às do incidente.json e as publica na seção Lacunas do documento.

## O que não está em log

Chamado, conversa do canal do incidente, nota de versão de fornecedor, relato de usuário. Entram na
`linha_do_tempo` do incidente.json com a fonte escrita por extenso ("Chamado no portal, 22/10
08:45"). Captura de tela também é evidência: cite o arquivo.

Material de coleta pode conter dado sensível: mantenha na pasta do projeto. O `.gitignore` deste
repositório ignora `coleta/` e `out/`.

# -*- coding: utf-8 -*-
"""Coleta a evidência de um incidente na AWS, somente leitura, pela AWS CLI.

Uso:
  python coleta_aws.py --perfil <perfil> --regiao sa-east-1 \\
      --inicio 2026-10-20T01:00 --fim 2026-10-22T10:00 --saida coleta/ \\
      [--log-group /aws-glue/jobs/error --consulta "fields @timestamp, @message | filter @message like /ERROR/"] \\
      [--dry-run]

Grava em --saida um JSON por fonte, todos no formato de evento da linha do tempo
({quando, fonte, evento, tipo, ref}):
  alarmes.json      mudanças de estado dos alarmes do CloudWatch (describe-alarm-history)
  cloudtrail.json   chamadas de API de escrita no período (lookup-events, ReadOnly=false)
  health.json       eventos do AWS Health da conta (exige plano Business ou superior; a falha vira lacuna)
  logs.json         resultado da consulta do Logs Insights, se --log-group e --consulta forem informados
  lacunas.json      o que não pôde ser lido, para entrar no documento

Horário sem fuso é lido como horário de Brasília. --dry-run apenas imprime os comandos, sem chamar nada.
Permissões: cloudwatch:DescribeAlarmHistory, cloudtrail:LookupEvents, health:DescribeEvents,
logs:StartQuery e logs:GetQueryResults. A política gerenciada ReadOnlyAccess cobre todas.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from comum import gravar_json, instante  # noqa: E402

ap = argparse.ArgumentParser(description="Coleta somente leitura de evidência de incidente na AWS.")
ap.add_argument("--perfil", required=True, help="perfil da AWS CLI")
ap.add_argument("--regiao", default="sa-east-1")
ap.add_argument("--inicio", required=True, help="início da janela, ISO 8601")
ap.add_argument("--fim", required=True, help="fim da janela, ISO 8601")
ap.add_argument("--saida", default="coleta")
ap.add_argument("--log-group")
ap.add_argument("--consulta", help="consulta do Logs Insights")
ap.add_argument("--max-cloudtrail", type=int, default=500)
ap.add_argument("--dry-run", action="store_true", help="apenas imprime os comandos")
a = ap.parse_args()

INI = instante(a.inicio).astimezone().isoformat()
FIM = instante(a.fim).astimezone().isoformat()
lacunas = []


def aws(*args, regiao=None):
    cmd = ["aws", *args, "--profile", a.perfil, "--region", regiao or a.regiao, "--output", "json"]
    if a.dry_run:
        print("  " + " ".join(cmd))
        return None
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else f"código {r.returncode}")
    return json.loads(r.stdout or "{}")


def salva(nome, eventos):
    if not a.dry_run:
        print(f"  {nome}: {len(eventos)} eventos")
        gravar_json(os.path.join(a.saida, nome), eventos)


# Alarmes do CloudWatch
try:
    d = aws("cloudwatch", "describe-alarm-history", "--history-item-type", "StateUpdate",
            "--start-date", INI, "--end-date", FIM, "--max-items", "1000")
    if d is not None:
        ev = []
        for h in d.get("AlarmHistoryItems", []):
            ev.append({"quando": h["Timestamp"], "fonte": "CloudWatch Alarms",
                       "evento": f"{h['AlarmName']}: {h['HistorySummary']}", "tipo": "alarme",
                       "ref": h["AlarmName"]})
        salva("alarmes.json", ev)
except Exception as e:
    lacunas.append(f"alarmes do CloudWatch: {e}")

# CloudTrail, somente eventos de escrita
try:
    d = aws("cloudtrail", "lookup-events", "--start-time", INI, "--end-time", FIM,
            "--lookup-attributes", "AttributeKey=ReadOnly,AttributeValue=false",
            "--max-items", str(a.max_cloudtrail))
    if d is not None:
        ev = []
        for e in d.get("Events", []):
            recursos = ", ".join(r.get("ResourceName", "") for r in e.get("Resources", [])[:2])
            ev.append({"quando": e["EventTime"], "fonte": "CloudTrail",
                       "evento": f"{e['EventName']} por {e.get('Username', '?')}" + (f" em {recursos}" if recursos else ""),
                       "tipo": "mudanca", "ref": e.get("EventId", "")})
        salva("cloudtrail.json", ev)
except Exception as e:
    lacunas.append(f"CloudTrail: {e}")

# AWS Health, serviço global atendido em us-east-1
try:
    d = aws("health", "describe-events", "--filter",
            json.dumps({"startTimes": [{"from": INI, "to": FIM}]}), regiao="us-east-1")
    if d is not None:
        ev = [{"quando": e["startTime"], "fonte": "AWS Health",
               "evento": f"{e['service']} {e['eventTypeCode']} ({e.get('statusCode', '')})",
               "tipo": "provedor", "ref": e["arn"]} for e in d.get("events", [])]
        salva("health.json", ev)
except Exception as e:
    lacunas.append(f"AWS Health (exige plano Business ou superior): {e}")

# Logs Insights
if a.log_group and a.consulta:
    try:
        ini_s = int(instante(a.inicio).timestamp())
        fim_s = int(instante(a.fim).timestamp())
        q = aws("logs", "start-query", "--log-group-name", a.log_group, "--start-time", str(ini_s),
                "--end-time", str(fim_s), "--query-string", a.consulta, "--limit", "1000")
        if q is not None:
            r = {}
            for _ in range(60):
                time.sleep(2)
                r = aws("logs", "get-query-results", "--query-id", q["queryId"])
                if r["status"] in ("Complete", "Failed", "Cancelled", "Timeout"):
                    break
            ev = []
            for linha in r.get("results", []):
                c = {x["field"]: x["value"] for x in linha}
                ev.append({"quando": c.get("@timestamp", "").replace(" ", "T") + "+00:00", "fonte": f"Logs {a.log_group}",
                           "evento": c.get("@message", "")[:300], "tipo": "log", "ref": a.log_group})
            salva("logs.json", ev)
    except Exception as e:
        lacunas.append(f"Logs Insights: {e}")

if lacunas and not a.dry_run:
    gravar_json(os.path.join(a.saida, "lacunas.json"), lacunas)
for l in lacunas:
    print(f"  [lacuna] {l}")

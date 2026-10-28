# -*- coding: utf-8 -*-
"""Coleta a evidência de um incidente na Azure, somente leitura, pela Azure CLI.

Uso:
  python coleta_azure.py --assinatura <id> [--grupo <resource-group>] \\
      --inicio 2026-10-20T01:00 --fim 2026-10-22T10:00 --saida coleta/ [--dry-run]

Grava activity_log.json (operações de escrita, falhas e alertas do Activity Log, inclusive os de
Service Health e Resource Health) no formato de evento da linha do tempo, e lacunas.json com o que
não pôde ser lido. Exige `az login` feito e o papel Reader no escopo. --dry-run apenas imprime os
comandos.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from comum import gravar_json, instante  # noqa: E402

ap = argparse.ArgumentParser(description="Coleta somente leitura de evidência de incidente na Azure.")
ap.add_argument("--assinatura", required=True, help="ID ou nome da assinatura")
ap.add_argument("--grupo", help="resource group; sem ele, o escopo é a assinatura inteira")
ap.add_argument("--inicio", required=True, help="início da janela, ISO 8601")
ap.add_argument("--fim", required=True, help="fim da janela, ISO 8601")
ap.add_argument("--saida", default="coleta")
ap.add_argument("--dry-run", action="store_true", help="apenas imprime os comandos")
a = ap.parse_args()

INI = instante(a.inicio).isoformat()
FIM = instante(a.fim).isoformat()
lacunas = []


def az(*args):
    cmd = ["az", *args, "--subscription", a.assinatura, "--output", "json"]
    if a.dry_run:
        print("  " + " ".join(cmd))
        return None
    r = subprocess.run(cmd, capture_output=True, text=True, shell=(os.name == "nt"))
    if r.returncode:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else f"código {r.returncode}")
    return json.loads(r.stdout or "[]")


try:
    escopo = ["--resource-group", a.grupo] if a.grupo else []
    d = az("monitor", "activity-log", "list", "--start-time", INI, "--end-time", FIM, "--max-events", "1000", *escopo)
    if d is not None:
        ev = []
        for e in d:
            cat = (e.get("category") or {}).get("value", "")
            status = (e.get("status") or {}).get("value", "")
            op = (e.get("operationName") or {}).get("localizedValue", "")
            if cat == "Administrative" and status not in ("Succeeded", "Failed"):
                continue
            ev.append({"quando": e["eventTimestamp"], "fonte": f"Activity Log ({cat})",
                       "evento": f"{op}: {status} por {e.get('caller', '?')}",
                       "tipo": "alarme" if cat in ("Alert", "ServiceHealth", "ResourceHealth") else "mudanca",
                       "ref": e.get("resourceId", "")})
        print(f"  activity_log.json: {len(ev)} eventos")
        gravar_json(os.path.join(a.saida, "activity_log.json"), ev)
except Exception as e:
    lacunas.append(f"Activity Log: {e}")

if lacunas and not a.dry_run:
    gravar_json(os.path.join(a.saida, "lacunas.json"), lacunas)
for l in lacunas:
    print(f"  [lacuna] {l}")

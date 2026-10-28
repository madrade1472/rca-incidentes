# -*- coding: utf-8 -*-
"""comum.py: funções compartilhadas da skill rca-incidentes. Só biblioteca padrão, Python 3.8+."""
import json
import os
import re
from datetime import datetime, timedelta, timezone

AQUI = os.path.dirname(os.path.realpath(__file__))
SKILL = os.path.dirname(AQUI)
# Travessões (en dash, em dash e barra horizontal), escritos como escape para não aparecerem no fonte.
TRAVESSAO = re.compile("[\u2013\u2014\u2015]")

FUSO_PADRAO = "America/Sao_Paulo"


def _fuso(nome):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(nome)
    except Exception:  # Python 3.8 ou Windows sem tzdata: o Brasil não tem horário de verão desde 2019
        if nome == FUSO_PADRAO:
            return timezone(timedelta(hours=-3))
        raise


LOCAL = _fuso(FUSO_PADRAO)


def definir_fuso(nome):
    """Troca o fuso usado para ler horários sem fuso e para exibir horários (padrão: Brasília)."""
    global LOCAL
    LOCAL = _fuso(nome or FUSO_PADRAO)
    return LOCAL


def instante(texto):
    """Lê um horário ISO 8601. Sem fuso, assume o fuso local do incidente (padrão: Brasília)."""
    if isinstance(texto, datetime):
        dt = texto
    else:
        dt = datetime.fromisoformat(str(texto).strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=LOCAL)


def local(dt, com_data=True):
    d = instante(dt).astimezone(LOCAL)
    return d.strftime("%d/%m/%Y %H:%M") if com_data else d.strftime("%H:%M")


def data_prazo(texto):
    """Lê um prazo em dd/mm/aaaa ou aaaa-mm-dd. Devolve None quando não reconhece."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(texto).strip(), fmt)
        except ValueError:
            pass
    return None


def duracao(inicio, fim):
    """Duração legível entre dois instantes: '2 h 15 min', '3 d 4 h', '12 min'."""
    seg = int((instante(fim) - instante(inicio)).total_seconds())
    if seg < 0:
        return "negativa"
    d, resto = divmod(seg, 86400)
    h, resto = divmod(resto, 3600)
    m = resto // 60
    if d:
        return f"{d} d {h} h" if h else f"{d} d"
    if h:
        return f"{h} h {m} min" if m else f"{h} h"
    return f"{m} min"


def ler_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(p, dados):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return p


def gravar_texto(p, texto):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return p


MARCOS = [
    ("inicio_impacto", "Início do impacto"),
    ("deteccao", "Detecção"),
    ("reconhecimento", "Reconhecimento"),
    ("mitigacao", "Mitigação"),
    ("resolucao", "Resolução"),
]

SEVERIDADES = {
    "SEV1": "Indisponibilidade total ou perda de dado em produção, com impacto direto no negócio",
    "SEV2": "Degradação severa ou funcionalidade crítica fora do ar para parte dos usuários",
    "SEV3": "Degradação parcial com contorno disponível",
    "SEV4": "Impacto mínimo, sem efeito percebido pelo usuário final",
}


def metricas(inc):
    """Tempos entre os marcos: até detectar, reconhecer, mitigar e a duração do impacto."""
    m = inc.get("marcos", {})
    out = {}
    pares = [("Tempo até detectar", "inicio_impacto", "deteccao"),
             ("Tempo até reconhecer", "deteccao", "reconhecimento"),
             ("Tempo até mitigar", "inicio_impacto", "mitigacao"),
             ("Duração do impacto", "inicio_impacto", "resolucao")]
    for rotulo, a, b in pares:
        if m.get(a) and m.get(b):
            out[rotulo] = duracao(m[a], m[b])
    return out

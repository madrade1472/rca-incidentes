# -*- coding: utf-8 -*-
"""Confere o incidente.json antes de montar o documento. Sai com 1 se houver erro e 0 se estiver tudo certo.

Uso: python valida_incidente.py incidente.json

Erro: campo obrigatório ausente, marcos fora de ordem, evento sem fonte, ação sem dono ou prazo,
severidade desconhecida, causa raiz que para em "erro humano", travessão no texto, passo inválido
no caminho da falha.
Aviso: linguagem que procura culpado, falta de ação de detecção quando a detecção demorou, prazo
fora do formato dd/mm/aaaa, lacunas registradas.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from comum import MARCOS, SEVERIDADES, TRAVESSAO, data_prazo, definir_fuso, instante, ler_json  # noqa: E402

TIPOS_ACAO = {"prevenir", "detectar", "mitigar", "processo"}
PRIORIDADES = {"P1", "P2", "P3", "P4"}
TIPOS_PASSO = {"no", "seta"}
CULPA = re.compile(r"\b(culpa|culpado|negligen\w+|descuido|falha d[oa] (analista|operador|desenvolvedor)|"
                   r"erro d[oa] (?-i:[A-Z])\w+)\b", re.I)


def textos(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from textos(v)
    elif isinstance(x, list):
        for v in x:
            yield from textos(v)


def validar(inc):
    erros, avisos = [], []
    try:
        definir_fuso(inc.get("fuso"))
    except Exception:
        erros.append(f"fuso desconhecido: {inc.get('fuso')}")
    for k in ("id", "titulo", "severidade", "resumo", "marcos", "causa_raiz", "porques", "acoes"):
        if not inc.get(k):
            erros.append(f"campo obrigatório ausente: {k}")
    if inc.get("severidade") and inc["severidade"] not in SEVERIDADES:
        erros.append(f"severidade '{inc['severidade']}' fora da escala {', '.join(SEVERIDADES)}")

    m = inc.get("marcos") or {}
    presentes = [(k, rot) for k, rot in MARCOS if m.get(k)]
    for k in ("inicio_impacto", "deteccao", "resolucao"):
        if not m.get(k):
            erros.append(f"marco obrigatório ausente: {k}")
    try:
        for (k1, r1), (k2, r2) in zip(presentes, presentes[1:]):
            if instante(m[k2]) < instante(m[k1]):
                erros.append(f"marco fora de ordem: {r2} antes de {r1}")
    except ValueError as e:
        erros.append(f"horário inválido nos marcos: {e}")

    for i, ev in enumerate(inc.get("linha_do_tempo", [])):
        if not ev.get("fonte"):
            erros.append(f"evento {i + 1} da linha do tempo sem fonte: '{ev.get('evento', '')[:50]}'")
        if not ev.get("evento"):
            erros.append(f"evento {i + 1} da linha do tempo sem descrição")
        try:
            instante(ev.get("quando", ""))
        except ValueError:
            erros.append(f"evento {i + 1} com horário inválido: {ev.get('quando')}")

    if re.fullmatch(r"\s*(erro|falha)\s+human[oa]\.?\s*", inc.get("causa_raiz", ""), re.I):
        erros.append("a causa raiz parou em 'erro humano': pergunte por que o sistema permitiu o erro")
    if len(inc.get("porques", [])) < 3:
        avisos.append("menos de três porquês: confira se a causa raiz não é apenas o sintoma")

    tipos = set()
    for i, ac in enumerate(inc.get("acoes", [])):
        rot = f"ação {i + 1} ('{ac.get('titulo', '')[:40]}')"
        for k in ("titulo", "dono", "prazo"):
            if not ac.get(k):
                erros.append(f"{rot} sem {k}")
        if ac.get("prazo") and not data_prazo(ac["prazo"]):
            avisos.append(f"{rot} com prazo '{ac['prazo']}' fora do formato dd/mm/aaaa")
        if ac.get("tipo") not in TIPOS_ACAO:
            erros.append(f"{rot} com tipo '{ac.get('tipo')}', use {', '.join(sorted(TIPOS_ACAO))}")
        if ac.get("prioridade") not in PRIORIDADES:
            erros.append(f"{rot} com prioridade '{ac.get('prioridade')}', use P1 a P4")
        tipos.add(ac.get("tipo"))
    if inc.get("acoes") and "prevenir" not in tipos:
        avisos.append("nenhuma ação do tipo prevenir: o incidente pode se repetir")
    if m.get("inicio_impacto") and m.get("deteccao"):
        try:
            if (instante(m["deteccao"]) - instante(m["inicio_impacto"])).total_seconds() > 1800 and "detectar" not in tipos:
                avisos.append("a detecção levou mais de 30 min e não há ação do tipo detectar")
        except ValueError:
            pass

    cf = inc.get("caminho_falha")
    if cf:
        passos = cf.get("passos") if isinstance(cf, dict) else None
        if not passos:
            erros.append("caminho_falha sem a lista 'passos'")
        else:
            for i, p in enumerate(passos):
                if p.get("tipo") not in TIPOS_PASSO:
                    erros.append(f"passo {i + 1} do caminho da falha com tipo '{p.get('tipo')}', use 'no' ou 'seta'")
                elif p["tipo"] == "no" and not p.get("titulo"):
                    erros.append(f"passo {i + 1} do caminho da falha é um nó sem titulo")
            if passos[0].get("tipo") == "seta" or passos[-1].get("tipo") == "seta":
                avisos.append("o caminho da falha começa ou termina em seta")

    for t in textos(inc):
        if TRAVESSAO.search(t):
            erros.append(f"travessão no texto: '{t[:60]}'")
        if CULPA.search(t):
            avisos.append(f"linguagem de culpa, o RCA é sem culpados: '{t[:60]}'")
    for l in inc.get("lacunas", []):
        avisos.append(f"lacuna registrada: {l}")
    return erros, avisos


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    erros, avisos = validar(ler_json(sys.argv[1]))
    for a in avisos:
        print(f"  [aviso] {a}")
    for e in erros:
        print(f"  [erro] {e}")
    print("ok" if not erros else f"{len(erros)} erro(s)")
    sys.exit(1 if erros else 0)

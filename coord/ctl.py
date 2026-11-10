"""Cliente de línea de comandos para operar y observar el clúster.

Ejemplos:
  python -m coord.ctl estado
  python -m coord.ctl sembrar
  python -m coord.ctl asignar nodo2 --cpu 1 --mem 512 --bw 10 --nodo 3
  python -m coord.ctl inventario
  python -m coord.ctl convergencia
  python -m coord.ctl snapshot --etiqueta antes
  python -m coord.ctl lider-falso --nodo 1
"""
import argparse
import json
import os
import sys
import time

from . import config as cfgmod
from .net import request


def call(cfg, nid, msg, timeout=3.0):
    n = cfg["nodes"][nid]
    return request(n["host"], n["port"], dict(msg), timeout)


def ids_de(cfg, solo=None):
    todos = sorted(cfg["nodes"])
    return [i for i in todos if not solo or i in solo]


def estados(cfg, solo=None):
    return {nid: call(cfg, nid, {"type": "status"}) for nid in ids_de(cfg, solo)}


def inventarios(cfg, solo=None):
    return {nid: call(cfg, nid, {"type": "inventory"}) for nid in ids_de(cfg, solo)}


def cmd_estado(cfg, a):
    print(f"{'nodo':<5}{'estado':<10}{'término':<9}{'líder':<7}{'Redis':<8}{'quórum':<8}"
          f"{'sin-quórum':<11}{'conflictos(det/res)':<20}{'rechazados':<10}")
    for nid, s in estados(cfg, a.solo).items():
        if not s:
            print(f"{nid:<5}INACCESIBLE")
            continue
        c = s["conflictos"]
        print(f"{nid:<5}{s['estado']:<10}{s['termino']:<9}{str(s['lider']):<7}{s['redis_rol']:<8}"
              f"{str(s['quorum']):<8}{s['escrituras_sin_quorum_pendientes']:<11}"
              f"{c['detectados']}/{c['resueltos']:<17}{s['reclamos_rechazados']:<10}")


def fmt_entry(e):
    return (f"cpu={e['cpu']} mem={e['mem']} bw={e['bw']} vv={json.dumps(e['vv'], sort_keys=True)} "
            f"L={e['lamport']} w={e['writer']}")


def cmd_inventario(cfg, a):
    for nid, r in inventarios(cfg).items():
        if a.nodo and nid != a.nodo:
            continue
        print(f"--- nodo {nid} ---")
        if not r or not r.get("ok"):
            print("  INACCESIBLE")
            continue
        for res, e in sorted(r["inventory"].items()):
            print(f"  {res}: {fmt_entry(e)}")


def escribir(cfg, a, op):
    msg = {"type": "write", "op": op, "resource": a.recurso}
    for k in ("cpu", "mem", "bw"):
        v = getattr(a, k)
        if v is not None:
            msg[k] = v
    objetivos = [a.nodo] if a.nodo else sorted(cfg["nodes"], reverse=True)
    for nid in objetivos:
        r = call(cfg, nid, msg)
        if r is None:
            if a.nodo:
                print(f"nodo {nid}: INACCESIBLE")
            continue
        if r.get("ok"):
            e = r["entry"]
            print(f"OK vía nodo {nid} (coordinador {r['coordinador']}, quórum={r['quorum']}): "
                  f"{a.recurso} -> {fmt_entry(e)}")
            return 0
        print(f"RECHAZADA por nodo {nid}: {r.get('error')}")
        return 1
    print("ningún nodo respondió")
    return 2


def cmd_sembrar(cfg, a):
    for nid in sorted(cfg["nodes"]):
        ns = argparse.Namespace(recurso=f"nodo{nid}", cpu=a.cpu, mem=a.mem, bw=a.bw, nodo=a.nodo)
        escribir(cfg, ns, "set")


def cmd_convergencia(cfg, a):
    inv = inventarios(cfg)
    canon = {}
    for nid, r in inv.items():
        if not r or not r.get("ok"):
            print(f"nodo {nid}: INACCESIBLE")
            canon[nid] = None
        else:
            canon[nid] = json.dumps(
                {k: {x: v[x] for x in ("cpu", "mem", "bw", "vv")} for k, v in r["inventory"].items()},
                sort_keys=True)
    vals = set(v for v in canon.values() if v is not None)
    ok = len(vals) == 1 and None not in canon.values()
    for nid, v in canon.items():
        print(f"nodo {nid}: {'(inaccesible)' if v is None else __import__('hashlib').md5(v.encode()).hexdigest()[:10]}")
    print("CONVERGENCIA:", "SÍ, todos los nodos tienen el mismo estado" if ok else "NO")
    return 0 if ok else 1


def cmd_snapshot(cfg, a):
    sts, invs = estados(cfg, a.solo), inventarios(cfg, a.solo)
    lineas = [f"\n### {a.etiqueta.upper()} — {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
              "| nodo | estado | término | líder | Redis | recurso | cpu | mem | bw | vector de versión | Lamport |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for nid in ids_de(cfg, a.solo):
        s, r = sts[nid], invs[nid]
        if not s or not r or not r.get("ok"):
            lineas.append(f"| {nid} | INACCESIBLE | | | | | | | | | |")
            continue
        if not r["inventory"]:
            lineas.append(f"| {nid} | {s['estado']} | {s['termino']} | {s['lider']} | {s['redis_rol']} | (vacío) | | | | | |")
        for res, e in sorted(r["inventory"].items()):
            lineas.append(f"| {nid} | {s['estado']} | {s['termino']} | {s['lider']} | {s['redis_rol']} | "
                          f"{res} | {e['cpu']} | {e['mem']} | {e['bw']} | {json.dumps(e['vv'], sort_keys=True)} | {e['lamport']} |")
    texto = "\n".join(lineas)
    print(texto)
    os.makedirs(os.path.dirname(a.salida) or ".", exist_ok=True)
    with open(a.salida, "a", encoding="utf-8") as f:
        f.write(texto + "\n")
    print(f"\n(añadido a {a.salida})")


def cmd_lider_falso(cfg, a):
    r = call(cfg, a.nodo, {"type": "fake_leader"}, timeout=10)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if r and r.get("ok"):
        rech = [p for p, v in r["respuestas"].items() if v is False]
        print(f"El reclamo falso fue RECHAZADO por: {rech}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Control del clúster (Taller 1)")
    ap.add_argument("--config", default="config/cluster.json")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("estado"); p.add_argument("--nodos", help="ej. 1,2 (solo esos nodos)")
    p = sp.add_parser("inventario"); p.add_argument("--nodo", type=int)
    for nombre in ("set", "asignar", "liberar"):
        p = sp.add_parser(nombre)
        p.add_argument("recurso")
        for k in ("cpu", "mem", "bw"):
            p.add_argument(f"--{k}", type=int)
        p.add_argument("--nodo", type=int, help="nodo al que se envía la petición")
    p = sp.add_parser("sembrar")
    p.add_argument("--cpu", type=int, default=2)
    p.add_argument("--mem", type=int, default=2048)
    p.add_argument("--bw", type=int, default=100)
    p.add_argument("--nodo", type=int)
    sp.add_parser("convergencia")
    p = sp.add_parser("snapshot")
    p.add_argument("--etiqueta", required=True)
    p.add_argument("--nodos", help="ej. 1,2 (solo esos nodos)")
    p.add_argument("--salida", default="resultados/E5-experimento-particion.md")
    p = sp.add_parser("lider-falso"); p.add_argument("--nodo", type=int, required=True)
    a = ap.parse_args(argv)
    a.solo = [int(x) for x in a.nodos.split(",")] if getattr(a, "nodos", None) else None
    cfg = cfgmod.load(a.config)
    rc = 0
    if a.cmd == "estado": cmd_estado(cfg, a)
    elif a.cmd == "inventario": cmd_inventario(cfg, a)
    elif a.cmd == "set": rc = escribir(cfg, a, "set")
    elif a.cmd == "asignar": rc = escribir(cfg, a, "allocate")
    elif a.cmd == "liberar": rc = escribir(cfg, a, "release")
    elif a.cmd == "sembrar": cmd_sembrar(cfg, a)
    elif a.cmd == "convergencia": rc = cmd_convergencia(cfg, a)
    elif a.cmd == "snapshot": cmd_snapshot(cfg, a)
    elif a.cmd == "lider-falso": cmd_lider_falso(cfg, a)
    sys.exit(rc)


if __name__ == "__main__":
    main()

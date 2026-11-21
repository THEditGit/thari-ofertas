#!/usr/bin/env python3
"""Junta as ofertas novas (um arquivo por oferta) ao products.json do site.

Uso: python3 scripts/build_products.py <pasta dados> <products.json>

- <pasta dados>/offers/*.json: uma oferta por arquivo (id, titulo, preco, preco_antigo,
  link, loja, nicho, data, imagem). Entra no site ou atualiza a oferta com o mesmo id.
- <pasta dados>/removed.txt: um id por linha; essas ofertas saem do site.
- O que ja esta no products.json e mantido (ate 300 ofertas, das mais novas).
"""
import glob
import json
import os
import sys
import time

MAX_PRODUCTS = 300


def main():
    dados, products_path = sys.argv[1], sys.argv[2]
    try:
        with open(products_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"atualizado": None, "produtos": []}
    by_id = {p["id"]: p for p in data.get("produtos", []) if "id" in p}
    for path in glob.glob(os.path.join(dados, "offers", "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                p = json.load(f)
            by_id[p["id"]] = p
        except Exception as e:  # arquivo quebrado nao derruba o site
            print(f"ignorado {path}: {e}")
    removed = set()
    rpath = os.path.join(dados, "removed.txt")
    if os.path.exists(rpath):
        with open(rpath, encoding="utf-8") as f:
            removed = {l.split("#")[0].strip() for l in f if l.split("#")[0].strip()}
    prods = [p for i, p in by_id.items() if i not in removed]
    prods = sorted(prods, key=lambda p: p.get("data") or 0, reverse=True)[:MAX_PRODUCTS]
    if prods == data.get("produtos"):
        print("sem mudanca")
        return
    with open(products_path, "w", encoding="utf-8") as f:
        json.dump({"atualizado": int(time.time()), "produtos": prods}, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"atualizado: {len(prods)} ofertas no site ({len(removed)} removidas)")


if __name__ == "__main__":
    main()

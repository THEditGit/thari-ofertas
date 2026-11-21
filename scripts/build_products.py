#!/usr/bin/env python3
"""Monta products.json juntando um arquivo por oferta (pasta offers/ da branch dados).

Uso: python3 scripts/build_products.py <pasta offers> <products.json>

Cada oferta e um JSON pequeno (id, titulo, preco, preco_antigo, link, loja, nicho, data, imagem).
Produtos que vieram de outra fonte (id sem o prefixo 'ml-') sao mantidos.
Para tirar uma oferta do site, apague o arquivo dela em offers/ na branch dados.
"""
import glob
import json
import os
import sys
import time

MAX_PRODUCTS = 300


def main():
    offers_dir, products_path = sys.argv[1], sys.argv[2]
    try:
        with open(products_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"atualizado": None, "produtos": []}
    others = [p for p in data.get("produtos", []) if not str(p.get("id", "")).startswith("ml-")]
    ours = []
    for path in glob.glob(os.path.join(offers_dir, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                ours.append(json.load(f))
        except Exception as e:  # arquivo quebrado nao derruba o site
            print(f"ignorado {path}: {e}")
    prods = sorted(ours + others, key=lambda p: p.get("data") or 0, reverse=True)[:MAX_PRODUCTS]
    if prods == data.get("produtos"):
        print("sem mudanca")
        return
    with open(products_path, "w", encoding="utf-8") as f:
        json.dump({"atualizado": int(time.time()), "produtos": prods}, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"atualizado: {len(ours)} ofertas + {len(others)} de outras fontes (mostrando {len(prods)})")


if __name__ == "__main__":
    main()

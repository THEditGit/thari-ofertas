#!/usr/bin/env python3
"""Lê as postagens novas do grupo Thari Ofertas no Telegram e atualiza products.json.

Uso: TELEGRAM_BOT_TOKEN=... python3 scripts/sync_telegram.py

O bot precisa ser administrador do grupo (assim ele recebe todas as mensagens).
A API do Telegram guarda as mensagens não lidas por 24 horas, então este script
precisa rodar pelo menos uma vez por dia (a automação do GitHub roda a cada hora).

Só entram no site as postagens que têm um link. Para escolher o nicho na mão,
coloque uma hashtag no post, por exemplo #casa, #beleza, #moda, #eletronicos,
#infantil, #pet, #esporte, #mercado ou #ferramentas.
Para tirar um produto do site, responda ao post no grupo com /remover.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(ROOT, "products.json")
IMAGES = os.path.join(ROOT, "images")
GROUP_USERNAME = os.environ.get("TELEGRAM_GROUP", "ThariOfertas").lstrip("@").lower()
MAX_PRODUCTS = 300

# Nichos: id -> palavras-chave (sem acento, minúsculas). A ordem importa:
# o primeiro nicho com mais palavras encontradas ganha.
NICHOS = {
    "eletronicos": ["fone", "celular", "smartphone", "iphone", "samsung", "xiaomi", "carregador",
                    "cabo usb", "notebook", "tablet", "smartwatch", "relogio inteligente", "caixa de som",
                    "bluetooth", "mouse", "teclado", "monitor", "tv ", "smart tv", "headset", "power bank",
                    "camera", "alexa", "echo dot", "ssd", "pendrive", "gamer", "controle", "console",
                    "playstation", "xbox", "nintendo", "airpods", "kindle", "projetor", "roteador"],
    "casa": ["cozinha", "panela", "frigideira", "airfryer", "air fryer", "liquidificador", "batedeira",
             "cafeteira", "garrafa", "pote", "organizador", "toalha", "lencol", "travesseiro", "cama",
             "colcha", "cortina", "tapete", "luminaria", "abajur", "decoracao", "aspirador", "vassoura",
             "mop", "ventilador", "umidificador", "copo", "caneca", "talher", "faqueiro", "jogo de",
             "sanduicheira", "microondas", "geladeira", "fogao", "forno", "mixer", "chaleira", "lixeira",
             "cabide", "edredom", "prato", "tabua", "escorredor", "pano de prato"],
    "beleza": ["perfume", "maquiagem", "batom", "base ", "rimel", "mascara de cilios", "skincare",
               "hidratante", "shampoo", "condicionador", "creme", "serum", "protetor solar", "esmalte",
               "secador", "chapinha", "prancha", "modelador", "escova", "barbeador", "depilador",
               "sabonete", "desodorante", "body splash", "kit beleza", "cabelo", "unha", "sombra",
               "pincel", "boticario", "natura", "eudora", "oleo capilar"],
    "moda": ["camiseta", "camisa", "blusa", "vestido", "calca", "bermuda", "short", "saia", "jaqueta",
             "casaco", "moletom", "tenis", "sandalia", "chinelo", "sapato", "bota", "bolsa", "mochila",
             "carteira", "oculos", "relogio", "brinco", "colar", "pulseira", "anel", "cueca", "calcinha",
             "sutia", "pijama", "meia", "bone", "cinto", "biquini", "lingerie", "legging", "conjunto"],
    "infantil": ["infantil", "bebe", "crianca", "brinquedo", "boneca", "lego", "carrinho", "fralda",
                 "mamadeira", "chupeta", "berco", "kids", "pelucia", "quebra-cabeca", "escolar", "mochila infantil"],
    "pet": ["pet", "cachorro", "gato", "racao", "coleira", "caminha", "arranhador", "petisco", "areia sanitaria",
            "comedouro", "bebedouro", "tapete higienico"],
    "esporte": ["academia", "fitness", "whey", "creatina", "suplemento", "halter", "anilha", "bicicleta",
                "bike", "corrida", "yoga", "garrafa termica", "squeeze", "esporte", "futebol", "bola",
                "camping", "barraca", "patins", "skate", "natacao", "elastico", "colchonete"],
    "mercado": ["cafe", "capsula", "chocolate", "biscoito", "leite", "azeite", "arroz", "feijao",
                "cerveja", "vinho", "refrigerante", "sabao", "detergente", "amaciante", "papel higienico",
                "limpeza", "desinfetante", "agua sanitaria", "fralda", "nescau", "achocolatado", "bebida"],
    "ferramentas": ["furadeira", "parafusadeira", "ferramenta", "chave de fenda", "alicate", "martelo",
                    "trena", "serra", "lixadeira", "kit ferramentas", "esmerilhadeira", "compressor",
                    "lavadora de alta pressao", "wap", "makita", "bosch", "black+decker", "tramontina"],
}
HASHTAGS = {
    "casa": "casa", "cozinha": "casa", "decoracao": "casa", "lar": "casa",
    "beleza": "beleza", "skincare": "beleza", "maquiagem": "beleza", "perfume": "beleza",
    "moda": "moda", "roupa": "moda", "roupas": "moda", "calcados": "moda", "acessorios": "moda",
    "eletronicos": "eletronicos", "eletronico": "eletronicos", "tech": "eletronicos", "games": "eletronicos",
    "celular": "eletronicos", "infantil": "infantil", "bebe": "infantil", "kids": "infantil",
    "brinquedos": "infantil", "pet": "pet", "pets": "pet", "esporte": "esporte", "esportes": "esporte",
    "fitness": "esporte", "academia": "esporte", "mercado": "mercado", "supermercado": "mercado",
    "ferramentas": "ferramentas", "ferramenta": "ferramentas", "outros": "outros",
}
LOJAS = [
    ("shopee", "Shopee"), ("shp.ee", "Shopee"),
    ("mercadolivre", "Mercado Livre"), ("mercadolibre", "Mercado Livre"), ("meli.la", "Mercado Livre"),
    ("amazon", "Amazon"), ("amzn.to", "Amazon"),
    ("magazineluiza", "Magalu"), ("magalu", "Magalu"),
    ("aliexpress", "AliExpress"), ("s.click.aliexpress", "AliExpress"),
    ("kabum", "KaBuM!"), ("americanas", "Americanas"), ("casasbahia", "Casas Bahia"),
    ("shein", "Shein"), ("netshoes", "Netshoes"), ("temu", "Temu"),
]

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
PRICE_RE = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)", re.I)
CUPOM_RE = re.compile(r"cupom\s*(?:de desconto)?\s*[:\-–]?\s*([A-Z0-9][A-Z0-9_\-]{3,})", re.I)


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def api(token, method, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (list, dict)) else v
                                   for k, v in params.items()}).encode()
    with urllib.request.urlopen(url, data=data, timeout=60) as r:
        res = json.load(r)
    if not res.get("ok"):
        raise RuntimeError(f"{method}: {res}")
    return res["result"]


def to_float(p):
    return float(p.replace(".", "").replace(",", "."))


def full_text(msg):
    """Texto do post com os links escondidos em palavras (text_link) colocados de volta."""
    text = msg.get("text") or msg.get("caption") or ""
    ents = msg.get("entities") or msg.get("caption_entities") or []
    links = [e["url"] for e in ents if e.get("type") == "text_link" and e.get("url")]
    # Botões embaixo do post (inline keyboard) também costumam ter o link de afiliado.
    for row in (msg.get("reply_markup") or {}).get("inline_keyboard", []):
        for b in row:
            if b.get("url"):
                links.append(b["url"])
    return text, links


def clean_line(line):
    line = URL_RE.sub("", line)
    line = re.sub(r"#\w+", "", line)
    # tira emojis e símbolos do começo/fim
    line = re.sub(r"^[\W_]+|[\W_]+$", "", line, flags=re.UNICODE)
    return re.sub(r"\s+", " ", line).strip()


def parse_post(msg):
    text, extra_links = full_text(msg)
    urls = URL_RE.findall(text) + extra_links
    urls = [u.rstrip(".,;!") for u in urls if "t.me/" not in u.lower()]
    if not urls:
        return None
    link = urls[0]

    title = ""
    for line in text.splitlines():
        c = clean_line(line)
        if len(c) < 4 or PRICE_RE.search(line) or re.match(r"(?i)^(cupom|link|compre|oferta|promo)", c):
            continue
        if re.fullmatch(r"(?i)(ofertas?|promo(cao|ção)?|achadinho|imperdivel|imperdível|corre+)!*", c):
            continue
        title = c
        break
    title = title[:140] or "Oferta"

    prices = []
    for line in text.splitlines():
        for p in PRICE_RE.findall(line):
            try:
                prices.append((to_float(p), norm(line)))
            except ValueError:
                pass
    price = old_price = None
    if prices:
        old = [v for v, l in prices if re.search(r"\bde\b|antes|era|~", l) and not re.search(r"\bpor\b", l)]
        new = [v for v, l in prices if re.search(r"\bpor\b|agora|apenas|so |sai|hoje", l)]
        price = (new or [min(v for v, _ in prices)])[0]
        cands = [v for v in (old or [v for v, _ in prices]) if v > price]
        old_price = max(cands) if cands else None

    cupom = None
    m = CUPOM_RE.search(text)
    if m:
        cupom = m.group(1).upper()

    tags = [norm(t) for t in re.findall(r"#(\w+)", text)]
    nicho = next((HASHTAGS[t] for t in tags if t in HASHTAGS), None)
    if not nicho:
        hay = " " + norm(text) + " "
        best, score = "outros", 0
        for nid, words in NICHOS.items():
            s = sum(1 for w in words if w in hay)
            if s > score:
                best, score = nid, s
        nicho = best

    host = norm(urllib.parse.urlparse(link).netloc)
    host = host.split(":")[0].removeprefix("www.")
    loja = "Amazon" if host == "a.co" else next((nome for k, nome in LOJAS if k in host), None)

    return {
        "id": msg["message_id"],
        "titulo": title,
        "preco": price,
        "preco_antigo": old_price,
        "cupom": cupom,
        "link": link,
        "loja": loja,
        "nicho": nicho,
        "data": msg.get("date"),
        "imagem": None,
    }


def save_photo(token, msg, pid):
    photos = msg.get("photo")
    if not photos:
        return None
    best = max(photos, key=lambda p: p.get("width", 0) * p.get("height", 0))
    # A versão ~800px já basta para os cards e deixa o site leve.
    fit = [p for p in photos if p.get("width", 0) >= 600]
    if fit:
        best = min(fit, key=lambda p: p["width"])
    info = api(token, "getFile", file_id=best["file_id"])
    url = f"https://api.telegram.org/file/bot{token}/{info['file_path']}"
    os.makedirs(IMAGES, exist_ok=True)
    name = f"{pid}.jpg"
    with urllib.request.urlopen(url, timeout=60) as r, open(os.path.join(IMAGES, name), "wb") as f:
        f.write(r.read())
    return f"images/{name}"


def is_our_group(chat):
    return (chat.get("username") or "").lower() == GROUP_USERNAME or \
        str(chat.get("id")) == os.environ.get("TELEGRAM_GROUP_ID", "")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("Defina TELEGRAM_BOT_TOKEN")
    try:
        with open(PRODUCTS, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"atualizado": None, "produtos": []}
    by_id = {p["id"]: p for p in data["produtos"]}

    updates = api(token, "getUpdates", timeout=0, limit=100,
                  allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post"])
    changed = False
    last = None
    while updates:
        for u in updates:
            last = u["update_id"]
            msg = u.get("message") or u.get("edited_message") or u.get("channel_post") or u.get("edited_channel_post")
            if not msg or not is_our_group(msg.get("chat", {})):
                continue
            text = (msg.get("text") or "").strip().lower()
            if text.startswith("/remover") and msg.get("reply_to_message"):
                rid = msg["reply_to_message"]["message_id"]
                if by_id.pop(rid, None):
                    img = os.path.join(IMAGES, f"{rid}.jpg")
                    if os.path.exists(img):
                        os.remove(img)
                    changed = True
                    print(f"removido {rid}")
                continue
            prod = parse_post(msg)
            if not prod:
                continue
            old = by_id.get(prod["id"])
            try:
                prod["imagem"] = save_photo(token, msg, prod["id"]) or (old or {}).get("imagem")
            except Exception as e:  # imagem é opcional
                print(f"sem imagem para {prod['id']}: {e}")
                prod["imagem"] = (old or {}).get("imagem")
            by_id[prod["id"]] = prod
            changed = True
            print(f"{'atualizado' if old else 'novo'} {prod['id']}: {prod['titulo']} [{prod['nicho']}]")
        # confirma as mensagens lidas e pega as próximas
        updates = api(token, "getUpdates", offset=last + 1, timeout=0, limit=100,
                      allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post"])

    if changed:
        prods = sorted(by_id.values(), key=lambda p: p.get("data") or 0, reverse=True)
        for p in prods[MAX_PRODUCTS:]:
            img = os.path.join(IMAGES, f"{p['id']}.jpg")
            if os.path.exists(img):
                os.remove(img)
        data = {"atualizado": int(time.time()), "produtos": prods[:MAX_PRODUCTS]}
        with open(PRODUCTS, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
    print("pronto" + (" (com mudanças)" if changed else " (nada novo)"))


if __name__ == "__main__":
    main()

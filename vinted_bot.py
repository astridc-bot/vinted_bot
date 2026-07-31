import json
import os
import requests

# --- CONFIGURAZIONE DISCORD ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1521502269118615622/2KQEzJpDBs6db1w8sI5XLXdRn9_A_vTkIG85p55QwNWcPyHl220vmvJ9acj8uMxGqBi8"

SEARCH_KEYWORD = "derhy"
SEEN_ITEMS_FILE = "seen_vinted_items.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

def send_discord_webhook(content=None, embed=None):
    payload = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]
        
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio Discord: {e}", flush=True)

def load_seen_items():
    if os.path.exists(SEEN_ITEMS_FILE):
        try:
            with open(SEEN_ITEMS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_items(seen_set):
    with open(SEEN_ITEMS_FILE, "w") as f:
        json.dump(list(seen_set), f)

def send_discord_alert(item):
    title = item.get("title", "Senza titolo")
    price = item.get("price", "N/A")
    currency = item.get("currency", "EUR")
    item_url = item.get("url", "https://www.vinted.it")
    
    # Foto dell'articolo
    photos = item.get("photos", [])
    photo_url = photos[0].get("url") if photos else None

    embed = {
        "title": f"👗 Nuovo capo Vinted: {title}",
        "url": item_url,
        "color": 1752220,  # Colore Turchese Vinted
        "fields": [
            {"name": "💰 Prezzo", "value": f"{price} {currency}", "inline": True},
            {"name": "🔍 Brand / Categoria", "value": "Derhy (Donna)", "inline": True}
        ],
        "footer": {"text": "Vinted Monitor Bot"}
    }

    if photo_url:
        embed["image"] = {"url": photo_url}

    send_discord_webhook(content="@everyone Trovato un nuovo vestito Derhy su Vinted!", embed=embed)

def get_vinted_data():
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "it-IT,it;q=0.9"
    })

    try:
        # 1. Visita la home per ottenere i cookie di sessione Vinted
        session.get("https://www.vinted.it", timeout=10)

        # 2. API Vinted: Categoria 1904 = Donna -> Abbigliamento
        api_url = f"https://www.vinted.it/api/v2/catalog/items?search_text={SEARCH_KEYWORD}&catalog_ids[]=1904&order=newest_first"
        
        resp = session.get(api_url, timeout=10)
        
        if resp.status_code == 200:
            raw_items = resp.json().get("items", [])
            filtered_items = []
            
            # Filtro per verificare che "derhy" sia presente nel titolo
            for item in raw_items:
                title = item.get("title", "").lower()
                if SEARCH_KEYWORD in title:
                    filtered_items.append(item)
                    
            return filtered_items
        else:
            print(f"Errore Vinted HTTP {resp.status_code}", flush=True)
            return None

    except Exception as e:
        print(f"Errore durante il recupero da Vinted: {e}", flush=True)
        return None

def main():
    seen_items = load_seen_items()
    items = get_vinted_data()

    if items is None:
        embed_fail = {
            "title": "🔴 ERRORE Vinted",
            "description": "Impossibile connettersi a Vinted (blocco IP o problema di rete).",
            "color": 15158332
        }
        send_discord_webhook(embed=embed_fail)
        return

    # Primo avvio su GitHub Actions: popola la lista senza notificare in massa
    if not seen_items:
        print("Inizializzazione Vinted: salvo gli articoli presenti...", flush=True)
        for item in items:
            item_id = item.get("id")
            if item_id:
                seen_items.add(item_id)
        save_seen_items(seen_items)
        send_discord_webhook(content=f"🟢 **Vinted Bot attivo**: Memorizzati {len(seen_items)} articoli **Derhy Donna**. In attesa di nuovi annunci.")
        return

    # Controllo nuovi annunci reali
    new_found = False
    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen_items:
            send_discord_alert(item)
            seen_items.add(item_id)
            new_found = True

    if new_found:
        save_seen_items(seen_items)
        print("✨ Nuovi articoli Vinted inviati!", flush=True)
    else:
        print("Nessun nuovo capo Derhy trovato su Vinted.", flush=True)

if __name__ == "__main__":
    main()

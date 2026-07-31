import datetime
import json
import os
import time
import cloudscraper  # Importato cloudscraper

# --- CONFIGURAZIONE ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1521502269118615622/2KQEzJpDBs6db1w8sI5XLXdRn9_A_vTkIG85p55QwNWcPyHl220vmvJ9acj8uMxGqBi8"
SEARCH_KEYWORD = "derhy"
SEEN_ITEMS_FILE = "seen_vinted_items.json"
CHECK_INTERVAL_SECONDS = 30  # Frequenza controllo in secondi

def get_current_time():
    return datetime.datetime.now().strftime("%H:%M:%S")

def send_discord_webhook(content=None, embed=None):
    # Usiamo cloudscraper/requests per inviare le notifiche a Discord
    payload = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]
    try:
        scraper = cloudscraper.create_scraper()
        scraper.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"[{get_current_time()}] Errore invio Discord: {e}", flush=True)

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
    price = item.get("price", {}).get("amount", item.get("price", "N/A"))
    currency = item.get("price", {}).get("currency_code", "EUR")
    item_url = item.get("url") or f"https://www.vinted.it/items/{item.get('id')}"
    
    photos = item.get("photos", [])
    photo_url = photos[0].get("url") if photos else item.get("photo", {}).get("url")

    embed = {
        "title": f"👗 Nuovo capo Vinted: {title}",
        "url": item_url,
        "color": 1752220,
        "fields": [
            {"name": "💰 Prezzo", "value": f"{price} {currency}", "inline": True},
            {"name": "🔍 Categoria/Brand", "value": "Derhy", "inline": True}
        ],
        "footer": {"text": "Vinted Monitor Bot"}
    }

    if photo_url:
        embed["image"] = {"url": photo_url}

    send_discord_webhook(content="@everyone Trovato un nuovo articolo con 'Derhy' nel titolo!", embed=embed)

def get_vinted_data():
    now = get_current_time()
    print(f"[{now}] 🔍 Avvio scansione Vinted per keyword: '{SEARCH_KEYWORD}'...", flush=True)

    # MODIFICA CHIAVE: Creiamo uno scraper che bypassa le sfide Cloudflare
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    try:
        # 1. Recupera la home per impostare i cookie di sessione bypassando Cloudflare
        home_resp = scraper.get("https://www.vinted.it", timeout=15)
        
        if home_resp.status_code in (403, 429):
            print(f"[{now}] ⚠️ ATTENZIONE: Homepage bloccata da Cloudflare/Anti-bot! (HTTP {home_resp.status_code})", flush=True)
            return None

        # 2. Richiesta all'API di ricerca di Vinted
        api_url = f"https://www.vinted.it/api/v2/catalog/items?search_text={SEARCH_KEYWORD}&order=newest_first"
        resp = scraper.get(api_url, timeout=15)
        
        if resp.status_code == 200:
            raw_items = resp.json().get("items", [])
            filtered_items = []
            
            for item in raw_items:
                title = str(item.get("title", "")).lower()
                if SEARCH_KEYWORD in title:
                    filtered_items.append(item)
                    
            print(f"[{now}] ✅ Scansione completata. Trovati {len(filtered_items)} articoli con '{SEARCH_KEYWORD}' nel TITOLO.", flush=True)
            return filtered_items

        elif resp.status_code in (403, 429):
            print(f"[{now}] ⚠️ ATTENZIONE: API Vinted bloccata da Cloudflare! (HTTP {resp.status_code})", flush=True)
            return None
            
        else:
            print(f"[{now}] ❌ Errore Vinted HTTP {resp.status_code}", flush=True)
            return None

    except Exception as e:
        print(f"[{now}] ❌ Errore durante il recupero da Vinted: {e}", flush=True)
        return None

def check_for_updates(seen_items):
    now = get_current_time()
    items = get_vinted_data()

    if items is None:
        print(f"[{now}] Scansione interrotta o fallita per errore di connessione/blocco.", flush=True)
        return seen_items

    if not seen_items:
        print(f"[{now}] Inizializzazione: salvo gli ID correnti...", flush=True)
        for item in items:
            item_id = item.get("id")
            if item_id:
                seen_items.add(item_id)
        save_seen_items(seen_items)
        send_discord_webhook(content=f"🟢 **Vinted Bot attivo**: Inizializzato con {len(seen_items)} articoli. In attesa di nuove uscite!")
        return seen_items

    new_found = False
    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen_items:
            send_discord_alert(item)
            seen_items.add(item_id)
            new_found = True
            print(f"[{now}] 🔔 Nuova notifica inviata per item ID: {item_id}", flush=True)

    if new_found:
        save_seen_items(seen_items)
        
    return seen_items

if __name__ == "__main__":
    seen_items = load_seen_items()
    print(f"[{get_current_time()}] 🚀 Bot avviato con Cloudscraper. Controllo ogni {CHECK_INTERVAL_SECONDS} secondi...")
    
    while True:
        try:
            seen_items = check_for_updates(seen_items)
        except Exception as e:
            print(f"[{get_current_time()}] ❌ Errore imprevisto nel ciclo: {e}", flush=True)
            
        time.sleep(CHECK_INTERVAL_SECONDS)

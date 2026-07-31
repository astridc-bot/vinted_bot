import datetime
import json
import os
import requests

# --- CONFIGURAZIONE ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1521502269118615622/2KQEzJpDBs6db1w8sI5XLXdRn9_A_vTkIG85p55QwNWcPyHl220vmvJ9acj8uMxGqBi8"
SEARCH_KEYWORD = "derhy"
SEEN_ITEMS_FILE = "seen_vinted_items.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def get_current_time():
    """Restituisce l'orario corrente formattato HH:MM:SS."""
    return datetime.datetime.now().strftime("%H:%M:%S")

def send_discord_webhook(content=None, embed=None):
    payload = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
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
    
    # Recupera foto
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

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "it-IT,it;q=0.9"
    })

    try:
        # 1. Recupera i cookie di sessione da Vinted Italia
        home_resp = session.get("https://www.vinted.it", timeout=10)
        
        # Controllo Cloudflare sulla Homepage
        if home_resp.status_code in (403, 429):
            print(f"[{now}] ⚠️ ATTENZIONE: Homepage bloccata da Cloudflare/Anti-bot! (HTTP {home_resp.status_code})", flush=True)
            return None

        # 2. Endpoint API di ricerca Vinted
        api_url = f"https://www.vinted.it/api/v2/catalog/items?search_text={SEARCH_KEYWORD}&order=newest_first"
        
        resp = session.get(api_url, timeout=10)
        
        if resp.status_code == 200:
            raw_items = resp.json().get("items", [])
            filtered_items = []
            
            for item in raw_items:
                title = str(item.get("title", "")).lower()
                
                # CONTROLLO RIGIDO: deve contenere "derhy" ESCLUSIVAMENTE NEL TITOLO
                if SEARCH_KEYWORD in title:
                    filtered_items.append(item)
                    
            print(f"[{now}] ✅ Scansione completata. Trovati {len(filtered_items)} articoli con '{SEARCH_KEYWORD}' nel TITOLO.", flush=True)
            return filtered_items

        elif resp.status_code in (403, 429):
            print(f"[{now}] ⚠️ ATTENZIONE: API Vinted bloccata da Cloudflare! (HTTP {resp.status_code})", flush=True)
            # Opzionale: avvisa anche su Discord se viene bloccato
            send_discord_webhook(content=f"⚠️ **Vinted Bot Bloccato**: Ricevuto errore HTTP {resp.status_code} da Cloudflare.")
            return None
            
        else:
            print(f"[{now}] ❌ Errore Vinted HTTP {resp.status_code}", flush=True)
            return None

    except Exception as e:
        print(f"[{now}] ❌ Errore durante il recupero da Vinted: {e}", flush=True)
        return None

def main():
    now = get_current_time()
    seen_items = load_seen_items()
    items = get_vinted_data()

    if items is None:
        print(f"[{now}] Scansione interrotta o fallita per errore di connessione/blocco.", flush=True)
        return

    # Primo avvio: memorizza tutti gli ID attuali per evitare notifiche massive
    if not seen_items:
        print(f"[{now}] Inizializzazione: salvo gli ID correnti...", flush=True)
        for item in items:
            item_id = item.get("id")
            if item_id:
                seen_items.add(item_id)
        save_seen_items(seen_items)
        send_discord_webhook(content=f"🟢 **Vinted Bot attivo**: Inizializzato con {len(seen_items)} articoli con 'Derhy' nel titolo. In attesa di nuove uscite!")
        return

    # Invio notifiche per ogni nuovo ID
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

if __name__ == "__main__":
    main()

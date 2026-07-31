import datetime
import json
import os
import time
import cloudscraper
from bs4 import BeautifulSoup

# --- CONFIGURAZIONE ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1521502269118615622/2KQEzJpDBs6db1w8sI5XLXdRn9_A_vTkIG85p55QwNWcPyHl220vmvJ9acj8uMxGqBi8"
SEARCH_KEYWORD = "derhy"
SEEN_ITEMS_FILE = "seen_vinted_items.json"
CHECK_INTERVAL_SECONDS = 30  # Frequenza controllo in secondi

def get_current_time():
    return datetime.datetime.now().strftime("%H:%M:%S")

def send_discord_webhook(content=None, embed=None):
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
    price = item.get("price", "N/A")
    item_url = item.get("url", "https://www.vinted.it")
    photo_url = item.get("photo")

    embed = {
        "title": f"👗 Nuovo capo Vinted: {title}",
        "url": item_url,
        "color": 1752220,
        "fields": [
            {"name": "💰 Prezzo", "value": price, "inline": True},
            {"name": "🔍 Categoria/Brand", "value": "Derhy", "inline": True}
        ],
        "footer": {"text": "Vinted HTML Monitor Bot"}
    }

    if photo_url:
        embed["image"] = {"url": photo_url}

    send_discord_webhook(content="@everyone Trovato un nuovo articolo con 'Derhy' nel titolo!", embed=embed)

def parse_vinted_html(html_content):
    """Estrae gli annunci analizzando il codice HTML della pagina."""
    soup = BeautifulSoup(html_content, "html.parser")
    items = []
    
    # Cerca i box contenitori degli annunci
    item_containers = soup.select('div[data-testid="grid-item"], div.feed-grid__item')
    
    for container in item_containers:
        # Estrai il link dell'articolo e l'ID
        link_elem = container.find("a", href=True)
        if not link_elem:
            continue
            
        href = link_elem["href"]
        if "/items/" not in href:
            continue
            
        item_url = href if href.startswith("http") else f"https://www.vinted.it{href}"
        
        # Estrai l'ID numerico dall'URL (es. /items/12345678-titolo)
        try:
            item_id = href.split("/items/")[1].split("-")[0]
        except IndexingError:
            continue
            
        # Estrai il titolo dell'immagine/annuncio
        img_elem = container.find("img")
        title = img_elem.get("alt", "") if img_elem else ""
        if not title:
            title = link_elem.get("title", "Senza titolo")
            
        # Estrai la foto
        photo_url = img_elem.get("src") if img_elem else None
        
        # Estrai il prezzo (cerca testi col simbolo €)
        price = "N/A"
        price_elem = container.find(lambda tag: tag.name in ["p", "span", "h3"] and "€" in tag.text)
        if price_elem:
            price = price_elem.text.strip()
            
        # Filtro per la parola chiave
        if SEARCH_KEYWORD in title.lower():
            items.append({
                "id": item_id,
                "title": title,
                "price": price,
                "url": item_url,
                "photo": photo_url
            })
            
    return items

def get_vinted_data():
    now = get_current_time()
    print(f"[{now}] 🔍 Avvio HTML Scraping per keyword: '{SEARCH_KEYWORD}'...", flush=True)

    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    # URL di ricerca HTML pubblica
    search_url = f"https://www.vinted.it/vetements?search_text={SEARCH_KEYWORD}&order=newest_first"

    try:
        resp = scraper.get(search_url, timeout=15)
        
        if resp.status_code == 200:
            filtered_items = parse_vinted_html(resp.text)
            print(f"[{now}] ✅ Scansione HTML completata. Trovati {len(filtered_items)} articoli con '{SEARCH_KEYWORD}' nel TITOLO.", flush=True)
            return filtered_items

        elif resp.status_code in (403, 429):
            print(f"[{now}] ⚠️ ATTENZIONE: Pagina HTML bloccata da Cloudflare! (HTTP {resp.status_code})", flush=True)
            return None
            
        else:
            print(f"[{now}] ❌ Errore Vinted HTTP {resp.status_code}", flush=True)
            return None

    except Exception as e:
        print(f"[{now}] ❌ Errore durante lo scraping HTML: {e}", flush=True)
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
        send_discord_webhook(content=f"🟢 **Vinted HTML Bot attivo**: Inizializzato con {len(seen_items)} articoli con 'Derhy' nel titolo. In attesa di nuove uscite!")
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
    print(f"[{get_current_time()}] 🚀 Bot HTML avviato. Controllo in corso ogni {CHECK_INTERVAL_SECONDS} secondi...")
    
    while True:
        try:
            seen_items = check_for_updates(seen_items)
        except Exception as e:
            print(f"[{get_current_time()}] ❌ Errore imprevisto nel ciclo: {e}", flush=True)
            
        time.sleep(CHECK_INTERVAL_SECONDS)

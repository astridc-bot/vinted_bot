import datetime
import json
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import cloudscraper
from bs4 import BeautifulSoup

# --- CONFIGURAZIONE ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1521502269118615622/2KQEzJpDBs6db1w8sI5XLXdRn9_A_vTkIG85p55QwNWcPyHl220vmvJ9acj8uMxGqBi8"
SEARCH_KEYWORD = "derhy"
SEEN_ITEMS_FILE = "seen_vinted_items.json"
CHECK_INTERVAL_SECONDS = 30  # Frequenza controllo in secondi

# Dummy HTTP Server per soddisfare l'healthcheck di Render (elimina l'avviso "No open ports")
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Vinted Bot Active & Running!")

    def log_message(self, format, *args):
        return  # Nasconde i log HTTP per non intasare la console

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

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
    soup = BeautifulSoup(html_content, "html.parser")
    items = []
    
    links = soup.find_all("a", href=True)
    
    for link in links:
        href = link["href"]
        if "/items/" in href:
            item_url = href if href.startswith("http") else f"https://www.vinted.it{href}"
            clean_url = item_url.split("?")[0]
            
            img_elem = link.find("img")
            title = ""
            if img_elem and img_elem.get("alt"):
                title = img_elem.get("alt")
            elif link.get("title"):
                title = link.get("title")

            if not title:
                try:
                    title = clean_url.split("/items/")[1].replace("-", " ")
                except IndexError:
                    title = "Senza titolo"

            photo_url = img_elem.get("src") if img_elem else None

            price = "Vedi su Vinted"
            parent = link.find_parent("div")
            if parent:
                price_elem = parent.find(lambda tag: tag.name in ["p", "span", "div"] and "€" in tag.text)
                if price_elem:
                    price = price_elem.text.strip()

            if SEARCH_KEYWORD in title.lower() or SEARCH_KEYWORD in clean_url.lower():
                items.append({
                    "id": clean_url,
                    "title": title.strip().capitalize(),
                    "price": price,
                    "url": clean_url,
                    "photo": photo_url
                })
            
    unique_items = {item["id"]: item for item in items}.values()
    return list(unique_items)

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

    # HEADERS FONDAMENTALI PER EVITARE L'ERRORE HTTP 406
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.vinted.it/",
        "Sec-Ch-Ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1"
    }

    search_url = f"https://www.vinted.it/vetements?search_text={SEARCH_KEYWORD}&order=newest_first"

    try:
        resp = scraper.get(search_url, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            filtered_items = parse_vinted_html(resp.text)
            print(f"[{now}] ✅ Scansione HTML completata. Trovati {len(filtered_items)} articoli con '{SEARCH_KEYWORD}'.", flush=True)
            return filtered_items

        elif resp.status_code in (403, 406, 429):
            print(f"[{now}] ⚠️ ATTENZIONE: Blocco anti-bot Vinted! (HTTP {resp.status_code})", flush=True)
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
        print(f"[{now}] Inizializzazione: salvo tutti gli articoli correnti per evitare spam...", flush=True)
        for item in items:
            item_id = item.get("id")
            if item_id:
                seen_items.add(item_id)
        save_seen_items(seen_items)
        send_discord_webhook(content=f"🟢 **Vinted Bot riattivato**: Salvati {len(seen_items)} articoli correnti. In attesa di nuove uscite!")
        return seen_items

    new_found = False
    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen_items:
            send_discord_alert(item)
            seen_items.add(item_id)
            new_found = True
            print(f"[{now}] 🔔 Nuova notifica inviata per: {item_id}", flush=True)

    if new_found:
        save_seen_items(seen_items)
        
    return seen_items

if __name__ == "__main__":
    # Avvia il dummy server HTTP in un thread separato per Render
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    seen_items = load_seen_items()
    print(f"[{get_current_time()}] 🚀 Bot avviato. Controllo ogni {CHECK_INTERVAL_SECONDS} secondi...")
    
    while True:
        try:
            seen_items = check_for_updates(seen_items)
        except Exception as e:
            print(f"[{get_current_time()}] ❌ Errore imprevisto nel ciclo: {e}", flush=True)
            
        time.sleep(CHECK_INTERVAL_SECONDS)

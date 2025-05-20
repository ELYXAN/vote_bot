import asyncio
import json
import os
import time
from datetime import datetime, timedelta
import webbrowser  # Import für das Öffnen des Browsers
import secrets     # Import für den 'state' Parameter

import aiohttp
import gspread
import pandas as pd
# import websockets # Nicht direkt im gezeigten Code verwendet, ggf. später für echten WebSocket
from fuzzywuzzy import process
from oauth2client.service_account import ServiceAccountCredentials

# --- Konfiguration und Konstanten ---
CONFIG_FILE = 'config.json'
BROADCASTER_ID = 'YOUR_BROADCASTER_ID_HERE' # Muss als String sein für API calls
CLIENT_SECRET = 'CLIENT_SECRET'
REDIRECT_URI = 'http://localhost' # Standard für lokale Skripte

# Scopes - WICHTIG: Passe diese an, falls nötig
STREAMER_SCOPES = 'channel:read:redemptions channel:manage:redemptions'
CHAT_BOT_SCOPES = 'chat:read chat:edit user:write:chat'

# Standardkonfiguration (inkl. Scopes für Info)
DEFAULT_CONFIG = {
    'streamer': {
        'client_id': 'CLIENT_ID',
        'client_secret': CLIENT_SECRET, # Füge hier dein Secret ein!
        'access_token': '',
        'refresh_token': '',
        'token_expiry': '',
        'scopes': STREAMER_SCOPES
    },
    'chat_bot': {
        'client_id': 'CLIENT_ID',
        'client_secret': CLIENT_SECRET, # Füge hier dein Secret ein!
        'access_token': '',
        'refresh_token': '',
        'token_expiry': '',
        'scopes': CHAT_BOT_SCOPES
    },
    'twitch_username': 'TWITCH_CHANNEL_NAME',
    'rewards': {
        'normal_vote': 'VOTE_ID_1',
        'super_vote': 'VOTE_ID_2'
    },
    'spreadsheet_id': 'YOUR_SPREADSHEET_ID',
    'min_match_score': 80,
    'super_vote_weight': 10,
    'broadcaster_id': BROADCASTER_ID
}

# Cache für Daten
cache = {
    'games_list': [],
    'processed_ids': set(),
    'last_cache_update': 0,
    'cache_validity': 300,  # 5 Minuten
    'worksheet': None,
    'spreadsheet': None
}

# Event-Verarbeitung Queue
vote_queue = asyncio.Queue()

# --- Banner Funktion ---
def banner():
    # ... (Banner Code unverändert) ...
    print("""
██╗   ██╗ ██████╗ ████████╗███████╗    ████████╗██████╗  █████╗  ██████╗██╗  ██╗███████╗██████╗ 
██║   ██║██╔═══██╗╚══██╔══╝██╔════╝    ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
██║   ██║██║   ██║   ██║   █████╗         ██║   ██████╔╝███████║██║     █████╔╝ █████╗  ██████╔╝
██║   ██║██║   ██║   ██║   ██╔══╝         ██║   ██╔══██╗██╔══██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗
╚██████╔╝╚██████╔╝   ██║   ███████╗       ██║   ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██║  ██║
 ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝       ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

Version 3.0 - Made by: ELYXAN / KUS_SWAT_ - Async + OAuth Fix - Websocket Version

Read the Docs - https://github.com/ELYXAN/vote_bot/edit/main/vote_bot_3.0.py
    """)


# --- Hilfsfunktionen ---
def load_config():
    """Lädt die Konfiguration oder erstellt eine neue mit Standardwerten"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            # Lade vorhandene Konfiguration
            loaded_config = json.load(f)
            # Stelle sicher, dass alle Default-Keys vorhanden sind (für Updates)
            # Überschreibe aber nicht vorhandene Token/Secrets etc.
            for key, value in DEFAULT_CONFIG.items():
                if key not in loaded_config:
                    loaded_config[key] = value
                elif isinstance(value, dict): # Für 'streamer' und 'chat_bot' dicts
                     for sub_key, sub_value in value.items():
                         if sub_key not in loaded_config[key]:
                             loaded_config[key][sub_key] = sub_value
            # ACHTUNG: Secrets aus Default überschreiben NICHT die vom User gespeicherten
            print(loaded_config['streamer'].get('client_secret'))
            print(loaded_config['streamer']['client_secret'])
            print(loaded_config['chat_bot'].get('client_secret'))
            print(loaded_config['chat_bot']['client_secret'])
            if not loaded_config['streamer'].get('client_secret')  == '':
                 print("WARNUNG: Bitte trage das 'client_secret' für 'streamer' in config.json ein!")
            if not loaded_config['chat_bot'].get('client_secret')  == '':
                 print("WARNUNG: Bitte trage das 'client_secret' für 'chat_bot' in config.json ein!")
            return loaded_config
    else:
        print(f"Konfigurationsdatei {CONFIG_FILE} nicht gefunden. Erstelle neue.")
        print("WICHTIG: Bitte trage die 'client_secret' Werte in der config.json ein, bevor du den Bot neu startest!")
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

def save_config(config):
    """Speichert die aktualisierte Konfiguration"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# --- (load/save processed_ids, save_inaccurate_game unverändert) ---
def load_processed_ids():
    """Lädt die Liste der bereits verarbeiteten Vote-IDs"""
    try:
        with open('Vote_IDs.csv', 'r') as f:
            return set(line.strip() for line in f.readlines())
    except FileNotFoundError:
        return set()

def save_processed_id(id_set, vote_id):
    """Speichert eine neue Vote-ID in der Liste"""
    id_set.add(vote_id)
    with open('Vote_IDs.csv', 'a') as f:
        f.write(str(vote_id) + '\n')
    return id_set

def save_inaccurate_game(game_name):
    """Speichert ein ungenau eingegebenes Spiel"""
    with open('inacurate_games.csv', 'a') as f:
        f.write(f"{game_name} Vote Anzahl: 1\n")
    print(f"Eintrag in CSV Datei: {game_name}")

# --- Token Management ---

def check_token_validity(config, account_type):
    """Überprüft, ob das Token noch gültig ist (rein basierend auf Ablaufdatum)"""
    if not config[account_type].get('access_token') or not config[account_type].get('token_expiry'):
        return False

    try:
        # Konvertiere ISO-Format String zu datetime Objekt
        # Stellt sicher, dass die Zeitzoneninformation (falls vorhanden) korrekt behandelt wird
        expiry_time_str = config[account_type]['token_expiry']
        # Entferne 'Z' am Ende, falls vorhanden, Python's fromisoformat mag das nicht direkt
        if expiry_time_str.endswith('Z'):
            expiry_time_str = expiry_time_str[:-1] + '+00:00'

        # Konvertiere zu datetime, falls es keine Zeitzoneninfo hat, nimm an es ist UTC
        expiry_time = datetime.fromisoformat(expiry_time_str)
        if expiry_time.tzinfo is None:
             # Wenn keine Zeitzone angegeben ist, nimm an, es ist die lokale Zeit
             # oder besser: versuche es als UTC zu interpretieren, da Twitch oft UTC liefert
              pass # Oder spezifiziere eine Zeitzone, z.B. expiry_time = expiry_time.replace(tzinfo=timezone.utc)

        # Aktuelle Zeit, idealerweise auch Zeitzonen-bewusst (nutze UTC für Vergleiche)
        now = datetime.now(expiry_time.tzinfo) # Nutze die gleiche Zeitzone wie expiry_time

        # Füge einen Puffer hinzu (z.B. 60 Sekunden), um Token rechtzeitig zu erneuern
        return now < (expiry_time - timedelta(seconds=60))
    except (ValueError, TypeError) as e:
        print(f"Fehler beim Parsen des Token-Ablaufdatums für {account_type}: {e}")
        return False


async def request_initial_token(session, config, account_type):
    """Fordert den Benutzer auf, die Anwendung zu autorisieren, um erste Tokens zu erhalten."""
    print("-" * 50)
    print(f"INITIIERE AUTORISIERUNG für Account: {account_type}")
    print("-" * 50)

    client_id = config[account_type]['client_id']
    scopes = config[account_type]['scopes']
    state = secrets.token_urlsafe(16) # Zufälliger State für CSRF-Schutz

    auth_url = (
        f"https://id.twitch.tv/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scopes.replace(' ', '+')}" # Scopes mit '+' trennen für URL
        f"&state={state}"
    )

    print(f"\nBitte öffne die folgende URL in deinem Browser:")
    print(auth_url)
    print(f"\nNachdem du die Anwendung autorisiert hast, wirst du zu '{REDIRECT_URI}?code=...' weitergeleitet.")
    print("Die Seite wird wahrscheinlich einen Fehler anzeigen (das ist normal!).")
    print("Kopiere den kompletten Wert des 'code'-Parameters aus der Adressleiste deines Browsers.")
    print("Der Code ist der Teil nach 'code=' und vor '&scope=...' (falls vorhanden).")

    # Versuche, den Browser automatisch zu öffnen
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f"(Konnte den Browser nicht automatisch öffnen: {e})")

    while True:
        authorization_code = input("\nFüge den kopierten 'code' hier ein und drücke Enter: ").strip()
        if authorization_code:
            break
        else:
            print("Eingabe ungültig, bitte versuche es erneut.")

    # Code gegen Tokens tauschen
    token_url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': client_id,
        'client_secret': config[account_type]['client_secret'],
        'code': authorization_code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI
    }

    try:
        async with session.post(token_url, data=params) as response:
            if response.status == 200:
                data = await response.json()
                config[account_type]['access_token'] = data['access_token']
                config[account_type]['refresh_token'] = data['refresh_token']
                # Expiry-Zeit berechnen und speichern (als ISO Format String)
                expires_in = data.get('expires_in', 3600) # Standard 1h falls nicht vorhanden
                config[account_type]['token_expiry'] = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

                print(f"Token für {account_type} erfolgreich erhalten und gespeichert!")
                save_config(config) # Speichere die neuen Tokens sofort
                print("-" * 50)
                return True
            else:
                print(f"Fehler beim Austauschen des Codes gegen Tokens für {account_type}: {response.status}")
                print(await response.text())
                print("Mögliche Ursachen: Falscher Code eingegeben, Client Secret falsch, Redirect URI stimmt nicht überein.")
                print("-" * 50)
                return False
    except Exception as e:
        print(f"Exception beim Token-Austausch für {account_type}: {str(e)}")
        print("-" * 50)
        return False


async def refresh_token(session, config, account_type):
    """Token über Refresh-Token erneuern"""
    print(f"Versuche Token für {account_type} zu erneuern...")

    refresh_token_value = config[account_type].get('refresh_token')
    if not refresh_token_value:
        print(f"Kein Refresh-Token für {account_type} vorhanden. Überspringe Erneuerung.")
        return False # Kein Refresh-Token -> Erneuerung nicht möglich

    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token_value,
        'client_id': config[account_type]['client_id'],
        'client_secret': config[account_type]['client_secret']
    }

    try:
        async with session.post(url, data=params) as response: # data= statt params= für POST Body
            if response.status == 200:
                data = await response.json()
                config[account_type]['access_token'] = data['access_token']
                # WICHTIG: Twitch KANN einen NEUEN Refresh-Token senden, diesen auch speichern!
                if 'refresh_token' in data and data['refresh_token']:
                    config[account_type]['refresh_token'] = data['refresh_token']
                else:
                     print(f"WARNUNG: Kein neuer Refresh Token von Twitch für {account_type} erhalten. Der alte bleibt bestehen.")

                # Expiry-Zeit berechnen und speichern
                expires_in = data.get('expires_in', 3600)
                config[account_type]['token_expiry'] = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

                print(f"Token für {account_type} erfolgreich erneuert! Gültig bis: {config[account_type]['token_expiry']}")
                save_config(config) # Speichere die erneuerten Tokens
                return True
            elif response.status in [400, 401]:
                response_text = await response.text()
                print(f"Fehler beim Erneuern des Tokens für {account_type}: {response.status} - {response_text}")
                if "Invalid refresh token" in response_text:
                    print(f"Refresh-Token für {account_type} ist ungültig geworden.")
                    # Reset der Tokens, damit beim nächsten Mal die Neu-Autorisierung getriggert wird
                    config[account_type]['access_token'] = ''
                    config[account_type]['refresh_token'] = ''
                    config[account_type]['token_expiry'] = ''
                    save_config(config)
                return False # Refresh fehlgeschlagen
            else:
                print(f"Unerwarteter Fehler beim Erneuern des Tokens für {account_type}: {response.status} - {await response.text()}")
                return False
    except Exception as e:
        print(f"Exception beim Token-Refresh für {account_type}: {str(e)}")
        return False


async def ensure_valid_token(session, config, account_type):
    """Stellt sicher, dass ein gültiges Token vorhanden ist (prüft, erneuert, fordert neu an)."""
    if check_token_validity(config, account_type):
        # print(f"Token für {account_type} ist gültig.")
        return True # Token ist vorhanden und gültig

    print(f"Token für {account_type} ist ungültig oder fehlt. Versuche Erneuerung/Neuautorisierung...")

    # 1. Versuche Refresh-Token, falls vorhanden
    if config[account_type].get('refresh_token'):
        if await refresh_token(session, config, account_type):
            return True # Erfolgreich erneuert

    # 2. Wenn Refresh fehlgeschlagen oder nicht vorhanden war -> Initialen Token anfordern
    print(f"Token-Erneuerung für {account_type} fehlgeschlagen oder kein Refresh-Token vorhanden.")
    # Überprüfe, ob Client Secret vorhanden ist
    if not config[account_type].get('client_secret')  in CLIENT_SECRET:
         print(f"FEHLER: Client Secret für '{account_type}' fehlt in config.json. Bitte eintragen und neu starten.")
         return False

    if await request_initial_token(session, config, account_type):
        return True # Erfolgreich initialen Token erhalten
    else:
        print(f"FEHLER: Konnte keinen gültigen Token für {account_type} erhalten.")
        return False # Auch initialer Token fehlgeschlagen


# --- (Google Sheets, EventSub, Listener, Prozessor etc. bleiben größtenteils gleich) ---
# --- Stelle sicher, dass ensure_valid_token VOR API-Aufrufen genutzt wird! ---

async def init_google_sheets(config):
    """Initialisiert die Verbindung zu Google Sheets"""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = ServiceAccountCredentials.from_json_keyfile_name('Vote tracking.json', scopes) # Stelle sicher, dass die Datei existiert
        client = gspread.authorize(creds)

        # Spreadsheet öffnen
        cache['spreadsheet'] = client.open_by_key(config['spreadsheet_id'])
        cache['worksheet'] = cache['spreadsheet'].get_worksheet(0) # Nimmt das erste Blatt

        # Games-Liste laden
        await update_games_cache()
        print("Google Sheets Verbindung erfolgreich.")
    except FileNotFoundError:
         print("FEHLER: Google Sheets Credentials Datei ('Vote tracking.json') nicht gefunden.")
         cache['worksheet'] = None # Stelle sicher, dass es None ist, wenn Fehler auftritt
    except Exception as e:
         print(f"FEHLER bei der Initialisierung von Google Sheets: {e}")
         cache['worksheet'] = None


async def update_games_cache():
    """Aktualisiert den Cache der Spieleliste"""
    if cache['worksheet']:
        try:
            # Nimm nur die zweite Spalte (Index 1), ignoriere Header (optional, je nach Sheet)
            # Verwende get('B2:B') um nur die relevante Spalte ab Zeile 2 zu holen
            games_data = cache['worksheet'].get('B2:B')
            # Extrahiere die Spielnamen aus der Liste von Listen
            cache['games_list'] = [item[0] for item in games_data if item] # Nur wenn Zeile nicht leer ist
            cache['last_cache_update'] = time.time()
            print(f"Spiele-Cache aktualisiert ({len(cache['games_list'])} Spiele gefunden)")
        except Exception as e:
            print(f"Fehler beim Aktualisieren des Spiele-Caches von Google Sheets: {e}")
            # Optional: Cache leeren oder alten behalten?
            # cache['games_list'] = []
    else:
        print("Google Sheets nicht initialisiert, kann Spiele-Cache nicht aktualisieren.")

# +++ NEUE FUNKTION +++
async def calculate_rank_and_notify(session, config, game_name, new_votes, user):
    """
    Liest den aktuellen Stand, berechnet den neuen Rang lokal nach Hinzufügen
    des Votes und sendet die Benachrichtigung.
    Gibt den berechneten Rang zurück oder 0 bei Fehler.
    """
    if not cache.get('worksheet'): # Sicherer Zugriff auf Cache
        print("Sheet nicht verfügbar, Rang kann nicht berechnet werden.")
        return 0

    print(f"Berechne hypothetischen Rang für '{game_name}' mit {new_votes} Votes...")
    rank = 0
    try:
        # Hole aktuelle Votes und Spiele (A2:B) - UNFORMATTED für Zahlen
        # Wichtig: Hole String-Werte, um Konsistenz zu wahren, Konvertierung später
        current_data = cache['worksheet'].get('A2:B', value_render_option='UNFORMATTED_VALUE')
        # Manchmal braucht man value_render_option='FORMATTED_STRING' wenn Zahlen seltsam sind

        game_votes_list = []
        game_found_in_list = False

        if current_data:
            for row in current_data:
                if len(row) >= 2:
                    try:
                        # Versuche Vote-Zahl zu bekommen, nimm 0 bei Fehler/Leere
                        current_game_votes = int(row[0]) if str(row[0]).strip() else 0
                    except (ValueError, TypeError):
                        current_game_votes = 0
                    # Spielname als String
                    current_game_name = str(row[1]).strip()

                    if not current_game_name: # Überspringe leere Spielnamen-Zellen
                         continue

                    # Wenn es das gevotete Spiel ist, nutze die *neue* Stimmenzahl
                    if current_game_name == game_name:
                        game_votes_list.append({'votes': new_votes, 'name': current_game_name})
                        game_found_in_list = True
                    else:
                        game_votes_list.append({'votes': current_game_votes, 'name': current_game_name})
        else:
             print("Keine Daten in A2:B gefunden für Rangberechnung.")


        # Wenn das Spiel komplett neu war und nicht in der Liste ist, füge es hinzu
        if not game_found_in_list:
             print(f"'{game_name}' ist neu, füge zur lokalen Liste hinzu.")
             game_votes_list.append({'votes': new_votes, 'name': game_name})

        # Sortiere die lokale Liste: Absteigend nach Votes, dann aufsteigend nach Name
        # Sortiere direkt die Liste von Dictionaries
        game_votes_list.sort(key=lambda x: (-x['votes'], x['name']))

        # Finde den Rang (1-basiert) in der *lokal sortierten* Liste
        for i, game_data in enumerate(game_votes_list, start=1):
            if game_data['name'] == game_name:
                rank = i
                break

        # Sende die Nachricht
        if rank > 0:
            print(f"'{game_name}' ist nach diesem Vote auf Rang #{rank}.")
            chat_message = f"@{user} hat für '{game_name}' gevotet! | Votes: {new_votes} | Neue Position: #{rank}"
            await send_chat_message(session, config, chat_message)
        else:
            # Fallback, falls Rang nicht gefunden wurde (sollte nicht passieren)
            print(f"WARNUNG: Konnte Rang für '{game_name}' nicht ermitteln nach lokaler Sortierung.")
            chat_message = f"@{user} hat für '{game_name}' gevotet! | Votes: {new_votes}"
            await send_chat_message(session, config, chat_message)

        return rank

    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API Fehler beim Lesen für Rangberechnung: {e}")
        return 0 # Fehler signalisieren
    except Exception as e:
        print(f"Fehler beim Rang berechnen für '{game_name}': {e}")
        import traceback
        traceback.print_exc()
        return 0 # Fehler signalisieren
    
# -- Platzhalter für EventSub WebSocket ---
# Die Implementierung eines persistenten EventSub WebSockets ist komplexer
# und würde eine eigene Verbindungs- und Nachrichtenbehandlungslogik erfordern.
# Der aktuelle Code pollt die API, was weniger effizient ist.
async def listen_to_redemptions(config):
    """Hört auf Channel Point Redemptions (momentan via API Polling)"""
    print("Starte Listener für Channel Point Redemptions (API Polling)...")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Stelle sicher, dass das Streamer-Token gültig ist
                if not await ensure_valid_token(session, config, 'streamer'):
                    print("Streamer-Token ungültig, warte 60 Sekunden...")
                    await asyncio.sleep(60) # Längere Pause bei Token-Problem
                    continue

                # Überprüfe alle konfigurierten Reward-IDs
                rewards_to_check = []
                if config['rewards'].get('normal_vote'):
                    rewards_to_check.append(('normal_vote', config['rewards']['normal_vote']))
                if config['rewards'].get('super_vote'):
                     rewards_to_check.append(('super_vote', config['rewards']['super_vote']))

                if not rewards_to_check:
                     print("Keine Reward-IDs in config.json gefunden. Listener pausiert.")
                     await asyncio.sleep(30)
                     continue


                headers = {
                    'Client-ID': config['streamer']['client_id'],
                    'Authorization': f"Bearer {config['streamer']['access_token']}"
                }

                found_new = False
                for vote_type, reward_id in rewards_to_check:
                    endpoint = f"https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions"
                    params = {
                        'broadcaster_id': config['broadcaster_id'],
                        'reward_id': reward_id,
                        'status': 'UNFULFILLED',
                        'first': '50' # Hole bis zu 50 auf einmal
                    }

                    async with session.get(endpoint, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            redemptions = data.get('data', [])
                            #print(f"Abfrage für {vote_type} ({reward_id}): {len(redemptions)} unerfüllt gefunden.")

                            for entry in redemptions:
                                vote_id = entry.get('id')
                                if vote_id not in cache['processed_ids']:
                                    found_new = True
                                    await vote_queue.put({
                                        'entry': entry,
                                        'vote_type': vote_type,
                                        'reward_id': reward_id
                                    })
                                    print(f"Neuer Vote '{entry.get('user_input', '')}' von {entry.get('user_name')} ({vote_type}) zur Queue hinzugefügt (ID: {vote_id}).")
                                    # Füge zur Sicherheit sofort zur lokalen Kopie hinzu,
                                    # gespeichert wird es erst in process_votes
                                    cache['processed_ids'].add(vote_id)

                        elif response.status == 401:
                            print("Listener: Streamer-Token ungültig (401). Wird im nächsten Zyklus erneuert.")
                            # Breche innere Schleife ab, da Token ungültig
                            break
                        elif response.status == 403:
                             print(f"Listener: Zugriff verweigert (403) für Reward {reward_id}. Überprüfe Berechtigungen (Scopes) des Streamer-Tokens.")
                        else:
                            print(f"Fehler beim Abrufen von Redemptions für {reward_id}: {response.status} - {await response.text()}")

                    await asyncio.sleep(0.5) # Kleine Pause zwischen den Reward-Abfragen

                # Wartezeit, nur wenn keine neuen Votes gefunden wurden, um schneller zu reagieren
                if not found_new:
                    await asyncio.sleep(2.0) # Wartezeit zwischen den Poll-Zyklen
                else:
                     await asyncio.sleep(0.5) # Kürzere Wartezeit wenn was gefunden wurde

            except aiohttp.ClientConnectorError as e:
                 print(f"Verbindungsfehler im Listener: {e}. Warte 15 Sekunden...")
                 await asyncio.sleep(15)
            except Exception as e:
                print(f"Unerwarteter Fehler im Redemption Listener: {str(e)}")
                await asyncio.sleep(10) # Warte bei unbekannten Fehlern


async def process_votes(config):
    """Verarbeitet Votes aus der Queue"""
    print("Starte Vote Processor...")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                vote_data = await vote_queue.get()
                entry = vote_data['entry']
                vote_type = vote_data['vote_type']
                reward_id = vote_data['reward_id']
                vote_id = entry.get('id')
                user = entry.get('user_name')
                user_input = entry.get('user_input', '').strip()

                print(f"\nVerarbeite Vote ID: {vote_id} von {user} für '{user_input}' ({vote_type})")

                if not cache.get('worksheet'):
                    print("Google Sheet nicht verfügbar. Vote kann nicht verarbeitet werden.")
                    vote_queue.task_done()
                    continue

                # Token Checks (Streamer für Fulfill, Bot wird in Notify geprüft)
                if not await ensure_valid_token(session, config, 'streamer'):
                     print("Streamer-Token ungültig. Vote kann nicht als erfüllt markiert werden.")
                     vote_queue.task_done()
                     continue


                if time.time() - cache['last_cache_update'] > cache['cache_validity']:
                    await update_games_cache() # update_games_cache muss angepasst sein, um nur B2:B zu lesen!

                vote_weight = config.get('super_vote_weight', 10) if vote_type == 'super_vote' else 1

                match = None
                score = 0
                # ... (Fuzzy Matching Code wie vorher) ...
                try:
                    # process.extractOne braucht eine nicht-leere Liste
                    if cache['games_list']:
                         user_input_lower = user_input.lower()
                         games_list_lower = [game.lower() for game in cache['games_list']]
                         result = process.extractOne(user_input_lower, games_list_lower, score_cutoff=config.get('min_match_score', 80))

                         if result:
                              match_index = games_list_lower.index(result[0])
                              match = cache['games_list'][match_index]
                              score = result[1]
                              print(f"Match gefunden: '{match}' (Score: {score}) für Eingabe '{user_input}'")
                         else:
                              print(f"Kein ausreichend gutes Match für '{user_input}'.")
                    else:
                         print("Spieleliste ist leer. Fuzzy Matching nicht möglich.")

                except Exception as e:
                    print(f"Fehler beim Fuzzy Matching für '{user_input}': {str(e)}")

                # --- Verarbeitung des Matches ---
                if match:
                    try:
                        # Finde Zelle für das Spiel
                        cell = None
                        try:
                             # Versuche genaue Übereinstimmung (Groß/Klein beachtet)
                             cell = cache['worksheet'].find(match, in_column=2)
                        except gspread.exceptions.CellNotFound:
                              print(f"Spiel '{match}' nicht exakt in Spalte 2 gefunden. Versuche Cache-Update...")
                              await update_games_cache() # Stelle sicher, dass Cache aktuell ist
                              # Versuche es erneut nach Cache Update
                              try:
                                   cell = cache['worksheet'].find(match, in_column=2)
                              except gspread.exceptions.CellNotFound:
                                   print(f"Spiel '{match}' auch nach Cache-Update nicht gefunden.")
                                   # Hier könnte man überlegen, das Spiel als "neu" zu behandeln
                                   # Für jetzt: Fahre fort, calculate_rank_and_notify wird es hinzufügen

                        # Aktuelle Votes lesen (falls Zelle gefunden)
                        current_votes = 0
                        if cell:
                              current_votes_str = cache['worksheet'].cell(cell.row, 1).value
                              try:
                                  current_votes = int(current_votes_str) if current_votes_str else 0
                              except ValueError:
                                  print(f"WARNUNG: Ungültiger Wert '{current_votes_str}' in Vote-Zelle ({cell.row}, 1) für '{match}'. Setze auf 0.")
                                  current_votes = 0
                        else:
                             print(f"Spiel '{match}' ist neu oder konnte nicht im Sheet gefunden werden. Starte mit 0 Votes.")


                        new_votes = current_votes + vote_weight

                        # --------- NEUE REIHENFOLGE ---------
                        # 1. Rang berechnen und Nachricht senden (nutzt new_votes)
                        #    Diese Funktion liest das Sheet selbst und simuliert die Änderung
                        await calculate_rank_and_notify(session, config, match, new_votes, user)

                        # 2. Einzelne Zelle im Sheet aktualisieren (falls vorhanden)
                        if cell:
                            try:
                                cache['worksheet'].update_cell(cell.row, 1, new_votes)
                                print(f"Vote für '{match}' Zelle ({cell.row}, 1) auf {new_votes} aktualisiert.")
                            except gspread.exceptions.APIError as e:
                                print(f"Google API Fehler beim Aktualisieren der Zelle für '{match}': {e}")
                                # Führe trotzdem Sortierung aus? Ja.
                        else:
                            # Wenn die Zelle nicht gefunden wurde, MUSS sort_spreadsheet
                            # das neue Spiel hinzufügen können (passiert durch get_all_records).
                            print(f"Spiel '{match}' wird durch die Sortierung neu hinzugefügt.")


                        # 3. Gesamtes Spreadsheet im Hintergrund sortieren
                        await sort_spreadsheet_and_notify(config)
                        # ---------------------------------

                        # 4. Vote als erledigt markieren
                        await fulfill_vote(session, config, reward_id, vote_id)

                    except gspread.exceptions.APIError as e:
                         print(f"Google Sheets API Fehler bei Verarbeitung von '{match}': {e}")
                    except Exception as e:
                        print(f"Unerwarteter Fehler bei der Verarbeitung des Votes für '{match}': {str(e)}")
                        import traceback
                        traceback.print_exc()

                else:
                    # Kein Match gefunden
                    print(f"Kein passendes Spiel für '{user_input}'. Wird als ungenau gespeichert.")
                    save_inaccurate_game(user_input)
                    await fulfill_vote(session, config, reward_id, vote_id)

                # Markiere den Job in der Queue als erledigt
                vote_queue.task_done()
                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"Schwerwiegender Fehler im Vote-Verarbeitungs-Loop: {str(e)}")
                import traceback
                traceback.print_exc()
                if 'vote_data' in locals():
                    vote_queue.task_done()
                await asyncio.sleep(1)


async def sort_spreadsheet_and_notify(config):
    """Sortiert das Spreadsheet nach Votes (ohne Benachrichtigung)."""
    if not cache.get('worksheet'):
        print("Spreadsheet nicht verfügbar, Sortierung übersprungen.")
        return

    # Kurze Pause einfügen, um sicherzustellen, dass update_cell verarbeitet wurde?
    # await asyncio.sleep(0.5) # Optional, evtl. nicht nötig

    try:
        print("Sortiere Spreadsheet (im Hintergrund)...")
        # Daten holen (alle Werte auf einmal, um API-Aufrufe zu reduzieren)
        # Holen als Liste von Dicts ist oft einfacher mit Pandas
        all_records = cache['worksheet'].get_all_records(numericise_ignore=['all']) # Strings behalten

        if not all_records:
            print("Keine Daten im Spreadsheet gefunden (get_all_records). Sortierung abgebrochen.")
            return

        df = pd.DataFrame(all_records)

        # Überprüfe Spaltennamen (ersetze 'Game' ggf. durch den tatsächlichen Namen)
        vote_column = 'Votes'
        game_column = 'Game'
        if vote_column not in df.columns:
             print(f"FEHLER: Spalte '{vote_column}' nicht im Spreadsheet gefunden!")
             return
        if game_column not in df.columns:
             print(f"FEHLER: Spalte '{game_column}' nicht im Spreadsheet gefunden!")
             return

        # Konvertiere 'Votes' zu Int, behandle Fehler
        df[vote_column] = pd.to_numeric(df[vote_column], errors='coerce').fillna(0).astype(int)
        # Stelle sicher, dass Spielnamen Strings sind und trimme Leerzeichen
        df[game_column] = df[game_column].astype(str).str.strip()
        # Entferne Zeilen mit leerem Spielnamen nach dem Trimmen
        df = df[df[game_column] != '']


        # Nach Votes absteigend sortieren, dann alphabetisch nach Spiel
        sorted_df = df.sort_values(by=[vote_column, game_column], ascending=[False, True])

        # Daten für das Update vorbereiten (Header + sortierte Daten als Liste von Listen)
        update_data = [sorted_df.columns.values.tolist()] + sorted_df.astype(str).values.tolist()

        # Gesamtes Blatt (oder relevanten Bereich) aktualisieren
        # Update ab A1 überschreibt das gesamte Blatt mit den sortierten Daten
        # Stelle sicher, dass die Anzahl der Zeilen/Spalten passt
        range_to_update = f'A1:{gspread.utils.rowcol_to_a1(len(update_data), len(update_data[0]))}'
        # cache['worksheet'].update(values=update_data, range_name='A1') # Einfacher, überschreibt aber ggf. Formatierung
        cache['worksheet'].update(range_name=range_to_update, values=update_data) # Sicherer für Bereich

        print(f"Spreadsheet erfolgreich sortiert und aktualisiert (Bereich: {range_to_update}).")

        # Cache der Spieleliste direkt mit sortierter Liste aktualisieren
        cache['games_list'] = sorted_df[game_column].tolist()
        cache['last_cache_update'] = time.time()
        print(f"Lokaler Spiele-Cache mit {len(cache['games_list'])} Spielen aktualisiert.")


    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API Fehler beim Sortieren/Aktualisieren: {e}")
    except Exception as e:
        print(f"Unerwarteter Fehler beim Sortieren des Spreadsheets: {str(e)}")
        import traceback
        traceback.print_exc()

async def send_chat_message(session, config, message):
    """Sendet eine Nachricht in den Twitch-Chat"""
    # Sicherstellen, dass Bot-Token gültig ist
    if not await ensure_valid_token(session, config, 'chat_bot'):
        print("Chat-Bot Token ungültig. Nachricht kann nicht gesendet werden.")
        return

    # Hole die Bot User ID (wird für sender_id benötigt)
    bot_user_id = None
    try:
         # Versuche die Bot User ID über den Token zu bekommen
         validate_url = 'https://id.twitch.tv/oauth2/validate'
         headers_val = {'Authorization': f"Bearer {config['chat_bot']['access_token']}"}
         async with session.get(validate_url, headers=headers_val) as val_resp:
              if val_resp.status == 200:
                   val_data = await val_resp.json()
                   bot_user_id = val_data.get('user_id')
                   # Speichere ID für zukünftige Nutzung (optional)
                   config['chat_bot']['user_id'] = bot_user_id
                   # print(f"Bot User ID erhalten: {bot_user_id}")
              else:
                   print(f"Konnte Bot User ID nicht validieren: {val_resp.status}")
    except Exception as e:
         print(f"Fehler beim Abrufen der Bot User ID: {e}")

    if not bot_user_id:
         # Fallback: Versuche aus Config zu laden, falls vorher gespeichert
         bot_user_id = config['chat_bot'].get('user_id')

    if not bot_user_id:
         print("FEHLER: Konnte die User ID des Chat-Bots nicht ermitteln. Nachricht kann nicht gesendet werden.")
         print("Stelle sicher, dass der Bot-Token gültig ist und die Validierung funktioniert.")
         # Als Quick-Fix könnte man die Bot-ID manuell in die config.json eintragen
         # z.B. unter 'chat_bot': {'user_id': '12345678'}
         # Man findet die ID z.B. über https://api.twitch.tv/helix/users?login=BOT_USERNAME
         return


    chat_messages_url = 'https://api.twitch.tv/helix/chat/messages'
    headers = {
        'Authorization': f"Bearer {config['chat_bot']['access_token']}",
        'Client-Id': config['chat_bot']['client_id'],
        'Content-Type': 'application/json'
    }

    data = {
        "broadcaster_id": config['broadcaster_id'],
        "sender_id": bot_user_id, # ID des Bots, der die Nachricht sendet
        "message": message
    }

    try:
        async with session.post(chat_messages_url, headers=headers, json=data) as response:
            if response.status == 200:
                print(f"Chat-Nachricht gesendet: {message}")
            elif response.status == 403:
                 resp_text = await response.text()
                 print(f"Fehler beim Senden der Chat-Nachricht (403 Forbidden): {resp_text}")
                 if "Missing scope" in resp_text:
                      print("-> Dem Bot-Token fehlt der nötige Scope ('chat:edit'). Bitte neu autorisieren.")
                 elif "user does not have permission" in resp_text:
                      print("-> Der Bot ist möglicherweise kein Moderator im Kanal oder hat keine Berechtigung zum Senden.")
                 elif "broadcaster language" in resp_text:
                      print("-> Chat möglicherweise im Emote-Only, Follower-Only, Sub-Only Modus?")
            else:
                 print(f"Fehler beim Senden der Chat-Nachricht: {response.status} - {await response.text()}")
    except Exception as e:
        print(f"Exception beim Senden der Chat-Nachricht: {str(e)}")


async def fulfill_vote(session, config, reward_id, vote_id):
    """Markiert einen Vote als erfüllt"""
    # Token-Check ist bereits in process_votes erfolgt, hier nur der API Call
    redeem_url = 'https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions'
    headers = {
        'Client-Id': config['streamer']['client_id'],
        'Authorization': f"Bearer {config['streamer']['access_token']}",
        'Content-Type': 'application/json'
    }

    params = {
        'broadcaster_id': config['broadcaster_id'],
        'reward_id': reward_id,
        'id': vote_id
    }

    payload = {
        'status': 'FULFILLED'
    }

    try:
        async with session.patch(redeem_url, headers=headers, json=payload, params=params) as response:
            if response.status == 200:
                print(f"Vote {vote_id} erfolgreich als FULFILLED markiert.")
                # Speichere die ID persistent erst *nach* erfolgreichem Fulfill
                cache # Zugriff auf globale Variable
                cache['processed_ids'] = save_processed_id(cache['processed_ids'], vote_id)
            elif response.status == 400 and "redemption is already" in await response.text():
                 print(f"Vote {vote_id} war bereits als FULFILLED/CANCELED markiert.")
                 # Auch hier die ID speichern, da sie abgeschlossen ist
                 cache
                 cache['processed_ids'] = save_processed_id(cache['processed_ids'], vote_id)
            elif response.status == 403:
                 print(f"Fehler beim Erfüllen von Vote {vote_id} (403 Forbidden). Fehlt der Scope 'channel:manage:redemptions'?")
            else:
                 print(f"Fehler beim Erfüllen des Votes {vote_id}: {response.status} - {await response.text()}")
                 # ID hier NICHT speichern, damit es erneut versucht werden kann? Oder doch? Schwierige Entscheidung.
                 # Aktuell: Nicht speichern bei Fehler.

    except Exception as e:
        print(f"Exception beim Erfüllen des Votes {vote_id}: {str(e)}")


async def main():
    """Hauptfunktion des Programms"""
    banner()
    print("Vote Tracker Bot wird gestartet...")

    # Konfiguration laden
    config = load_config()

    # Überprüfe, ob Client Secrets gesetzt sind
    if not config['streamer'].get('client_secret')  == CLIENT_SECRET or \
       not config['chat_bot'].get('client_secret')  == CLIENT_SECRET:
        print("\n" + "="*60)
        print("FEHLER: Mindestens ein Client Secret fehlt in der config.json!")
        print("Bitte trage die korrekten Client Secrets für 'streamer' und 'chat_bot' ein.")
        print("Du erhältst die Secrets in der Twitch Developer Console bei deiner Anwendungsregistrierung.")
        print("Bot wird beendet.")
        print("="*60 + "\n")
        return # Beende das Skript

    # Geladene IDs in den Cache laden
    cache['processed_ids'] = load_processed_ids()
    print(f"{len(cache['processed_ids'])} bereits verarbeitete Vote-IDs geladen.")

    # Google Sheets initialisieren (kann fehlschlagen, wird intern behandelt)
    await init_google_sheets(config)

    # Initiale Token-Validierung und ggf. Anforderung
    print("\nÜberprüfe Twitch API Tokens...")
    async with aiohttp.ClientSession() as session:
        streamer_ok = await ensure_valid_token(session, config, 'streamer')
        bot_ok = await ensure_valid_token(session, config, 'chat_bot')

    if not streamer_ok or not bot_ok:
        print("\n" + "="*60)
        print("FEHLER: Konnte nicht für alle Accounts gültige Tokens sicherstellen.")
        if not streamer_ok: print("- Problem mit 'streamer' Account Token.")
        if not bot_ok: print("- Problem mit 'chat_bot' Account Token.")
        print("Bitte überprüfe die Fehlermeldungen oben und die config.json.")
        print("Möglicherweise musst du die Autorisierung im Browser durchführen, wenn das Skript dich dazu auffordert.")
        print("Bot wird beendet.")
        print("="*60 + "\n")
        return # Beende das Skript

    print("\nAlle Tokens scheinen gültig zu sein.")
    print(f"Bot läuft für Kanal: {config.get('twitch_username', 'Unbekannt')}")
    print(f"Broadcaster ID: {config.get('broadcaster_id', 'Unbekannt')}")
    print(f"Überwachte Normal Vote Reward ID: {config.get('rewards', {}).get('normal_vote', 'Nicht gesetzt')}")
    print(f"Überwachte Super Vote Reward ID: {config.get('rewards', {}).get('super_vote', 'Nicht gesetzt')}")
    print(f"Spreadsheet ID: {config.get('spreadsheet_id', 'Nicht gesetzt')}")
    print("\nÜberwache Votes...")

    # Tasks starten
    # Wichtig: Jede Task muss ihre eigene Session haben oder eine gemeinsame nutzen
    # Sie rufen intern ensure_valid_token auf, was bei Bedarf die Tokens prüft/erneuert
    listener_task = asyncio.create_task(listen_to_redemptions(config))
    processor_task = asyncio.create_task(process_votes(config))

    # Warten auf Abbruch (z.B. durch Strg+C)
    try:
        # Warte auf beide Tasks. Wenn einer mit Fehler abbricht, wird gather eine Exception werfen.
        await asyncio.gather(listener_task, processor_task)
    except asyncio.CancelledError:
        print("\nBot wird durch Benutzer gestoppt...")
    except Exception as e:
        print(f"\nUnerwarteter Fehler in der Haupt-Schleife: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print("Tasks werden beendet...")
        listener_task.cancel()
        processor_task.cancel()
        # Warte kurz, damit die Tasks auf das Cancel-Signal reagieren können
        await asyncio.sleep(1)
        print("Bot wurde beendet.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgramm durch Strg+C beendet.")

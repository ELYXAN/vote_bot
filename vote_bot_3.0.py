import requests
import gspread
import webbrowser
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from fuzzywuzzy import process
import time
import pandas as pd
from datetime import datetime, timedelta

# Konfigurationsdatei
CONFIG_FILE = 'config.json'

# Standardkonfiguration
DEFAULT_CONFIG = {
    'streamer': {
        'client_id': '5r243f2p934ptjpg0ahzdzer9rgsy4',
        'client_secret': 'x8klk8bokm0hw8lekxbq2pa2319xub',
        'access_token': '',
        'refresh_token': '',
        'token_expiry': ''
    },
    'chat_bot': {
        'client_id': 'kvr3o58p1524wqmlhwp4xwqk9o9223',
        'client_secret': '',
        'access_token': '',
        'refresh_token': '',
        'token_expiry': ''
    },
    'twitch_username': 'kilodawe',
    'rewards': {
        'normal_vote': '1770f700-f38e-4554-b6ef-a343530c3bae',
        'super_vote': 'c10f02d3-867e-44cf-8002-aab58990050e'
    },
    'spreadsheet_id': '1rIVCDXx5KwqF42F2Yq11k5UQeF_cfNY3KVcFSmZxw80',  #kilodawes spreadsheet id: 1fTVluQLftB-y-HFCfSUdsiJf7NsQimyqMvGadN818vc
    'min_match_score': 80,
    'super_vote_weight': 10
}

#Title Screen
def banner():
    """Display the banner at startup."""
    print("""
██╗   ██╗ ██████╗ ████████╗███████╗    ████████╗██████╗  █████╗  ██████╗██╗  ██╗███████╗██████╗ 
██║   ██║██╔═══██╗╚══██╔══╝██╔════╝    ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
██║   ██║██║   ██║   ██║   █████╗         ██║   ██████╔╝███████║██║     █████╔╝ █████╗  ██████╔╝
██║   ██║██║   ██║   ██║   ██╔══╝         ██║   ██╔══██╗██╔══██║██║     ██╔═██╗ ██╔══╝  ██╔══██╗
╚██████╔╝╚██████╔╝   ██║   ███████╗       ██║   ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██║  ██║
 ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝       ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

Version 3.0 - Made by: ELYXAN
    """)

# Hilfsfunktionen
def load_config():
    """Lädt die Konfiguration oder erstellt eine neue mit Standardwerten"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

def save_config(config):
    """Speichert die aktualisierte Konfiguration"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def check_token_validity(config, account_type):
    """Überprüft, ob das Token noch gültig ist"""
    if not config[account_type]['access_token']:
        return False
    
    if not config[account_type]['token_expiry']:
        return False
    
    try:
        expiry_time = datetime.fromisoformat(config[account_type]['token_expiry'])
        # Füge einen Puffer hinzu (30 Sekunden), um Token zu erneuern bevor er abläuft
        return datetime.now() < (expiry_time - timedelta(seconds=30))
    except (ValueError, TypeError):
        # Falls das Datum ungültig ist
        return False

def refresh_token(config, account_type):
    """Token über Refresh-Token erneuern"""
    print(f"Versuche Token für {account_type} zu erneuern...")
    
    if not config[account_type]['refresh_token']:
        print(f"Kein Refresh-Token für {account_type} vorhanden. Öffne Auth-Seite...")
        open_auth_page(config, account_type)
        return False
    
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'grant_type': 'refresh_token',
        'refresh_token': config[account_type]['refresh_token'],
        'client_id': config[account_type]['client_id'],
        'client_secret': config[account_type]['client_secret']
    }
    
    try:
        response = requests.post(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            config[account_type]['access_token'] = data['access_token']
            # Speichern des neuen Refresh-Tokens, falls eines gesendet wurde
            if 'refresh_token' in data:
                config[account_type]['refresh_token'] = data['refresh_token']
            
            # Expiry-Zeit berechnen und speichern
            config[account_type]['token_expiry'] = (datetime.now() + timedelta(seconds=data['expires_in'])).isoformat()
            save_config(config)
            print(f"Token für {account_type} erfolgreich erneuert! Gültig bis: {config[account_type]['token_expiry']}")
            return True
        elif response.status_code == 400 and "Invalid refresh token" in response.text:
            # Refresh-Token ist ungültig geworden, neues Token anfordern
            print(f"Refresh-Token für {account_type} ist ungültig. Fordere neues Token an...")
            config[account_type]['refresh_token'] = ''
            save_config(config)
            open_auth_page(config, account_type)
            return False
        else:
            print(f"Fehler beim Erneuern des Tokens für {account_type}: {response.text}")
            # Bei anderen Fehlern Auth-Seite öffnen
            open_auth_page(config, account_type)
            return False
    except Exception as e:
        print(f"Exception beim Token-Refresh für {account_type}: {str(e)}")
        return False

def ensure_valid_token(config, account_type):
    """Stellt sicher, dass ein gültiges Token vorhanden ist und erneuert es bei Bedarf"""
    if not check_token_validity(config, account_type):
        print(f"Token für {account_type} ist nicht gültig oder läuft bald ab.")
        if not refresh_token(config, account_type):
            return False
    return True

def validate_token(config, account_type):
    """Validiert ein Token durch tatsächlichen API-Aufruf"""
    headers = {
        'Client-ID': config[account_type]['client_id'],
        'Authorization': f"Bearer {config[account_type]['access_token']}"
    }
    
    # Einen einfachen API-Aufruf machen, um das Token zu testen
    response = requests.get('https://api.twitch.tv/helix/users', headers=headers)
    
    if response.status_code == 200:
        return True
    elif response.status_code == 401:
        # Token ist ungültig
        return False
    else:
        print(f"Unerwartete Antwort bei Token-Validierung: {response.status_code}, {response.text}")
        return False

def open_auth_page(config, account_type):
    """Öffnet die Authentifizierungsseite im Browser"""
    print(f"\n--- Token für {account_type} ist abgelaufen oder fehlt ---")
    client_id = config[account_type]['client_id']
    
    # Verschiedene Scopes für die verschiedenen Accounts
    scopes = ""
    if account_type == "streamer":
        scopes = "channel:read:redemptions+channel:manage:redemptions"
    elif account_type == "chat_bot":
        scopes = "chat:edit+chat:read"
    
    auth_url = f"https://id.twitch.tv/oauth2/authorize?client_id={client_id}&redirect_uri=http://localhost&response_type=token&scope={scopes}"
    
    print(f"Öffne Browser für {account_type}-Authentifizierung...")
    print(f"Bitte melde dich mit dem richtigen Twitch-Account an ({account_type})!")
    print("Nach der Anmeldung wirst du auf eine Seite mit 'localhost' in der URL weitergeleitet.")
    print("Kopiere den kompletten Token (Teil nach 'access_token=' und vor dem '&') aus der URL und füge ihn hier ein:")
    
    webbrowser.open(auth_url)
    new_token = input("Token einfügen: ").strip()
    
    config[account_type]['access_token'] = new_token
    config[account_type]['token_expiry'] = (datetime.now() + timedelta(hours=4)).isoformat()
    save_config(config)
    
    return True

def ensure_valid_token(config, account_type):
    """Stellt sicher, dass ein gültiges Token vorhanden ist"""
    if not check_token_validity(config, account_type):
        if not refresh_token(config, account_type):
            return False
    return True

def lade_IDliste():
    """Lädt die Liste der bereits verarbeiteten Vote-IDs"""
    try:
        with open('Vote_IDs.csv', 'r') as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []

def speichere_id(id_liste, vote_id):
    """Speichert eine neue Vote-ID in der Liste"""
    id_liste.append(vote_id)
    with open('Vote_IDs.csv', 'w') as f:
        for id in id_liste:
            f.write(str(id) + '\n')
    return id_liste

def lade_Inacurate_games_liste():
    """Lädt die Liste der ungenauen Spiele-Votes"""
    try:
        with open('inacurate_games.csv', 'r') as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []

def speichere_inaccurate_game(game_name):
    """Speichert ein ungenau eingegebenes Spiel"""
    with open('inacurate_games.csv', 'a') as f:
        f.write(f"{game_name} Vote Anzahl: 1\n")
    print(f"Eintrag in CSV Datei: {game_name}")

def get_broadcaster_id(config):
    """Holt die Broadcaster-ID des Twitch-Kanals"""
    headers = {
        'Client-ID': config['streamer']['client_id'],
        'Authorization': f"Bearer {config['streamer']['access_token']}"
    }
    endpoint = f"https://api.twitch.tv/helix/users?login={config['twitch_username']}"
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return data['data'][0]['id']
    else:
        print(f"Fehler beim Abrufen der Broadcaster-ID: {response.text}")
        return None

def get_games_list(sheet):
    """Holt die Liste aller Spiele aus dem Spreadsheet"""
    return sheet.col_values(2)

def process_vote(config, vote_data, spreadsheet, broadcaster_id, vote_type):
    """Verarbeitet einen einzelnen Vote"""
    # Vote-Gewicht basierend auf Vote-Typ
    vote_weight = config['super_vote_weight'] if vote_type == 'super_vote' else 1
    
    # Reward-ID und Titel basierend auf Vote-Typ
    reward_id = config['rewards'][vote_type]
    reward_title = 'Super Vote-Playlist' if vote_type == 'super_vote' else 'Vote Playlist'
    
    # Ausgelesene Vote-IDs laden
    ausgelesene_Liste = lade_IDliste()
    
    # Spieleliste aus dem Spreadsheet laden
    worksheet = spreadsheet.get_worksheet(0)
    games_list_from_sheet = get_games_list(worksheet)
    
    # Verarbeite alle Votes
    for entry in vote_data.get('data', []):
        vote_id = entry.get('id')
        title = entry.get('reward', {}).get('title', '')
        user = entry.get('user_name')
        
        # Überprüfen, ob der Vote bereits verarbeitet wurde und ob der Titel passt
        if vote_id not in ausgelesene_Liste and title == reward_title:
            # Vote-ID als verarbeitet markieren
            ausgelesene_Liste = speichere_id(ausgelesene_Liste, vote_id)
            
            # Benutzereingabe (Spielname) auslesen
            user_input = entry.get('user_input')
            
            # Spiel in der Liste finden (Fuzzy Matching)
            try:
                match, score = process.extractOne(user_input, games_list_from_sheet, score_cutoff=config['min_match_score'])
            except:
                # Kein Match gefunden - als ungenau speichern
                speichere_inaccurate_game(user_input)
                continue
            
            if match is not None:
                # Index des Spiels in der Liste finden
                index = games_list_from_sheet.index(match)
                print(f"Match gefunden: {user_input} --> {match} (Index {index})")
                
                try:
                    # Zelle mit dem Spiel finden
                    cell = worksheet.find(match, in_column=2)
                    
                    # Aktuelle Votes auslesen
                    current_votes = int(worksheet.cell(cell.row, 1).value)
                    
                    # Neue Votes berechnen
                    new_votes = current_votes + vote_weight
                    
                    # Votes aktualisieren
                    worksheet.update_cell(cell.row, 1, new_votes)
                    
                    print(f"Vote für {match} erfolgreich hinzugefügt. Alt: {current_votes}, Neu: {new_votes}, ID: {vote_id}")
                    
                    # Tabelle neu sortieren
                    sort_spreadsheet(config, match, new_votes, user, broadcaster_id)
                    
                    # Vote als erledigt markieren
                    fulfill_vote(config, broadcaster_id, reward_id, vote_id)
                    
                except gspread.exceptions.WorksheetNotFound:
                    print(f"Spiel {user_input} nicht in der Tabelle gefunden.")

def sort_spreadsheet(config, game_name, new_votes, user, broadcaster_id):
    """Sortiert das Spreadsheet nach Votes und gibt Position im Chat aus"""
    # Google Sheets Setup
    sort_scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    sort_creds = ServiceAccountCredentials.from_json_keyfile_name("Vote tracking.json", sort_scope)
    sort_client = gspread.authorize(sort_creds)
    
    # Spreadsheet öffnen
    spreadsheet = sort_client.open("Bot Playlist - kilo´s road to 1000")
    sort_sheet = spreadsheet.sheet1
    
    # Statt die gesamte Tabelle neu zu sortieren, nur die Position des geänderten Spiels aktualisieren
    # Daten holen (alle Werte auf einmal, um API-Aufrufe zu reduzieren)
    sorting_data = sort_sheet.get_all_values()
    
    # In DataFrame konvertieren
    df = pd.DataFrame(sorting_data[1:], columns=sorting_data[0])
    
    # 'Votes' als Integer konvertieren
    df['Votes'] = df['Votes'].astype(int)
    
    # Nach Votes absteigend sortieren
    sorted_df = df.sort_values(by='Votes', ascending=False)
    
    # Überprüfen, ob Reihenfolge geändert wurde
    current_order = [row[1] for row in sorting_data[1:]]  # Spiele in aktueller Reihenfolge
    new_order = sorted_df.iloc[:, 1].tolist()  # Spiele in neuer Reihenfolge
    
    # Nur neu sortieren, wenn die Reihenfolge tatsächlich geändert wurde
    if current_order != new_order:
        # Sortierte Daten zurück ins Sheet schreiben
        sorted_data = [sorting_data[0]] + sorted_df.values.tolist()
        sort_sheet.update('A1', sorted_data)
    
    # Position des Spiels ermitteln - ohne erneut Daten zu laden
    position = 0
    for i, row in enumerate(sorted_df.iterrows(), start=1):
        if row[1][1] == game_name:  # Game ist in Spalte 1 (index 1)
            position = i
            break
    
    # Chat-Nachricht senden
    chat_message = f"@{user} Spiel: {game_name} | Votes: {new_votes} | Aktuelle Position: {position}"
    send_chat_message(config, broadcaster_id, chat_message)

def send_chat_message(config, broadcaster_id, message):
    """Sendet eine Nachricht in den Twitch-Chat"""
    chat_messages_url = 'https://api.twitch.tv/helix/chat/messages'
    headers = {
        'Authorization': f"Bearer {config['chat_bot']['access_token']}",
        'Client-Id': config['chat_bot']['client_id'],
        'Content-Type': 'application/json'
    }
    
    data = {
        "broadcaster_id": broadcaster_id,
        "sender_id": "1045752272",  # ID des Bots
        "message": message
    }
    
    response = requests.post(chat_messages_url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Fehler beim Senden der Chat-Nachricht: {response.text}")

def fulfill_vote(config, broadcaster_id, reward_id, vote_id):
    """Markiert einen Vote als erfüllt"""
    redeem_url = 'https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions'
    headers = {
        'Client-Id': config['streamer']['client_id'],
        'Authorization': f"Bearer {config['streamer']['access_token']}",
        'Content-Type': 'application/json'
    }
    
    params = {
        'broadcaster_id': broadcaster_id,
        'reward_id': reward_id,
        'id': vote_id
    }
    
    payload = {
        'status': 'FULFILLED'
    }
    
    response = requests.patch(redeem_url, headers=headers, json=payload, params=params)
    if response.status_code != 200:
        print(f"Fehler beim Erfüllen des Votes: {response.text}")

def main():
    """Hauptfunktion des Programms"""
    print("Vote Tracker Bot wird gestartet...")

    #load banner
    banner()
    
    # Konfiguration laden
    config = load_config()
    
    # Sicherstellen, dass beide Tokens gültig sind
    streamer_valid = ensure_valid_token(config, 'streamer')
    chat_bot_valid = ensure_valid_token(config, 'chat_bot')
    
    if not streamer_valid or not chat_bot_valid:
        print("Fehler: Token konnten nicht validiert werden. Bitte neu starten.")
        return
    
    # Broadcaster-ID holen
    broadcaster_id = get_broadcaster_id(config)
    if not broadcaster_id:
        print("Fehler: Broadcaster-ID konnte nicht abgerufen werden.")
        return
    
    # Google Sheets Setup
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = ServiceAccountCredentials.from_json_keyfile_name('Vote tracking.json', scopes)
    client = gspread.authorize(creds)
    
    # Spreadsheet öffnen
    spreadsheet = client.open_by_key(config['spreadsheet_id'])
    worksheet = spreadsheet.get_worksheet(0)
    
    # Cache für Spieleliste, um API-Aufrufe zu reduzieren
    games_list_cache = get_games_list(worksheet)
    last_cache_update = time.time()
    cache_validity = 300  # Cache 5 Minuten gültig halten
    
    # Ausgelesene Vote-IDs laden
    ausgelesene_Liste = lade_IDliste()
    
    print(f"Bot läuft für Kanal: {config['twitch_username']}")
    print("Überwache Votes...")
    
    # Polling-Intervall reduzieren
    polling_interval = 1.5  # 1.5 Sekunden statt 5 Sekunden
    
    # Haupt-Loop
    while True:
        try:
            # Cache aktualisieren, wenn er abgelaufen ist
            if time.time() - last_cache_update > cache_validity:
                games_list_cache = get_games_list(worksheet)
                last_cache_update = time.time()
                print("Spiele-Cache aktualisiert")
            
            # Headers für API-Anfragen
            headers = {
                'Client-ID': config['streamer']['client_id'],
                'Authorization': f"Bearer {config['streamer']['access_token']}"
            }
            
            # Token-Gültigkeit prüfen und ggf. erneuern
            if not check_token_validity(config, 'streamer'):
                refresh_token(config, 'streamer')
                continue
                
            if not check_token_validity(config, 'chat_bot'):
                refresh_token(config, 'chat_bot')
                continue
            
            # Beide Vote-Typen in einer Schleife abrufen und verarbeiten, um Code-Duplikation zu vermeiden
            for vote_type in ['normal_vote', 'super_vote']:
                reward_id = config['rewards'][vote_type]
                endpoint = f"https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions?broadcaster_id={broadcaster_id}&reward_id={reward_id}&status=UNFULFILLED"
                response = requests.get(endpoint, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Verarbeite Votes mit dem gecachten Spieleliste
                    for entry in data.get('data', []):
                        vote_id = entry.get('id')
                        title = entry.get('reward', {}).get('title', '')
                        user = entry.get('user_name')
                        reward_title = 'Super Vote-Playlist' if vote_type == 'super_vote' else 'Vote Playlist'
                        vote_weight = config['super_vote_weight'] if vote_type == 'super_vote' else 1
                        
                        # Überprüfen, ob der Vote bereits verarbeitet wurde und ob der Titel passt
                        if vote_id not in ausgelesene_Liste and title == reward_title:
                            # Vote-ID als verarbeitet markieren
                            ausgelesene_Liste = speichere_id(ausgelesene_Liste, vote_id)
                            
                            # Benutzereingabe (Spielname) auslesen
                            user_input = entry.get('user_input')
                            
                            # Spiel in der Liste finden (Fuzzy Matching)
                            try:
                                match, score = process.extractOne(user_input, games_list_cache, score_cutoff=config['min_match_score'])
                            except:
                                # Kein Match gefunden - als ungenau speichern
                                speichere_inaccurate_game(user_input)
                                continue
                            
                            if match is not None:
                                try:
                                    # Zelle mit dem Spiel finden
                                    cell = worksheet.find(match, in_column=2)
                                    
                                    # Aktuelle Votes auslesen
                                    current_votes = int(worksheet.cell(cell.row, 1).value)
                                    
                                    # Neue Votes berechnen
                                    new_votes = current_votes + vote_weight
                                    
                                    # Votes aktualisieren
                                    worksheet.update_cell(cell.row, 1, new_votes)
                                    
                                    print(f"Vote für {match} erfolgreich hinzugefügt. Alt: {current_votes}, Neu: {new_votes}, ID: {vote_id}")
                                    
                                    # Tabelle neu sortieren und Chat-Nachricht senden
                                    sort_spreadsheet(config, match, new_votes, user, broadcaster_id)
                                    
                                    # Vote als erledigt markieren
                                    fulfill_vote(config, broadcaster_id, reward_id, vote_id)
                                    
                                except gspread.exceptions.WorksheetNotFound:
                                    print(f"Spiel {user_input} nicht in der Tabelle gefunden.")
                
                elif response.status_code == 401:
                    # Token erneuern, wenn es abgelaufen ist
                    refresh_token(config, 'streamer')
                    continue
                else:
                    print(f"Fehler beim Abrufen der {vote_type}: {response.text}")
            
            # Pause zwischen Abfragen (reduziert)
            time.sleep(polling_interval)
            
        except Exception as e:
            print(f"Ein Fehler ist aufgetreten: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    main()
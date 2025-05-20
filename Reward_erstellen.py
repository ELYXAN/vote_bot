import requests

# Twitch API-Informationen
client_id = ''
oauth_token = ''
oauth_token_manage = ''
broadcaster_id = ''  # Die ID des Kanals, für den die Belohnung erstellt werden soll

# Twitch API-Endpunkt für die Erstellung einer Kanalpunkte-Belohnung
rewards_endpoint = f'https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={broadcaster_id}'

# Parameter für die Kanalpunkte-Belohnung
reward_params = {
    'title': 'test vote',
    'cost': 1,  # Die Kosten der Belohnung in Kanalpunkten
    'prompt': 'Deine Stimme (1) für ein Spiel aus unserer Playlist.',
    'is_user_input_required': True,
    'is_max_per_stream_enabled': False,
    'max_per_stream': 1,
}

headers = {
    'Client-ID': client_id,
    'Authorization': f'Bearer {oauth_token_manage}',
    'Content-Type': 'application/json',
}

# API-Anfrage durchführen, um die Kanalpunkte-Belohnung zu erstellen
response = requests.post(rewards_endpoint, headers=headers, json=reward_params)

if response.status_code == 200:
    data = response.json()
    print("Kanalpunkte-Belohnung erfolgreich erstellt:", data)
else:
    print(f"Fehler bei der API-Anfrage. Statuscode: {response.status_code}, Fehlermeldung: {response.text}")

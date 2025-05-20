import requests

# Twitch API-Informationen
client_id = ''
oauth_token_manage = ''
broadcaster_id = ''  # Die ID des Kanals, für den die Belohnung gelöscht werden soll
reward_id_to_delete = ''  # Die ID der zu löschenden Belohnung

# Twitch API-Endpunkt für die Löschung einer Kanalpunkte-Belohnung
delete_reward_endpoint = f'https://api.twitch.tv/helix/channel_points/custom_rewards?id={reward_id_to_delete}&broadcaster_id={broadcaster_id}'

headers = {
    'Client-ID': client_id,
    'Authorization': f'Bearer {oauth_token_manage}',
}

# API-Anfrage durchführen, um die Kanalpunkte-Belohnung zu löschen
response = requests.delete(delete_reward_endpoint, headers=headers)

if response.status_code == 204:
    print("Kanalpunkte-Belohnung erfolgreich gelöscht.")
else:
    print(f"Fehler bei der API-Anfrage. Statuscode: {response.status_code}, Fehlermeldung: {response.text}")

import requests

# Twitch API-Informationen
client_id = '5r243f2p934ptjpg0ahzdzer9rgsy4'
oauth_token_manage = '0x2r5f9wsie1sf96v3l5d8d1j9ol0b'
broadcaster_id = '619338130'  # Die ID des Kanals, für den die Belohnung gelöscht werden soll
reward_id_to_delete = '2b67c6a5-3802-4bc3-bbfc-0fc43a038436'  # Die ID der zu löschenden Belohnung

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

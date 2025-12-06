#!/bin/bash
# Diagnose-Script für ntfy.sh Benachrichtigungen
# Dieses Script hilft bei der Fehlersuche

echo "==================================="
echo "ntfy.sh Diagnose-Script"
echo "==================================="
echo ""

# 1. Prüfe Umgebungsvariablen
echo "1. Umgebungsvariablen prüfen:"
echo "-----------------------------------"
docker compose exec fpp-control env | grep NOTIFY | sort
echo ""

# 2. Prüfe ob Container läuft
echo "2. Container-Status:"
echo "-----------------------------------"
docker compose ps fpp-control
echo ""

# 3. DNS-Test
echo "3. DNS-Auflösung testen:"
echo "-----------------------------------"
docker compose exec fpp-control getent hosts ntfy.sh || echo "⚠ DNS-Auflösung fehlgeschlagen"
echo ""

# 4. Python-basierter Test aus Container (da curl nicht verfügbar)
echo "4. Python-Test von ntfy.sh aus Container:"
echo "-----------------------------------"
NTFY_TOPIC=$(docker compose exec fpp-control env | grep NOTIFY_NTFY_TOPIC | cut -d= -f2 | tr -d '\r')
if [ -z "$NTFY_TOPIC" ]; then
    echo "⚠ NOTIFY_NTFY_TOPIC ist nicht gesetzt!"
else
    echo "Topic: $NTFY_TOPIC"
    docker compose exec fpp-control python3 -c "
import requests
try:
    response = requests.post('https://ntfy.sh/$NTFY_TOPIC', 
                            data='Test vom Container (diagnose-ntfy.sh)'.encode('utf-8'),
                            headers={'Title': 'Diagnose Test'},
                            timeout=5)
    print(f'Status: {response.status_code}')
    print(f'Response: {response.text}')
    if response.status_code == 200:
        print('✓ Erfolgreich!')
    else:
        print('✗ Fehler!')
except Exception as e:
    print(f'✗ Exception: {e}')
"
fi
echo ""

# 5. Letzte Logs
echo "5. Letzte Log-Einträge (nach 'notification' filtern):"
echo "-----------------------------------"
docker compose logs --tail=50 fpp-control | grep -i notification
echo ""

echo "==================================="
echo "Diagnose abgeschlossen"
echo "==================================="
echo ""
echo "Nächste Schritte:"
echo "1. Wenn DNS fehlschlägt: docker compose down && docker compose build --no-cache && docker compose up -d"
echo "2. Wenn Python-Test funktioniert aber keine Logs sichtbar: Prüfe ob Aktion ausgelöst wurde"
echo "3. Wenn 'send_notification called' in Logs aber kein 'ntfy.sh notification sent': Siehe Fehlermeldung"
echo "4. Wenn Python-Test fehlschlägt: Netzwerk/Firewall-Problem"

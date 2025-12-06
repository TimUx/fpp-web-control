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
docker compose exec fpp-control nslookup ntfy.sh || docker compose exec fpp-control getent hosts ntfy.sh
echo ""

# 4. Manueller curl-Test aus Container
echo "4. Manueller ntfy.sh Test aus Container:"
echo "-----------------------------------"
NTFY_TOPIC=$(docker compose exec fpp-control env | grep NOTIFY_NTFY_TOPIC | cut -d= -f2 | tr -d '\r')
if [ -z "$NTFY_TOPIC" ]; then
    echo "⚠ NOTIFY_NTFY_TOPIC ist nicht gesetzt!"
else
    echo "Topic: $NTFY_TOPIC"
    docker compose exec fpp-control curl -d "Test vom Container" https://ntfy.sh/$NTFY_TOPIC
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
echo "2. Wenn curl funktioniert aber keine Logs sichtbar: Prüfe NOTIFY_ENABLED und NOTIFY_NTFY_ENABLED"
echo "3. Wenn Fehler in Logs: Siehe NOTIFICATIONS.md für spezifische Lösungen"

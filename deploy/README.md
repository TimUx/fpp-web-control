# FalconBeat-Audio hinter einem Reverse Proxy

Der Lautsprecher-Button spielt die Show-Musik synchron auf dem Gerät des
Besuchers. Der Browser braucht dafür zwei Wege zum FalconBeat-Server – unter
**derselben Adresse** wie fpp-web-control (kein CORS, kein Mixed Content):

| Pfad bei fpp-web-control | Ziel im FalconBeat-Container (Port 80) | Zweck |
|---|---|---|
| `/falconbeat/ws`        | `/ws`      | WebSocket: Uhrensync + Play/Pause |
| `/falconbeat/media/*`   | `/media/*` | Audiodateien (nur `GET`) |

Der Proxy muss das Präfix `/falconbeat` entfernen. Mehr wird nicht
freigegeben – weder die Listener-Seite noch `/upload/complete` oder `/discover`.

fpp-web-control selbst spricht den FalconBeat-Server nur für den Health-Check
an (`FALCONBEAT_SERVER_URL`, sonst die Adresse aus dem FPP-Plugin).

## Traefik (Docker Swarm, Labels am FalconBeat-Service)

Siehe [`traefik-swarm-labels.yml`](traefik-swarm-labels.yml). Die Labels
gehören unter `deploy.labels` des **FalconBeat**-Service, weil der Router auf
dessen Traefik-Service zeigt.

Wichtig: ein eigenes, großzügiges Rate-Limit verwenden (wie beim
FalconBeat-Router). Viele Besucher teilen sich hinter Mobilfunk-NAT eine IP.

## Traefik (File-Provider, z. B. internes LAN-Traefik)

Siehe [`traefik-file-provider.yml`](traefik-file-provider.yml).

## Prüfen

```bash
# 200 + JSON, wenn die Media-Route steht
curl -i https://<deine-domain>/falconbeat/media/nowplaying.json

# 404: die Listener-Seite ist über diesen Pfad nicht erreichbar
curl -i https://<deine-domain>/falconbeat/
```

Danach in fpp-web-control `GET /api/state` → `"falconbeat": {"available": true}`.

## Rate-Limit und Komprimierung für fpp-web-control

Der zweite Block in [`traefik-swarm-labels.yml`](traefik-swarm-labels.yml) gibt
dem fpp-web-control-Router ein eigenes, großzügiges Rate-Limit und schaltet die
Komprimierung ein. Ohne das laufen mehrere Besucher hinter derselben
Mobilfunk-Adresse während einer Show in ein knappes Standard-Limit.

Die Stack-Datei [`../docker-stack.yml`](../docker-stack.yml) enthält diese Labels bereits.

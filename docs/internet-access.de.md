# 🌐 Aus dem Internet erreichbar machen – sicher

**Deutsch** · [English](internet-access.md)

Besucher stehen vor deinem Haus und nutzen die **mobilen Daten** ihres Handys, nicht dein WLAN. FPP Web Control muss also aus dem Internet erreichbar sein. Diese Anleitung zeigt die üblichen Wege – von „gar nichts am Router ändern“ bis „eigene Domain mit Portfreigabe“ – und worauf du achten musst, damit nur die Web-App erreichbar ist und nie dein Falcon Player oder dein Heimnetz.

---

## 📖 Inhalt

- [Grundregel: nur die Web-App geht ins Internet](#-grundregel-nur-die-web-app-geht-ins-internet)
- [Welcher Weg passt?](#-welcher-weg-passt)
- [Schritt 0: Internetanschluss prüfen](#-schritt-0-internetanschluss-prüfen)
- [Weg A: Cloudflare Tunnel (ohne Portfreigabe)](#-weg-a-cloudflare-tunnel-ohne-portfreigabe)
- [Weg B: eigene Domain oder DynDNS + Portfreigabe + Reverse Proxy](#-weg-b-eigene-domain-oder-dyndns--portfreigabe--reverse-proxy)
- [Weg C: Tailscale Funnel (schnell, ohne Domain)](#-weg-c-tailscale-funnel-schnell-ohne-domain)
- [Weg D: kleiner Cloud-Server als Relais (VPS + WireGuard)](#-weg-d-kleiner-cloud-server-als-relais-vps--wireguard)
- [FalconBeat (Musik am Handy) über das Internet](#-falconbeat-musik-am-handy-über-das-internet)
- [Sicherheits-Checkliste](#-sicherheits-checkliste)
- [Von außen testen](#-von-außen-testen)
- [Fehlersuche](#-fehlersuche)

---

## 🧱 Grundregel: nur die Web-App geht ins Internet

```
 Handy des Besuchers ──(Internet, HTTPS)──▶ Reverse Proxy / Tunnel ──▶ FPP Web Control ──(LAN)──▶ Falcon Player
                                                      └──▶ FalconBeat (nur /falconbeat/ws, /falconbeat/media/*)
```

- **Der FPP bleibt im LAN.** Die FPP-Oberfläche hat keinen Schutz, der fürs Internet taugt. Nie einen Port auf den FPP freigeben und nie einen Tunnel auf ihn zeigen lassen. FPP Web Control spricht im LAN mit dem FPP, die Besucher nie.
- **Nur HTTPS (Port 443).** Handys verweigern einfaches HTTP immer öfter, und die Musik-Funktion braucht in vielen Browsern eine sichere Seite.
- **Zugangsschutz einschalten.** `ACCESS_CODE` setzen oder besser den [Tagescode an der Matrix](../README.de.md#tagescode-an-der-pixel-matrix) nutzen. Dann können nur Leute vor deinem Haus Shows starten, obwohl die Seite öffentlich ist.
- **So wenig wie möglich freigeben.** Ein Hostname, ein Dienst. Von FalconBeat nur die zwei Pfade, die der Browser braucht (siehe [unten](#-falconbeat-musik-am-handy-über-das-internet)).

---

## 🧭 Welcher Weg passt?

| Weg | Router ändern | Eigene Domain | Geht bei CGNAT / DS-Lite | Aufwand | Gut für |
|---|---|---|---|---|---|
| **A: Cloudflare Tunnel** | nein | ja (bei Cloudflare) | ✅ ja | gering | die meisten Heim-Setups – Empfehlung |
| **B: Portfreigabe + Reverse Proxy** | 80/443 freigeben | eigene Domain oder kostenloses DynDNS | ❌ nein (braucht öffentliche IPv4) | mittel | volle Kontrolle, kein Dritter dazwischen |
| **C: Tailscale Funnel** | nein | nein (`*.ts.net`-Adresse) | ✅ ja | sehr gering | Ausprobieren, kleine Shows |
| **D: VPS als Relais** | nein | ja | ✅ ja | hoch | wer schon einen Server betreibt |

Im Zweifel: **Weg A**. Er braucht keine offenen Ports am Router und funktioniert auch, wenn dein Anbieter dir keine öffentliche IPv4-Adresse gibt.

---

## 🔎 Schritt 0: Internetanschluss prüfen

Eine Portfreigabe (Weg B) funktioniert nur, wenn dein Router eine **öffentliche IPv4-Adresse** hat. Viele Anbieter geben keine mehr heraus:

- **DS-Lite**: in Deutschland verbreitet (z. B. Vodafone Kabel, manche Glasfaseranbieter) – du bekommst IPv6 plus eine geteilte IPv4.
- **CGNAT** (Carrier-Grade NAT): typisch bei LTE/5G-Routern, Starlink und manchen Glasfaseranbietern.

**So prüfst du es:** Vergleiche die IPv4-Adresse, die dein Router als Internet-/WAN-Adresse anzeigt (FRITZ!Box: *Übersicht* bzw. *Internet → Online-Monitor*), mit der Adresse auf [ifconfig.me](https://ifconfig.me) oder [wieistmeineip.de](https://www.wieistmeineip.de/).

- Gleiche Adresse → öffentliche IPv4, alle Wege funktionieren.
- Unterschiedlich, oder der Router zeigt `100.64.x.x`–`100.127.x.x`, `10.x.x.x`, `192.168.x.x` bzw. „DS-Lite“ → nimm **Weg A, C oder D**. (Manche Anbieter stellen auf Nachfrage auf eine echte IPv4 um, teils gegen eine kleine Gebühr.)

---

## ☁️ Weg A: Cloudflare Tunnel (ohne Portfreigabe)

Ein kleines Programm (`cloudflared`) in deinem Netz baut eine **ausgehende** Verbindung zu Cloudflare auf. Besucher verbinden sich mit Cloudflare, Cloudflare reicht die Anfragen durch den Tunnel an FPP Web Control weiter. Am Router wird kein Port geöffnet, und deine Heim-IP bleibt verborgen.

**Du brauchst:** ein kostenloses Cloudflare-Konto und eine Domain, deren DNS bei Cloudflare liegt (dort kaufen oder eine bestehende umziehen; eine `.de` kostet wenige Euro im Jahr).

### Schritte

1. Im Cloudflare-Dashboard **Zero Trust → Networks → Tunnels → Create a tunnel** öffnen, Typ **Cloudflared**, Namen vergeben (z. B. `lichtershow`).
2. Als Umgebung **Docker** wählen und den **Token** aus dem angezeigten Befehl kopieren.
3. `cloudflared` neben FPP Web Control starten – z. B. in derselben `docker-compose.yml`:

   ```yaml
   services:
     fpp-control:
       image: ghcr.io/timux/fpp-web-control:latest
       restart: unless-stopped
       env_file:
         - path: .env
           required: false
       volumes:
         - ./config:/app/config
         - ./data:/app/data
       # kein "ports:" nötig – nur der Tunnel spricht mit der App

     cloudflared:
       image: cloudflare/cloudflared:latest
       restart: unless-stopped
       command: tunnel --no-autoupdate run
       environment:
         - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}   # Token in die .env schreiben
   ```

4. In den Tunnel-Einstellungen einen **Public Hostname** anlegen: z. B. `lichtershow.example.de`, Service `HTTP`, URL `fpp-control:8000` (der Dienstname aus der Compose-Datei).
5. `https://lichtershow.example.de` am Handy mit ausgeschaltetem WLAN öffnen. Das HTTPS-Zertifikat stellt Cloudflare automatisch bereit.

### Hinweise

- **WebSockets** (für die Musik) funktionieren durch den Tunnel ohne weitere Einstellungen.
- **Adresse der Besucher:** Cloudflare gibt die Adresse des Besuchers in `X-Forwarded-For` weiter, die Sperre nach falschen Codes greift also pro Besucher. Setzt du zwischen `cloudflared` und die App noch einen Reverse Proxy, muss dieser `X-Forwarded-For` *ergänzen* (Caddy und Traefik tun das von sich aus).
- **Caching:** Für diesen Host kein „Cache Everything“ einschalten. Die App sagt dem Browser selbst, was er behalten darf; der Status muss immer frisch sein.
- **Zusätzlicher Schutz (optional):** Unter *Security → WAF* lassen sich ein Rate-Limit setzen oder Länder sperren, aus denen du keine Besucher erwartest. Das Rate-Limit großzügig wählen (siehe Checkliste).
- **Nutzungsbedingungen:** Cloudflare regelt in seinen Tarifen das Ausliefern großer Mediendateien. Die Audiodateien einer Lichtershow sind klein (wenige MB pro Lied); bei sehr viel Verkehr die aktuellen Bedingungen prüfen.

---

## 🏠 Weg B: eigene Domain oder DynDNS + Portfreigabe + Reverse Proxy

Der klassische Weg: Der Router leitet die Ports 80 und 443 an einen Reverse Proxy in deinem Netz weiter, der HTTPS übernimmt und die Anfragen an FPP Web Control weitergibt.

### 1. Ein Name für deine Adresse

Deine Heim-IP kann sich ändern. Du brauchst einen Namen, der immer auf sie zeigt:

- **Eigene Domain** (z. B. bei INWX, IONOS, Strato, Netcup, Cloudflare) plus DynDNS-Aktualisierung – viele Anbieter und Cloudflare bieten dafür eine Schnittstelle.
- **Kostenloses DynDNS**: [deSEC](https://desec.io/), [DuckDNS](https://www.duckdns.org/), [Dynu](https://www.dynu.com/), [No-IP](https://www.noip.com/). Du bekommst z. B. `meine-lichtershow.duckdns.org`.
- **Im Router eingebaut**: Viele Router aktualisieren DynDNS selbst (FRITZ!Box: *Internet → Freigaben → DynDNS*, oder MyFRITZ!). Sonst einen Container wie [ddns-updater](https://github.com/qdm12/ddns-updater) oder `ddclient` laufen lassen.

Tipp: Mit eigener Domain einen `CNAME` anlegen, z. B. `lichtershow.example.de` → `meine-lichtershow.duckdns.org`. So behältst du eine schöne Adresse.

### 2. Portfreigabe am Router

**TCP 80 und TCP 443** an den **Rechner mit dem Reverse Proxy** freigeben – nicht an den FPP und nicht direkt an Port 8080 der App.

- **FRITZ!Box:** *Internet → Freigaben → Portfreigaben → Gerät für Freigaben hinzufügen* → Server wählen → *Neue Freigabe* → *Portfreigabe* für HTTPS (443) und HTTP (80).
- **Andere Router:** unter „Portweiterleitung“, „Virtueller Server“ oder „NAT“. Dem Server vorher im Router eine feste LAN-Adresse geben.

Port 80 wird nur für das Zertifikat (Let's-Encrypt-HTTP-Challenge) und die Umleitung auf HTTPS gebraucht. Sperrt dein Anbieter Port 80, eine DNS-Challenge nutzen (Caddy und Traefik können das mit einem Plugin für deinen DNS-Anbieter) oder Weg A.

### 3. Reverse Proxy mit automatischem HTTPS

Am einfachsten ist **Caddy**: Es holt und erneuert das Let's-Encrypt-Zertifikat selbst.

`docker-compose.yml`:

```yaml
services:
  fpp-control:
    image: ghcr.io/timux/fpp-web-control:latest
    restart: unless-stopped
    env_file:
      - path: .env
        required: false
    volumes:
      - ./config:/app/config
      - ./data:/app/data

  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
```

`Caddyfile`:

```caddyfile
lichtershow.example.de {
    encode gzip
    header {
        Strict-Transport-Security "max-age=31536000"
    }
    reverse_proxy fpp-control:8000
}
```

Alternativen:

- **[Nginx Proxy Manager](https://nginxproxymanager.com/)** – Weboberfläche für nginx mit Let's Encrypt; einen *Proxy Host* für deine Domain → `fpp-control:8000` anlegen, *Websockets Support* und *Force SSL* einschalten.
- **Traefik** – Vorlagen in [deploy/](../deploy/README.de.md), inklusive FalconBeat-Routen und passendem Rate-Limit.

---

## 🔒 Weg C: Tailscale Funnel (schnell, ohne Domain)

[Tailscale Funnel](https://tailscale.com/kb/1223/funnel) stellt einen Dienst eines Rechners in deinem Tailnet unter `https://<rechner>.<tailnet>.ts.net` bereit – mit HTTPS, ohne Portfreigabe und ohne Domain.

```bash
# auf dem Docker-Host, nach der Installation von Tailscale und dem Freischalten von Funnel in der Admin-Konsole
sudo tailscale funnel --bg 8080
```

Die App ist dann unter der Adresse erreichbar, die Tailscale ausgibt. Grenzen: keine eigene Domain, und die Bandbreite von Funnel ist begrenzt – gut zum Ausprobieren und für kleine Shows; für eine belebte Straße mit Musik-Funktion lieber A oder B.

---

## 🖥️ Weg D: kleiner Cloud-Server als Relais (VPS + WireGuard)

Wer schon einen kleinen Server mietet (VPS, wenige Euro im Monat): Dort läuft der Reverse Proxy mit öffentlicher IP, über WireGuard (oder Tailscale) ist er mit deinem Zuhause verbunden und leitet durch den Tunnel an die LAN-Adresse von FPP Web Control weiter. Das funktioniert bei CGNAT/DS-Lite, verbirgt deine Heim-IP und bleibt komplett in deiner Hand – ist aber der aufwendigste Weg, und der Server will gepflegt werden.

---

## 🔊 FalconBeat (Musik am Handy) über das Internet

Der Browser erreicht den FalconBeat-Server über **denselben Hostnamen** wie die App. Nur diese zwei Pfade weiterleiten, das Präfix `/falconbeat` entfernen:

| Öffentlicher Pfad | Ziel | Zweck |
|---|---|---|
| `/falconbeat/ws` | FalconBeat `/ws` | WebSocket: Uhrensync, Play/Pause |
| `/falconbeat/media/*` | FalconBeat `/media/*` | Audiodateien (nur GET) |

Caddy:

```caddyfile
lichtershow.example.de {
    encode gzip
    handle_path /falconbeat/* {
        @allowed path /ws /media/*
        handle @allowed {
            reverse_proxy falconbeat:80
        }
        respond 404
    }
    reverse_proxy fpp-control:8000
}
```

Mit Cloudflare Tunnel den Public Hostname auf einen Caddy-Container zeigen lassen (URL `caddy:80`, im Caddyfile dann `http://lichtershow.example.de` als Adresse, weil Cloudflare HTTPS schon übernimmt) und Caddy das Routing oben machen lassen – der Tunnel selbst kann das Präfix `/falconbeat` nicht entfernen. Mehr (Traefik, nginx): [deploy/README.de.md](../deploy/README.de.md).

---

## ✅ Sicherheits-Checkliste

- [ ] **Nur die Web-App** ist von außen erreichbar. Keine Portfreigabe auf den FPP, FalconBeat-Verwaltung, Home Assistant, den Router oder SSH.
- [ ] **Überall HTTPS**, HTTP leitet nur auf HTTPS um.
- [ ] **Zugangsschutz** ist an: `ACCESS_CODE` oder der Tagescode an der Matrix (`CODE_MATRIX_MODEL`). Nach 6 falschen Codes muss ein Besucher 10 Minuten warten.
- [ ] **Der Proxy setzt `X-Forwarded-For`** (Caddy, Traefik, nginx mit `proxy_add_x_forwarded_for`, Cloudflare). Sonst sehen für die App alle Besucher wie eine Adresse aus.
- [ ] **Großzügiges Rate-Limit**, falls du eines setzt: Während einer Show fragt jeder Besucher etwa alle 4 Sekunden ab, und im Mobilfunk teilen sich viele Besucher eine IP. Bewährt: etwa 1.200 Anfragen pro Minute und IP mit 300 als Burst.
- [ ] **Updates:** App-Image, Proxy und Router-Firmware aktuell halten (`docker compose pull && docker compose up -d`).
- [ ] **Geheimnisse** (Zugangscode, Tokens) in `.env` oder Docker Secrets, nie in einem öffentlichen Repository.
- [ ] **Optional härten:** Geoblocking für Länder ohne erwartete Besucher, [CrowdSec](https://www.crowdsec.net/) oder fail2ban vor dem Proxy, ein eigenes Netz/VLAN für die Show-Geräte.
- [ ] **Außerhalb der Saison** den Tunnel/Proxy einfach stoppen oder `FPP_SHOW_START_DATE`/`FPP_SHOW_END_DATE` setzen – außerhalb der Saison sind die Knöpfe ohnehin gesperrt.

---

## 📱 Von außen testen

1. Am Handy das **WLAN ausschalten** und die Adresse über mobile Daten öffnen.
2. Das Schloss im Browser muss ein gültiges Zertifikat zeigen.
3. Schnelle Prüfungen von einem beliebigen Rechner:

   ```bash
   curl -I https://lichtershow.example.de/            # 200
   curl -s https://lichtershow.example.de/api/state   # JSON mit "fppReachable": true
   curl -I https://lichtershow.example.de/falconbeat/media/nowplaying.json   # 200, wenn FalconBeat genutzt wird
   ```

4. Sicherstellen, dass der FPP **nicht** erreichbar ist: `http://<deine-öffentliche-ip>/` darf nicht die FPP-Oberfläche zeigen.

---

## 🛠️ Fehlersuche

| Problem | Wahrscheinliche Ursache | Was tun |
|---|---|---|
| Geht zu Hause, nicht über mobile Daten | Test aus dem eigenen WLAN, oder Portfreigabe fehlt | Mit ausgeschaltetem WLAN testen; Portfreigabe prüfen und ob sie auf den Proxy-Rechner zeigt |
| Portfreigabe gesetzt, trotzdem nicht erreichbar | DS-Lite / CGNAT (keine öffentliche IPv4) | Siehe [Schritt 0](#-schritt-0-internetanschluss-prüfen); Weg A, C oder D nehmen |
| Zertifikatsfehler / kein Zertifikat | Port 80 nicht freigegeben oder gesperrt, DNS zeigt auf falsche IP | Prüfen, ob der Name auf deine aktuelle IP zeigt (`nslookup`); Port 80 freigeben oder DNS-Challenge nutzen |
| Seite lädt, „Musik hören“ bleibt stumm | FalconBeat-Pfade nicht weitergeleitet | Siehe [FalconBeat über das Internet](#-falconbeat-musik-am-handy-über-das-internet) |
| Besucher bekommen „Zu viele Fehlversuche“, ohne es versucht zu haben | Proxy setzt kein `X-Forwarded-For`, alle teilen sich eine Adresse | Proxy so einstellen, dass er `X-Forwarded-For` setzt bzw. ergänzt |
| Fehler 429 während einer Show | Rate-Limit zu knapp | Erhöhen (siehe Checkliste) |
| Nach einem Update alte Version | Browser-Cache | Die App versioniert ihre Dateien, einmal neu laden genügt. In Cloudflare keine „Cache Everything“-Regel für diesen Host |

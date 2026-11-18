# 🌐 Reaching the app from the internet – safely

[Deutsch](internet-access.de.md) · **English**

Visitors stand in front of your house and use their **phone's mobile data**, not your Wi-Fi. So FPP Web Control has to be reachable from the internet. This guide shows the usual ways to do that, from "no router changes at all" to "own domain with port forwarding", and what to watch out for so that only the web app is exposed – never your Falcon Player or your home network.

---

## 📖 Contents

- [The basic rule: only the web app goes online](#-the-basic-rule-only-the-web-app-goes-online)
- [Which way suits you?](#-which-way-suits-you)
- [Step 0: check your internet connection](#-step-0-check-your-internet-connection)
- [Option A: Cloudflare Tunnel (no port forwarding)](#-option-a-cloudflare-tunnel-no-port-forwarding)
- [Option B: own domain or dynamic DNS + port forwarding + reverse proxy](#-option-b-own-domain-or-dynamic-dns--port-forwarding--reverse-proxy)
- [Option C: Tailscale Funnel (quick, no domain)](#-option-c-tailscale-funnel-quick-no-domain)
- [Option D: small cloud server as a relay (VPS + WireGuard)](#-option-d-small-cloud-server-as-a-relay-vps--wireguard)
- [FalconBeat (music on phones) through the internet](#-falconbeat-music-on-phones-through-the-internet)
- [Security checklist](#-security-checklist)
- [Testing from outside](#-testing-from-outside)
- [Troubleshooting](#-troubleshooting)

---

## 🧱 The basic rule: only the web app goes online

```
 Visitor's phone ──(internet, HTTPS)──▶ Reverse proxy / tunnel ──▶ FPP Web Control ──(LAN)──▶ Falcon Player
                                                     └──▶ FalconBeat (/falconbeat/ws, /falconbeat/media/* only)
```

- **FPP stays in your LAN.** The FPP web interface has no protection suitable for the internet. Never forward a port to the FPP, and never point a tunnel at it. FPP Web Control talks to FPP over the LAN; visitors never do.
- **Only HTTPS (port 443).** Phones increasingly refuse plain HTTP, and the music feature needs a secure page in many browsers.
- **Use access protection.** Set `ACCESS_CODE` or, better, the [daily code on the matrix](../README.md#daily-code-on-the-pixel-matrix). Then only people standing in front of your house can start shows, even though the page is public.
- **Expose as little as possible.** One host name, one service. Of FalconBeat only the two paths the browser needs (see [below](#-falconbeat-music-on-phones-through-the-internet)).

---

## 🧭 Which way suits you?

| Way | Router changes | Own domain | Works behind CGNAT / DS-Lite | Effort | Good for |
|---|---|---|---|---|---|
| **A: Cloudflare Tunnel** | none | yes (on Cloudflare) | ✅ yes | low | most home setups – the recommended way |
| **B: Port forwarding + reverse proxy** | forward 80/443 | own domain or free dynamic DNS | ❌ no (needs a public IPv4) | medium | full control, no third party in between |
| **C: Tailscale Funnel** | none | no (`*.ts.net` address) | ✅ yes | very low | trying it out, small shows |
| **D: VPS relay** | none | yes | ✅ yes | high | people who already run a server |

If you are unsure: **use A**. It needs no open ports on your router and also works when your provider doesn't give you a public IPv4 address.

---

## 🔎 Step 0: check your internet connection

Port forwarding (option B) only works if your router has a **public IPv4 address**. Many providers no longer give you one:

- **CGNAT** (carrier-grade NAT): common with mobile/5G home internet (e.g. T-Mobile Home Internet, Starlink), fibre start-ups and many cable providers.
- **DS-Lite**: common in Germany (e.g. Vodafone cable, some fibre providers) – you get IPv6 plus a shared IPv4.

**How to check:** compare the WAN/internet IPv4 address shown in your router with the address shown on [ifconfig.me](https://ifconfig.me) or [whatismyip.com](https://www.whatismyip.com/).

- Same address → you have a public IPv4, all options work.
- Different, or the router shows `100.64.x.x`–`100.127.x.x`, `10.x.x.x`, `192.168.x.x` as WAN address → CGNAT/DS-Lite. Use **option A, C or D**. (Some providers switch you to a public IPv4 on request, sometimes for a small fee.)

---

## ☁️ Option A: Cloudflare Tunnel (no port forwarding)

A small program (`cloudflared`) in your network opens an **outgoing** connection to Cloudflare. Visitors connect to Cloudflare, Cloudflare passes the requests through the tunnel to FPP Web Control. No ports are opened on your router, and your home IP address stays hidden.

**You need:** a free Cloudflare account and a domain whose DNS is managed by Cloudflare (buy one there or move an existing one; a `.com` costs around $10 a year).

### Steps

1. In the Cloudflare dashboard open **Zero Trust → Networks → Tunnels → Create a tunnel**, type **Cloudflared**, give it a name (e.g. `lightshow`).
2. Choose **Docker** as environment and copy the **token** from the command shown.
3. Run `cloudflared` next to FPP Web Control – e.g. in the same `docker-compose.yml`:

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
       # no "ports:" needed – only the tunnel talks to the app

     cloudflared:
       image: cloudflare/cloudflared:latest
       restart: unless-stopped
       command: tunnel --no-autoupdate run
       environment:
         - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}   # put the token into .env
   ```

4. In the tunnel settings add a **public hostname**: e.g. `lightshow.example.com`, service `HTTP`, URL `fpp-control:8000` (the service name from the Compose file).
5. Open `https://lightshow.example.com` on your phone with Wi-Fi switched off. Cloudflare provides the HTTPS certificate automatically.

### Notes

- **WebSockets** (needed for the music) work through the tunnel without extra settings.
- **Visitor address:** Cloudflare passes the visitor's address in `X-Forwarded-For`, so the lock after wrong codes works per visitor. If you put another reverse proxy between `cloudflared` and the app, make sure it *appends* to `X-Forwarded-For` (Caddy and Traefik do by default).
- **Caching:** don't enable "Cache Everything" for this host. The app already tells browsers what they may keep; the status must always be fresh.
- **Security extras (optional):** under *Security → WAF* you can rate-limit or block countries you don't expect visitors from. Keep the rate limit generous (see the checklist).
- **Terms:** Cloudflare's plans have rules about serving large media files. The audio files of a light show are small (a few MB per song), but check Cloudflare's current terms if you expect a lot of traffic.

---

## 🏠 Option B: own domain or dynamic DNS + port forwarding + reverse proxy

The classic way: your router forwards ports 80 and 443 to a reverse proxy in your network, which handles HTTPS and passes requests on to FPP Web Control.

### 1. A name for your address

Your home IP address can change. You need a name that always points to it:

- **Own domain** (e.g. from Namecheap, Porkbun, IONOS, INWX, Cloudflare) plus a dynamic DNS update – many registrars and Cloudflare offer an API for that.
- **Free dynamic DNS**: [DuckDNS](https://www.duckdns.org/), [deSEC](https://desec.io/), [Dynu](https://www.dynu.com/), [No-IP](https://www.noip.com/). You get a name like `mylightshow.duckdns.org`.
- **Router built-in**: many routers update dynamic DNS themselves (e.g. FRITZ!Box: *Internet → Shares → Dynamic DNS*, or MyFRITZ!). Otherwise run an updater container such as [ddns-updater](https://github.com/qdm12/ddns-updater) or `ddclient`.

Tip: with your own domain, create a `CNAME` like `lightshow.example.com` → `mylightshow.duckdns.org`, so you keep a nice address and the dynamic part stays hidden.

### 2. Port forwarding on the router

Forward **TCP 80 and TCP 443** to the **host that runs the reverse proxy** – not to the FPP, and not to the app's port 8080 directly.

- **FRITZ!Box:** *Internet → Permit Access → Port Sharing → Add device for sharing* → choose the server → *New sharing* → *Port sharing* for HTTPS (443) and HTTP (80).
- **Other routers:** look for "Port forwarding", "Virtual server" or "NAT". Give the server a fixed LAN address first (DHCP reservation).

Port 80 is only needed for getting the certificate (Let's Encrypt HTTP challenge) and for redirecting to HTTPS. If your provider blocks port 80, use a DNS challenge (Caddy and Traefik support it with a DNS provider plugin) or option A.

### 3. Reverse proxy with automatic HTTPS

**Caddy** is the easiest: it gets and renews the Let's Encrypt certificate by itself.

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
lightshow.example.com {
    encode gzip
    header {
        Strict-Transport-Security "max-age=31536000"
    }
    reverse_proxy fpp-control:8000
}
```

Alternatives:

- **[Nginx Proxy Manager](https://nginxproxymanager.com/)** – a web interface for nginx with Let's Encrypt; add a *Proxy Host* for your domain → `fpp-control:8000`, enable *Websockets Support* and *Force SSL*.
- **Traefik** – templates in [deploy/](../deploy/README.md), including FalconBeat routes and a suitable rate limit.

---

## 🔒 Option C: Tailscale Funnel (quick, no domain)

[Tailscale Funnel](https://tailscale.com/kb/1223/funnel) publishes a service of a machine in your tailnet under `https://<machine>.<tailnet>.ts.net` – with HTTPS, without port forwarding and without a domain.

```bash
# on the Docker host, after installing Tailscale and enabling Funnel in the admin console
sudo tailscale funnel --bg 8080
```

The app is then reachable at the address Tailscale prints. Limits: the address can't be your own domain, and Funnel's bandwidth is limited – fine for trying it out and small shows; for a busy street with the music feature, prefer A or B.

---

## 🖥️ Option D: small cloud server as a relay (VPS + WireGuard)

If you already rent a small server (VPS, a few dollars/euros a month): run the reverse proxy there with a public IP, connect it to your home with WireGuard (or Tailscale), and let the proxy forward to FPP Web Control's LAN address through the tunnel. This works behind CGNAT, hides your home IP and keeps everything under your own control – but it is the most work and you have to maintain the server.

---

## 🔊 FalconBeat (music on phones) through the internet

The browser reaches the FalconBeat server through the **same host name** as the app. Forward only these two paths, with the `/falconbeat` prefix removed:

| Public path | Target | Purpose |
|---|---|---|
| `/falconbeat/ws` | FalconBeat `/ws` | WebSocket: clock sync, play/pause |
| `/falconbeat/media/*` | FalconBeat `/media/*` | audio files (GET only) |

Caddy:

```caddyfile
lightshow.example.com {
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

With a Cloudflare Tunnel, point the tunnel's public hostname at a Caddy container (URL `caddy:80`, and use `http://lightshow.example.com` as the site address in the Caddyfile, since Cloudflare already handles HTTPS) and let Caddy do the routing above – the tunnel itself can't strip the `/falconbeat` prefix. More (Traefik, nginx): [deploy/README.md](../deploy/README.md).

---

## ✅ Security checklist

- [ ] **Only the web app** is reachable from outside. No port forwarding to FPP, FalconBeat's admin pages, Home Assistant, the router or SSH.
- [ ] **HTTPS everywhere**, HTTP only redirects to HTTPS.
- [ ] **Access protection** is on: `ACCESS_CODE` or the daily code on the matrix (`CODE_MATRIX_MODEL`). After 6 wrong codes a visitor has to wait 10 minutes.
- [ ] **The proxy sets `X-Forwarded-For`** (Caddy, Traefik, nginx `proxy_add_x_forwarded_for`, Cloudflare). Otherwise all visitors look like one address to the app.
- [ ] **A generous rate limit**, if you set one: during a show every visitor polls about every 4 seconds, and on mobile networks many visitors share one IP. Something like 1,200 requests per minute per IP with a burst of 300 works well.
- [ ] **Updates:** keep the app image, the proxy and the router firmware up to date (`docker compose pull && docker compose up -d`).
- [ ] **Secrets** (access code, tokens) in `.env` or Docker secrets, never in a public repository.
- [ ] **Optional hardening:** geo-blocking of countries you don't expect visitors from, [CrowdSec](https://www.crowdsec.net/) or fail2ban in front of the proxy, a separate network/VLAN for the show devices.
- [ ] **Outside the season** you can simply stop the tunnel/proxy, or set `FPP_SHOW_START_DATE`/`FPP_SHOW_END_DATE` – the buttons are locked outside the season anyway.

---

## 📱 Testing from outside

1. Switch your phone's **Wi-Fi off** and open the address with mobile data.
2. The padlock must show a valid certificate.
3. Quick checks from any computer:

   ```bash
   curl -I https://lightshow.example.com/            # 200
   curl -s https://lightshow.example.com/api/state   # JSON with "fppReachable": true
   curl -I https://lightshow.example.com/falconbeat/media/nowplaying.json   # 200 if you use FalconBeat
   ```

4. Make sure the FPP is **not** reachable: `http://<your-public-ip>/` must not show the FPP interface.

---

## 🛠️ Troubleshooting

| Problem | Likely cause | What to do |
|---|---|---|
| Works at home, not on mobile data | Testing from inside your Wi-Fi, or port forwarding missing | Test with Wi-Fi off; check the router's port forwarding and that it points to the proxy host |
| Port forwarding set, still unreachable | CGNAT / DS-Lite (no public IPv4) | See [step 0](#-step-0-check-your-internet-connection); use option A, C or D |
| Certificate error / no certificate | Port 80 not forwarded or blocked, DNS points to the wrong IP | Check that the name resolves to your current IP (`nslookup`); forward port 80, or use a DNS challenge |
| Page loads, "Listen" button gives no sound | FalconBeat paths not forwarded | See [FalconBeat through the internet](#-falconbeat-music-on-phones-through-the-internet) |
| Visitors get "Too many failed attempts" although they didn't try | The proxy doesn't set `X-Forwarded-For`, so everybody shares one address | Configure the proxy to set/append `X-Forwarded-For` |
| Errors 429 during a show | Rate limit too strict | Raise it (see the checklist) |
| Old version shown after an update | Browser cache | The app versions its files; a reload fixes it. Disable "Cache Everything" rules in Cloudflare for this host |

# FalconBeat audio behind a reverse proxy

[Deutsch](README.de.md) · **English**

How to make the app reachable from the internet in the first place is described in [Reaching the app from the internet](../docs/internet-access.md).

The speaker button plays the show music in sync on the visitor's device. For that the browser needs two routes to the FalconBeat server – under the **same address** as fpp-web-control (no CORS, no mixed content):

| Path at fpp-web-control | Target in the FalconBeat container (port 80) | Purpose |
|---|---|---|
| `/falconbeat/ws`        | `/ws`      | WebSocket: clock sync + play/pause |
| `/falconbeat/media/*`   | `/media/*` | Audio files (`GET` only) |

The proxy must strip the `/falconbeat` prefix. Nothing else is exposed – neither the listener page nor `/upload/complete` or `/discover`.

fpp-web-control itself only contacts the FalconBeat server for the health check (`FALCONBEAT_SERVER_URL`, otherwise the address from the FPP plugin).

## Traefik (Docker Swarm, labels on the FalconBeat service)

See [`traefik-swarm-labels.yml`](traefik-swarm-labels.yml). The labels belong under `deploy.labels` of the **FalconBeat** service, because the router points to its Traefik service.

Important: use a separate, generous rate limit (as on the FalconBeat router). Behind mobile carrier NAT many visitors share one IP address.

## Traefik (file provider, e.g. an internal LAN Traefik)

See [`traefik-file-provider.yml`](traefik-file-provider.yml).

## Caddy

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
    reverse_proxy fpp-web-control:8000
}
```

## nginx

```nginx
location /falconbeat/ws {
    proxy_pass http://falconbeat:80/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 1h;
}
location /falconbeat/media/ {
    limit_except GET { deny all; }
    proxy_pass http://falconbeat:80/media/;
}
```

## Check

```bash
# 200 + JSON when the media route works
curl -i https://<your-domain>/falconbeat/media/nowplaying.json

# 404: the listener page is not reachable through this path
curl -i https://<your-domain>/falconbeat/
```

Then fpp-web-control's `GET /api/state` should report `"falconbeat": {"available": true}`.

## Rate limit and compression for fpp-web-control

The second block in [`traefik-swarm-labels.yml`](traefik-swarm-labels.yml) gives the fpp-web-control router a separate, generous rate limit and switches on compression. Without that, several visitors behind the same mobile address run into a tight default limit during a show.

The stack file [`../docker-stack.yml`](../docker-stack.yml) already contains these labels.

---
sidebar_position: 2
slug: /operations/tls-and-reverse-proxy
---

# TLS & Reverse Proxy

Configure TLS before exposing the API publicly.

## Exposure rules

- expose the API only
- keep PostgreSQL, Redis, and MinIO private
- terminate TLS in front of port `8000`

## Caddy

```caddy
algenta.example.com {
  reverse_proxy 127.0.0.1:8000
}
```

## nginx

```nginx
server {
    listen 443 ssl http2;
    server_name algenta.example.com;

    ssl_certificate     /etc/letsencrypt/live/algenta.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/algenta.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Browser origins

Set `CORS_ORIGINS` to the exact browser origins that should call the API:

```bash
CORS_ORIGINS=https://app.example.com,https://admin.example.com
```

## Related pages

- [Setup & Configuration](/self-hosting)
- [Logs & Metrics](/operations/logs-and-metrics)
- [Upgrade & Rollback](/operations/upgrade-and-rollback)

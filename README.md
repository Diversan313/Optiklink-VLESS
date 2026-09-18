# OptikLink-VLESS

### **Language:** English | [Русский](README_RU.md)

---

Deploy **VLESS** (Xray-core) or **Telegram MTProto** (mtg) proxy on OptikLink servers.

Works with [OptikLink KeepAlive](https://github.com/Diversan313/OptiKA) or standalone.

---

## Configuration

All options are set in **`settings.txt`**:

```text
IP =
PORT =
MODE =
PROTOCOL =
TLS =
UUID =
PATH =
SNI =
ALLOW_INSECURE =
MT_SECRET =
MT_DOMAIN =
MT_PREFER_IP =
MT_TIME_SKEW =
NAME =
LOG_FILE =
```

Empty fields are filled automatically.

### Common

| Parameter | Default | Description |
|-----------|---------|-------------|
| `IP` | auto-detect | Server IP |
| `PORT` | `6202` | Port |
| `MODE` | `vless` | `vless` or `mtproto` |
| `NAME` | `Optiklink` | Display name |
| `LOG_FILE` | `false` | Write `bot.log` (rotates ~1 MB) |

### VLESS (`MODE = vless` or empty)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PROTOCOL` | `ws` | `ws` or `xhttp` |
| `TLS` | `true` | Self-signed certificate |
| `UUID` | new UUID | Empty → generate new |
| `PATH` | `/vless` / `/xhttp` | Transport path |
| `SNI` | `optiklink.local` | TLS SNI |
| `ALLOW_INSECURE` | `false` | Skip cert check on client |

Recommended: `PROTOCOL = ws`, `TLS = true`, `ALLOW_INSECURE = true`.

### MTProto (`MODE = mtproto`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MT_SECRET` | auto | Fake-TLS secret (empty → generate) |
| `MT_DOMAIN` | `www.google.com` | Fake-TLS camouflage host |
| `MT_PREFER_IP` | `prefer-ipv4` | `prefer-ipv4` / `prefer-ipv6` / `only-ipv4` / `only-ipv6` |
| `MT_TIME_SKEW` | `30s` | Allowed clock drift |

If you change `MT_DOMAIN`, clear `MT_SECRET` so a new secret is generated.

---

## Run

```bash
python3 bot.py
```

The script downloads Xray or mtg if needed, builds the config and prints the connection link(s) to the console and `links.txt`.

---

## Files

| File | Purpose |
|------|---------|
| `settings.txt` | User settings |
| `bot.py` | Main script |
| `links.txt` | Connection link(s) |
| `xray_config.json` | Xray config (VLESS) |
| `mtg_config.toml` | mtg config (MTProto) |
| `server.crt` / `server.key` | TLS certificate (VLESS) |
| `bot.log` | Optional log (`LOG_FILE = true`) |

---

## Notes

- OptikLink usually provides a single port — choose **one** mode (`vless` or `mtproto`).
- After changing VLESS settings, clear `UUID` to generate a new identifier.
- In v2rayNG, `allowInsecure` from the share link may not apply; enable skip certificate verification manually.
- If `bot.log` grew large, delete it and keep `LOG_FILE = false`.


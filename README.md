# OptikLink-VLESS

### **Language:** English | [Русский](README_RU.md)

---

Deploy VLESS (Xray-core) on OptikLink servers.

Works with [OptikLink KeepAlive](https://github.com/Diversan313/optiksffq2z) or standalone.

---

## Configuration

All options are set in **`settings.txt`**:

```text
IP =
PORT =
PROTOCOL =
TLS =
UUID =
PATH =
SNI =
NAME =
ALLOW_INSECURE =
```

Empty fields are filled automatically.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `IP` | auto-detect | Server IP |
| `PORT` | `6202` | Port |
| `PROTOCOL` | `ws` | `ws` or `xhttp` |
| `TLS` | `true` | TLS (self-signed certificate) |
| `UUID` | new UUID | Empty value generates a new one |
| `PATH` | `/vless` / `/xhttp` | Transport path |
| `SNI` | `optiklink.local` | TLS SNI |
| `NAME` | `Optiklink` | Display name in client |
| `ALLOW_INSECURE` | `false` | Skip certificate verification on client |

Recommended start: `PROTOCOL = ws`, `TLS = true`, `ALLOW_INSECURE = true`.

---

## Run

```bash
python3 bot.py
```

The script downloads Xray if needed, creates a certificate, builds the config, and prints the connection link to the console and `links.txt`.

---

## Files

| File | Purpose |
|------|---------|
| `settings.txt` | User settings |
| `bot.py` | Main script |
| `links.txt` | VLESS link |
| `xray_config.json` | Xray config |
| `server.crt` / `server.key` | TLS certificate |

---

## Notes

- OptikLink usually provides a single port — pick one protocol.
- After changing settings, clear `UUID` to generate a new identifier.
- In v2rayNG, `allowInsecure` from the share link may not apply; enable skip certificate verification manually in the profile.


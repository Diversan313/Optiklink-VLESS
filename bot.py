#!/usr/bin/env python3
"""
OptikLink VLESS Deployer
Source of truth: settings.txt
"""

import os
import stat
import subprocess
import urllib.request
import zipfile
import json
import time
import threading
import sys
import uuid
import hashlib
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SETTINGS_FILE = "settings.txt"
CONFIG_FILE = "config.json"
XRAY_CONFIG_FILE = "xray_config.json"
LINKS_FILE = "links.txt"
CERT_FILE = "server.crt"
KEY_FILE = "server.key"
XRAY_BIN = "xray"
LOG_FILE = "bot.log"
STATE_FILE = ".deploy_state.json"

# Defaults (used only when field is empty)
DEFAULT_PORT = 6202
DEFAULT_PROTOCOL = "ws"
DEFAULT_TLS = True
DEFAULT_SNI = "optiklink.local"
DEFAULT_NAME = "Optiklink"
DEFAULT_DNS = ["8.8.8.8", "1.1.1.1"]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
def get_public_ip() -> str:
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
        "https://ipinfo.io/ip",
    ]
    for url in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                ip = resp.read().decode("utf-8").strip()
                if ip and len(ip.split(".")) == 4:
                    return ip
        except Exception:
            continue
    return ""


# ---------------------------------------------------------------------------
# Xray binary
# ---------------------------------------------------------------------------
def ensure_xray() -> None:
    if os.path.exists(XRAY_BIN) and os.access(XRAY_BIN, os.X_OK):
        return

    log("Downloading Xray-core...")
    zip_name = "xray.zip"
    try:
        urllib.request.urlretrieve(
            "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip",
            zip_name,
        )
        with zipfile.ZipFile(zip_name, "r") as z:
            z.extractall(".")
        if os.path.exists(zip_name):
            os.remove(zip_name)
        st = os.stat(XRAY_BIN)
        os.chmod(XRAY_BIN, st.st_mode | stat.S_IEXEC)
        log("Xray ready.")
    except Exception as e:
        log(f"Failed to download Xray: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# TLS
# ---------------------------------------------------------------------------
def ensure_tls_certs(sni: str = DEFAULT_SNI) -> bool:
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return True

    log("Generating self-signed TLS certificate...")
    try:
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-nodes", "-keyout", KEY_FILE, "-out", CERT_FILE,
                "-days", "3650", "-subj", f"/CN={sni}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        log("Certificate created (OpenSSL).")
        return True
    except Exception:
        pass

    try:
        subprocess.run(
            [f"./{XRAY_BIN}", "tls", "cert", "--domain", sni],
            capture_output=True,
            text=True,
            check=True,
        )
        if os.path.exists("cert.pem") and os.path.exists("key.pem"):
            os.rename("cert.pem", CERT_FILE)
            os.rename("key.pem", KEY_FILE)
        log("Certificate created (Xray).")
        return True
    except Exception as e:
        log(f"Certificate generation failed: {e}")
        return False


def get_cert_sha256() -> str:
    if not os.path.exists(CERT_FILE):
        return ""
    try:
        result = subprocess.run(
            ["openssl", "x509", "-in", CERT_FILE, "-noout", "-fingerprint", "-sha256"],
            capture_output=True,
            text=True,
            check=True,
        )
        line = result.stdout.strip()
        if "=" in line:
            return line.split("=", 1)[1].replace(":", "").lower()
    except Exception as e:
        log(f"Fingerprint error: {e}")
    return ""


# ---------------------------------------------------------------------------
# settings.txt
# ---------------------------------------------------------------------------
def parse_settings(path: str) -> dict:
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().upper()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            data[key] = value
    return data


def write_settings_value(key: str, value: str) -> None:
    """Update a single KEY = value line in settings.txt (preserves comments)."""
    if not os.path.exists(SETTINGS_FILE):
        return
    lines = []
    found = False
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip().upper()
                if k == key.upper():
                    lines.append(f"{key.upper()} = {value}\n")
                    found = True
                    continue
            lines.append(line)
    if not found:
        lines.append(f"\n{key.upper()} = {value}\n")
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


def ensure_settings_file() -> None:
    if os.path.exists(SETTINGS_FILE):
        return

    template = """# ============================================================
#  OptikLink VLESS Settings
# ============================================================

# -------------------- SERVER --------------------
IP =
PORT =

# -------------- PROTOCOL & ENCRYPTION -----------
# PROTOCOL: ws | xhttp
# TLS: true | false
PROTOCOL =
TLS =

# -------------------- OPTIONAL ------------------
# Leave empty to use defaults
UUID =
PATH =
SNI =
NAME =

# ALLOW_INSECURE: true | false
# true  = client skips cert check (needed for most apps with self-signed TLS)
# false = strict check (works if client supports pcs= pin)
ALLOW_INSECURE =
"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        f.write(template)
    log(f"Created {SETTINGS_FILE}. Fill in IP and PORT, then restart.")
    sys.exit(0)


def settings_fingerprint(raw: dict) -> str:
    """Hash of fields that affect the server identity/transport."""
    keys = ("IP", "PORT", "PROTOCOL", "TLS", "PATH", "SNI")
    payload = "|".join(f"{k}={(raw.get(k) or '').strip().lower()}" for k in keys)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_config() -> dict:
    """
    Always rebuild from settings.txt.
    If settings changed (or UUID empty) — generate a new UUID.
    """
    ensure_settings_file()
    raw = parse_settings(SETTINGS_FILE)
    log(f"Loaded {SETTINGS_FILE}")

    ip = (raw.get("IP") or "").strip()
    port_str = (raw.get("PORT") or "").strip()
    protocol = (raw.get("PROTOCOL") or "").strip().lower()
    tls_str = (raw.get("TLS") or "").strip().lower()
    uuid_val = (raw.get("UUID") or "").strip()
    path = (raw.get("PATH") or "").strip()
    sni = (raw.get("SNI") or "").strip()
    name = (raw.get("NAME") or "").strip()
    alin_str = (raw.get("ALLOW_INSECURE") or "").strip().lower()

    # Port
    if port_str:
        try:
            port = int(port_str)
        except ValueError:
            log(f"Invalid PORT: {port_str}")
            sys.exit(1)
    else:
        port = DEFAULT_PORT

    # Protocol
    if not protocol:
        protocol = DEFAULT_PROTOCOL
    if protocol not in ("ws", "xhttp"):
        log(f"Invalid PROTOCOL: {protocol}. Use: ws, xhttp")
        sys.exit(1)

    # TLS
    if tls_str:
        tls = tls_str in ("1", "true", "yes", "on")
    else:
        tls = DEFAULT_TLS

    # Path — always match protocol when empty
    if not path:
        path = "/xhttp" if protocol == "xhttp" else "/vless"
    path = "/" + path.lstrip("/")

    if not sni:
        sni = DEFAULT_SNI
    if not name:
        name = DEFAULT_NAME

    # ALLOW_INSECURE: empty → false (strict). Set true if client rejects cert.
    if alin_str:
        allow_insecure = alin_str in ("1", "true", "yes", "on")
    else:
        allow_insecure = False

    # IP
    if not ip:
        log("IP not set, detecting public IP...")
        ip = get_public_ip()
        if not ip:
            log(f"Cannot detect IP. Set IP in {SETTINGS_FILE}")
            sys.exit(1)
        log(f"Detected IP: {ip}")
        write_settings_value("IP", ip)

    # Settings change → drop stale generated files
    fp = settings_fingerprint(raw)
    state = load_state()
    settings_changed = state.get("fingerprint") != fp

    if settings_changed:
        log("Settings changed — full rebuild.")
        for f in (CONFIG_FILE, XRAY_CONFIG_FILE, LINKS_FILE):
            if os.path.exists(f):
                os.remove(f)

    # UUID empty in settings → always generate a new one
    if not uuid_val:
        uuid_val = str(uuid.uuid4())
        log(f"UUID empty — generated new: {uuid_val}")
        write_settings_value("UUID", uuid_val)
    else:
        log(f"Using UUID from settings: {uuid_val}")

    cfg = {
        "server_ip": ip,
        "port": port,
        "uuid": uuid_val,
        "mode": protocol,
        "tls": tls,
        "path": path,
        "sni": sni,
        "dns_servers": DEFAULT_DNS,
        "remark": name,
        "allow_insecure": allow_insecure,
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    log(f"Wrote {CONFIG_FILE}")

    save_state({"fingerprint": fp, "uuid": uuid_val})

    return cfg


# ---------------------------------------------------------------------------
# Xray config
# ---------------------------------------------------------------------------
def build_xray_config(cfg: dict) -> dict:
    use_tls = cfg["tls"]
    mode = cfg["mode"]
    path = cfg["path"]
    sni = cfg.get("sni", DEFAULT_SNI)

    stream = {}

    if mode == "ws":
        stream["network"] = "ws"
        stream["wsSettings"] = {"path": path}
    else:
        stream["network"] = "xhttp"
        stream["xhttpSettings"] = {
            "path": path,
            "mode": "auto",
        }

    if use_tls:
        ok = ensure_tls_certs(sni)
        if not ok:
            use_tls = False
            cfg["tls"] = False
            stream["security"] = "none"
        else:
            stream["security"] = "tls"
            stream["tlsSettings"] = {
                "certificates": [
                    {
                        "certificateFile": CERT_FILE,
                        "keyFile": KEY_FILE,
                    }
                ]
            }
    else:
        stream["security"] = "none"

    inbound = {
        "listen": "0.0.0.0",
        "port": cfg["port"],
        "protocol": "vless",
        "settings": {
            "clients": [{"id": cfg["uuid"]}],
            "decryption": "none",
        },
        "streamSettings": stream,
        "sniffing": {
            "enabled": True,
            "destOverride": ["http", "tls", "quic"],
        },
    }

    return {
        "log": {"loglevel": "warning"},
        "dns": {"servers": cfg.get("dns_servers", DEFAULT_DNS)},
        "inbounds": [inbound],
        "outbounds": [{"protocol": "freedom", "tag": "direct"}],
    }


def generate_link(cfg: dict) -> str:
    uid = cfg["uuid"]
    ip = cfg["server_ip"]
    port = cfg["port"]
    mode = cfg["mode"]
    path = cfg["path"].lstrip("/")
    use_tls = cfg["tls"]
    sni = cfg.get("sni", DEFAULT_SNI)
    remark = cfg.get("remark", DEFAULT_NAME)

    security = "tls" if use_tls else "none"
    params = [
        f"type={mode}",
        f"path=%2F{path}",
        f"security={security}",
        "encryption=none",
    ]

    if use_tls:
        allow_insecure = bool(cfg.get("allow_insecure", False))
        if allow_insecure:
            params.append("allowInsecure=1")
            params.append("insecure=1")
        else:
            params.append("allowInsecure=0")
            params.append("insecure=0")
        params.append(f"sni={sni}")
        params.append("fp=chrome")
        pcs = get_cert_sha256()
        if pcs:
            params.append(f"pcs={pcs}")

    query = "&".join(params)
    tag = f"{remark}-{mode.upper()}" + ("-TLS" if use_tls else "")
    return f"vless://{uid}@{ip}:{port}?{query}#{tag}"


# ---------------------------------------------------------------------------
# Keep-alive
# ---------------------------------------------------------------------------
def keep_alive(port: int, use_tls: bool = False) -> None:
    """External ping only. Do not hit local port with plain HTTP when TLS is on."""
    while True:
        try:
            urllib.request.urlopen("https://1.1.1.1", timeout=5)
        except Exception:
            pass
        if not use_tls:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
            except Exception:
                pass
        time.sleep(60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    log("=" * 50)
    log("OptikLink VLESS Deployer")
    log("=" * 50)

    ensure_xray()
    cfg = load_config()

    log(f"Mode: {cfg['mode'].upper()} | TLS: {cfg['tls']} | Port: {cfg['port']}")
    log(f"IP: {cfg['server_ip']} | UUID: {cfg['uuid']}")
    log(f"Path: {cfg['path']}")

    xray_cfg = build_xray_config(cfg)

    # Always write xray config from scratch
    with open(XRAY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(xray_cfg, f, indent=2, ensure_ascii=False)
    log(f"Wrote {XRAY_CONFIG_FILE}")

    link = generate_link(cfg)
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        f.write(link + "\n")

    log("-" * 50)
    log("CONNECTION LINK:")
    log(link)
    log("-" * 50)
    log(f"Saved to {LINKS_FILE}")

    threading.Thread(target=keep_alive, args=(cfg["port"], cfg["tls"]), daemon=True).start()

    while True:
        try:
            log("Starting Xray...")
            process = subprocess.Popen(
                [f"./{XRAY_BIN}", "run", "-c", XRAY_CONFIG_FILE],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in process.stdout:
                stripped = line.strip()
                if stripped:
                    log(f"[xray] {stripped}")
            process.wait()
            log(f"Xray exited with code {process.returncode}")
        except Exception as e:
            log(f"Xray error: {e}")

        log("Restarting in 5 seconds...")
        time.sleep(5)


if __name__ == "__main__":
    main()

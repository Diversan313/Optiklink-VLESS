#!/usr/bin/env python3
"""
OptikLink Proxy Deployer
VLESS (Xray-core) and Telegram MTProto (mtg).
Source of truth: settings.txt
"""

import os
import stat
import subprocess
import urllib.request
import urllib.parse
import zipfile
import tarfile
import json
import base64
import platform
import time
import threading
import sys
import uuid
import hashlib
from datetime import datetime

SETTINGS_FILE = "settings.txt"
CONFIG_FILE = "config.json"
XRAY_CONFIG_FILE = "xray_config.json"
LINKS_FILE = "links.txt"
CERT_FILE = "server.crt"
KEY_FILE = "server.key"
XRAY_BIN = "xray"
MTG_BIN = "mtg"
LOG_FILE = "bot.log"
STATE_FILE = ".deploy_state.json"
MTPROTO_CONFIG_FILE = "mtproto_config.json"
MTG_CONFIG_FILE = "mtg_config.toml"

DEFAULT_PORT = 6202
DEFAULT_PROXY_TYPE = "vless"
DEFAULT_PROTOCOL = "ws"
DEFAULT_TLS = True
DEFAULT_SNI = "optiklink.local"
DEFAULT_NAME = "Optiklink"
DEFAULT_DNS = ["8.8.8.8", "1.1.1.1"]
DEFAULT_MT_DOMAIN = "www.google.com"
DEFAULT_MT_PREFER_IP = "prefer-ipv4"
DEFAULT_MT_TIME_SKEW = "30s"
MT_PREFER_IP_VALUES = ("prefer-ipv4", "prefer-ipv6", "only-ipv4", "only-ipv6")
DEFAULT_LOG_FILE = False
MAX_LOG_BYTES = 1000000

LOG_TO_FILE = False


def _rotate_log_if_needed():
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_BYTES:
            os.replace(LOG_FILE, LOG_FILE + ".old")
    except Exception:
        pass


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    if not LOG_TO_FILE:
        return
    try:
        _rotate_log_if_needed()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_public_ip():
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


def ensure_xray():
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


def mtg_asset_suffix():
    """Return the mtg release suffix for the current Linux CPU architecture."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system != "linux":
        log(f"Unsupported OS for automatic mtg download: {platform.system()}")
        sys.exit(1)

    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "i386": "386",
        "i686": "386",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "armv7",
        "armv6l": "armv6",
        "mips": "mips",
        "mipsle": "mipsle",
    }
    arch = arch_map.get(machine)
    if not arch:
        log(f"Unsupported CPU architecture for mtg: {machine}")
        sys.exit(1)
    return f"linux-{arch}"


def ensure_mtg():
    if os.path.exists(MTG_BIN) and os.access(MTG_BIN, os.X_OK):
        return

    log("Downloading mtg (MTProto proxy)...")
    tar_name = "mtg.tar.gz"
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/9seconds/mtg/releases/latest",
            headers={"User-Agent": "OptikLink-VLESS"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            release = json.load(resp)

        tag = release.get("tag_name") or ""
        version = tag.lstrip("v")
        if not version:
            raise RuntimeError("cannot detect latest mtg version")

        asset_name = f"mtg-{version}-{mtg_asset_suffix()}.tar.gz"
        assets = release.get("assets") or []
        download_url = ""
        for asset in assets:
            if asset.get("name") == asset_name:
                download_url = asset.get("browser_download_url") or ""
                break
        if not download_url:
            raise RuntimeError(f"release asset not found: {asset_name}")

        urllib.request.urlretrieve(download_url, tar_name)
        with tarfile.open(tar_name, "r:gz") as tar:
            mtg_member = None
            for member in tar.getmembers():
                if member.isfile() and os.path.basename(member.name) == MTG_BIN:
                    mtg_member = member
                    break
            if not mtg_member:
                raise RuntimeError("mtg binary not found in archive")
            src = tar.extractfile(mtg_member)
            if not src:
                raise RuntimeError("cannot extract mtg binary")
            with open(MTG_BIN, "wb") as out:
                out.write(src.read())

        if os.path.exists(tar_name):
            os.remove(tar_name)
        st = os.stat(MTG_BIN)
        os.chmod(MTG_BIN, st.st_mode | stat.S_IEXEC)
        log("mtg ready.")
    except Exception as e:
        if os.path.exists(tar_name):
            try:
                os.remove(tar_name)
            except Exception:
                pass
        log(f"Failed to download mtg: {e}")
        sys.exit(1)


def ensure_tls_certs(sni=DEFAULT_SNI):
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


def get_cert_sha256():
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


def normalize_mt_domain(domain):
    host = (domain or DEFAULT_MT_DOMAIN).strip()
    if host.startswith("http://"):
        host = host[7:]
    elif host.startswith("https://"):
        host = host[8:]
    host = host.split("/", 1)[0].split(":", 1)[0].strip().lower()
    if not host:
        host = DEFAULT_MT_DOMAIN
    try:
        host = host.encode("idna").decode("ascii")
    except Exception:
        log(f"Invalid MT_DOMAIN: {domain}")
        sys.exit(1)
    if any(ch.isspace() for ch in host):
        log(f"Invalid MT_DOMAIN: {domain}")
        sys.exit(1)
    return host


def is_hex_secret(value):
    if len(value) % 2 != 0:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value)


def normalize_mt_secret(secret):
    """Return a Telegram-compatible hex secret from hex or mtg base64 input."""
    value = (secret or "").strip()
    if value.startswith("0x") or value.startswith("0X"):
        value = value[2:]
    value = "".join(value.split())
    if is_hex_secret(value):
        if len(value) < 32:
            log("Invalid MT_SECRET: hex secret must be at least 32 characters")
            sys.exit(1)
        return value.lower()

    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
        if len(decoded) < 16:
            raise ValueError("too short")
        return decoded.hex()
    except Exception:
        log("Invalid MT_SECRET: use hex secret or mtg base64 secret")
        sys.exit(1)


def generate_mt_secret(domain):
    # Fake-TLS MTProto secret: ee + 16 random bytes + hex(hostname).
    # It is accepted by mtg and can be pasted into Telegram tg://proxy links.
    host = normalize_mt_domain(domain)
    return "ee" + os.urandom(16).hex() + host.encode("ascii").hex()


def get_mt_secret_domain(secret):
    # Fake-TLS secret embeds the camouflage hostname after: ee + 16 random bytes.
    if not secret.startswith("ee") or len(secret) <= 34:
        return ""
    domain_hex = secret[34:]
    if len(domain_hex) % 2 != 0:
        return ""
    try:
        return bytes.fromhex(domain_hex).decode("ascii").lower()
    except Exception:
        return ""


def mt_secret_to_base64(secret):
    try:
        raw = bytes.fromhex(secret)
    except Exception:
        log("Invalid MT_SECRET: cannot convert hex secret to mtg base64 secret")
        sys.exit(1)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def parse_settings(path):
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


def write_settings_value(key, value):
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


def ensure_settings_file():
    if os.path.exists(SETTINGS_FILE):
        return
    template = """# ============================================================
#  OptikLink Proxy Settings
# ============================================================

# -------------------- SERVER --------------------
IP =
PORT =

# -------------------- MODE ----------------------
# MODE: vless | mtproto (empty = vless)
MODE =

# -------------- VLESS / XRAY --------------------
# PROTOCOL: ws | xhttp
# TLS: true | false
PROTOCOL =
TLS =
UUID =
PATH =
SNI =
ALLOW_INSECURE =

# -------------------- MTPROTO -------------------
# MT_SECRET: empty = generate a new Fake-TLS secret
# MT_DOMAIN: empty = www.google.com (Fake-TLS camouflage host)
# MT_PREFER_IP: prefer-ipv4 | prefer-ipv6 | only-ipv4 | only-ipv6
# MT_TIME_SKEW: allowed client/server clock drift (empty = 30s)
MT_SECRET =
MT_DOMAIN =
MT_PREFER_IP =
MT_TIME_SKEW =

# -------------------- OPTIONAL ------------------
NAME =

# LOG_FILE: true | false (empty = false)
# true  = write bot.log (rotates ~1 MB)
# false = console only (recommended)
LOG_FILE =
"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        f.write(template)
    log(f"Created {SETTINGS_FILE}. Fill in IP and PORT, then restart.")
    sys.exit(0)


def settings_fingerprint(raw):
    keys = (
        "MODE", "PROXY", "TYPE", "IP", "PORT", "PROTOCOL", "TLS", "PATH", "SNI",
        "MT_DOMAIN", "MT_PREFER_IP", "MT_TIME_SKEW",
    )
    payload = "|".join(f"{k}={(raw.get(k) or '').strip().lower()}" for k in keys)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def cleanup_generated_files_if_needed(fp):
    state = load_state()
    settings_changed = state.get("fingerprint") != fp
    if settings_changed:
        log("Settings changed — full rebuild.")
        for f in (CONFIG_FILE, XRAY_CONFIG_FILE, MTPROTO_CONFIG_FILE, LINKS_FILE):
            if os.path.exists(f):
                os.remove(f)
    return state


def load_config():
    global LOG_TO_FILE
    ensure_settings_file()
    raw = parse_settings(SETTINGS_FILE)

    log_str = (raw.get("LOG_FILE") or "").strip().lower()
    if log_str:
        LOG_TO_FILE = log_str in ("1", "true", "yes", "on")
    else:
        LOG_TO_FILE = DEFAULT_LOG_FILE

    log(f"Loaded {SETTINGS_FILE} (log_file={LOG_TO_FILE})")

    ip = (raw.get("IP") or "").strip()
    port_str = (raw.get("PORT") or "").strip()
    protocol = (raw.get("PROTOCOL") or "").strip().lower()
    mode_raw = (
        (raw.get("MODE") or "")
        or (raw.get("PROXY") or "")
        or (raw.get("TYPE") or "")
    ).strip().lower()
    name = (raw.get("NAME") or "").strip()

    if not mode_raw:
        proxy_type = DEFAULT_PROXY_TYPE
    else:
        proxy_type = mode_raw

    if proxy_type in ("vless", "xray"):
        proxy_type = "vless"
    elif proxy_type in ("mtproto", "mtproxy", "telegram"):
        proxy_type = "mtproto"
    else:
        log(f"Invalid MODE: {proxy_type}. Use: vless, mtproto")
        sys.exit(1)

    if port_str:
        try:
            port = int(port_str)
        except ValueError:
            log(f"Invalid PORT: {port_str}")
            sys.exit(1)
    else:
        port = DEFAULT_PORT

    if port < 1 or port > 65535:
        log(f"Invalid PORT: {port}. Use a value from 1 to 65535")
        sys.exit(1)

    if not name:
        name = DEFAULT_NAME

    if not ip:
        log("IP not set, detecting public IP...")
        ip = get_public_ip()
        if not ip:
            log(f"Cannot detect IP. Set IP in {SETTINGS_FILE}")
            sys.exit(1)
        log(f"Detected IP: {ip}")
        write_settings_value("IP", ip)
        raw["IP"] = ip

    if proxy_type == "mtproto":
        mt_domain_raw = (raw.get("MT_DOMAIN") or "").strip()
        mt_domain = normalize_mt_domain(mt_domain_raw)
        if not mt_domain_raw:
            write_settings_value("MT_DOMAIN", mt_domain)
            raw["MT_DOMAIN"] = mt_domain

        mt_prefer_ip = (raw.get("MT_PREFER_IP") or "").strip().lower()
        if not mt_prefer_ip:
            mt_prefer_ip = DEFAULT_MT_PREFER_IP
            write_settings_value("MT_PREFER_IP", mt_prefer_ip)
            raw["MT_PREFER_IP"] = mt_prefer_ip
        if mt_prefer_ip not in MT_PREFER_IP_VALUES:
            log(
                f"Invalid MT_PREFER_IP: {mt_prefer_ip}. "
                f"Use: {', '.join(MT_PREFER_IP_VALUES)}"
            )
            sys.exit(1)

        mt_time_skew = (
            raw.get("MT_TIME_SKEW")
            or raw.get("MT_TOLERATE_TIME_SKEWNESS")
            or ""
        ).strip()
        if not mt_time_skew:
            mt_time_skew = DEFAULT_MT_TIME_SKEW
            write_settings_value("MT_TIME_SKEW", mt_time_skew)
            raw["MT_TIME_SKEW"] = mt_time_skew

        fp = settings_fingerprint(raw)
        cleanup_generated_files_if_needed(fp)

        mt_secret_raw = (raw.get("MT_SECRET") or raw.get("SECRET") or "").strip()
        if not mt_secret_raw:
            mt_secret = generate_mt_secret(mt_domain)
            log("MT_SECRET empty — generated new Fake-TLS secret.")
            write_settings_value("MT_SECRET", mt_secret)
        else:
            mt_secret = normalize_mt_secret(mt_secret_raw)
            compare_secret = "".join(mt_secret_raw.split()).lower()
            if compare_secret.startswith("0x"):
                compare_secret = compare_secret[2:]
            if mt_secret != compare_secret:
                write_settings_value("MT_SECRET", mt_secret)
            embedded_domain = get_mt_secret_domain(mt_secret)
            if embedded_domain and embedded_domain != mt_domain:
                log(
                    f"Warning: MT_SECRET was generated for {embedded_domain}, "
                    f"but MT_DOMAIN is {mt_domain}. Clear MT_SECRET to regenerate."
                )
            log("Using MT_SECRET from settings.")

        cfg = {
            "proxy_type": "mtproto",
            "server_ip": ip,
            "port": port,
            "mode": "mtproto",
            "mt_secret": mt_secret,
            "mt_secret_base64": mt_secret_to_base64(mt_secret),
            "mt_domain": mt_domain,
            "mt_prefer_ip": mt_prefer_ip,
            "mt_time_skew": mt_time_skew,
            "remark": name,
            "log_file": LOG_TO_FILE,
        }

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        with open(MTPROTO_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        log(f"Wrote {CONFIG_FILE}")
        log(f"Wrote {MTPROTO_CONFIG_FILE}")
        save_state({"fingerprint": fp, "mt_secret": mt_secret})
        return cfg

    tls_str = (raw.get("TLS") or "").strip().lower()
    uuid_val = (raw.get("UUID") or "").strip()
    path = (raw.get("PATH") or "").strip()
    sni = (raw.get("SNI") or "").strip()
    alin_str = (raw.get("ALLOW_INSECURE") or "").strip().lower()

    if not protocol:
        protocol = DEFAULT_PROTOCOL
    if protocol not in ("ws", "xhttp"):
        log(f"Invalid PROTOCOL for VLESS: {protocol}. Use: ws, xhttp")
        sys.exit(1)

    if tls_str:
        tls = tls_str in ("1", "true", "yes", "on")
    else:
        tls = DEFAULT_TLS

    if not path:
        path = "/xhttp" if protocol == "xhttp" else "/vless"
    path = "/" + path.lstrip("/")

    if not sni:
        sni = DEFAULT_SNI

    if alin_str:
        allow_insecure = alin_str in ("1", "true", "yes", "on")
    else:
        allow_insecure = False

    fp = settings_fingerprint(raw)
    cleanup_generated_files_if_needed(fp)

    if not uuid_val:
        uuid_val = str(uuid.uuid4())
        log(f"UUID empty — generated new: {uuid_val}")
        write_settings_value("UUID", uuid_val)
    else:
        log(f"Using UUID from settings: {uuid_val}")

    cfg = {
        "proxy_type": "vless",
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
        "log_file": LOG_TO_FILE,
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    log(f"Wrote {CONFIG_FILE}")
    save_state({"fingerprint": fp, "uuid": uuid_val})
    return cfg

def build_xray_config(cfg):
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
        stream["xhttpSettings"] = {"path": path, "mode": "auto"}

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
                    {"certificateFile": CERT_FILE, "keyFile": KEY_FILE}
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


def generate_link(cfg):
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


def generate_mtproto_links(cfg):
    query = urllib.parse.urlencode(
        {
            "server": cfg["server_ip"],
            "port": str(cfg["port"]),
            "secret": cfg["mt_secret"],
        }
    )
    return [
        f"tg://proxy?{query}",
        f"https://t.me/proxy?{query}",
    ]


def keep_alive(port=None, use_tls=False, ping_local=True):
    while True:
        try:
            urllib.request.urlopen("https://1.1.1.1", timeout=5)
        except Exception:
            pass
        if ping_local and port and not use_tls:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2)
            except Exception:
                pass
        time.sleep(60)


def run_xray_loop():
    while True:
        try:
            log("Starting Xray...")
            if LOG_TO_FILE:
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
            else:
                process = subprocess.Popen(
                    [f"./{XRAY_BIN}", "run", "-c", XRAY_CONFIG_FILE],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                process.wait()
            log(f"Xray exited with code {process.returncode}")
        except Exception as e:
            log(f"Xray error: {e}")

        log("Restarting in 5 seconds...")
        time.sleep(5)


def toml_quote(value):
    # TOML basic strings are compatible with JSON string escaping.
    return json.dumps(str(value), ensure_ascii=False)


def write_mtg_config(cfg):
    content = "\n".join([
        "# Generated by OptikLink Proxy Deployer. Do not edit manually.",
        f"debug = {str(bool(LOG_TO_FILE)).lower()}",
        f"secret = {toml_quote(cfg['mt_secret'])}",
        f"bind-to = {toml_quote('0.0.0.0:' + str(cfg['port']))}",
        "concurrency = 8192",
        f"prefer-ip = {toml_quote(cfg.get('mt_prefer_ip', DEFAULT_MT_PREFER_IP))}",
        "allow-fallback-on-unknown-dc = true",
        f"tolerate-time-skewness = {toml_quote(cfg.get('mt_time_skew', DEFAULT_MT_TIME_SKEW))}",
        "",
        "[network]",
        'dns = "https://1.1.1.1"',
        "",
        "[network.timeout]",
        'tcp = "10s"',
        'http = "10s"',
        'idle = "5m"',
        'handshake = "10s"',
        "",
        "[defense.anti-replay]",
        "enabled = true",
        'max-size = "1MB"',
        "",
    ])
    with open(MTG_CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"Wrote {MTG_CONFIG_FILE}")


def redact_secret(text, cfg):
    for value in (cfg.get("mt_secret"), cfg.get("mt_secret_base64")):
        if value:
            text = text.replace(value, "<secret>")
    return text


def format_mtg_log(line, cfg, skip_config=False):
    line = redact_secret(line, cfg)

    # mtg --debug prints a huge multi-line configuration JSON on startup.
    # It contains no connection/error information, so keep bot.log useful.
    if skip_config:
        return None, '"message":"configuration"' not in line
    if '"configuration":' in line:
        return None, '"message":"configuration"' not in line

    if '"logger":"allowlist.ipblocklist.firehol"' in line and '"message":"ip list was updated"' in line:
        return None, False

    try:
        item = json.loads(line)
    except Exception:
        return line, False

    level = item.get("level", "info")
    logger_name = item.get("logger", "mtg")
    message = item.get("message", "")
    client_ip = item.get("client-ip")
    stream_id = item.get("stream-id")
    error = item.get("error")

    # These debug lines are emitted for every stream direction and spam the log;
    # the matching Stream started/finished/error lines are enough for diagnostics.
    if logger_name == "proxy.domain-fronting" and not error:
        return None, False

    parts = [level]
    if logger_name:
        parts.append(logger_name)
    if message:
        parts.append(f"- {message}")
    if client_ip:
        parts.append(f"client={client_ip}")
    if stream_id:
        parts.append(f"stream={stream_id}")
    if error:
        parts.append(f"error={error}")
    return " ".join(parts), False


def run_mtg_loop(cfg):
    write_mtg_config(cfg)
    cmd = [f"./{MTG_BIN}", "run", MTG_CONFIG_FILE]

    # mtg prints per-connection and handshake errors only in debug mode.
    # Enable it when bot.log is requested; secrets are redacted before logging.
    if LOG_TO_FILE:
        log("MTProto connection/error logging enabled (mtg debug, secrets redacted).")

    while True:
        try:
            log("Starting mtg MTProto proxy...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            skip_mtg_config = False
            for line in process.stdout:
                stripped = line.strip()
                if stripped:
                    formatted, skip_mtg_config = format_mtg_log(
                        stripped, cfg, skip_mtg_config
                    )
                    if formatted:
                        log(f"[mtg] {formatted}")
            process.wait()
            log(f"mtg exited with code {process.returncode}")
        except Exception as e:
            log(f"mtg error: {e}")

        log("Restarting in 5 seconds...")
        time.sleep(5)


def main():
    log("=" * 50)
    log("OptikLink Proxy Deployer")
    log("=" * 50)

    cfg = load_config()

    if cfg.get("proxy_type") == "mtproto":
        ensure_mtg()
        log(f"Mode: MTPROTO | Port: {cfg['port']}")
        log(f"IP: {cfg['server_ip']} | Fake-TLS domain: {cfg['mt_domain']}")
        log(f"MT prefer IP: {cfg['mt_prefer_ip']}")

        links = generate_mtproto_links(cfg)
        with open(LINKS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(links) + "\n")

        log("-" * 50)
        log("MTPROTO CONNECTION LINKS:")
        for link in links:
            log(link)
        log("-" * 50)
        log(f"Saved to {LINKS_FILE}")

        threading.Thread(target=keep_alive, args=(None, False, False), daemon=True).start()
        run_mtg_loop(cfg)
        return

    ensure_xray()
    log(f"Mode: {cfg['mode'].upper()} | TLS: {cfg['tls']} | Port: {cfg['port']}")
    log(f"IP: {cfg['server_ip']} | UUID: {cfg['uuid']}")
    log(f"Path: {cfg['path']}")

    xray_cfg = build_xray_config(cfg)
    with open(XRAY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(xray_cfg, f, indent=2, ensure_ascii=False)
    log(f"Wrote {XRAY_CONFIG_FILE}")

    link = generate_link(cfg)
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        f.write(link + "\n")

    log("-" * 50)
    log("VLESS CONNECTION LINK:")
    log(link)
    log("-" * 50)
    log(f"Saved to {LINKS_FILE}")

    threading.Thread(target=keep_alive, args=(cfg["port"], cfg["tls"]), daemon=True).start()
    run_xray_loop()


if __name__ == "__main__":
    main()

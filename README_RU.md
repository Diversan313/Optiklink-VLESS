# OptikLink-VLESS

### **Language:** [English](README.md) | Русский

---

Развёртывание **VLESS** (Xray-core) или **Telegram MTProto** (mtg) прокси на серверах OptikLink.

Может работать вместе с [OptikLink KeepAlive](https://github.com/Diversan313/OptiKA) или отдельно.

---

## Настройка

Все параметры задаются в файле **`settings.txt`**:

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

Пустые поля заполняются автоматически.

### Общие

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `IP` | автоопределение | IP сервера |
| `PORT` | `6202` | Порт |
| `MODE` | `vless` | `vless` или `mtproto` |
| `NAME` | `Optiklink` | Имя в клиенте |
| `LOG_FILE` | `false` | Писать `bot.log` (ротация ~1 МБ) |

### VLESS (`MODE = vless` или пусто)

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `PROTOCOL` | `ws` | `ws` или `xhttp` |
| `TLS` | `true` | Самоподписанный сертификат |
| `UUID` | новый UUID | Пусто → генерация нового |
| `PATH` | `/vless` / `/xhttp` | Путь транспорта |
| `SNI` | `optiklink.local` | SNI для TLS |
| `ALLOW_INSECURE` | `false` | Пропуск проверки сертификата |

Рекомендуется: `PROTOCOL = ws`, `TLS = true`, `ALLOW_INSECURE = true`.

### MTProto (`MODE = mtproto`)

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `MT_SECRET` | авто | Fake-TLS секрет (пусто → генерация) |
| `MT_DOMAIN` | `www.google.com` | Хост-маскировка Fake-TLS |
| `MT_PREFER_IP` | `prefer-ipv4` | `prefer-ipv4` / `prefer-ipv6` / `only-ipv4` / `only-ipv6` |
| `MT_TIME_SKEW` | `30s` | Допустимый сдвиг времени |

При смене `MT_DOMAIN` очистите `MT_SECRET`, чтобы сгенерировался новый секрет.

---

## Запуск

```bash
python3 bot.py
```

Скрипт скачивает Xray или mtg (при необходимости), собирает конфиг и выводит ссылку(и) подключения в консоль и в `links.txt`.

---

## Файлы

| Файл | Назначение |
|------|------------|
| `settings.txt` | Настройки пользователя |
| `bot.py` | Основной скрипт |
| `links.txt` | Ссылка(и) подключения |
| `xray_config.json` | Конфиг Xray (VLESS) |
| `mtg_config.toml` | Конфиг mtg (MTProto) |
| `server.crt` / `server.key` | TLS-сертификат (VLESS) |
| `bot.log` | Опциональный лог (`LOG_FILE = true`) |

---

## Примечания

- На OptikLink обычно доступен один порт — выбирайте **один** режим (`vless` или `mtproto`).
- При смене настроек VLESS очистите `UUID`, чтобы сгенерировать новый идентификатор.
- В v2rayNG параметр `allowInsecure` из ссылки может не примениться: включите пропуск проверки сертификата вручную.
- Если `bot.log` уже разросся — удалите его и держите `LOG_FILE = false`.


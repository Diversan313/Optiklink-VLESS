# OptikLink-VLESS

### **Language:** [English](README.md) | Русский

---

Развёртывание VLESS (Xray-core) на серверах OptikLink.

Может работать вместе с [OptikLink KeepAlive](https://github.com/Diversan313/OptiKA) или отдельно.

---

## Настройка

Все параметры задаются в файле **`settings.txt`**:

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
LOG_FILE =
```

Пустые поля заполняются автоматически.

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `IP` | автоопределение | IP сервера |
| `PORT` | `6202` | Порт |
| `PROTOCOL` | `ws` | `ws` или `xhttp` |
| `TLS` | `true` | TLS (самоподписанный сертификат) |
| `UUID` | новый UUID | Пустое значение — генерация нового |
| `PATH` | `/vless` / `/xhttp` | Путь транспорта |
| `SNI` | `optiklink.local` | SNI для TLS |
| `NAME` | `Optiklink` | Имя в клиенте |
| `ALLOW_INSECURE` | `false` | Пропуск проверки сертификата на клиенте |
| `LOG_FILE` | `false` | Писать `bot.log` (ротация ~1 МБ). На слабых дисках оставляйте `false` |

Рекомендуемый старт: `PROTOCOL = ws`, `TLS = true`, `ALLOW_INSECURE = true`, `LOG_FILE = false`.

---

## Запуск

```bash
python3 bot.py
```

Скрипт скачивает Xray (при необходимости), создаёт сертификат, собирает конфиг и выводит ссылку подключения в консоль и в `links.txt`.

---

## Файлы

| Файл | Назначение |
|------|------------|
| `settings.txt` | Настройки пользователя |
| `bot.py` | Основной скрипт |
| `links.txt` | VLESS-ссылка |
| `xray_config.json` | Конфиг Xray |
| `server.crt` / `server.key` | TLS-сертификат |
| `bot.log` | Опциональный лог (только если `LOG_FILE = true`) |

---

## Примечания

- На OptikLink обычно доступен один порт — выбирайте один протокол.
- При смене настроек очистите `UUID`, чтобы сгенерировать новый идентификатор.
- В v2rayNG параметр `allowInsecure` из ссылки может не примениться: включите пропуск проверки сертификата вручную в профиле.
- Если `bot.log` уже разросся — удалите его и держите `LOG_FILE = false` (или пустым).

# AWG Panel 7.1 Complete

Полный установщик для Ubuntu/Debian: AmneziaWG + AWG 3.1 + AWG Panel.

## Возможности
- Dashboard и статус AWG
- управление клиентами
- генерация native `.conf` и QR
- профиль Strong Mobile
- HeaderProtectionKey
- RandomTrailers и DisableCookies
- обфускация AmneziaWG 3.1
- логи и отдельная страница «О панели»
- мобильная адаптация
- чистый фон без задвоения интерфейса
- резервные копии
- сохранение существующей `panel.db`
- проверка запуска AWG после установки

## Установка

```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel
chmod +x install.sh
sudo ./install.sh
```

Панель запускается на `http://SERVER_IP:8080/login`.

По умолчанию:
- логин: `admin`
- пароль: `change-me`

Сразу смените пароль в настройках.

## Strong Mobile

Установщик применяет рабочий профиль:

- ListenPort: `1234/UDP`
- MTU: `1380`
- Jc: `4`
- Jmin/Jmax: `40/120`
- S1-S4: `16/24/16/32`
- H1-H4: `1/2/3/4`
- ContentPaddingAddition: `0-64`
- RandomTrailers: `on`
- DisableCookies: `on`
- RekeyAfterTime: `120-180`
- RekeyTimeout: `3-8`
- RejectAfterTime: `150-210`
- KeepaliveTimeout: `8-15`
- MaxHandshakeAttempts: `8-15`

`amneziawg-proxy` не используется, так как он несовместим с AWG 3.x.

## Структура

- `install.sh` — полный установщик AWG 3.1 + панели
- `app.py` — Flask web panel
- `background.svg` — чистый фон панели без элементов интерфейса

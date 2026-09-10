# AWG Panel 9.0 — AWG 3.1 + NaïveProxy + Telegram

Web-панель для AmneziaWG 3.1 с NaïveProxy, Telegram-ботом, мониторингом, диагностикой и резервным копированием.

## Поддерживаемые ОС

`install-universal.sh` ориентирован на Ubuntu 22.04/24.04 LTS x86_64 и Debian 12/13 x86_64. Для VPS рекомендуется KVM; LXC/OpenVZ установщик отклоняет.

## Установка

```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel
chmod +x install-v9.sh
sudo ./install-v9.sh
```

После установки панель доступна по адресу `http://SERVER_IP:8080/login`. Для обновления существующей установки используется `upgrade-panel9.sh`; перед заменой файлов создаётся резервная копия.

## Возможности

- AWG Panel **9.0**;
- AmneziaWG **3.1**;
- клиенты: `.conf`, QR и `vpn://`;
- профиль Strong Mobile;
- Dashboard Pro с RAM/DISK/сетевой статистикой и CPU;
- диагностика AWG, systemd, forwarding, firewall и HTTP;
- резервное копирование конфигурации и базы;
- мобильная адаптация;
- фон без задвоения;
- NaïveProxy через Caddy/forward_proxy;
- автоматический TLS через Caddy ACME;
- Telegram Bot со списком разрешённых Telegram ID;
- Windows x64 приложение;
- Android APK;
- исходник iOS/Xcode проекта.

## Strong Mobile

Канонический профиль панели:

- UDP `443`
- MTU `1280`
- Jc/Jmin/Jmax `4/40/120`
- S1-S4 `16/24/16/32`
- H1-H4 `1/2/3/4`
- RandomTrailers `on`
- DisableCookies `on`
- существующий `HeaderProtectionKey` сохраняется.

## Диагностика

```bash
cd /root/awg31-panel
git pull --ff-only origin main
chmod +x diagnostics.sh repair-awg-mobile.sh
./diagnostics.sh
```

Для восстановления Strong Mobile:

```bash
./repair-awg-mobile.sh
```

## NaïveProxy

Откройте **NaïveProxy** в левом меню. Укажите домен, email, логин, пароль и TCP-порт. Домен должен указывать на VPS, а TCP-порт должен быть свободен. AWG UDP/443 и NaïveProxy TCP/443 могут работать одновременно.

После установки доступен `naive-config.json` с клиентским форматом:

```json
{
  "listen": "socks://127.0.0.1:1080",
  "proxy": "https://USER:PASSWORD@DOMAIN:443"
}
```

## Telegram Bot

Создайте бота через официального `@BotFather`, получите токен и Telegram ID. В панели откройте **Telegram Bot**, укажите token и разрешённые ID через запятую.

Команды: `/start`, `/help`, `/status`, `/restart`.

Токен хранится отдельно от веб-кода с ограниченными правами доступа.

## Безопасность

При установке создаётся случайный секрет `AWGPANEL_SECRET`, сохраняемый в `/etc/awg31-panel/panel-secret` с правами `600`. Существующие данные панели и пароль администратора не должны заменяться обычным обновлением.

## CI

GitHub Actions проверяет Python-синтаксис/импорты и собирает Android APK и Windows x64 приложение.

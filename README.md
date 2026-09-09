# AWG Panel 8.1 — AWG 3.1 + NaïveProxy + Telegram

Web-панель для AmneziaWG 3.1 с NaïveProxy, Telegram-ботом, мониторингом и резервным копированием.

## Поддерживаемые ОС

Универсальный установщик `install-universal.sh` официально ориентирован на:
- Ubuntu 22.04 LTS x86_64;
- Ubuntu 24.04 LTS x86_64;
- Debian 12 x86_64;
- Debian 13 x86_64.

Именно Ubuntu 22.04/24.04 и Debian 12/13 указаны Amnezia как официально поддерживаемые ОС для VPS. Для AmneziaWG 3.x важна версия работающего ядра; на x86_64 с современным ядром устанавливается соответствующая версия модуля из PPA Amnezia.

LXC/OpenVZ и другие контейнерные VPS установщик отклоняет — используйте KVM.

## Установка

### Универсальный вариант — рекомендуется

```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel
chmod +x install-universal.sh
sudo ./install-universal.sh
```

Установщик автоматически определяет Ubuntu/Debian, проверяет архитектуру и виртуализацию, устанавливает зависимости и AmneziaWG, после чего запускает основной установщик панели.

### Ubuntu 24.04

```bash
chmod +x install.sh
sudo ./install.sh
```

`install.sh` остаётся прямым установщиком для Ubuntu. Для Debian используйте `install-universal.sh`.

Панель: `http://SERVER_IP:8080/login`

Установщик перед изменениями делает резервные копии `app.py`, базы и AWG-конфигурации. При новой установке создаётся случайный пароль администратора; при обновлении существующий пароль сохраняется.

## Возможности
- единая версия панели **8.1**;
- безопасный случайный пароль при новой установке;
- существующий `panel.db` и пароль сохраняются при обновлении;
- резервные копии перед обновлением;
- клиенты AWG: `.conf`, QR и `vpn://`;
- единый Strong Mobile профиль AWG 3.1 для сервера и клиентских конфигураций;
- Dashboard Pro с трафиком клиентов;
- системный мониторинг и диагностика;
- резервное копирование конфигурации и базы данных;
- диагностика сервиса, интерфейса, forwarding и firewall;
- мобильная адаптация;
- чистый футуристичный фон без задвоения;
- **NaïveProxy через Caddy/forward_proxy**: установка, запуск, остановка, перезапуск и удаление сервиса;
- автоматический TLS через Caddy ACME;
- пользователь и пароль NaïveProxy;
- готовый `naive-config.json`;
- **Telegram Bot**: статус AWG/NaïveProxy, количество peers, перезапуск AWG и inline-кнопки;
- Telegram-доступ ограничивается списком разрешённых Telegram ID;
- токен бота хранится отдельно в `/etc/awg31-panel/telegram.env` с правами `600`.

## Canonical Strong Mobile

Установщик и `repair-awg-mobile.sh` приводят сервер к одному профилю:
- UDP `443`
- MTU `1280`
- Jc/Jmin/Jmax `4/40/120`
- S1-S4 `16/24/16/32`
- H1-H4 `1/2/3/4`
- RandomTrailers `on`
- DisableCookies `on`
- существующий `HeaderProtectionKey` сохраняется;
- клиентские конфигурации панели получают те же AWG 3.1 параметры из серверного профиля.

`awg-quick strip awg0` выполняется до запуска systemd, поэтому синтаксическая ошибка конфигурации не должна приводить к запуску сломанного интерфейса.

## Диагностика

```bash
cd /root/awg31-panel
git pull --ff-only origin main
chmod +x diagnostics.sh repair-awg-mobile.sh
./diagnostics.sh
```

Если на существующем VPS нужно только привести AWG к мобильному профилю:

```bash
./repair-awg-mobile.sh
```

Диагностика проверяет версию tools/kernel module, systemd, `awg0`, UAPI, HTTP панели, forwarding, конфигурацию AWG, UDP 443, NAT и Python-модули.

## Telegram Bot

Создайте бота через официального `@BotFather`, получите Bot Token и узнайте свой Telegram ID. В панели откройте **Telegram Bot**, укажите token и один или несколько разрешённых ID через запятую, затем нажмите **Сохранить и запустить**.

Бот использует Telegram Bot API через HTTPS и long polling (`getUpdates`). Long polling и webhook являются взаимоисключающими способами получения обновлений.

Команды:
- `/start` — меню;
- `/help` — помощь;
- `/status` — статус AWG, NaïveProxy и peers;
- `/restart` — перезапуск AWG.

## NaïveProxy

После установки панели откройте **NaïveProxy** в левом меню. Укажите домен, email для ACME/TLS, логин, пароль и TCP-порт.

AWG использует UDP 443, поэтому NaïveProxy может использовать TCP 443 одновременно на том же IP: TCP и UDP — разные протоколы.

Клиентский формат:

```json
{
  "listen": "socks://127.0.0.1:1080",
  "proxy": "https://USER:PASSWORD@DOMAIN:443"
}
```

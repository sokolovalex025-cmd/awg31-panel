# AWG Panel 7.3 — AWG 3.1 + NaïveProxy + Telegram

Web-панель для AmneziaWG 3.1 на Ubuntu 24.04 с NaïveProxy и Telegram-ботом.

## Возможности
- безопасный случайный пароль при новой установке;
- существующий `panel.db` и пароль сохраняются при обновлении;
- резервные копии перед обновлением;
- клиенты AWG: `.conf`, QR и `vpn://`;
- Strong Mobile профиль AWG 3.1;
- диагностика сервиса, интерфейса, forwarding и firewall tools;
- мобильная адаптация;
- чистый футуристичный фон без задвоения;
- **NaïveProxy через Caddy/forward_proxy**: установка, запуск, остановка, перезапуск и удаление сервиса;
- автоматический TLS через Caddy ACME;
- пользователь и пароль NaïveProxy;
- готовый `naive-config.json`;
- **Telegram Bot**: статус AWG/NaïveProxy, количество peers, перезапуск AWG и inline-кнопки;
- Telegram-доступ ограничивается списком разрешённых Telegram ID;
- токен бота хранится отдельно в `/etc/awg31-panel/telegram.env` с правами `600`.

## Установка
```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel
chmod +x install.sh
sudo ./install.sh
```

Панель: `http://SERVER_IP:8080/login`

При новой установке установщик выводит случайный пароль администратора и сохраняет его в `/opt/awg31-panel/.initial_password`. При обновлении существующий пароль не меняется.

## Telegram Bot
Создайте бота через официального `@BotFather`, получите Bot Token и узнайте свой Telegram ID. В панели откройте **Telegram Bot**, укажите token и один или несколько разрешённых ID через запятую, затем нажмите **Сохранить и запустить**.

Бот использует Telegram Bot API через HTTPS и long polling (`getUpdates`). Telegram указывает, что long polling и webhook являются взаимоисключающими способами получения обновлений. citeturn0search0

Команды:
- `/start` — меню;
- `/help` — помощь;
- `/status` — статус AWG, NaïveProxy и peers;
- `/restart` — перезапуск AWG.

Кнопки:
- 📊 Статус;
- 👥 Клиенты/peers;
- 🛡 AWG;
- 🚀 NaïveProxy;
- 🔄 Перезапустить AWG.

Для создания бота Telegram рекомендует использовать `@BotFather`; токен необходимо хранить в секрете. citeturn0search3

## NaïveProxy
После установки панели откройте **NaïveProxy** в левом меню. Укажите домен, email для ACME/TLS, логин, пароль и TCP-порт, обычно `443`.

Панель собирает Caddy с NaïveProxy `forward_proxy`, создаёт systemd-сервис и конфигурацию. AWG UDP и NaïveProxy TCP могут работать параллельно.

Клиентский формат:
```json
{
  "listen": "socks://127.0.0.1:1080",
  "proxy": "https://USER:PASSWORD@DOMAIN:443"
}
```

## Strong Mobile
- UDP `1234`
- MTU `1380`
- Jc/Jmin/Jmax `4/40/120`
- S1-S4 `16/24/16/32`
- H1-H4 `1/2/3/4`
- ContentPaddingAddition `0-64`
- RandomTrailers `on`
- DisableCookies `on`
- Rekey/handshake timing оптимизированы для мобильных сетей.

# AWG Panel 7.2 — AWG 3.1 + NaïveProxy

Web-панель для AmneziaWG 3.1 на Ubuntu 24.04 с отдельным модулем NaïveProxy.

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
- готовый `naive-config.json` для клиента.

## Установка
```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel
chmod +x install.sh
sudo ./install.sh
```

Панель: `http://SERVER_IP:8080/login`

При новой установке установщик выводит случайный пароль администратора и сохраняет его в `/opt/awg31-panel/.initial_password`. При обновлении существующий пароль не меняется.

## NaïveProxy
После установки панели откройте **NaïveProxy** в левом меню. Укажите:
1. домен, направленный DNS A/AAAA на VPS;
2. email для ACME/TLS;
3. логин;
4. пароль;
5. TCP-порт, обычно `443`.

Панель сама собирает Caddy с NaïveProxy `forward_proxy`, создаёт systemd-сервис и конфигурацию. Для TLS/ACME убедитесь, что нужные TCP-порты доступны. AWG UDP и NaïveProxy TCP могут работать параллельно.

Клиентский формат NaïveProxy:
```json
{
  "listen": "socks://127.0.0.1:1080",
  "proxy": "https://USER:PASSWORD@DOMAIN:443"
}
```

Модуль основан на Caddy `forwardproxy` и ветке `naive` NaïveProxy. Программное обеспечение является сторонним проектом; проверяйте актуальные релизы и ограничения перед эксплуатацией.

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

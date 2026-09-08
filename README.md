# AWG Panel 7.1 Stable — Mobile Strong

Web-панель для AmneziaWG 3.1 на Ubuntu 24.04.

## Улучшения 7.1
- безопасный случайный пароль при новой установке;
- существующий `panel.db` и пароль сохраняются при обновлении;
- резервные копии перед обновлением;
- rollback конфигурации при неудачном запуске AWG;
- клиенты: `.conf`, QR и `vpn://`;
- мониторинг handshake и RX/TX;
- Strong Mobile профиль AWG 3.1;
- диагностика сервиса, интерфейса, forwarding и firewall tools;
- мобильная адаптация;
- исправленный фон без задвоения.

## Установка
```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel
chmod +x install.sh
sudo ./install.sh
```

Панель: `http://SERVER_IP:8080/login`

При новой установке установщик выводит случайный пароль администратора и сохраняет его в `/opt/awg31-panel/.initial_password`. При обновлении существующий пароль не меняется.

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

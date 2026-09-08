# AWG Panel 6.7.2 — Mobile Strong

Web-панель для AmneziaWG 3.1 на Ubuntu 24.04.

## Возможности
- Dashboard и статус AWG
- управление клиентами
- генерация CONF / QR / vpn://
- профиль Strong Mobile
- обфускация AmneziaWG 3.1
- логи и информация о панели
- мобильная адаптация
- фон без задвоения

## Установка
```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel
chmod +x install.sh
sudo ./install.sh
```

Панель запускается на `http://SERVER_IP:8080`.

Установка сохраняет существующие `panel.db` и `awg0.conf` и создаёт резервные копии.

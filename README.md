# NOVA Network Control Center

Профессиональная web-панель управления сетевым шлюзом: AmneziaWG 3.1, NaïveProxy, Telegram, мониторинг, диагностика, безопасность и резервное копирование.

**Brand:** NOVA Network Control Center

## Возможности

- NOVA Dashboard и Live Traffic;
- управление клиентами AWG 3.1;
- профиль Strong Mobile;
- **AWG Cluster Balancer** — распределение новых клиентов между несколькими VPS;
- health-check, latency, weighted least-load и автоматический failover для новых выдач;
- Security Center и журнал аудита;
- Firewall Center;
- диагностика AWG, systemd, сети и HTTP;
- резервные копии и безопасное обновление;
- NaïveProxy через Caddy с автоматическим TLS;
- Telegram Bot;
- Android APK, Windows x64 и исходник iOS;
- адаптивный интерфейс с мобильным выезжающим меню.

## Балансировка AWG 3.1

Балансировщик работает на уровне **выдачи клиентских конфигураций**, а не путём переноса существующего UDP-сеанса между VPS. Поэтому активная сессия клиента не разрывается из-за перераспределения.

Схема:

```text
NOVA Panel
    |
    +-- NL-01  (AWG 3.1)
    +-- NL-02  (AWG 3.1)
    +-- DE-01  (AWG 3.1)
```

Для каждого узла используется NOVA node agent на TCP `9090`. Health API необходимо ограничить firewall-правилом только по IP управляющей панели.

### Включение на управляющей панели

```bash
cd /root/awg31-panel
git pull --ff-only origin main
chmod +x install-balancer.sh
sudo ./install-balancer.sh
```

После этого в NOVA появится раздел **Балансировка**.

### Установка node agent на текущем VPS

```bash
chmod +x install-local-balancer-node.sh
sudo ./install-local-balancer-node.sh
```

### Установка node agent на дополнительном VPS

Склонируй репозиторий или скачай скрипт и передай тот же секрет, который создал `install-balancer.sh` на управляющей панели:

```bash
chmod +x install-balancer-node.sh
sudo ./install-balancer-node.sh 'BALANCER_TOKEN_ОТ_ПАНЕЛИ'
```

После установки добавь VPS через **Панель → Балансировка → Добавить сервер**. Вес `100` — стандартная ёмкость; более мощному VPS можно дать больший вес.

> Важно: TCP `9090` не должен быть открыт для всего интернета. Разреши его только с IP управляющей панели.

## AmneziaWG 3.1 Strong Mobile

Производственный UDP-порт панели: **1234**.

Профиль сохраняет:

- UDP `1234`
- MTU `1280`
- Jc/Jmin/Jmax `4/40/120`
- S1-S4 `16/24/16/32`
- H1-H4 `1/2/3/4`
- RandomTrailers `on`
- DisableCookies `on`
- существующий HeaderProtectionKey

Обновление NOVA не должно менять ключи, peer-конфигурации или производственный UDP-порт.

## Установка

```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel
chmod +x install-v9.sh
sudo ./install-v9.sh
```

После установки панель доступна на `http://SERVER_IP:8080/login`.

Для обновления:

```bash
cd /root/awg31-panel
git pull --ff-only origin main
chmod +x upgrade-panel9.sh
sudo ./upgrade-panel9.sh
```

Перед заменой файлов updater создаёт резервные копии.

## Security

NOVA использует случайный `AWGPANEL_SECRET`, безопасные параметры session cookie, ограничение попыток входа, аудит авторизации и security HTTP headers. Балансировщик использует отдельный секрет для node API.

## Клиенты

Для каждого клиента доступны конфигурация `.conf` и QR-код. Клиентские ключи хранятся на сервере и не должны попадать в Git.

## Проект

Репозиторий исторически называется `awg31-panel`; пользовательский бренд проекта — **NOVA Network Control Center**.

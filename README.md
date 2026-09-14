# NOVA 11 Network Control Center

Профессиональная web-панель управления **AmneziaWG 3.1** с command-center интерфейсом NOVA 11.

## Возможности

- NOVA 11 Dashboard и Live Traffic;
- управление клиентами AWG 3.1 и QR/.conf профилями;
- Strong Mobile и мобильная диагностика;
- **NOVA Doctor**: проверка AWG, NAT, forwarding, firewall, DNS и сервисов;
- безопасное **«Исправить всё»** с предварительным backup;
- NOVA Shield / Resilience;
- автоматический watchdog для AWG, панели и nginx;
- резервные копии;
- **AWG Cluster Balancer** для новых клиентских выдач между VPS;
- Keenetic AWG bridge и routing toolkit;
- Telegram Bot для выдачи и продления VPN-профилей;
- NaïveProxy / Caddy integration;
- Android, Windows и iOS исходники;
- адаптивный интерфейс для ПК и мобильных устройств.

## Установка

Рекомендуется Ubuntu 24.04 LTS + AmneziaWG 3.1. Сначала убедитесь, что команда `awg` доступна.

```bash
curl -fsSL https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/install-nova11.sh -o /root/install-nova11.sh
chmod +x /root/install-nova11.sh
/root/install-nova11.sh
```

Для уже установленной NOVA:

```bash
cd /root/awg31-panel
git fetch origin main
git reset --hard origin/main
chmod +x update-panel.sh
./update-panel.sh
```

Updater устанавливает зависимости, синхронизирует файлы, выполняет проверку Python/shell, применяет согласованный профиль AWG 3.1 с backup/rollback, включает watchdog и запускает полный `nova-verify.sh`.

## AWG 3.1

`nova_awg31_fix.py` приводит интерфейс `awg0` к согласованному профилю и сохраняет существующие `ListenPort` и `MTU`. При отсутствии `HeaderProtectionKey` создаётся новый секрет. Секрет никогда не выводится в лог.

Профиль NOVA:

- Jc/Jmin/Jmax: `4/40/120`
- S1-S4: `16/16/16/16`
- H1-H4: `1/2/3/4`
- ContentPaddingAddition: `0-64`
- RandomTrailers: `on`
- DisableCookies: `on`
- RekeyAfterTime: `120-180`
- RekeyTimeout: `3-8`
- RejectAfterTime: `150-210`
- KeepaliveTimeout: `8-15`
- MaxHandshakeAttempts: `8-15`

После миграции клиенты должны получить свежие конфигурации, соответствующие серверному профилю.

## NOVA Doctor

Открыть `/doctor`.

Проверяются:

- команда и сервис AmneziaWG;
- `awg0`;
- panel/nginx;
- IPv4 forwarding;
- WAN route;
- NAT и FORWARD;
- HeaderProtectionKey;
- DNS.

Кнопка **«Исправить всё»** сначала создаёт backup, затем применяет сетевой fix и AWG 3.1 guard, перезапускает необходимые сервисы и выполняет повторную диагностику.

## Watchdog

`nova-watchdog.timer` запускает проверку раз в минуту. Он перезапускает только неработающие сервисы и использует AWG 3.1 guard только если `awg0` не читается.

## Балансировка

Балансировщик распределяет **новые выдачи**, а не переносит существующие UDP-сеансы. Node API должен быть доступен только управляющей панели. Для подключения VPS используется `/balancer/provision`; SSH-ключ остаётся на основной панели.

## Telegram

Telegram credentials хранятся на VPS и не должны попадать в Git. Бот поддерживает выдачу, просмотр и продление AWG-профилей.

## Безопасность

- `AWGPANEL_SECRET` хранится вне Git с правами `600`;
- приватные ключи клиентов не должны попадать в Git;
- backup API не экспортирует приватный AWG key;
- balancer node защищён bearer-токеном;
- порт node API следует разрешать firewall только с IP основной панели;
- для публичной панели рекомендуется HTTPS через доменный менеджер.

## Основные файлы

```text
app.py                    ядро web-панели
nova11.py                 NOVA 11 UI/runtime
panel_bootstrap.py        SQLite + запуск NOVA 11
nova_awg31_fix.py         AWG 3.1 migration/guard
nova_mobile_diagnostics.py мобильная диагностика
nova_resilience.py        Doctor + resilience + backups
nova_shield.py            connectivity health
nova-watchdog.sh          автоматическое восстановление сервисов
nova-watchdog.service     watchdog service
nova-watchdog.timer       запуск watchdog раз в минуту
balancer.py               AWG cluster balancer
balancer-node.py          node agent
balancer_provision.py     SSH provisioning
telegram_bot.py           Telegram Bot
keenetic.py               Keenetic toolkit
nova-network-fix.sh       NAT/forwarding/firewall fix
nova-verify.sh            production verification
update-panel.sh           one-command updater
```

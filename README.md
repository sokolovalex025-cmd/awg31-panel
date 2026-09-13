# NOVA Network Control Center

Профессиональная web-панель управления сетевым шлюзом **AmneziaWG 3.1** с единым интерфейсом NOVA.

## Что входит

- NOVA Dashboard и Live Traffic;
- управление клиентами AWG 3.1;
- профиль **Strong Mobile**;
- диагностика AWG, сети, UDP и handshake;
- Firewall / Network инструменты;
- резервное копирование и безопасное обновление;
- **AWG Cluster Balancer** для распределения новых выдач между VPS;
- **Keenetic AWG bridge** и routing toolkit;
- VPS route feed для Keenetic;
- **Telegram Bot** для выдачи и продления VPN-профилей;
- NaïveProxy / Caddy integration;
- Android, Windows и iOS исходники;
- адаптивный интерфейс для ПК и мобильных устройств.

## Производственный AWG 3.1

Основной интерфейс `awg0` остаётся отдельным от Keenetic bridge.

- UDP: `1234`
- MTU: `1280`
- Jc/Jmin/Jmax: `4/40/120`
- S1-S4: `16/24/16/32`
- H1-H4: `1/2/3/4`
- RandomTrailers: `on`
- DisableCookies: `on`

Обновление NOVA сохраняет существующие peer-конфигурации и ключи.

## Обновление существующей панели

```bash
cd /root/awg31-panel
git pull --ff-only origin main
chmod +x nova-update-all.sh upgrade-panel9.sh keenetic-awg2.sh
sudo ./nova-update-all.sh
```

`upgrade-panel9.sh` сначала валидирует Python-модули, создаёт резервные копии и только после успешной проверки заменяет рабочие файлы. При ошибке выполняется rollback.

## Балансировка AWG

Балансировщик распределяет **новые клиентские выдачи**, а не переносит активные UDP-сеансы.

Для установки управляющей панели:

```bash
chmod +x install-balancer.sh
sudo ./install-balancer.sh
```

Для node agent на текущем VPS:

```bash
chmod +x install-local-balancer-node.sh
sudo ./install-local-balancer-node.sh
```

Для дополнительного VPS:

```bash
chmod +x install-balancer-node.sh
sudo ./install-balancer-node.sh 'BALANCER_TOKEN'
```

TCP `9090` node API должен быть закрыт от общего интернета и разрешён только управляющей панели.

## Keenetic

В панели доступен раздел **Настроить Keenetic**. Он содержит:

- отдельный AWG bridge `awg-keenetic`;
- конфигурацию клиента;
- диагностику data-plane;
- routing guide;
- VPS route feed;
- автоматический route updater для Entware/KeeneticOS.

Установка автоматического обновления маршрутов выполняется отдельным скриптом `install-keenetic-route-updater.sh` после указания URL NOVA-панели и Connection Policy.

## Telegram

`install-telegram-full-v2.sh` устанавливает Telegram Bot для выдачи, просмотра и продления AWG-профилей. Секреты Telegram хранятся только на VPS и не должны попадать в Git.

## Безопасность

- `AWGPANEL_SECRET` создаётся случайно и хранится вне репозитория;
- Telegram credentials хранятся в `/etc/awg31-panel/telegram.env`;
- клиентские приватные ключи не должны храниться в Git;
- node API балансировщика должен быть ограничен firewall;
- производственный `awg0` и Keenetic bridge используют отдельные интерфейсы.

## Структура

```text
app.py                    ядро web-панели
app9.py                   NOVA UI и расширения
keenetic.py               Keenetic toolkit
balancer.py               AWG cluster balancer
balancer-node.py          node agent
telegram_bot.py           Telegram Bot
telegram_payments.py      Telegram payment integration
naiveproxy_panel.py       NaïveProxy integration
security_hardening.py     security helpers
system_panel.py           VPS/system monitoring
mobile_nav.py             mobile navigation helpers
upgrade-panel9.sh         безопасное обновление панели
nova-update-all.sh        единое обновление NOVA
keenetic-awg2.sh          установка отдельного Keenetic bridge
keenetic-route-updater.sh route updater
install-keenetic-route-updater.sh updater installer
```

Исторические repair/patch/legacy installer скрипты удалены из репозитория, чтобы основной проект оставался компактным и обслуживаемым.

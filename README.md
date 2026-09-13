# NOVA 11 Network Control Center

Профессиональная web-панель управления **AmneziaWG 3.1** с единым command-center интерфейсом NOVA 11.

## NOVA 11

Новая UI-система построена вокруг тёмного command-center дизайна: стеклянная навигация, спокойная surface-шкала, чёткая типографика, компактные KPI, адаптивность и отдельные состояния для ошибок/диагностики. Keenetic является штатным пунктом меню, а не HTML-патчем.

- NOVA 11 Dashboard и Live Traffic;
- управление клиентами AWG 3.1;
- профиль Strong Mobile;
- диагностика AWG, сети, UDP и handshake;
- Firewall / Network инструменты;
- резервное копирование;
- **AWG Cluster Balancer** для распределения новых выдач между VPS;
- **Keenetic AWG bridge** и routing toolkit;
- VPS route feed для Keenetic;
- **Telegram Bot** для выдачи и продления VPN-профилей;
- NaïveProxy / Caddy integration;
- Android, Windows и iOS исходники;
- адаптивный интерфейс для ПК и мобильных устройств.

## Чистая установка на новый VPS

Рекомендуемый порядок: Ubuntu 24.04 LTS → AmneziaWG 3.1 → NOVA 11.

Сначала установите AmneziaWG 3.1 и убедитесь, что команда `awg` доступна. После этого:

```bash
curl -fsSL https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/install-nova11.sh -o /root/install-nova11.sh
chmod +x /root/install-nova11.sh
/root/install-nova11.sh
```

Установщик:

- клонирует актуальный `main`;
- создаёт Python venv;
- устанавливает Flask и QR-зависимости;
- создаёт базу панели при первом запуске;
- создаёт отдельный `AWGPANEL_SECRET`;
- запускает `awgpanel` через `panel_bootstrap.py → nova11.py`;
- **не перезаписывает `/etc/amnezia/amneziawg/awg0.conf`**;
- не переустанавливает Keenetic bridge автоматически.

После установки откройте панель на `:8080`.

## Производственный AWG 3.1

Основной интерфейс `awg0` остаётся отдельным от Keenetic bridge.

- UDP: `1234`
- MTU: `1280`
- Jc/Jmin/Jmax: `4/40/120`
- S1-S4: `16/24/16/32`
- H1-H4: `1/2/3/4`
- RandomTrailers: `on`
- DisableCookies: `on`

Обновление NOVA не должно менять существующие peer-конфигурации и ключи без явного действия администратора.

## Обновление существующей панели

Для уже работающей установки сохраняется старый updater для совместимости, но новые чистые установки используют NOVA 11 runtime:

```bash
cd /root/awg31-panel
git pull --ff-only origin main
chmod +x install-nova11.sh
sudo ./install-nova11.sh
```

## Keenetic

В NOVA 11 **🛜 Настроить Keenetic** является штатным пунктом навигации. Дополнительно доступна плавающая кнопка Keenetic.

Раздел содержит:

- отдельный AWG bridge `awg-keenetic`;
- конфигурацию клиента;
- диагностику data-plane;
- routing guide;
- VPS route feed;
- route updater для Entware/KeeneticOS.

## Балансировка AWG

Балансировщик распределяет **новые клиентские выдачи**, а не переносит активные UDP-сеансы.

```bash
chmod +x install-balancer.sh
sudo ./install-balancer.sh
```

Node API должен быть закрыт от общего интернета и разрешён только управляющей панели.

## Telegram

`install-telegram-full-v2.sh` устанавливает Telegram Bot для выдачи, просмотра и продления AWG-профилей. Секреты Telegram хранятся только на VPS и не должны попадать в Git.

## Безопасность

- `AWGPANEL_SECRET` создаётся случайно и хранится вне репозитория;
- Telegram credentials хранятся на VPS;
- клиентские приватные ключи не должны попадать в Git;
- node API балансировщика должен быть ограничен firewall;
- производственный `awg0` и Keenetic bridge используют отдельные интерфейсы.

## Основные файлы

```text
app.py                    ядро web-панели
nova11.py                 NOVA 11 UI/runtime
panel_bootstrap.py        чистая инициализация SQLite + запуск NOVA 11
app9.py                   предыдущий совместимый runtime
keenetic.py               Keenetic toolkit
balancer.py               AWG cluster balancer
balancer-node.py          node agent
telegram_bot.py           Telegram Bot
upgrade-panel9.sh         legacy-safe updater
nova-update-all.sh        единое обновление существующей установки
install-nova11.sh         чистая установка NOVA 11
keenetic-awg2.sh          отдельный Keenetic bridge
keenetic-route-updater.sh route updater
```

Исторические repair/patch/legacy installer скрипты удалены из основного workflow, чтобы проект оставался компактным и обслуживаемым.

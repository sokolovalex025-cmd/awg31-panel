# AWG Panel Android

Android-версия AWG Panel — мобильная оболочка над существующей web-панелью.

Она не является VPN-клиентом: приложение управляет уже установленной на VPS панелью AWG Panel.

## Возможности

- WebView с мобильным интерфейсом панели;
- сохранение адреса VPS;
- кнопки Назад / Вперёд / Обновить;
- поддержка JavaScript и авторизации панели;
- поддержка ссылок `target="_blank"`, в том числе QR;
- HTTPS и текущий HTTP-порт панели `:8080`;
- APK собирается GitHub Actions.

## Сборка

После push GitHub Actions создаёт debug APK как artifact `AWG-Panel-debug`.

Для локальной сборки нужен Android SDK, JDK 17 и Gradle 8.9.

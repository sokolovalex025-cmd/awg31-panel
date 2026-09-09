# AWG Panel iOS

Готовый Xcode-проект для iPhone/iPad. Приложение открывает AWG Panel через WKWebView, хранит адрес панели и поддерживает HTTP/HTTPS.

## TestFlight

1. На Mac открой `ios/AWGPanel.xcodeproj` в Xcode 26 или новее.
2. В Signing & Capabilities выбери свой Apple Developer Team и при необходимости измени Bundle Identifier.
3. В App Store Connect создай запись приложения `AWG Panel` с тем же Bundle ID.
4. В Xcode: Product → Archive → Distribute App → App Store Connect → Upload.
5. После обработки сборки Apple включи её в TestFlight и пригласи себя как тестировщика.

Apple указывает, что перед первой загрузкой необходимо создать app record в App Store Connect. Для загрузки через Xcode используются поддерживаемые версии Xcode; в 2026 году для iOS-загрузок требуется актуальный SDK по требованиям App Store Connect.

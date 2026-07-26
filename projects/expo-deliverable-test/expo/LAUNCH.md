# Mobile — запуск в Expo Go

## Что нужно

1. **Компьютер** с Node.js **20+** ([скачать](https://nodejs.org))
2. **Телефон** с приложением **Expo Go**:
   - [iOS — App Store](https://apps.apple.com/app/expo-go/id982107779)
   - [Android — Google Play](https://play.google.com/store/apps/details?id=host.exp.exponent)

## Шаги

```bash
# в папке с package.json (после распаковки ZIP)
npm install
npx expo start
```

В терминале появится QR-код. Откройте **Expo Go** на телефоне и отсканируйте его.

## Если QR не открывается

- Убедитесь, что телефон и компьютер в **одной Wi‑Fi сети**
- Попробуйте туннель: `npx expo start --tunnel`

## Симулятор (опционально)

- **Android:** установите Android Studio, затем `npx expo run:android`
- **iOS:** только на Mac с Xcode — `npx expo run:ios`

Сборка на сервере ADE не поддерживается — запускайте локально на своём ПК.

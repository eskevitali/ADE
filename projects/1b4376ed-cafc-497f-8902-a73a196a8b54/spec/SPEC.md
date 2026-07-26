# ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ
## Приложение для быстрой отправки координат местоположения

## Архитектура системы

### Общая архитектура
- **Паттерн**: MVVM (Model-View-ViewModel) для Android
- **Язык разработки**: Kotlin для Android
- **Минимальная версия**: Android API 24 (Android 7.0)
- **Целевая версия**: Android API 34 (Android 14)

### Компоненты системы
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Presentation  │    │    Business     │    │      Data       │
│     Layer       │◄──►│     Layer       │◄──►│     Layer       │
│                 │    │                 │    │                 │
│ • Activities    │    │ • Use Cases     │    │ • Repositories  │
│ • Fragments     │    │ • ViewModels    │    │ • Data Sources  │
│ • Dialogs       │    │ • Services      │    │ • Local Storage │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Технологический стек
- **UI Framework**: Android Views + Material Design 3
- **Dependency Injection**: Hilt
- **Async Operations**: Coroutines + Flow
- **Local Storage**: SharedPreferences, Room Database
- **Location Services**: Google Play Services Location API
- **Advertising**: Google AdMob SDK
- **Analytics**: Firebase Analytics
- **Crash Reporting**: Firebase Crashlytics

## Модель данных

### Основные сущности

#### LocationData
```kotlin
data class LocationData(
    val latitude: Double,
    val longitude: Double,
    val accuracy: Float,
    val timestamp: Long,
    val address: String? = null,
    val provider: String
)
```

#### Contact
```kotlin
data class Contact(
    val id: String,
    val name: String,
    val phoneNumber: String? = null,
    val email: String? = null,
    val isSelected: Boolean = false
)
```

#### MessageTemplate
```kotlin
data class MessageTemplate(
    val id: String,
    val text: String,
    val isDefault: Boolean = false,
    val language: String
)
```

#### AppSettings
```kotlin
data class AppSettings(
    val selectedContacts: List<String>,
    val sendMethod: SendMethod,
    val messageTemplate: String,
    val isShakeEnabled: Boolean = true,
    val isPremium: Boolean = false,
    val showDialogAfterSend: Boolean = true, // ИЗМЕНЕНО: новое поле для управления диалогом
    val language: String = "en"
)

enum class SendMethod {
    SMS, EMAIL, WHATSAPP, TELEGRAM, MESSENGER
}
```

### База данных (Room)
```sql
-- Таблица контактов
CREATE TABLE contacts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone_number TEXT,
    email TEXT,
    is_selected INTEGER DEFAULT 0
);

-- Таблица шаблонов сообщений
CREATE TABLE message_templates (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    is_default INTEGER DEFAULT 0,
    language TEXT NOT NULL
);

-- Таблица истории отправок
CREATE TABLE location_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timestamp INTEGER NOT NULL,
    method TEXT NOT NULL,
    success INTEGER NOT NULL
);
```

## API и интерфейсы

### LocationService Interface
```kotlin
interface LocationService {
    suspend fun getCurrentLocation(): Result<LocationData>
    fun startLocationUpdates()
    fun stopLocationUpdates()
    fun isLocationEnabled(): Boolean
}
```

### MessageSender Interface
```kotlin
interface MessageSender {
    suspend fun sendMessage(
        contacts: List<Contact>,
        message: String,
        location: LocationData
    ): Result<Boolean>
}
```

### AdManager Interface
```kotlin
interface AdManager {
    fun loadBannerAd(adView: AdView)
    fun showInterstitialAd(activity: Activity, onClosed: () -> Unit)
    fun isAdLoaded(): Boolean
}
```

### SettingsRepository Interface
```kotlin
interface SettingsRepository {
    suspend fun getSettings(): AppSettings
    suspend fun updateSettings(settings: AppSettings)
    suspend fun isPremiumUser(): Boolean
}
```

## Пользовательские потоки (UI Flows)

### Поток 1: Первый запуск приложения
```
Splash Screen → Permission Request → Language Selection → 
Contact Selection → Send Method Setup → Tutorial → Main Screen
```

### Поток 2: Отправка через встряхивание
```
Background Service → Shake Detection → Location Request → 
Message Composition → Send Message → Silent Completion
```

### Поток 3: Отправка через ярлык (ИЗМЕНЕНО)
```
App Icon Tap → Location Request → Send Message → 
[Если showDialogAfterSend = true] → Dialog Window (with Ad) → 
Additional Message Input → Send Additional Message → Close Dialog
[Если showDialogAfterSend = false] → Silent Completion
```

### Поток 4: Настройки
```
Main Screen → Settings → Contact Management / Send Method / 
Message Templates / Premium Purchase / Language Settings / 
Dialog Settings (Premium)
```

## Структура экранов

### MainActivity (ИЗМЕНЕНО)
- **Назначение**: Обработка нажатия на ярлык приложения
- **Поведение**: 
  - При запуске немедленно отправляет координаты
  - Показывает диалог с результатом (если включено в настройках)
  - Завершает работу после закрытия диалога или тихой отправки

### SettingsActivity (ИЗМЕНЕНО)
- **Назначение**: Управление настройками
- **Компоненты**:
  - Список контактов с чекбоксами
  - Выбор способа отправки
  - Редактор шаблонов сообщений
  - Переключатель встряхивания
  - Настройки языка
  - **ДОБАВЛЕНО**: Переключатель "Показывать диалог после отправки" (только для Premium)
  - **ДОБАВЛЕНО**: Переключатель "Отключить рекламу" (только для Premium)
  - Покупка премиум-версии

### PostSendDialog (ИЗМЕНЕНО)
- **Назначение**: Диалог после отправки координат через ярлык
- **Условие показа**: Только если `showDialogAfterSend = true`
- **Размеры**: 75% экрана для контента, 25% для рекламы
- **Компоненты**:
  - Уведомление об успешной отправке координат
  - Поле ввода дополнительного текста (75% высоты)
  - Рекламный баннер AdMob (25% высоты) - только для бесплатной версии
  - Кнопка "Отправить дополнительное сообщение"
  - Кнопка "Закрыть" (четко видимая)

## Интеграция с AdMob

### Требования соответствия
- **Размещение рекламы**: только в нижней четверти диалогового окна
- **Четкое закрытие**: кнопка закрытия должна быть видимой и доступной
- **Детская аудитория**: соблюдение COPPA, семейные настройки рекламы
- **Контент**: только семейно-безопасная реклама
- **Премиум-версия**: полное отключение рекламы для платных пользователей

### Типы рекламы
- **Banner Ads**: в диалоговом окне (320x50 или 320x100)
- **Adaptive Banner**: адаптивные баннеры для разных размеров экрана

### Конфигурация AdMob
```kotlin
// Инициализация AdMob
MobileAds.initialize(context) { initializationStatus ->
    // Настройка для детской аудитории
    val requestConfiguration = RequestConfiguration.Builder()
        .setTagForChildDirectedTreatment(TAG_FOR_CHILD_DIRECTED_TREATMENT_TRUE)
        .setTagForUnderAgeOfConsent(TAG_FOR_UNDER_AGE_OF_CONSENT_TRUE)
        .build()
    MobileAds.setRequestConfiguration(requestConfiguration)
}
```

## Сервисы и фоновые процессы

### ShakeDetectionService
- **Тип**: Foreground Service
- **Назначение**: Обнаружение встряхивания устройства
- **Датчики**: Акселерометр
- **Алгоритм**: Анализ изменений ускорения по осям X, Y, Z

### LocationService
- **Тип**: Bound Service
- **Назначение**: Получение координат местоположения
- **Провайдеры**: GPS, Network, Passive
- **Точность**: HIGH_ACCURACY для быстрого определения

### MessageSendingService
- **Тип**: IntentService
- **Назначение**: Отправка сообщений различными способами
- **Поддерживаемые методы**: SMS, Email, WhatsApp, Telegram

## Безопасность и разрешения

### Необходимые разрешения
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.SEND_SMS" />
<uses-permission android:name="android.permission.READ_CONTACTS" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.WAKE_LOCK" />
```

### Обработка разрешений
- **Runtime Permissions**: запрос разрешений во время выполнения
- **Graceful Degradation**: работа с ограниченным функционалом при отказе
- **Permission Rationale**: объяснение необходимости разрешений

## Локализация

### Поддерживаемые языки
- **Английский (en)**: основной язык
- **Немецкий (de)**: полная локализация
- **Украинский (uk)**: полная локализация

### Структура ресурсов
```
res/
├── values/                 # Английский (по умолчанию)
├── values-de/             # Немецкий
├── values-uk/             # Украинский
└── values-night/          # Темная тема
```

### Локализуемые элементы
- Все текстовые строки интерфейса
- Шаблоны сообщений по умолчанию
- Описания разрешений
- Уведомления системы

## Критерии приемки

### Функциональные требования

#### FR-1: Отправка координат встряхиванием
- **Дано**: Приложение запущено в фоне, встряхивание включено
- **Когда**: Пользователь встряхивает устройство (3+ резких движения за 2 секунды)
- **Тогда**: 
  - Координаты определяются за <3 секунд
  - Сообщение отправляется выбранным контактам
  - Никаких UI элементов не отображается
  - Процесс завершается незаметно для пользователя

#### FR-2: Отправка через ярлык (ИЗМЕНЕНО)
- **Дано**: Приложение установлено, настройки сконфигурированы
- **Когда**: Пользователь нажимает на ярлык приложения в лаунчере
- **Тогда**:
  - Координаты определяются и отправляются немедленно в фоне
  - **Если showDialogAfterSend = true**: Открывается диалог с уведомлением об отправке и полем для дополнительного сообщения
  - **Если showDialogAfterSend = false**: Приложение завершает работу без показа UI
  - В диалоге реклама отображается в нижней четверти экрана (только для бесплатной версии)
  - Кнопка закрытия четко видна и функциональна

#### FR-3: Управление настройками (ИЗМЕНЕНО)
- **Дано**: Пользователь находится в настройках
- **Когда**: Пользователь изменяет настройки
- **Тогда**:
  - Изменения сохраняются немедленно
  - Настройки применяются к следующим отправкам
  - **ДОБАВЛЕНО**: Переключатель "Показывать диалог после отправки" доступен только для Premium пользователей
  - **ДОБАВЛЕНО**: Переключатель "Отключить рекламу" доступен только для Premium пользователей
  - Валидация входных данных работает корректно

#### FR-4: Премиум функции (ИЗМЕНЕНО)
- **Дано**: Пользователь приобрел премиум-версию
- **Когда**: Пользователь использует приложение
- **Тогда**:
  - Реклама не отображается в диалоговом окне
  - **ДОБАВЛЕНО**: Доступна настройка полного отключения диалогового окна
  - **ДОБАВЛЕНО**: Доступна настройка отключения рекламы
  - Все премиум функции доступны в настройках

### Нефункциональные требования

#### NFR-1: Производительность
- Время определения местоположения: <3 секунд
- Время отправки сообщения: <5 секунд
- Время запуска приложения: <2 секунд
- Потребление батареи в фоне: <2% в час

#### NFR-2: Точность
- Точность GPS: ±10 метров в 90% случаев
- Надежность отправки: 99% успешных отправок
- Обнаружение встряхивания: 95% точность, <1% ложных срабатываний

#### NFR-3: Совместимость
- Поддержка Android 7.0+ (API 24+)
- Работа на устройствах с RAM ≥2GB
- Поддержка экранов от 4" до 7"
- Совместимость с основными лаунчерами

#### NFR-4: Безопасность
- Шифрование локальных данных (AES-256)
- Безопасная передача координат
- Соответствие GDPR и COPPA
- Отсутствие сбора персональных данных без согласия

### Критерии качества AdMob

#### AD-1: Размещение рекламы
- **Проверка**: Реклама занимает точно 25% высоты диалогового окна
- **Проверка**: Кнопка закрытия находится вне рекламной области
- **Проверка**: Реклама не перекрывает функциональные элементы
- **Проверка**: Соблюдены минимальные отступы от краев экрана
- **ДОБАВЛЕНО**: Реклама полностью отключается для Premium пользователей

#### AD-2: Детская безопасность
- **Проверка**: Настроена фильтрация контента для детей
- **Проверка**: Отключена персонализированная реклама для детей
- **Проверка**: Соблюдены требования COPPA
- **Проверка**: Реклама соответствует семейным стандартам

#### AD-3: Пользовательский опыт
- **Проверка**: Реклама не мешает основному функционалу
- **Проверка**: Время загрузки рекламы не влияет на отправку координат
- **Проверка**: Четкое разделение контента и рекламы
- **Проверка**: Возможность закрыть диалог в любой момент
- **ДОБАВЛЕНО**: Возможность полного отключения диалога для Premium пользователей

## План тестирования

### Модульные тесты
- Тестирование бизнес-логики (Use Cases)
- Тестирование утилит и хелперов
- Тестирование репозиториев и источников данных
- **ДОБАВЛЕНО**: Тестирование логики показа/скрытия диалога
- Покрытие кода: >80%

### Интеграционные тесты
- Тестирование взаимодействия с системными сервисами
- Тестирование работы с базой данных
- Тестирование сетевых запросов
- Тестирование интеграции с AdMob
- **ДОБАВЛЕНО**: Тестирование Premium функций

### UI тесты
- Тестирование основных пользовательских сценариев
- Тестирование навигации между экранами
- Тестирование отображения рекламы
- **ДОБАВЛЕНО**: Тестирование поведения ярлыка приложения
- **ДОБАВЛЕНО**: Тестирование условного показа диалога
- Тестирование на разных размерах экранов

### Тестирование производительности
- Нагрузочное тестирование определения местоположения
- Тестирование потребления батареи
- Тестирование использования памяти
- Тестирование работы в фоновом режиме

## Изменения в реализации

### Критические изменения
1. **MainActivity**: Изменить поведение при запуске - немедленная отправка координат вместо показа кнопки
2. **PostSendDialog**: Добавить условную логику показа на основе настроек Premium
3. **SettingsActivity**: Добавить новые переключатели для Premium функций
4. **AppSettings**: Добавить поле `showDialogAfterSend`
5. **AdManager**: Добавить проверку Premium статуса перед загрузкой рекламы

### Новые компоненты
1. **PremiumManager**: Управление Premium функциями и проверка статуса подписки
2. **DialogController**: Контроллер для управления показом диалогового окна
3. **LauncherIconHandler**: Обработчик нажатий на ярлык приложения

### Обновления UI
1. Диалоговое окно должно показывать статус отправки координат
2. Настройки Premium должны быть четко выделены и заблокированы для бесплатных пользователей
3. Кнопка закрытия диалога должна быть более заметной
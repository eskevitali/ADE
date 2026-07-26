interface SettingsRepository {
    suspend fun getSettings(): AppSettings
    suspend fun updateSettings(settings: AppSettings)
    suspend fun isPremiumUser(): Boolean
}

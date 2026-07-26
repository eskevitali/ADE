enum class SendMethod { SMS, EMAIL, WHATSAPP, TELEGRAM, MESSENGER }

data class AppSettings(
    val selectedContacts: List<String> = emptyList(),
    val sendMethod: SendMethod = SendMethod.SMS,
    val messageTemplate: String = "My location: https://maps.google.com/?q={lat},{lon}",
    val isShakeEnabled: Boolean = true,
    val isPremium: Boolean = false,
    val showDialogAfterSend: Boolean = true,
    val language: String = "en",
    val disableAds: Boolean = false
)

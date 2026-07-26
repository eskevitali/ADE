interface MessageSender {
    suspend fun sendMessage(
        contacts: List<Contact>,
        message: String,
        location: LocationData
    ): Result<Boolean>
}

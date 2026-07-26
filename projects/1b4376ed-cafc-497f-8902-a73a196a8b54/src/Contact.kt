data class Contact(
    val id: String,
    val name: String,
    val phoneNumber: String? = null,
    val email: String? = null,
    val isSelected: Boolean = false
)

interface LocationService {
    suspend fun getCurrentLocation(): Result<LocationData>
    fun startLocationUpdates()
    fun stopLocationUpdates()
    fun isLocationEnabled(): Boolean
}

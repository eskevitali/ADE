interface AdManager {
    fun loadBannerAd(adView: com.google.android.gms.ads.AdView)
    fun showInterstitialAd(activity: android.app.Activity, onClosed: () -> Unit)
    fun isAdLoaded(): Boolean
    fun shouldShowAds(): Boolean // respects premium/disableAds
}

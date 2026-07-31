enum ItemCategory {
  bakery('Bakery', defaultShelfLifeDays: 4),
  makananSiapSaji('Makanan Siap Saji', defaultShelfLifeDays: 1),
  susuOlahan('Susu & Olahan', defaultShelfLifeDays: 5),
  minuman('Minuman', defaultShelfLifeDays: 3),
  sayurBuah('Sayur & Buah', defaultShelfLifeDays: 3),
  snack('Snack', defaultShelfLifeDays: 14),
  kalengan('Kalengan', defaultShelfLifeDays: 90),
  lainnya('Lainnya', defaultShelfLifeDays: 7);

  const ItemCategory(this.apiValue, {required this.defaultShelfLifeDays});

  final String apiValue;

  /// Perkiraan masa simpan (hari) (hanya default, bisa diubah)
  final int defaultShelfLifeDays;

  /// Kategori dengan catatan "hitung dalam porsi jadi"
  bool get needsPortionNote =>
      this == ItemCategory.minuman || this == ItemCategory.makananSiapSaji;

  static ItemCategory fromApiValue(String value) {
    return ItemCategory.values.firstWhere(
      (c) => c.apiValue == value,
      orElse: () => ItemCategory.lainnya,
    );
  }
}

enum DealStatus {
  active('active'),
  soldOut('sold_out'),
  removed('removed');

  const DealStatus(this.apiValue);
  final String apiValue;

  static DealStatus fromApiValue(String value) {
    return DealStatus.values.firstWhere(
      (s) => s.apiValue == value,
      orElse: () => DealStatus.active,
    );
  }
}

enum ClaimStatus {
  claimed('claimed'),
  redeemed('redeemed');

  const ClaimStatus(this.apiValue);
  final String apiValue;

  static ClaimStatus fromApiValue(String value) {
    return ClaimStatus.values.firstWhere(
      (s) => s.apiValue == value,
      orElse: () => ClaimStatus.claimed,
    );
  }
}

/// Sistem urgensi
enum UrgencyLevel { aman, perhatian, kritis }

/// 5 status hasil `POST /api/recommend`
enum RecommendResultStatus {
  recommendation,
  noAction,
  needsConfirmation,
  invalidInput,
  modelUnavailable,
}

enum BusinessType {
  warungToko('Warung/Toko'),
  bakery('Bakery'),
  kafeKedai('Kafe/Kedai'),
  rumahMakan('Rumah Makan'),
  katering('Katering'),
  jualanOnline('Jualan Online');

  const BusinessType(this.label);
  final String label;
}
/// Kategori barang.
///
/// [apiValue] mengikuti kontrak `POST /api/recommend` (SRS Penyisihan §3.3)
/// yang memakai istilah Inggris, sedangkan [label] adalah teks yang
/// ditampilkan ke vendor. Keduanya harus dipisah — kalau label Indonesia
/// ikut terkirim ke backend, kategori tidak akan dikenali.
enum ItemCategory {
  bakery('Bakery', 'Bakery', defaultShelfLifeDays: 4),
  makananSiapSaji('Prepared Food', 'Makanan Siap Saji', defaultShelfLifeDays: 3),
  susuOlahan('Dairy', 'Susu & Olahan', defaultShelfLifeDays: 14),
  minuman('Beverage', 'Minuman', defaultShelfLifeDays: 5),
  sayurBuah('Produce', 'Sayur & Buah', defaultShelfLifeDays: 7),
  snack('Snack', 'Snack', defaultShelfLifeDays: 90),
  kalengan('Canned', 'Kalengan', defaultShelfLifeDays: 365),
  lainnya('Other', 'Lainnya', defaultShelfLifeDays: 30);

  const ItemCategory(
    this.apiValue,
    this.label, {
    required this.defaultShelfLifeDays,
  });

  /// Nilai yang dikirim/diterima backend. Jangan tampilkan ke user.
  final String apiValue;

  /// Teks Bahasa Indonesia untuk UI. Jangan kirim ke backend.
  final String label;

  /// Default umur simpan per kategori, mengikuti tabel SRS Penyisihan §3.3.
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
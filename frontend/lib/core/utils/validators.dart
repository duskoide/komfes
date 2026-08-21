class Validators {
  Validators._();

  /// Normalisasi input nomor HP: `08123...` -> `8123...` (prefix +62 sudah
  /// terkunci di UI, terpisah dari field ini). Menolak karakter non-angka.
  static String normalizePhoneLocal(String raw) {
    var digits = raw.replaceAll(RegExp(r'[^0-9]'), '');
    if (digits.startsWith('0')) {
      digits = digits.substring(1);
    }
    if (digits.startsWith('62')) {
      digits = digits.substring(2);
    }
    return digits;
  }

  static bool isPhoneValid(String localDigits) {
    return localDigits.length >= 9 && localDigits.length <= 13;
  }

  static bool isOtpComplete(String otp) => otp.length == 6 && int.tryParse(otp) != null;

  /// `stock`, `days_remaining`, `daily_sales` — bilangan bulat >= 0.
  static bool isNonNegativeInt(String value) {
    final n = int.tryParse(value);
    return n != null && n >= 0;
  }

  static bool isPositiveInt(String value) {
    final n = int.tryParse(value);
    return n != null && n > 0;
  }
}

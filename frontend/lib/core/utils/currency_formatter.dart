import 'package:intl/intl.dart';

/// Format Rupiah
class CurrencyFormatter {
  CurrencyFormatter._();

  static final NumberFormat _formatter = NumberFormat.decimalPattern('id_ID');

  /// `15000` -> `Rp15.000`
  static String format(num value) {
    final digits = _formatter.format(value.round());
    return 'Rp$digits';
  }

  /// Parse angka dari teks yang sedang diketik (buang `Rp`, titik, spasi).
  static int parseDigits(String input) {
    final clean = input.replaceAll(RegExp(r'[^0-9]'), '');
    if (clean.isEmpty) return 0;
    return int.parse(clean);
  }

  /// Format ribuan TANPA prefix `Rp` — dipakai di dalam Field Rupiah saat mengetik
  static String formatDigitsOnly(num value) {
    return _formatter.format(value.round());
  }
}

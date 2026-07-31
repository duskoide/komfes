import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // Brand - green
  static const Color primary = Color(0xFF1B7A5A);
  static const Color primaryDark = Color(0xFF0F5A40);
  static const Color primaryLight = Color(0xFFE6F4EE);

  static const Color secondary = Color(0xFFB8722E);

  // Netral
  static const Color background = Color(0xFFFAFAF8);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceAlt = Color(0xFFF2F1ED);
  static const Color border = Color(0xFFE1DFD8);
  static const Color textPrimary = Color(0xFF1B1B18);
  static const Color textSecondary = Color(0xFF5B5A54);
  static const Color textDisabled = Color(0xFF9C9B94);

  // Sistem urgensi
  static const Color aman = Color(0xFF2E7D4F);
  static const Color amanBg = Color(0xFFE3F3E9);
  static const Color perhatian = Color(0xFFB4740E);
  static const Color perhatianBg = Color(0xFFFCEFD9);
  static const Color kritis = Color(0xFFC13A2E);
  static const Color kritisBg = Color(0xFFFBE6E3);

  // Error jaringan / validasi
  static const Color error = Color(0xFFC13A2E);
  static const Color errorBg = Color(0xFFFBE6E3);

  // Harga coret / bekas harga
  static const Color priceStrikethrough = Color(0xFF7A7A72);

  // Status chip
  static const Color statusAktif = aman;
  static const Color statusAktifBg = amanBg;
  static const Color statusHabis = Color(0xFF6B6A63);
  static const Color statusHabisBg = Color(0xFFE9E8E3);
  static const Color statusDihapus = Color(0xFF8A8A82);
  static const Color statusDihapusBg = Color(0xFFEDECE7);
  static const Color statusBelumDiambil = perhatian;
  static const Color statusBelumDiambilBg = perhatianBg;
  static const Color statusSudahDigunakan = aman;
  static const Color statusSudahDigunakanBg = amanBg;

  static const Color overlayScrim = Color(0x66000000);
}

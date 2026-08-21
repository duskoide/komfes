import 'dart:math';
import '../models/user.dart';
import 'app_exception.dart';

abstract class AuthRepository {
  /// POST /api/auth/otp/request
  Future<void> requestOtp(String fullPhone);

  /// POST /api/auth/otp/verify
  Future<UserSession> verifyOtp(String fullPhone, String otp);

  /// PATCH/POST setup toko vendor baru (bagian dari S-06).
  Future<ShopProfile> saveShopProfile(ShopProfile profile);
}

class MockAuthRepository implements AuthRepository {
  final _rand = Random();
  int _attempts = 0;

  @override
  Future<void> requestOtp(String fullPhone) async {
    await Future.delayed(const Duration(milliseconds: 900));
    _attempts = 0;
    // Mock selalu sukses mengirim; kode "benar" untuk demo selalu 123456.
  }

  @override
  Future<UserSession> verifyOtp(String fullPhone, String otp) async {
    await Future.delayed(const Duration(milliseconds: 900));
    _attempts++;
    if (_attempts > 5) {
      throw const OtpException('Terlalu banyak percobaan. Coba lagi dalam 5 menit.');
    }
    if (otp != '123456') {
      throw const OtpException('Kode salah.');
    }
    final isNew = !_knownPhones.contains(fullPhone);
    _knownPhones.add(fullPhone);
    return UserSession(
      phone: fullPhone,
      token: 'mock-token-${_rand.nextInt(999999)}',
      isNewVendor: isNew,
      shop: isNew ? null : _savedShop,
    );
  }

  final Set<String> _knownPhones = {};
  ShopProfile? _savedShop;

  @override
  Future<ShopProfile> saveShopProfile(ShopProfile profile) async {
    await Future.delayed(const Duration(milliseconds: 600));
    _savedShop = profile;
    return profile;
  }
}

import '../models/enums.dart';
import '../models/user.dart';
import 'api_client.dart';
import 'app_exception.dart';

abstract class AuthRepository {
  Future<void> requestOtp(String fullPhone);
  Future<UserSession> verifyOtp(String fullPhone, String otp);
  Future<ShopProfile> saveShopProfile(ShopProfile profile);
}

class HttpAuthRepository implements AuthRepository {
  const HttpAuthRepository(this._api);

  final ApiClient _api;

  @override
  Future<void> requestOtp(String fullPhone) async {
    final response = await _api.post(
      '/api/auth/otp/request',
      body: {'phone': fullPhone},
    );
    if (!response.isSuccess) throw OtpException(response.message);
  }

  @override
  Future<UserSession> verifyOtp(String fullPhone, String otp) async {
    final response = await _api.post(
      '/api/auth/otp/verify',
      body: {'phone': fullPhone, 'otp': otp},
    );
    if (!response.isSuccess) throw OtpException(response.message);

    final json = response.object;
    final token = json['token'] as String;
    _api.bearerToken = token;
    return UserSession(
      phone: json['phone'] as String,
      token: token,
      isNewVendor: json['is_new_vendor'] as bool,
      shop: json['shop'] == null
          ? null
          : _shopFromJson((json['shop'] as Map).cast<String, dynamic>()),
    );
  }

  @override
  Future<ShopProfile> saveShopProfile(ShopProfile profile) async {
    final response = await _api.post('/api/shops', body: profile.toJson());
    if (!response.isSuccess) throw RequestFailedException(response.message);
    return _shopFromJson(response.object);
  }

  ShopProfile _shopFromJson(Map<String, dynamic> json) {
    final businessTypeName = json['business_type'] as String;
    return ShopProfile(
      shopName: json['shop_name'] as String,
      businessType: BusinessType.values.firstWhere(
        (type) => type.name == businessTypeName,
        orElse: () => BusinessType.warungToko,
      ),
      shortAddress: json['short_address'] as String?,
    );
  }
}

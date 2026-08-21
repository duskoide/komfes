import 'enums.dart';

enum AppRole { vendor, consumer }

/// Data toko vendor
class ShopProfile {
  const ShopProfile({
    required this.shopName,
    required this.businessType,
    this.shortAddress,
  });

  final String shopName;
  final BusinessType businessType;
  final String? shortAddress;

  ShopProfile copyWith({
    String? shopName,
    BusinessType? businessType,
    String? shortAddress,
  }) {
    return ShopProfile(
      shopName: shopName ?? this.shopName,
      businessType: businessType ?? this.businessType,
      shortAddress: shortAddress ?? this.shortAddress,
    );
  }

  Map<String, dynamic> toJson() => {
        'shop_name': shopName,
        'business_type': businessType.name,
        'short_address': shortAddress,
      };
}

class UserSession {
  const UserSession({
    required this.phone,
    required this.token,
    required this.isNewVendor,
    this.shop,
  });

  final String phone;
  final String token;
  final bool isNewVendor;
  final ShopProfile? shop;

  UserSession copyWith({ShopProfile? shop, bool? isNewVendor}) {
    return UserSession(
      phone: phone,
      token: token,
      isNewVendor: isNewVendor ?? this.isNewVendor,
      shop: shop ?? this.shop,
    );
  }
}

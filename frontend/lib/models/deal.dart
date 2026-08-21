import 'enums.dart';

class Deal {
  const Deal({
    required this.id,
    required this.itemName,
    required this.shopName,
    required this.category,
    required this.originalPrice,
    required this.dealPrice,
    required this.discountPercent,
    required this.daysRemaining,
    required this.initialStock,
    required this.remainingStock,
    required this.promoCopy,
    required this.status,
    required this.createdAt,
    this.cost,
  });

  final String id;
  final String itemName;
  final String shopName;
  final ItemCategory category;
  final int originalPrice;
  final int dealPrice;
  final int discountPercent;
  final double daysRemaining;
  final int initialStock;
  final int remainingStock;
  final String promoCopy;
  final DealStatus status;
  final DateTime createdAt;

  final int? cost;

  int get claimedCount => initialStock - remainingStock;

  bool get isSoldOut => remainingStock <= 0;

  UrgencyLevel get urgency {
    if (daysRemaining <= 0) return UrgencyLevel.kritis;
    if (daysRemaining <= 1) return UrgencyLevel.kritis;
    if (daysRemaining <= 3) return UrgencyLevel.perhatian;
    return UrgencyLevel.aman;
  }

  String get remainingLabel {
    if (daysRemaining <= 0) return 'HARI INI SAJA!';
    if (daysRemaining < 1) return 'Hari ini saja';
    final d = daysRemaining.round();
    return d == 1 ? 'Sisa 1 hari' : 'Sisa $d hari';
  }

  Deal copyWith({
    int? remainingStock,
    DealStatus? status,
  }) {
    return Deal(
      id: id,
      itemName: itemName,
      shopName: shopName,
      category: category,
      originalPrice: originalPrice,
      dealPrice: dealPrice,
      discountPercent: discountPercent,
      daysRemaining: daysRemaining,
      initialStock: initialStock,
      remainingStock: remainingStock ?? this.remainingStock,
      promoCopy: promoCopy,
      status: status ?? this.status,
      createdAt: createdAt,
      cost: cost,
    );
  }

  factory Deal.fromJson(Map<String, dynamic> json) {
    return Deal(
      id: json['id'] as String,
      itemName: json['item_name'] as String,
      shopName: json['shop_name'] as String? ?? '',
      category: ItemCategory.fromApiValue(json['category'] as String? ?? ''),
      originalPrice: (json['original_price'] as num).toInt(),
      dealPrice: (json['deal_price'] as num).toInt(),
      discountPercent: (json['discount_percent'] as num).toInt(),
      daysRemaining: (json['days_remaining'] as num).toDouble(),
      initialStock: (json['initial_stock'] as num).toInt(),
      remainingStock: (json['remaining_stock'] as num).toInt(),
      promoCopy: json['promo_copy'] as String? ?? '',
      status: DealStatus.fromApiValue(json['status'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      cost: (json['cost'] as num?)?.toInt(),
    );
  }

  Map<String, dynamic> toPublishJson() => {
        'item_name': itemName,
        'shop_name': shopName,
        'category': category.apiValue,
        'original_price': originalPrice,
        if (cost != null) 'cost': cost,
        'deal_price': dealPrice,
        'discount_percent': discountPercent,
        'days_remaining': daysRemaining,
        'initial_stock': initialStock,
        'promo_copy': promoCopy,
      };
}

class Claim {
  const Claim({
    required this.code,
    required this.dealId,
    required this.status,
    required this.createdAt,
    this.redeemedAt,
    this.itemName,
    this.shopName,
    this.priceToPay,
  });

  final String code;
  final String dealId;
  final ClaimStatus status;
  final DateTime createdAt;
  final DateTime? redeemedAt;

  final String? itemName;
  final String? shopName;
  final int? priceToPay;

  factory Claim.fromJson(Map<String, dynamic> json) {
    return Claim(
      code: json['code'] as String,
      dealId: json['deal_id'] as String,
      status: ClaimStatus.fromApiValue(json['status'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      redeemedAt: json['redeemed_at'] != null
          ? DateTime.parse(json['redeemed_at'] as String)
          : null,
      itemName: json['item_name'] as String?,
      shopName: json['shop_name'] as String?,
      priceToPay: (json['price_to_pay'] as num?)?.toInt(),
    );
  }

  Claim copyWith({ClaimStatus? status, DateTime? redeemedAt}) {
    return Claim(
      code: code,
      dealId: dealId,
      status: status ?? this.status,
      createdAt: createdAt,
      redeemedAt: redeemedAt ?? this.redeemedAt,
      itemName: itemName,
      shopName: shopName,
      priceToPay: priceToPay,
    );
  }
}

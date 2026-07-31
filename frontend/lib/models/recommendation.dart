import 'enums.dart';

class ItemInputDraft {
  ItemInputDraft({
    this.freeText,
    this.itemName,
    this.category,
    this.originalPrice,
    this.cost,
    this.stock,
    this.daysRemaining,
    this.dailySales,
    this.totalShelfLife,
    this.shopName,
  });

  final String? freeText;
  String? itemName;
  ItemCategory? category;
  int? originalPrice;
  int? cost;
  int? stock;
  int? daysRemaining;
  int? dailySales;
  int? totalShelfLife;
  String? shopName;

  ItemInputDraft copyWith({
    String? itemName,
    ItemCategory? category,
    int? originalPrice,
    int? cost,
    int? stock,
    int? daysRemaining,
    int? dailySales,
    int? totalShelfLife,
    String? shopName,
  }) {
    return ItemInputDraft(
      freeText: freeText,
      itemName: itemName ?? this.itemName,
      category: category ?? this.category,
      originalPrice: originalPrice ?? this.originalPrice,
      cost: cost ?? this.cost,
      stock: stock ?? this.stock,
      daysRemaining: daysRemaining ?? this.daysRemaining,
      dailySales: dailySales ?? this.dailySales,
      totalShelfLife: totalShelfLife ?? this.totalShelfLife,
      shopName: shopName ?? this.shopName,
    );
  }

  bool get isStructuredComplete =>
      itemName != null &&
      itemName!.isNotEmpty &&
      category != null &&
      originalPrice != null &&
      cost != null &&
      stock != null &&
      daysRemaining != null &&
      dailySales != null;

  Map<String, dynamic> toStructuredJson() => {
        if (itemName != null) 'item_name': itemName,
        if (category != null) 'category': category!.apiValue,
        if (originalPrice != null) 'original_price': originalPrice,
        if (cost != null) 'cost': cost,
        if (stock != null) 'stock': stock,
        if (daysRemaining != null) 'days_remaining': daysRemaining,
        if (dailySales != null) 'daily_sales': dailySales,
        if (totalShelfLife != null) 'total_shelf_life': totalShelfLife,
        if (shopName != null) 'shop_name': shopName,
      };

  Map<String, dynamic> toJson() {
    if (freeText != null && freeText!.trim().isNotEmpty) {
      return {'free_text': freeText};
    }
    return toStructuredJson();
  }

  factory ItemInputDraft.fromJson(Map<String, dynamic> json) {
    return ItemInputDraft(
      itemName: json['item_name'] as String?,
      category: json['category'] != null
          ? ItemCategory.fromApiValue(json['category'] as String)
          : null,
      originalPrice: (json['original_price'] as num?)?.toInt(),
      cost: (json['cost'] as num?)?.toInt(),
      stock: (json['stock'] as num?)?.toInt(),
      daysRemaining: (json['days_remaining'] as num?)?.toInt(),
      dailySales: (json['daily_sales'] as num?)?.toInt(),
      totalShelfLife: (json['total_shelf_life'] as num?)?.toInt(),
      shopName: json['shop_name'] as String?,
    );
  }
}

class RecommendationNumbers {
  const RecommendationNumbers({
    required this.discountPercent,
    required this.recommendedPrice,
    required this.timing,
    required this.expectedSellThrough,
    required this.expectedRevenue,
    required this.expectedLossNoAction,
    required this.confidence,
  });

  final int discountPercent;
  final int recommendedPrice;
  final String timing;
  final String expectedSellThrough;
  final int expectedRevenue;
  final int expectedLossNoAction;
  final String confidence;

  bool get isHighConfidence =>
      confidence.toLowerCase().contains('cukup') || confidence.toLowerCase().contains('yakin');

  factory RecommendationNumbers.fromJson(Map<String, dynamic> json) {
    return RecommendationNumbers(
      discountPercent: (json['discount_percent'] as num).toInt(),
      recommendedPrice: (json['recommended_price'] as num).toInt(),
      timing: json['timing'] as String,
      expectedSellThrough: json['expected_sell_through'] as String,
      expectedRevenue: (json['expected_revenue'] as num).toInt(),
      expectedLossNoAction: (json['expected_loss_no_action'] as num).toInt(),
      confidence: json['confidence'] as String,
    );
  }
}

class DealPreview {
  const DealPreview({
    required this.itemName,
    required this.shopName,
    required this.originalPrice,
    required this.dealPrice,
    required this.discountPercent,
    required this.daysRemaining,
    required this.stock,
  });

  final String itemName;
  final String shopName;
  final int originalPrice;
  final int dealPrice;
  final int discountPercent;
  final int daysRemaining;
  final int stock;

  factory DealPreview.fromJson(Map<String, dynamic> json) {
    return DealPreview(
      itemName: json['item_name'] as String,
      shopName: json['shop_name'] as String? ?? '',
      originalPrice: (json['original_price'] as num).toInt(),
      dealPrice: (json['deal_price'] as num).toInt(),
      discountPercent: (json['discount_percent'] as num).toInt(),
      daysRemaining: (json['days_remaining'] as num).toInt(),
      stock: (json['stock'] as num).toInt(),
    );
  }
}

class RecommendResult {
  const RecommendResult({
    required this.status,
    this.normalizedInput,
    this.recommendation,
    this.explanation,
    this.promoCopy,
    this.preview,
    this.message,
    this.reassessInDays,
    this.parsedInput,
    this.missingFields,
  });

  final RecommendResultStatus status;

  // status == recommendation
  final ItemInputDraft? normalizedInput;
  final RecommendationNumbers? recommendation;
  final String? explanation;
  final String? promoCopy;
  final DealPreview? preview;

  // status == noAction / invalidInput / modelUnavailable
  final String? message;
  final int? reassessInDays;

  // status == needsConfirmation
  final ItemInputDraft? parsedInput;
  final List<String>? missingFields;

  factory RecommendResult.fromJson(Map<String, dynamic> json) {
    final statusStr = json['status'] as String;
    switch (statusStr) {
      case 'recommendation':
        return RecommendResult(
          status: RecommendResultStatus.recommendation,
          normalizedInput: ItemInputDraft.fromJson(
              json['normalized_input'] as Map<String, dynamic>),
          recommendation: RecommendationNumbers.fromJson(
              json['recommendation'] as Map<String, dynamic>),
          explanation: json['explanation'] as String?,
          promoCopy: json['promo_copy'] as String?,
          preview: DealPreview.fromJson(json['preview'] as Map<String, dynamic>),
        );
      case 'no_action':
        return RecommendResult(
          status: RecommendResultStatus.noAction,
          message: json['message'] as String?,
          reassessInDays: (json['reassess_in_days'] as num?)?.toInt(),
        );
      case 'needs_confirmation':
        return RecommendResult(
          status: RecommendResultStatus.needsConfirmation,
          parsedInput: ItemInputDraft.fromJson(
              (json['parsed_input'] as Map<String, dynamic>?) ?? {}),
          missingFields: (json['missing_fields'] as List?)?.cast<String>(),
        );
      case 'invalid_input':
        return RecommendResult(
          status: RecommendResultStatus.invalidInput,
          message: json['message'] as String?,
        );
      case 'model_unavailable':
      default:
        return RecommendResult(
          status: RecommendResultStatus.modelUnavailable,
          message: json['message'] as String? ?? 'Sistem AI sedang tidak tersedia.',
        );
    }
  }
}

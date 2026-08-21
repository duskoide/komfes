import '../models/deal.dart';
import '../models/enums.dart';
import 'api_client.dart';
import 'app_exception.dart';

abstract class DealRepository {
  Future<Deal> publish({
    required String itemName,
    required String shopName,
    required ItemCategory category,
    required int originalPrice,
    required int dealPrice,
    required int discountPercent,
    required double daysRemaining,
    required int initialStock,
    required String promoCopy,
    int? cost,
  });

  Future<List<Deal>> listDeals({DealStatus? status, String? shopName});
  Future<void> removeDeal(String dealId);
  Future<Claim> claim(String dealId);
  Future<Claim> redeem(String code);
  Future<List<Claim>> listClaimsForConsumer();
  Future<List<Claim>> listClaimsForDeal(String dealId);
}

class HttpDealRepository implements DealRepository {
  const HttpDealRepository(this._api);

  final ApiClient _api;

  @override
  Future<Deal> publish({
    required String itemName,
    required String shopName,
    required ItemCategory category,
    required int originalPrice,
    required int dealPrice,
    required int discountPercent,
    required double daysRemaining,
    required int initialStock,
    required String promoCopy,
    int? cost,
  }) async {
    if (cost == null) {
      throw const InvalidInputException('Harga modal wajib untuk publikasi.');
    }
    final response = await _api.post(
      '/api/deals',
      body: {
        'item_name': itemName,
        'shop_name': shopName,
        'category': category.apiValue,
        'original_price': originalPrice,
        'cost': cost,
        'deal_price': dealPrice,
        'discount_percent': discountPercent,
        'days_remaining': daysRemaining,
        'initial_stock': initialStock,
        'promo_copy': promoCopy,
      },
    );
    if (!response.isSuccess) throw InvalidInputException(response.message);
    return Deal.fromJson(response.object);
  }

  @override
  Future<List<Deal>> listDeals({DealStatus? status, String? shopName}) async {
    final response = await _api.get(
      '/api/deals',
      query: {'status': status?.apiValue, 'shop_name': shopName},
    );
    if (!response.isSuccess) throw RequestFailedException(response.message);
    return response.list
        .map((json) => Deal.fromJson((json as Map).cast<String, dynamic>()))
        .toList();
  }

  @override
  Future<void> removeDeal(String dealId) async {
    final response = await _api.delete('/api/deals/$dealId');
    if (response.statusCode == 404) throw NotFoundException(response.message);
    if (!response.isSuccess) throw RequestFailedException(response.message);
  }

  @override
  Future<Claim> claim(String dealId) async {
    final response = await _api.post('/api/deals/$dealId/claims');
    if (response.statusCode == 409) throw ConflictException(response.message);
    if (!response.isSuccess) throw RequestFailedException(response.message);
    return Claim.fromJson(response.object);
  }

  @override
  Future<Claim> redeem(String code) async {
    final normalized = code.trim().toUpperCase();
    final response = await _api.post(
      '/api/claims/${Uri.encodeComponent(normalized)}/redeem',
    );
    if (response.statusCode == 404) throw NotFoundException(response.message);
    if (response.statusCode == 409) throw ConflictException(response.message);
    if (!response.isSuccess) throw RequestFailedException(response.message);
    return Claim.fromJson(response.object);
  }

  @override
  Future<List<Claim>> listClaimsForConsumer() => _listClaims('/api/claims');

  @override
  Future<List<Claim>> listClaimsForDeal(String dealId) {
    return _listClaims('/api/deals/$dealId/claims');
  }

  Future<List<Claim>> _listClaims(String path) async {
    final response = await _api.get(path);
    if (response.statusCode == 404) throw NotFoundException(response.message);
    if (!response.isSuccess) throw RequestFailedException(response.message);
    return response.list
        .map((json) => Claim.fromJson((json as Map).cast<String, dynamic>()))
        .toList();
  }
}

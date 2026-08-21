import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:hargaturun/models/enums.dart';
import 'package:hargaturun/models/recommendation.dart';
import 'package:hargaturun/models/user.dart';
import 'package:hargaturun/services/api_client.dart';
import 'package:hargaturun/services/auth_repository.dart';
import 'package:hargaturun/services/deal_repository.dart';
import 'package:hargaturun/services/recommend_repository.dart';

void main() {
  test('recommendation repository parses an oracle response', () async {
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        expect(request.url.path, '/api/recommend');
        expect(jsonDecode(request.body)['category'], 'Bakery');
        return http.Response(
          jsonEncode({
            'status': 'recommendation',
            'normalized_input': {
              'item_name': 'Roti',
              'category': 'Bakery',
              'original_price': 20000,
              'cost': 10000,
              'stock': 30,
              'days_remaining': 1,
              'daily_sales': 5,
              'total_shelf_life': 4,
              'shop_name': 'Toko Sari',
            },
            'recommendation': {
              'discount_percent': 45,
              'recommended_price': 11000,
              'timing': 'Mulai diskon hari ini',
              'expected_sell_through': '10 dari 30 pcs',
              'expected_revenue': 110000,
              'expected_loss_no_action': 250000,
              'confidence': 'Cukup yakin',
            },
            'explanation': 'Stok perlu segera ditangani.',
            'promo_copy': 'Harga spesial hari ini.',
            'preview': {
              'item_name': 'Roti',
              'shop_name': 'Toko Sari',
              'original_price': 20000,
              'deal_price': 11000,
              'discount_percent': 45,
              'days_remaining': 1,
              'stock': 30,
            },
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );

    final result = await HttpRecommendRepository(api).recommend(
      ItemInputDraft(
        itemName: 'Roti',
        category: ItemCategory.bakery,
        originalPrice: 20000,
        cost: 10000,
        stock: 30,
        daysRemaining: 1,
        dailySales: 5,
        totalShelfLife: 4,
      ),
    );
    expect(result.status, RecommendResultStatus.recommendation);
    expect(result.recommendation!.recommendedPrice, 11000);
  });

  test('auth repository stores token for later API requests', () async {
    final requests = <http.Request>[];
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        requests.add(request);
        if (request.url.path.endsWith('/verify')) {
          return http.Response(
            jsonEncode({
              'phone': '+628123456789',
              'token': 'signed-token',
              'is_new_vendor': true,
              'shop': null,
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({
            'shop_name': 'Toko Sari',
            'business_type': 'bakery',
            'short_address': 'Depok',
          }),
          200,
        );
      }),
    );
    final repository = HttpAuthRepository(api);

    await repository.verifyOtp('+628123456789', '123456');
    await repository.saveShopProfile(
      const ShopProfile(
        shopName: 'Toko Sari',
        businessType: BusinessType.bakery,
        shortAddress: 'Depok',
      ),
    );

    expect(requests.last.headers['Authorization'], 'Bearer signed-token');
  });

  test('deal publish includes cost for server margin validation', () async {
    late Map<String, dynamic> body;
    final api = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        body = (jsonDecode(request.body) as Map).cast<String, dynamic>();
        return http.Response(
          jsonEncode({
            'id': 'deal-1',
            ...body,
            'remaining_stock': body['initial_stock'],
            'status': 'active',
            'created_at': '2026-08-17T12:00:00+00:00',
          }),
          201,
        );
      }),
    );

    final deal = await HttpDealRepository(api).publish(
      itemName: 'Roti',
      shopName: 'Toko Sari',
      category: ItemCategory.bakery,
      originalPrice: 20000,
      cost: 10000,
      dealPrice: 11000,
      discountPercent: 45,
      daysRemaining: 1,
      initialStock: 3,
      promoCopy: 'Harga spesial.',
    );

    expect(body['cost'], 10000);
    expect(deal.remainingStock, 3);
  });
}

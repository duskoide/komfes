import 'dart:math';
import '../models/deal.dart';
import '../models/enums.dart';
import 'app_exception.dart';

/// - `publish`   -> POST /api/deals
/// - `listDeals` -> GET  /api/deals?status=...
/// - `removeDeal`-> DELETE /api/deals/{id}
/// - `claim`     -> POST /api/deals/{id}/claims
/// - `redeem`    -> POST /api/claims/{code}/redeem
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

  /// `status` null = semua (Aktif/Habis/Dihapus)
  Future<List<Deal>> listDeals({DealStatus? status, String? shopName});

  Future<void> removeDeal(String dealId);

  Future<Claim> claim(String dealId);

  /// Melempar [NotFoundException] (404) atau [ConflictException] (409,
  /// sudah dipakai / deal tidak valid)
  Future<Claim> redeem(String code);

  Future<List<Claim>> listClaimsForConsumer();

  Future<List<Claim>> listClaimsForDeal(String dealId);
}

class MockDealRepository implements DealRepository {
  MockDealRepository() {
    _seed();
  }

  final List<Deal> _deals = [];
  final List<Claim> _claims = [];
  final _rand = Random();

  void _seed() {
    final now = DateTime.now();
    _deals.addAll([
      Deal(
        id: 'd1',
        itemName: 'Roti Tawar',
        shopName: 'Toko Sari Bakery',
        category: ItemCategory.bakery,
        originalPrice: 15000,
        dealPrice: 10500,
        discountPercent: 30,
        daysRemaining: 1,
        initialStock: 10,
        remainingStock: 8,
        promoCopy: 'Roti tawar fresh, diskon 30% karena mendekati tanggal kadaluarsa besok!',
        status: DealStatus.active,
        createdAt: now.subtract(const Duration(hours: 3)),
        cost: 10000,
      ),
      Deal(
        id: 'd2',
        itemName: 'Susu UHT 1L',
        shopName: 'Warung Bu Tuti',
        category: ItemCategory.susuOlahan,
        originalPrice: 18000,
        dealPrice: 13000,
        discountPercent: 28,
        daysRemaining: 2,
        initialStock: 6,
        remainingStock: 0,
        promoCopy: 'Susu UHT masih segar, buruan sebelum kehabisan.',
        status: DealStatus.soldOut,
        createdAt: now.subtract(const Duration(hours: 8)),
        cost: 12000,
      ),
      Deal(
        id: 'd3',
        itemName: 'Kue Lapis Legit Spesial Pandan',
        shopName: 'Toko Kue Ibu Ani yang Sudah Berdiri Sejak Lama',
        category: ItemCategory.bakery,
        originalPrice: 45000,
        dealPrice: 27000,
        discountPercent: 40,
        daysRemaining: 0,
        initialStock: 4,
        remainingStock: 3,
        promoCopy: 'HARI INI SAJA! Kue lapis legit pandan, harga spesial.',
        status: DealStatus.active,
        createdAt: now.subtract(const Duration(minutes: 40)),
        cost: 20000,
      ),
    ]);
    _claims.addAll([
      Claim(
        code: 'HT-4821',
        dealId: 'd1',
        status: ClaimStatus.claimed,
        createdAt: now.subtract(const Duration(minutes: 25)),
        itemName: 'Roti Tawar',
        shopName: 'Toko Sari Bakery',
        priceToPay: 10500,
      ),
    ]);
  }

  Future<void> _delay() => Future.delayed(const Duration(milliseconds: 600));

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
    await _delay();
    final deal = Deal(
      id: 'd${_rand.nextInt(999999)}',
      itemName: itemName,
      shopName: shopName,
      category: category,
      originalPrice: originalPrice,
      dealPrice: dealPrice,
      discountPercent: discountPercent,
      daysRemaining: daysRemaining,
      initialStock: initialStock,
      remainingStock: initialStock,
      promoCopy: promoCopy,
      status: DealStatus.active,
      createdAt: DateTime.now(),
      cost: cost,
    );
    _deals.insert(0, deal);
    return deal;
  }

  @override
  Future<List<Deal>> listDeals({DealStatus? status, String? shopName}) async {
    await _delay();
    return _deals
        .where((d) => status == null || d.status == status)
        .where((d) => shopName == null || d.shopName == shopName)
        .toList()
      ..sort((a, b) => a.daysRemaining.compareTo(b.daysRemaining));
  }

  @override
  Future<void> removeDeal(String dealId) async {
    await _delay();
    final idx = _deals.indexWhere((d) => d.id == dealId);
    if (idx == -1) throw const NotFoundException('Deal tidak ditemukan.');
    _deals[idx] = _deals[idx].copyWith(status: DealStatus.removed);
  }

  @override
  Future<Claim> claim(String dealId) async {
    await _delay();
    final idx = _deals.indexWhere((d) => d.id == dealId);
    if (idx == -1) throw const ConflictException('Deal tidak tersedia.');
    final deal = _deals[idx];
    if (deal.status != DealStatus.active || deal.remainingStock <= 0) {
      throw const ConflictException('Stok sudah habis.');
    }
    final newRemaining = deal.remainingStock - 1;
    _deals[idx] = deal.copyWith(
      remainingStock: newRemaining,
      status: newRemaining == 0 ? DealStatus.soldOut : DealStatus.active,
    );
    final code = 'HT-${1000 + _rand.nextInt(8999)}';
    final claimRecord = Claim(
      code: code,
      dealId: dealId,
      status: ClaimStatus.claimed,
      createdAt: DateTime.now(),
      itemName: deal.itemName,
      shopName: deal.shopName,
      priceToPay: deal.dealPrice,
    );
    _claims.insert(0, claimRecord);
    return claimRecord;
  }

  @override
  Future<Claim> redeem(String code) async {
    await _delay();
    final normalized = code.trim().toUpperCase();
    final idx = _claims.indexWhere((c) => c.code.toUpperCase() == normalized);
    if (idx == -1) {
      throw const NotFoundException();
    }
    final claim = _claims[idx];
    if (claim.status == ClaimStatus.redeemed) {
      throw ConflictException(
        'Kode ini sudah digunakan pada '
        '${claim.redeemedAt != null ? _timeOfDay(claim.redeemedAt!) : "sebelumnya"}.',
      );
    }
    final dealExists = _deals.any((d) => d.id == claim.dealId && d.status != DealStatus.removed);
    if (!dealExists) {
      throw const ConflictException('Deal ini sudah dihapus.');
    }
    final updated = claim.copyWith(status: ClaimStatus.redeemed, redeemedAt: DateTime.now());
    _claims[idx] = updated;
    return updated;
  }

  @override
  Future<List<Claim>> listClaimsForConsumer() async {
    await _delay();
    return List.of(_claims)..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  }

  @override
  Future<List<Claim>> listClaimsForDeal(String dealId) async {
    await _delay();
    return _claims.where((c) => c.dealId == dealId).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  }

  String _timeOfDay(DateTime dt) =>
      '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')} hari ini';
}

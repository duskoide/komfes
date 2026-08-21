import 'dart:math';
import '../models/enums.dart';
import '../models/recommendation.dart';
import 'app_exception.dart';

abstract class RecommendRepository {
  Future<RecommendResult> recommend(ItemInputDraft input);
}

class MockRecommendRepository implements RecommendRepository {
  @override
  Future<RecommendResult> recommend(ItemInputDraft input) async {
    await Future.delayed(const Duration(milliseconds: 2200));

    ItemInputDraft draft = input;
    if (input.freeText != null && input.freeText!.trim().isNotEmpty) {
      draft = _parseFreeText(input.freeText!);
      if (!draft.isStructuredComplete) {
        final missing = <String>[];
        if (draft.dailySales == null) missing.add('daily_sales');
        if (draft.category == null) missing.add('category');
        if (draft.cost == null) missing.add('cost');
        if (draft.stock == null) missing.add('stock');
        if (draft.originalPrice == null) missing.add('original_price');
        if (draft.daysRemaining == null) missing.add('days_remaining');
        return RecommendResult(
          status: RecommendResultStatus.needsConfirmation,
          parsedInput: draft,
          missingFields: missing,
        );
      }
    }

    final cost = draft.cost!;
    final price = draft.originalPrice!;
    final stock = draft.stock!;
    final daysRemaining = draft.daysRemaining!;
    final dailySales = draft.dailySales!;

    if (daysRemaining < 0) {
      return const RecommendResult(
        status: RecommendResultStatus.invalidInput,
        message: 'Barang sudah kadaluarsa. Sebaiknya dibuang atau didonasikan.',
      );
    }
    if (cost >= price) {
      return RecommendResult(
        status: RecommendResultStatus.invalidInput,
        message:
            'Harga modal (${_rp(cost)}) sama atau lebih besar dari harga jual (${_rp(price)}). '
            'Diskon akan membuatmu rugi.',
      );
    }

    final projectedNormalSales = dailySales * (daysRemaining <= 0 ? 1 : daysRemaining);
    final pressure = stock / (projectedNormalSales == 0 ? 1 : projectedNormalSales);

    if (pressure < 0.9 && daysRemaining > 3) {
      return RecommendResult(
        status: RecommendResultStatus.noAction,
        message: 'Barang ini kemungkinan terjual normal sebelum kadaluarsa.',
        reassessInDays: max(1, (daysRemaining - 2).round()),
      );
    }

    var discount = (15 + pressure * 20 + (daysRemaining <= 1 ? 15 : 0)).clamp(10, 70);
    discount = (discount / 5).round() * 5;
    var recommendedPrice = (price * (1 - discount / 100)).round();
    final floor = cost + 500;
    if (recommendedPrice < floor) {
      recommendedPrice = floor;
      discount = (100 - (recommendedPrice / price * 100)).round();
    }

    final sellThroughUnits = min(stock, (stock * (0.6 + pressure * 0.1)).round());
    final revenue = sellThroughUnits * recommendedPrice;
    final lossIfIgnored =
        ((stock - sellThroughUnits).clamp(0, stock)) * cost + (stock * cost * 0.2).round();

    final timing =
        daysRemaining <= 1 ? 'Mulai diskon hari ini' : 'Bisa tunggu 1 hari, cek lagi besok';
    final confidence = dailySales > 0 && stock > 0 ? 'Cukup yakin' : 'Kurang pasti';

    final itemName = draft.itemName ?? 'Barang';
    final shopName = draft.shopName ?? 'Tokomu';
    final explanation =
        '$itemName punya sisa waktu $daysRemaining hari dengan stok $stock pcs. '
        'Berdasarkan rata-rata penjualan ${dailySales}pcs/hari, diskon ${discount.round()}% '
        'membantu barang terjual sebelum kadaluarsa tanpa membuatmu rugi.';
    final promo =
        '$itemName spesial hari ini! Hemat ${discount.round()}% dari harga normal, stok terbatas.';

    return RecommendResult(
      status: RecommendResultStatus.recommendation,
      normalizedInput: draft,
      recommendation: RecommendationNumbers(
        discountPercent: discount.round(),
        recommendedPrice: recommendedPrice,
        timing: timing,
        expectedSellThrough: '$sellThroughUnits dari $stock pcs',
        expectedRevenue: revenue,
        expectedLossNoAction: lossIfIgnored.round(),
        confidence: confidence,
      ),
      explanation: explanation,
      promoCopy: promo,
      preview: DealPreview(
        itemName: itemName,
        shopName: shopName,
        originalPrice: price,
        dealPrice: recommendedPrice,
        discountPercent: discount.round(),
        daysRemaining: daysRemaining,
        stock: stock,
      ),
    );
  }

  ItemInputDraft _parseFreeText(String text) {
    final lower = text.toLowerCase();

    int? findRupiah(RegExp re) {
      final m = re.firstMatch(lower);
      if (m == null) return null;
      final numStr = m.group(1)!.replaceAll('.', '').replaceAll(',', '');
      var value = double.tryParse(numStr) ?? 0;
      final matched = lower.substring(m.start, m.end);
      if (matched.contains('rb') || matched.contains('ribu')) {
        value *= 1000;
      }
      return value.round();
    }

    final price = findRupiah(RegExp(r'harga\s*(\d+[.,]?\d*)\s*(rb|ribu)?'));
    final cost = findRupiah(RegExp(r'modal\s*(\d+[.,]?\d*)\s*(rb|ribu)?'));

    final stockMatch = RegExp(r'(\d+)\s*(biji|pcs|buah|pack|botol|porsi)').firstMatch(lower);
    final stock = stockMatch != null ? int.tryParse(stockMatch.group(1)!) : null;

    final daysMatch = RegExp(r'exp\s*(\d+)\s*hari').firstMatch(lower);
    int? daysRemaining = daysMatch != null ? int.tryParse(daysMatch.group(1)!) : null;
    if (lower.contains('exp hari ini')) daysRemaining ??= 0;
    if (lower.contains('besok')) daysRemaining ??= 1;

    String? itemName;
    final firstWords = text.trim().split(RegExp(r'\s+'));
    final cut = RegExp(r'\d').firstMatch(text);
    itemName = cut != null ? text.substring(0, cut.start).trim() : firstWords.take(3).join(' ');
    if (itemName.isEmpty) itemName = firstWords.take(2).join(' ');

    ItemCategory? category;
    if (lower.contains('roti') || lower.contains('kue')) {
      category = ItemCategory.bakery;
    } else {
      for (final c in ItemCategory.values) {
        // Dicocokkan dengan label Indonesia — teks bebas vendor tidak
        // pernah memakai istilah Inggris dari kontrak API.
        if (lower.contains(c.label.toLowerCase().split(' ').first)) {
          category = c;
          break;
        }
      }
    }

    String? shopName;
    final tokoMatch = RegExp(r'toko\s+([a-z ]+)$').firstMatch(lower);
    if (tokoMatch != null) shopName = 'Toko ${tokoMatch.group(1)!.trim()}';

    return ItemInputDraft(
      freeText: text,
      itemName: itemName,
      category: category,
      originalPrice: price,
      cost: cost,
      stock: stock,
      daysRemaining: daysRemaining,
      dailySales: null, // hampir selalu tidak ada di kalimat bebas -> confirm
      totalShelfLife: category?.defaultShelfLifeDays,
      shopName: shopName,
    );
  }

  String _rp(int v) => 'Rp${v.toString().replaceAllMapped(
        RegExp(r'\B(?=(\d{3})+(?!\d))'),
        (m) => '.',
      )}';
}

/// Implementasi alternatif untuk menguji state "server AI mati" dari
/// UI secara sengaja, tanpa mengubah kode produksi.
class SimulatedModelDownRepository implements RecommendRepository {
  @override
  Future<RecommendResult> recommend(ItemInputDraft input) async {
    await Future.delayed(const Duration(milliseconds: 1500));
    throw const ModelUnavailableException();
  }
}

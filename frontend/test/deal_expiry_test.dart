import 'package:flutter_test/flutter_test.dart';
import 'package:hargaturun/models/deal.dart';
import 'package:hargaturun/models/enums.dart';

Deal _deal({required double daysRemaining}) {
  return Deal(
    id: 'x',
    itemName: 'Roti',
    shopName: 'Toko',
    category: ItemCategory.bakery,
    originalPrice: 15000,
    dealPrice: 10000,
    discountPercent: 30,
    daysRemaining: daysRemaining,
    initialStock: 10,
    remainingStock: 8,
    promoCopy: '',
    status: DealStatus.active,
    createdAt: DateTime.now(),
  );
}

void main() {
  DateTime today() {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  group('Deal.expiryDate', () {
    test('kadaluarsa hari ini saat sisa hari <= 0', () {
      expect(_deal(daysRemaining: 0).expiryDate, today());
    });

    test('sisa < 1 hari tetap dihitung hari ini', () {
      expect(_deal(daysRemaining: 0.4).expiryDate, today());
    });

    test('sisa 1 hari -> besok', () {
      expect(
        _deal(daysRemaining: 1).expiryDate,
        today().add(const Duration(days: 1)),
      );
    });

    test('sisa 3 hari -> 3 hari dari hari ini', () {
      expect(
        _deal(daysRemaining: 3).expiryDate,
        today().add(const Duration(days: 3)),
      );
    });
  });

  group('Deal.expiryLabel', () {
    test('format tanggal Indonesia singkat "d MMM yyyy"', () {
      final d = _deal(daysRemaining: 2);
      final expiry = d.expiryDate;
      const months = [
        'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
        'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des',
      ];
      expect(
        d.expiryLabel,
        '${expiry.day} ${months[expiry.month - 1]} ${expiry.year}',
      );
    });
  });
}

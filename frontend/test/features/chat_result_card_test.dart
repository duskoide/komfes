import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hargaturun/core/theme/app_theme.dart';
import 'package:hargaturun/features/vendor/chat_result_card.dart';
import 'package:hargaturun/models/recommendation.dart';

import '../support/chat_fixtures.dart';

void main() {
  Future<void> pumpCard(WidgetTester tester, RecommendResult result) async {
    await tester.binding.setSurfaceSize(const Size(500, 1600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: SingleChildScrollView(child: ChatResultCard(result: result)),
        ),
      ),
    );
    await tester.pump();
  }

  group('rekomendasi', () {
    testWidgets('menampilkan angka apa adanya dari server', (tester) async {
      await pumpCard(tester, recommendationTurn().result!);

      expect(find.text('Rp10.500'), findsOneWidget);
      expect(find.text('Diskon 30%'), findsOneWidget);
      expect(find.text('Rp15.000'), findsOneWidget);
      expect(find.text('Mulai diskon hari ini'), findsOneWidget);
      expect(find.textContaining('8 dari 10 pcs'), findsOneWidget);
      expect(find.textContaining('Rp84.000'), findsOneWidget);
      expect(find.textContaining('Rp50.000'), findsOneWidget);
    });

    testWidgets('menampilkan penjelasan dan teks promo', (tester) async {
      await pumpCard(tester, recommendationTurn().result!);

      expect(
        find.text('Sisa dua hari dan stok sepuluh, diskon dibutuhkan.'),
        findsOneWidget,
      );
      expect(
        find.text('Roti tawar diskon 30% hari ini saja!'),
        findsOneWidget,
      );
    });

    testWidgets('keyakinan ditampilkan sebagai kata, bukan persentase',
        (tester) async {
      await pumpCard(tester, recommendationTurn().result!);

      expect(find.text('Prediksi Cukup yakin'), findsOneWidget);
      // Keyakinan tidak boleh muncul sebagai angka persen di mana pun.
      expect(find.textContaining(RegExp(r'Prediksi.*%')), findsNothing);
      expect(find.textContaining(RegExp(r'keyakinan.*\d')), findsNothing);
    });

    testWidgets('tidak ada aksi publikasi di babak penyisihan', (tester) async {
      await pumpCard(tester, recommendationTurn().result!);

      expect(find.textContaining('Publikasi'), findsNothing);
      expect(find.textContaining('Publikasikan'), findsNothing);
    });
  });

  group('belum perlu diskon', () {
    testWidgets('bernada tenang dan menyebut kapan dicek lagi', (tester) async {
      await pumpCard(tester, noActionTurn().result!);

      expect(find.text('Belum perlu diskon'), findsOneWidget);
      expect(find.text('Cek lagi dalam 5 hari.'), findsOneWidget);
      // Bukan layar error: ikonnya bukan ikon kesalahan.
      expect(find.byIcon(Icons.error_outline), findsNothing);
      expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);
    });
  });

  group('peringatan input', () {
    testWidgets('menampilkan angka yang bermasalah tanpa angka diskon apa pun',
        (tester) async {
      await pumpCard(tester, invalidInputTurn().result!);

      expect(find.textContaining('Rp15.000'), findsOneWidget);
      expect(find.textContaining('Rp12.000'), findsOneWidget);
      expect(find.textContaining('Diskon'), findsNothing);
    });
  });

  group('hasil basi', () {
    test('hasil dengan revisi berbeda tidak pernah diadopsi', () {
      // Vendor mengoreksi sesuatu, revisi state naik ke 3, tapi hasil yang
      // ada masih milik revisi 2. Hasil itu harus dianggap tidak ada.
      final stale = recommendationTurn(revision: 3, resultRevision: 2);
      expect(stale.freshResult, isNull);
      expect(stale.state.hasFreshResult, isFalse);

      final fresh = recommendationTurn(revision: 2, resultRevision: 2);
      expect(fresh.freshResult, isNotNull);
      expect(fresh.state.hasFreshResult, isTrue);
    });
  });
}

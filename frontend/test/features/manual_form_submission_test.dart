import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:hargaturun/core/routing/route_paths.dart';
import 'package:hargaturun/core/theme/app_theme.dart';
import 'package:hargaturun/features/vendor/check_item_screen.dart';
import 'package:hargaturun/features/vendor/confirm_data_screen.dart';
import 'package:hargaturun/models/enums.dart';
import 'package:hargaturun/models/recommendation.dart';
import 'package:hargaturun/services/recommend_repository.dart';
import 'package:hargaturun/state/repository_providers.dart';

class _ManualRepository implements RecommendRepository {
  _ManualRepository(this.result);
  final RecommendResult result;

  @override
  Future<RecommendResult> recommend(ItemInputDraft input) async => result;
}

ItemInputDraft _draft() => ItemInputDraft(
      itemName: 'Roti Tawar',
      category: ItemCategory.bakery,
      stock: 20,
      daysRemaining: 2,
      originalPrice: 15000,
      cost: 10000,
      dailySales: 2,
      totalShelfLife: 4,
    );

RecommendResult _recommendation() {
  final input = _draft();
  return RecommendResult(
    status: RecommendResultStatus.recommendation,
    normalizedInput: input,
    recommendation: const RecommendationNumbers(
      discountPercent: 20,
      recommendedPrice: 12000,
      timing: 'Hari ini',
      expectedSellThrough: '18 dari 20 pcs',
      expectedRevenue: 216000,
      expectedLossNoAction: 10000,
      confidence: 'Cukup yakin',
    ),
    explanation: 'Aman.',
    promoCopy: 'Promo.',
    preview: DealPreview(
      itemName: input.itemName!,
      shopName: 'Tokomu',
      originalPrice: input.originalPrice!,
      dealPrice: 12000,
      discountPercent: 20,
      daysRemaining: input.daysRemaining!,
      stock: input.stock!,
    ),
  );
}

RecommendResult _needsConfirmation() => RecommendResult(
      status: RecommendResultStatus.needsConfirmation,
      parsedInput: _draft(),
    );

Widget _app(GoRouter router, RecommendResult result) => ProviderScope(
      overrides: [recommendRepositoryProvider.overrideWithValue(_ManualRepository(result))],
      child: MaterialApp.router(theme: AppTheme.light, routerConfig: router),
    );

void main() {
  testWidgets('blank manual form can be filled and submitted', (tester) async {
    final router = GoRouter(
      initialLocation: RoutePaths.vendorManualForm,
      routes: [
        GoRoute(path: RoutePaths.vendorManualForm, builder: (_, __) => const CheckItemScreen()),
        GoRoute(path: RoutePaths.vendorResult, builder: (_, __) => const Text('Result')),
      ],
    );
    await tester.pumpWidget(_app(router, _recommendation()));
    await tester.pumpAndSettle();

    final fields = find.byType(TextField);
    await tester.enterText(fields.at(0), 'Roti Tawar');
    await tester.tap(find.byType(DropdownButton<ItemCategory>).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Bakery').last, warnIfMissed: false);
    await tester.pumpAndSettle();
    final selectedCategory = tester.widget<DropdownButton<ItemCategory>>(
      find.byType(DropdownButton<ItemCategory>).first,
    ).value;
    expect(selectedCategory, ItemCategory.bakery);

    await tester.enterText(fields.at(1), '20');
    await tester.enterText(fields.at(2), '2');
    await tester.enterText(fields.at(3), '15000');
    await tester.enterText(fields.at(4), '10000');
    await tester.enterText(fields.at(5), '2');
    await tester.pump();


    expect(find.bySemanticsLabel('Jumlah stok'), findsOneWidget);
    expect(find.bySemanticsLabel('Sisa waktu (hari)'), findsOneWidget);
    expect(find.bySemanticsLabel('Harga jual sekarang'), findsOneWidget);
    expect(find.bySemanticsLabel('Harga modal'), findsOneWidget);
    expect(find.bySemanticsLabel('Rata-rata terjual per hari'), findsOneWidget);
    expect(find.text('Dapatkan Rekomendasi'), findsOneWidget);
    final submit = find.widgetWithText(ElevatedButton, 'Dapatkan Rekomendasi');
    expect(submit, findsOneWidget);
    expect(tester.widget<ElevatedButton>(submit).onPressed, isNotNull);
    await tester.tap(submit);
    await tester.pumpAndSettle();
    expect(router.routeInformationProvider.value.uri.path, RoutePaths.vendorResult);
  });

  testWidgets('needs confirmation reaches dedicated processing route', (tester) async {
    final router = GoRouter(
      initialLocation: RoutePaths.vendorManualForm,
      routes: [
        GoRoute(
          path: RoutePaths.vendorManualForm,
          builder: (_, __) => CheckItemScreen(prefill: _draft()),
        ),
        GoRoute(
          path: RoutePaths.vendorManualConfirm,
          builder: (_, __) => const ConfirmDataScreen(),
        ),
        GoRoute(
          path: RoutePaths.vendorManualProcessing,
          builder: (_, __) => const Text('Processing'),
        ),
      ],
    );
    await tester.pumpWidget(_app(router, _needsConfirmation()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Dapatkan Rekomendasi'));
    await tester.pumpAndSettle();
    expect(router.routeInformationProvider.value.uri.path, RoutePaths.vendorManualConfirm);
    await tester.tap(find.text('Hitung Sekarang'));
    await tester.pumpAndSettle();
    expect(router.routeInformationProvider.value.uri.path, RoutePaths.vendorManualProcessing);
  });
}

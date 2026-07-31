import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/breakpoints.dart';
import '../../core/utils/currency_formatter.dart';
import '../../models/deal.dart';
import '../../models/enums.dart';
import '../../state/deal_providers.dart';
import '../../state/recommend_providers.dart';
import '../../state/repository_providers.dart';
import '../../widgets/ai_explanation_card.dart';
import '../../widgets/app_bottom_sheet.dart';
import '../../widgets/deal_card.dart';
import '../../widgets/rupiah_field.dart';
import '../../widgets/stat_card.dart';
import '../../widgets/sticky_bottom_bar.dart';

class RecommendationResultScreen extends ConsumerStatefulWidget {
  const RecommendationResultScreen({super.key});

  @override
  ConsumerState<RecommendationResultScreen> createState() => _RecommendationResultScreenState();
}

class _RecommendationResultScreenState extends ConsumerState<RecommendationResultScreen> {
  late final TextEditingController _priceController;
  late final TextEditingController _promoController;
  bool _publishing = false;
  String? _priceError;

  @override
  void initState() {
    super.initState();
    final flow = ref.read(recommendFlowProvider);
    final rec = flow.result!.recommendation!;
    _priceController = TextEditingController(text: CurrencyFormatter.formatDigitsOnly(rec.recommendedPrice));
    _promoController = TextEditingController(text: flow.result!.promoCopy ?? '');
  }

  void _validatePrice() {
    final flow = ref.read(recommendFlowProvider);
    final input = flow.result!.normalizedInput!;
    final price = CurrencyFormatter.parseDigits(_priceController.text);
    setState(() {
      if (isPriceBelowFloor(price: price, cost: input.cost!)) {
        _priceError =
            'Harga di bawah modal + Rp500. Minimal ${CurrencyFormatter.format(input.cost! + 500)}.';
      } else {
        _priceError = null;
      }
    });
  }

  Future<void> _openPublishConfirm(Deal previewDeal) async {
    final confirmed = await showAppBottomSheet<bool>(
      context: context,
      builder: (context) => _PublishConfirmSheet(deal: previewDeal),
    );
    if (confirmed != true) return;

    setState(() => _publishing = true);
    try {
      final published = await ref.read(dealRepositoryProvider).publish(
            itemName: previewDeal.itemName,
            shopName: previewDeal.shopName,
            category: previewDeal.category,
            originalPrice: previewDeal.originalPrice,
            dealPrice: previewDeal.dealPrice,
            discountPercent: previewDeal.discountPercent,
            daysRemaining: previewDeal.daysRemaining,
            initialStock: previewDeal.initialStock,
            promoCopy: previewDeal.promoCopy,
            cost: previewDeal.cost,
          );
      if (!mounted) return;
      ref.read(recommendFlowProvider.notifier).recordPublished(published);
      ref.invalidate(allVendorDealsProvider);
      ref.invalidate(vendorDealsProvider);
      _showPublishedSnackbar(published);
      ref.read(recommendFlowProvider.notifier).reset();
      context.go(RoutePaths.vendorDeals);
    } finally {
      if (mounted) setState(() => _publishing = false);
    }
  }

  void _showPublishedSnackbar(Deal deal) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${deal.itemName} berhasil dipublikasikan.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final flow = ref.watch(recommendFlowProvider);
    final result = flow.result!;
    final rec = result.recommendation!;
    final input = result.normalizedInput!;
    final isTablet = Breakpoints.isTabletLandscapeOf(context);

    final currentPrice = CurrencyFormatter.parseDigits(_priceController.text);
    final currentDiscount = input.originalPrice! > 0
        ? (100 - (currentPrice / input.originalPrice! * 100)).round().clamp(0, 99)
        : rec.discountPercent;

    final previewDeal = Deal(
      id: 'preview',
      itemName: input.itemName!,
      shopName: input.shopName ?? 'Tokomu',
      category: input.category!,
      originalPrice: input.originalPrice!,
      dealPrice: currentPrice,
      discountPercent: currentDiscount,
      daysRemaining: input.daysRemaining!.toDouble(),
      initialStock: input.stock!,
      remainingStock: input.stock!,
      promoCopy: _promoController.text,
      status: DealStatus.active,
      createdAt: DateTime.now(),
      cost: input.cost,
    );

    final numbers = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${rec.discountPercent}% off', style: AppTypography.displayNumber),
        const SizedBox(height: 4),
        Text(
          '${CurrencyFormatter.format(rec.recommendedPrice)} dari ${CurrencyFormatter.format(input.originalPrice!)}',
          style: AppTypography.body.copyWith(color: AppColors.textSecondary),
        ),
        const SizedBox(height: AppSpacing.md),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
          decoration: BoxDecoration(
            color: AppColors.surfaceAlt,
            borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
          ),
          child: Row(
            children: [
              const Icon(Icons.schedule, size: 16, color: AppColors.textSecondary),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: Text(rec.timing, style: AppTypography.bodyStrong)),
            ],
          ),
        ),
      ],
    );

    final statRow = Row(
      children: [
        Expanded(child: StatCard(value: rec.expectedSellThrough, label: 'Perkiraan terjual')),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: StatCard(
            value: CurrencyFormatter.format(rec.expectedRevenue),
            label: 'Perkiraan pendapatan',
            valueColor: AppColors.aman,
          ),
        ),
      ],
    );

    final lossCard = Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.kritisBg,
        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
      ),
      child: Row(
        children: [
          const Icon(Icons.trending_down, color: AppColors.kritis),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              'Kalau dibiarkan tanpa diskon, potensi rugi ${CurrencyFormatter.format(rec.expectedLossNoAction)}.',
              style: AppTypography.body.copyWith(color: AppColors.kritis),
            ),
          ),
        ],
      ),
    );

    final confidenceRow = Row(
      children: [
        Icon(
          rec.isHighConfidence ? Icons.verified : Icons.info_outline,
          size: 16,
          color: AppColors.textSecondary,
        ),
        const SizedBox(width: 4),
        Text('Tingkat keyakinan: ${rec.confidence}', style: AppTypography.caption),
      ],
    );

    final editableSection = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Sesuaikan kalau perlu', style: AppTypography.h3),
        const SizedBox(height: AppSpacing.sm),
        RupiahField(
          controller: _priceController,
          label: 'Harga diskon',
          errorText: _priceError,
          onChanged: (_) => _validatePrice(),
        ),
        const SizedBox(height: AppSpacing.lg),
        TextField(
          controller: _promoController,
          maxLines: 3,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(labelText: 'Kalimat promosi'),
        ),
      ],
    );

    final previewSection = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Pratinjau untuk pembeli', style: AppTypography.h3),
        const SizedBox(height: AppSpacing.sm),
        DealCard(deal: previewDeal, audience: DealCardAudience.consumer, density: DealCardDensity.lengkap),
      ],
    );

    final left = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        numbers,
        const SizedBox(height: AppSpacing.xl),
        statRow,
        const SizedBox(height: AppSpacing.md),
        lossCard,
        const SizedBox(height: AppSpacing.md),
        confidenceRow,
        const SizedBox(height: AppSpacing.xl),
        AiExplanationCard(text: result.explanation ?? ''),
        const SizedBox(height: AppSpacing.xxl),
        editableSection,
      ],
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Rekomendasi Harga'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () {
            ref.read(recommendFlowProvider.notifier).reset();
            context.go(RoutePaths.vendorHome);
          },
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(AppSpacing.xl, AppSpacing.lg, AppSpacing.xl, AppSpacing.xxxl),
        child: isTablet
            ? Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: left),
                  const SizedBox(width: AppSpacing.xxl),
                  Expanded(child: previewSection),
                ],
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [left, const SizedBox(height: AppSpacing.xxl), previewSection],
              ),
      ),
      bottomNavigationBar: StickyBottomBar(
        child: SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: _priceError == null && !_publishing
                ? () => _openPublishConfirm(previewDeal)
                : null,
            child: _publishing
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Publikasikan Sekarang'),
          ),
        ),
        secondaryChild: TextButton(
          onPressed: () {
            context.pushReplacement(RoutePaths.vendorCheckItem, extra: input);
          },
          child: const Text('Ubah Input'),
        ),
      ),
    );
  }
}

/// V-08 — konfirmasi terakhir sebelum tayang publik, sebagai bottom sheet.
class _PublishConfirmSheet extends StatelessWidget {
  const _PublishConfirmSheet({required this.deal});
  final Deal deal;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Publikasikan deal ini?', style: AppTypography.h2),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Deal akan langsung tayang dan bisa diklaim pembeli. '
          'Pastikan harga dan stok sudah benar — tidak bisa diedit setelah tayang.',
          style: AppTypography.body.copyWith(color: AppColors.textSecondary),
        ),
        const SizedBox(height: AppSpacing.lg),
        DealCard(deal: deal, audience: DealCardAudience.consumer, density: DealCardDensity.lengkap),
        const SizedBox(height: AppSpacing.xl),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Batal'),
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: ElevatedButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Ya, Publikasikan'),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

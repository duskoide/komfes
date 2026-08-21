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

    // Urutan visual mengikuti §V-05: harga rekomendasi paling besar,
    // diskon jadi badge, harga asli dicoret dan lebih kecil.
    final numbers = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          CurrencyFormatter.format(rec.recommendedPrice),
          style: AppTypography.displayNumber,
        ),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.xs,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.xs,
              ),
              decoration: BoxDecoration(
                color: AppColors.primaryLight,
                borderRadius: BorderRadius.circular(AppSpacing.radiusPill),
              ),
              child: Text(
                'Diskon ${rec.discountPercent}%',
                style: AppTypography.bodyStrong.copyWith(color: AppColors.primary),
              ),
            ),
            Text('·', style: AppTypography.body.copyWith(color: AppColors.textDisabled)),
            const Text('harga asli', style: AppTypography.caption),
            Text(
              CurrencyFormatter.format(input.originalPrice!),
              style: AppTypography.strikethrough,
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.lg),
        _TimingChip(timing: rec.timing, daysRemaining: input.daysRemaining ?? 0),
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
        const Text('Sesuaikan kalau perlu', style: AppTypography.h3),
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
        const Text('Pratinjau untuk pembeli', style: AppTypography.h3),
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
        secondaryChild: TextButton(
          onPressed: () {
            context.pushReplacement(RoutePaths.vendorCheckItem, extra: input);
          },
          child: const Text('Ubah Input'),
        ),
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
      ),
    );
  }
}

/// Chip "waktu mulai" dengan warna sistem urgensi (§2.4 dan §V-05 poin 2).
///
/// Warna hanya soal penyajian — teksnya tetap berasal dari server, dan
/// selalu ada ikon + kata, tidak pernah warna saja (§2.5).
class _TimingChip extends StatelessWidget {
  const _TimingChip({required this.timing, required this.daysRemaining});

  final String timing;
  final int daysRemaining;

  @override
  Widget build(BuildContext context) {
    final (fg, bg, icon) = switch (daysRemaining) {
      <= 1 => (AppColors.kritis, AppColors.kritisBg, Icons.priority_high_rounded),
      <= 3 => (AppColors.perhatian, AppColors.perhatianBg, Icons.schedule_rounded),
      _ => (AppColors.aman, AppColors.amanBg, Icons.event_available_rounded),
    };

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: fg),
          const SizedBox(width: AppSpacing.sm),
          Flexible(
            child: Text(
              timing,
              style: AppTypography.bodyStrong.copyWith(color: fg),
            ),
          ),
        ],
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
        const Text('Publikasikan deal ini?', style: AppTypography.h2),
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

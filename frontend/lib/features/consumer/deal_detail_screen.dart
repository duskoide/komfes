import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/breakpoints.dart';
import '../../core/utils/category_icons.dart';
import '../../models/enums.dart';
import '../../services/app_exception.dart';
import '../../state/deal_providers.dart';
import '../../state/session_providers.dart';
import '../../widgets/price_block.dart';
import '../../widgets/sticky_bottom_bar.dart';
import '../../widgets/urgency_chip.dart';

class ConsumerDealDetailScreen extends ConsumerWidget {
  const ConsumerDealDetailScreen({super.key, required this.dealId});
  final String dealId;

  Future<void> _handleClaim(BuildContext context, WidgetRef ref) async {
    final isLoggedIn = ref.read(isLoggedInProvider);
    if (!isLoggedIn) {
      context.push(RoutePaths.phone, extra: {'context': 'claim', 'dealId': dealId});
      return;
    }
    final code = await ref.read(claimActionProvider.notifier).claim(dealId);
    if (!context.mounted) return;
    if (code != null) {
      context.pushReplacement(RoutePaths.consumerClaimCodePath(code));
    } else {
      final err = ref.read(claimActionProvider);
      final message = err.hasError && err.error is ConflictException
          ? (err.error as ConflictException).message
          : 'Stok sudah habis atau deal tidak tersedia lagi.';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      ref.invalidate(dealByIdProvider(dealId));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dealAsync = ref.watch(dealByIdProvider(dealId));
    final claimState = ref.watch(claimActionProvider);
    final isTablet = Breakpoints.isTabletOf(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Detail Deal')),
      body: dealAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => const Center(child: Text('Gagal memuat data.')),
        data: (deal) {
          if (deal == null) return const Center(child: Text('Deal tidak ditemukan.'));

          final content = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(categoryEmoji(deal.category), style: const TextStyle(fontSize: 36)),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(deal.itemName, style: AppTypography.h1),
                        Text(deal.shopName, style: AppTypography.body.copyWith(color: AppColors.textSecondary)),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),
              Row(
                children: [
                  UrgencyChip(level: deal.urgency, label: deal.remainingLabel),
                  const SizedBox(width: AppSpacing.sm),
                  Icon(Icons.inventory_2_outlined, size: 16, color: AppColors.textSecondary),
                  const SizedBox(width: 4),
                  Text('Stok ${deal.remainingStock}', style: AppTypography.caption),
                ],
              ),
              const SizedBox(height: AppSpacing.xl),
              PriceBlock(
                dealPrice: deal.dealPrice,
                originalPrice: deal.originalPrice,
                discountPercent: deal.discountPercent,
              ),
              const SizedBox(height: AppSpacing.xl),
              if (deal.promoCopy.isNotEmpty) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceAlt,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
                  ),
                  child: Text(deal.promoCopy, style: AppTypography.body),
                ),
                const SizedBox(height: AppSpacing.xl),
              ],
              Text(
                'Ambil langsung di toko. Tunjukkan kode klaim ke penjual saat pengambilan.',
                style: AppTypography.caption,
              ),
            ],
          );

          return SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: isTablet
                ? Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 640), child: content))
                : content,
          );
        },
      ),
      bottomNavigationBar: dealAsync.maybeWhen(
        data: (deal) {
          if (deal == null) return null;
          final soldOut = deal.isSoldOut || deal.status != DealStatus.active;
          return StickyBottomBar(
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: soldOut || claimState.isLoading ? null : () => _handleClaim(context, ref),
                child: claimState.isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : Text(soldOut ? 'Stok Habis' : 'Klaim Sekarang'),
              ),
            ),
          );
        },
        orElse: () => null,
      ),
    );
  }
}

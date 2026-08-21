import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/breakpoints.dart';
import '../../models/enums.dart';
import '../../state/deal_providers.dart';
import '../../state/session_providers.dart';
import '../../state/verify_providers.dart';
import '../../widgets/stat_card.dart';
import '../../widgets/urgency_chip.dart';

class VendorDashboardScreen extends ConsumerWidget {
  const VendorDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    final dealsAsync = ref.watch(allVendorDealsProvider);
    final pendingClaimsAsync = ref.watch(pendingClaimsProvider);
    final shopName = session?.shop?.shopName ?? 'Tokomu';
    final isTablet = Breakpoints.isTabletLandscapeOf(context);

    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false, title: Text('Halo, $shopName')),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(allVendorDealsProvider);
          ref.invalidate(pendingClaimsProvider);
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: dealsAsync.when(
            loading: () => const _DashboardSkeleton(),
            error: (e, st) => _ErrorRetry(onRetry: () => ref.invalidate(allVendorDealsProvider)),
            data: (deals) {
              final hasAnyDeal = deals.isNotEmpty;
              final actionButton = _CheckItemButton();

              if (!hasAnyDeal) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    actionButton,
                    const SizedBox(height: AppSpacing.xxl),
                    Container(
                      padding: const EdgeInsets.all(AppSpacing.xl),
                      decoration: BoxDecoration(
                        color: AppColors.primaryLight,
                        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Belum ada deal.', style: AppTypography.h3),
                          const SizedBox(height: 4),
                          Text(
                            'Coba cek barang yang mau kadaluarsa.',
                            style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                          ),
                        ],
                      ),
                    ),
                  ],
                );
              }

              final active = deals.where((d) => d.status == DealStatus.active).toList();
              final totalStock = active.fold<int>(0, (a, d) => a + d.remainingStock);
              final pendingCount = pendingClaimsAsync.maybeWhen(
                data: (c) => c.length,
                orElse: () => 0,
              );
              final needsAttention = List.of(active)
                ..sort((a, b) => a.daysRemaining.compareTo(b.daysRemaining));

              final summary = Row(
                children: [
                  Expanded(child: StatCard(value: '${active.length}', label: 'Deal aktif')),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(child: StatCard(value: '$totalStock', label: 'Barang menunggu pembeli')),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: StatCard(
                      value: '$pendingCount',
                      label: 'Perlu diverifikasi',
                      valueColor: pendingCount > 0 ? AppColors.perhatian : null,
                    ),
                  ),
                ],
              );

              final attentionList = Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Perlu perhatian', style: AppTypography.h3),
                  const SizedBox(height: AppSpacing.sm),
                  ...needsAttention.take(3).map((d) => Card(
                        margin: const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: ListTile(
                          onTap: () => context.push(RoutePaths.vendorDealDetailPath(d.id)),
                          title: Text(d.itemName, maxLines: 1, overflow: TextOverflow.ellipsis),
                          subtitle: Text('${d.remainingStock} dari ${d.initialStock} tersisa'),
                          trailing: UrgencyChip(level: d.urgency, label: d.remainingLabel),
                        ),
                      )),
                ],
              );

              final claimsList = pendingClaimsAsync.maybeWhen(
                data: (claims) => claims.isEmpty
                    ? const SizedBox.shrink()
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Klaim masuk', style: AppTypography.h3),
                          const SizedBox(height: AppSpacing.sm),
                          ...claims.take(3).map((c) => Card(
                                margin: const EdgeInsets.only(bottom: AppSpacing.sm),
                                child: ListTile(
                                  leading: const Icon(Icons.confirmation_number_outlined),
                                  title: Text(c.code, style: AppTypography.bodyStrong),
                                  subtitle: Text(c.itemName ?? ''),
                                  trailing: FilledButton(
                                    onPressed: () => context.push(RoutePaths.vendorVerify),
                                    child: const Text('Verifikasi'),
                                  ),
                                ),
                              )),
                        ],
                      ),
                orElse: () => const SizedBox.shrink(),
              );

              if (isTablet) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [actionButton, const SizedBox(height: AppSpacing.xl), summary],
                      ),
                    ),
                    const SizedBox(width: AppSpacing.xxl),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          attentionList,
                          const SizedBox(height: AppSpacing.xl),
                          claimsList,
                        ],
                      ),
                    ),
                  ],
                );
              }

              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  actionButton,
                  const SizedBox(height: AppSpacing.xl),
                  summary,
                  const SizedBox(height: AppSpacing.xxl),
                  attentionList,
                  const SizedBox(height: AppSpacing.xxl),
                  claimsList,
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Aksi utama vendor — elemen TERBESAR di layar (§V-01), bukan tab.
class _CheckItemButton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: () => context.push(RoutePaths.vendorChat),
        icon: const Icon(Icons.search_rounded),
        label: const Padding(
          padding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
          child: Text('Cek Barang', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
        ),
        style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(72)),
      ),
    );
  }
}

class _DashboardSkeleton extends StatelessWidget {
  const _DashboardSkeleton();

  @override
  Widget build(BuildContext context) {
    Widget box(double h) => Container(
          height: h,
          margin: const EdgeInsets.only(bottom: AppSpacing.md),
          decoration: BoxDecoration(
            color: AppColors.surfaceAlt,
            borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
          ),
        );
    return Column(children: [box(72), box(90), box(80), box(80)]);
  }
}

class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxl),
      child: Column(
        children: [
          const Icon(Icons.wifi_off, size: 40, color: AppColors.textSecondary),
          const SizedBox(height: AppSpacing.md),
          Text('Gagal memuat data.', style: AppTypography.body),
          const SizedBox(height: AppSpacing.md),
          OutlinedButton(onPressed: onRetry, child: const Text('Coba Lagi')),
        ],
      ),
    );
  }
}

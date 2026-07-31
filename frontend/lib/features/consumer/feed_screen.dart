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
import '../../widgets/deal_card.dart';
import '../../widgets/empty_state.dart';

final _categoryFilterProvider = StateProvider.autoDispose<ItemCategory?>((ref) => null);

class ConsumerFeedScreen extends ConsumerWidget {
  const ConsumerFeedScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dealsAsync = ref.watch(consumerFeedProvider);
    final categoryFilter = ref.watch(_categoryFilterProvider);
    final isTablet = Breakpoints.isTabletOf(context);

    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false, title: const Text('Deals Hari Ini')),
      body: Column(
        children: [
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
              children: [
                Padding(
                  padding: const EdgeInsets.only(right: AppSpacing.sm),
                  child: ChoiceChip(
                    label: const Text('Semua'),
                    selected: categoryFilter == null,
                    onSelected: (_) => ref.read(_categoryFilterProvider.notifier).state = null,
                  ),
                ),
                for (final c in ItemCategory.values)
                  Padding(
                    padding: const EdgeInsets.only(right: AppSpacing.sm),
                    child: ChoiceChip(
                      label: Text(c.apiValue),
                      selected: categoryFilter == c,
                      onSelected: (_) => ref.read(_categoryFilterProvider.notifier).state = c,
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.read(consumerFeedProvider.notifier).refresh(),
              child: dealsAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, st) => Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.wifi_off, size: 40, color: AppColors.textSecondary),
                      const SizedBox(height: AppSpacing.md),
                      Text('Gagal memuat deals.', style: AppTypography.body),
                      const SizedBox(height: AppSpacing.md),
                      OutlinedButton(
                        onPressed: () => ref.read(consumerFeedProvider.notifier).refresh(),
                        child: const Text('Coba Lagi'),
                      ),
                    ],
                  ),
                ),
                data: (deals) {
                  final filtered = categoryFilter == null
                      ? deals
                      : deals.where((d) => d.category == categoryFilter).toList();

                  if (filtered.isEmpty) {
                    return SingleChildScrollView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      child: SizedBox(
                        height: 460,
                        child: EmptyState(
                          icon: Icons.local_offer_outlined,
                          title: 'Belum ada deal',
                          description: 'Coba lagi nanti, promo baru muncul setiap hari.',
                        ),
                      ),
                    );
                  }

                  return GridView.builder(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: isTablet ? 2 : 1,
                      mainAxisExtent: 300,
                      mainAxisSpacing: AppSpacing.md,
                      crossAxisSpacing: AppSpacing.md,
                    ),
                    itemCount: filtered.length,
                    itemBuilder: (context, i) {
                      final d = filtered[i];
                      return DealCard(
                        deal: d,
                        audience: DealCardAudience.consumer,
                        onTap: () => context.push(RoutePaths.consumerDealDetailPath(d.id)),
                        onClaimPressed: () => context.push(RoutePaths.consumerDealDetailPath(d.id)),
                      );
                    },
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

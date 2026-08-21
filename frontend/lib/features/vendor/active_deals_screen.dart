import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/breakpoints.dart';
import '../../models/enums.dart';
import '../../state/deal_providers.dart';
import '../../widgets/deal_card.dart';
import '../../widgets/empty_state.dart';

class ActiveDealsScreen extends ConsumerWidget {
  const ActiveDealsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filter = ref.watch(vendorDealFilterProvider);
    final dealsAsync = ref.watch(vendorDealsProvider);
    final isTablet = Breakpoints.isTabletOf(context);

    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false, title: const Text('Deal Saya')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
            child: Row(
              children: [
                _FilterChip(
                  label: 'Aktif',
                  selected: filter == DealStatus.active,
                  onTap: () => ref.read(vendorDealFilterProvider.notifier).state = DealStatus.active,
                ),
                const SizedBox(width: AppSpacing.sm),
                _FilterChip(
                  label: 'Habis',
                  selected: filter == DealStatus.soldOut,
                  onTap: () => ref.read(vendorDealFilterProvider.notifier).state = DealStatus.soldOut,
                ),
                const SizedBox(width: AppSpacing.sm),
                _FilterChip(
                  label: 'Dihapus',
                  selected: filter == DealStatus.removed,
                  onTap: () => ref.read(vendorDealFilterProvider.notifier).state = DealStatus.removed,
                ),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ref.read(vendorDealsProvider.notifier).refresh(),
              child: dealsAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, st) => const Center(child: Text('Gagal memuat data.')),
                data: (deals) {
                  if (deals.isEmpty) {
                    return SingleChildScrollView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      child: SizedBox(
                        height: 480,
                        child: EmptyState(
                          icon: Icons.local_offer_outlined,
                          title: filter == DealStatus.active ? 'Belum ada deal aktif' : 'Belum ada data',
                          description: filter == DealStatus.active
                              ? 'Cek barang yang mau kadaluarsa untuk mulai.'
                              : 'Deal akan muncul di sini sesuai statusnya.',
                          actionLabel: filter == DealStatus.active ? 'Cek Barang' : null,
                          onAction: filter == DealStatus.active
                              ? () => context.push(RoutePaths.vendorCheckItem)
                              : null,
                        ),
                      ),
                    );
                  }
                  return GridView.builder(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.lg,
                      AppSpacing.lg,
                      AppSpacing.lg,
                      AppSpacing.xxxl + AppSpacing.xl,
                    ),
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: isTablet ? 2 : 1,
                      mainAxisExtent: 260,
                      mainAxisSpacing: AppSpacing.md,
                      crossAxisSpacing: AppSpacing.md,
                    ),
                    itemCount: deals.length,
                    itemBuilder: (context, i) {
                      final d = deals[i];
                      return DealCard(
                        deal: d,
                        audience: DealCardAudience.vendor,
                        onTap: () => context.push(RoutePaths.vendorDealDetailPath(d.id)),
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

class _FilterChip extends StatelessWidget {
  const _FilterChip({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(label: Text(label), selected: selected, onSelected: (_) => onTap());
  }
}

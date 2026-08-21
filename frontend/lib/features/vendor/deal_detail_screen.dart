import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/currency_formatter.dart';
import '../../models/deal.dart';
import '../../models/enums.dart';
import '../../state/deal_providers.dart';
import '../../widgets/deal_card.dart';
import '../../widgets/status_chip.dart';

class VendorDealDetailScreen extends ConsumerWidget {
  const VendorDealDetailScreen({super.key, required this.dealId});
  final String dealId;

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref, Deal deal) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Hapus deal ini?'),
        content: Text(
          '"${deal.itemName}" tidak akan tampil lagi untuk pembeli. '
          '${deal.remainingStock > 0 ? "Sisa ${deal.remainingStock} pcs tidak akan bisa diklaim lagi." : ""}',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Batal')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.error),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Ya, Hapus'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(vendorDealsProvider.notifier).removeDeal(deal.id);
      if (context.mounted) context.pop();
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dealAsync = ref.watch(dealByIdProvider(dealId));
    final claimsAsync = ref.watch(claimsForDealProvider(dealId));

    return Scaffold(
      appBar: AppBar(title: const Text('Detail Deal')),
      body: dealAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => const Center(child: Text('Gagal memuat data.')),
        data: (deal) {
          if (deal == null) return const Center(child: Text('Deal tidak ditemukan.'));
          return SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DealCard(deal: deal, audience: DealCardAudience.vendor, density: DealCardDensity.lengkap),
                const SizedBox(height: AppSpacing.xl),
                Text('Data awal', style: AppTypography.h3),
                const SizedBox(height: AppSpacing.sm),
                _kv('Harga modal', deal.cost != null ? CurrencyFormatter.format(deal.cost!) : '—'),
                _kv('Harga asli', CurrencyFormatter.format(deal.originalPrice)),
                _kv('Stok awal', '${deal.initialStock} pcs'),
                _kv('Dipublikasikan', _formatDate(deal.createdAt)),
                const SizedBox(height: AppSpacing.xl),
                Text('Klaim (${deal.claimedCount})', style: AppTypography.h3),
                const SizedBox(height: AppSpacing.sm),
                claimsAsync.when(
                  loading: () => const Padding(
                    padding: EdgeInsets.all(AppSpacing.lg),
                    child: Center(child: CircularProgressIndicator()),
                  ),
                  error: (e, st) => const Text('Gagal memuat klaim.'),
                  data: (claims) {
                    if (claims.isEmpty) {
                      return Text('Belum ada klaim.', style: AppTypography.caption);
                    }
                    return Column(
                      children: [
                        for (final c in claims)
                          Card(
                            margin: const EdgeInsets.only(bottom: AppSpacing.sm),
                            child: ListTile(
                              title: Text(c.code, style: AppTypography.bodyStrong),
                              subtitle: Text(_formatDate(c.createdAt)),
                              trailing: StatusChip.claim(
                                c.status.name == 'redeemed'
                                    ? ClaimStatusChipKind.sudahDiambil
                                    : ClaimStatusChipKind.belumDiambil,
                              ),
                            ),
                          ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: AppSpacing.xxl),
                if (deal.status != DealStatus.removed)
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.error,
                        side: const BorderSide(color: AppColors.error),
                      ),
                      onPressed: () => _confirmDelete(context, ref, deal),
                      child: const Text('Hapus Deal'),
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _kv(String k, String v) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(k, style: AppTypography.caption)),
          Text(v, style: AppTypography.bodyStrong),
        ],
      ),
    );
  }

  String _formatDate(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 60) return '${diff.inMinutes} menit lalu';
    if (diff.inHours < 24) return '${diff.inHours} jam lalu';
    return '${dt.day}/${dt.month}/${dt.year}';
  }
}

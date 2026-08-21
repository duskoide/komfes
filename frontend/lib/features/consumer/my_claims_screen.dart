import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/currency_formatter.dart';
import '../../state/deal_providers.dart';
import '../../state/session_providers.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/status_chip.dart';

class MyClaimsScreen extends ConsumerWidget {
  const MyClaimsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isLoggedIn = ref.watch(isLoggedInProvider);

    if (!isLoggedIn) {
      return Scaffold(
        appBar: AppBar(automaticallyImplyLeading: false, title: const Text('Klaim Saya')),
        body: EmptyState(
          icon: Icons.confirmation_number_outlined,
          title: 'Belum masuk',
          description: 'Masuk untuk melihat riwayat klaimmu.',
          actionLabel: 'Masuk',
          onAction: () => context.push(RoutePaths.phone, extra: {'context': 'claim'}),
        ),
      );
    }

    final claimsAsync = ref.watch(myClaimsProvider);

    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false, title: const Text('Klaim Saya')),
      body: claimsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => const Center(child: Text('Gagal memuat data.')),
        data: (claims) {
          if (claims.isEmpty) {
            return EmptyState(
              icon: Icons.confirmation_number_outlined,
              title: 'Belum ada klaim',
              description: 'Klaim deal pertamamu dan lihat riwayatnya di sini.',
              actionLabel: 'Lihat Deals',
              onAction: () => context.go(RoutePaths.consumerFeed),
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(AppSpacing.lg),
            itemCount: claims.length,
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
            itemBuilder: (context, i) {
              final c = claims[i];
              final isRedeemed = c.status.name == 'redeemed';
              return Card(
                child: ListTile(
                  onTap: () => context.push(RoutePaths.consumerClaimCodePath(c.code)),
                  title: Text(c.itemName ?? c.code, style: AppTypography.bodyStrong),
                  subtitle: Text(
                    '${c.shopName ?? ''}${c.priceToPay != null ? ' • ${CurrencyFormatter.format(c.priceToPay!)}' : ''}',
                  ),
                  trailing: StatusChip.claim(
                    isRedeemed ? ClaimStatusChipKind.sudahDiambil : ClaimStatusChipKind.belumDiambil,
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

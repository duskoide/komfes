import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../models/user.dart';
import '../../services/connectivity_service.dart';
import '../../state/connectivity_providers.dart';
import '../../state/repository_providers.dart';
import '../../state/session_providers.dart';

class VendorProfileScreen extends ConsumerWidget {
  const VendorProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    final shop = session?.shop;

    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false, title: const Text('Profil')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.xl),
        children: [
          Container(
            padding: const EdgeInsets.all(AppSpacing.lg),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                const CircleAvatar(
                  radius: 28,
                  backgroundColor: AppColors.primaryLight,
                  child: Icon(Icons.storefront, color: AppColors.primary),
                ),
                const SizedBox(width: AppSpacing.lg),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(shop?.shopName ?? 'Tokomu', style: AppTypography.h3),
                      Text(session?.phone ?? '', style: AppTypography.caption),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.xl),
          _MenuTile(
            icon: Icons.edit_outlined,
            label: 'Edit Data Toko',
            onTap: () => context.push(RoutePaths.setupShop),
          ),
          _MenuTile(
            icon: Icons.shopping_bag_outlined,
            label: 'Lihat sebagai Konsumen',
            onTap: () {
              ref.read(activeRoleProvider.notifier).state = AppRole.consumer;
              context.go(RoutePaths.consumerFeed);
            },
          ),
          _MenuTile(
            icon: Icons.help_outline,
            label: 'Bantuan',
            onTap: () {},
          ),
          const Divider(height: AppSpacing.xxl),
          _DebugOfflineToggle(),
          const SizedBox(height: AppSpacing.md),
          _MenuTile(
            icon: Icons.logout,
            label: 'Keluar',
            color: AppColors.error,
            onTap: () {
              ref.read(sessionProvider.notifier).logout();
              ref.read(activeRoleProvider.notifier).state = null;
              context.go(RoutePaths.role);
            },
          ),
        ],
      ),
    );
  }
}

class _MenuTile extends StatelessWidget {
  const _MenuTile({required this.icon, required this.label, required this.onTap, this.color});
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon, color: color ?? AppColors.textPrimary),
      title: Text(label, style: AppTypography.body.copyWith(color: color)),
      trailing: const Icon(Icons.chevron_right, color: AppColors.textSecondary),
      onTap: onTap,
    );
  }
}

/// Toggle debug — tidak untuk produksi, hanya supaya reviewer bisa menguji
/// Banner Offline (§2.6) tanpa mematikan Wi-Fi sungguhan.
class _DebugOfflineToggle extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(isOnlineProvider).maybeWhen(data: (v) => v, orElse: () => true);
    return SwitchListTile(
      contentPadding: EdgeInsets.zero,
      title: const Text('Simulasikan offline (debug)', style: AppTypography.caption),
      value: !isOnline,
      onChanged: (v) {
        (ref.read(connectivityServiceProvider) as MockConnectivityService).setOnline(!v);
      },
    );
  }
}

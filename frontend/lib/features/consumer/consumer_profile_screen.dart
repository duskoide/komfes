import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../models/user.dart';
import '../../state/session_providers.dart';

class ConsumerProfileScreen extends ConsumerWidget {
  const ConsumerProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    final isLoggedIn = session != null;

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
                  child: Icon(Icons.person, color: AppColors.primary),
                ),
                const SizedBox(width: AppSpacing.lg),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(isLoggedIn ? session.phone : 'Belum masuk', style: AppTypography.h3),
                      if (!isLoggedIn)
                        Text('Masuk untuk klaim & riwayat', style: AppTypography.caption),
                    ],
                  ),
                ),
                if (!isLoggedIn)
                  FilledButton(
                    onPressed: () => context.push(RoutePaths.phone, extra: {'context': 'claim'}),
                    child: const Text('Masuk'),
                  ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.xl),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.storefront_outlined),
            title: const Text('Punya usaha? Jadi Vendor'),
            trailing: const Icon(Icons.chevron_right, color: AppColors.textSecondary),
            onTap: () {
              ref.read(activeRoleProvider.notifier).state = AppRole.vendor;
              if (isLoggedIn) {
                context.go(RoutePaths.vendorHome);
              } else {
                context.push(RoutePaths.phone, extra: {'context': 'vendor'});
              }
            },
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.help_outline),
            title: const Text('Bantuan'),
            trailing: const Icon(Icons.chevron_right, color: AppColors.textSecondary),
            onTap: () {},
          ),
          if (isLoggedIn) ...[
            const Divider(height: AppSpacing.xxl),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.logout, color: AppColors.error),
              title: const Text('Keluar', style: TextStyle(color: AppColors.error)),
              onTap: () {
                ref.read(sessionProvider.notifier).logout();
                context.go(RoutePaths.consumerFeed);
              },
            ),
          ],
        ],
      ),
    );
  }
}

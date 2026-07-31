import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/breakpoints.dart';
import '../../models/user.dart';
import '../../state/session_providers.dart';

class RoleSelectScreen extends ConsumerWidget {
  const RoleSelectScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isTablet = Breakpoints.isTabletOf(context);

    final vendorCard = _RoleCard(
      icon: Icons.storefront,
      title: 'Saya punya usaha makanan',
      description: 'Dapat rekomendasi harga diskon dari AI',
      buttonLabel: 'Lanjut sebagai Vendor',
      onTap: () {
        ref.read(activeRoleProvider.notifier).state = AppRole.vendor;
        context.push(RoutePaths.phone, extra: {'context': 'vendor'});
      },
    );

    final consumerCard = _RoleCard(
      icon: Icons.shopping_bag_outlined,
      title: 'Saya mau cari makanan murah',
      description: 'Lihat promo hari ini di sekitarmu',
      buttonLabel: 'Lihat Deals',
      onTap: () {
        // Sengaja: kartu konsumen TIDAK menuju login, langsung ke feed (§S-03).
        ref.read(activeRoleProvider.notifier).state = AppRole.consumer;
        context.go(RoutePaths.consumerFeed);
      },
    );

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: AppSpacing.lg),
              Text('Kamu siapa?', style: AppTypography.h1),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Ini menentukan tampilan app untukmu.',
                style: AppTypography.body.copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(height: AppSpacing.xxl),
              Expanded(
                child: isTablet
                    ? Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Expanded(child: vendorCard),
                          const SizedBox(width: AppSpacing.lg),
                          Expanded(child: consumerCard),
                        ],
                      )
                    : Column(
                        children: [
                          Expanded(child: vendorCard),
                          const SizedBox(height: AppSpacing.lg),
                          Expanded(child: consumerCard),
                        ],
                      ),
              ),
              const SizedBox(height: AppSpacing.lg),
              Center(
                child: Text(
                  'Bisa diubah nanti di Profil.',
                  style: AppTypography.caption,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RoleCard extends StatelessWidget {
  const _RoleCard({
    required this.icon,
    required this.title,
    required this.description,
    required this.buttonLabel,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String description;
  final String buttonLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.xl),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: const BoxDecoration(color: AppColors.primaryLight, shape: BoxShape.circle),
              child: Icon(icon, size: 30, color: AppColors.primary),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(title, style: AppTypography.h2, textAlign: TextAlign.center),
            const SizedBox(height: AppSpacing.sm),
            Text(
              description,
              style: AppTypography.body.copyWith(color: AppColors.textSecondary),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(onPressed: onTap, child: Text(buttonLabel)),
            ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';

class ClaimCodeScreen extends StatelessWidget {
  const ClaimCodeScreen({super.key, required this.code});
  final String code;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        title: const Text('Klaim Berhasil'),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 88,
                height: 88,
                decoration: const BoxDecoration(color: AppColors.amanBg, shape: BoxShape.circle),
                child: const Icon(Icons.check_circle, size: 44, color: AppColors.aman),
              ),
              const SizedBox(height: AppSpacing.xl),
              Text('Klaim berhasil!', style: AppTypography.h1, textAlign: TextAlign.center),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Tunjukkan kode ini ke penjual saat mengambil barang.',
                style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.xxl),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl),
                decoration: BoxDecoration(
                  color: AppColors.primaryLight,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
                  border: Border.all(color: AppColors.primary.withOpacity(0.3)),
                ),
                child: Text(
                  code,
                  style: AppTypography.codeDisplay.copyWith(color: AppColors.primaryDark),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: AppSpacing.xxl),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => context.go(RoutePaths.consumerClaims),
                  child: const Text('Lihat Klaim Saya'),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              TextButton(
                onPressed: () => context.go(RoutePaths.consumerFeed),
                child: const Text('Kembali ke Deals'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

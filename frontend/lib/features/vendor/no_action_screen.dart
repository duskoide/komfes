import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../state/recommend_providers.dart';

class NoActionScreen extends ConsumerWidget {
  const NoActionScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final result = ref.watch(recommendFlowProvider).result!;

    return Scaffold(
      appBar: AppBar(title: const Text('Cek Barang')),
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
              Text('Barang ini masih aman', style: AppTypography.h1, textAlign: TextAlign.center),
              const SizedBox(height: AppSpacing.sm),
              Text(
                result.message ?? 'Belum perlu diskon sekarang.',
                style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                textAlign: TextAlign.center,
              ),
              if (result.reassessInDays != null) ...[
                const SizedBox(height: AppSpacing.lg),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceAlt,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusPill),
                  ),
                  child: Text(
                    'Cek lagi dalam ${result.reassessInDays} hari',
                    style: AppTypography.label,
                  ),
                ),
              ],
              const SizedBox(height: AppSpacing.xxl),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    ref.read(recommendFlowProvider.notifier).reset();
                    context.go(RoutePaths.vendorHome);
                  },
                  child: const Text('Kembali ke Beranda'),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              TextButton(
                onPressed: () {
                  final draft = ref.read(recommendFlowProvider).draft;
                  context.pushReplacement(RoutePaths.vendorCheckItem, extra: draft);
                },
                child: const Text('Cek Barang Lain'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

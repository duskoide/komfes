import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../state/recommend_providers.dart';
import '../../widgets/item_summary.dart';

/// V-06 — tidak melakukan apa-apa adalah jawaban yang benar. Sengaja tanpa
/// warna/ikon error: ini kabar baik, vendor menghemat margin (§V-06).
class NoActionScreen extends ConsumerWidget {
  const NoActionScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flow = ref.watch(recommendFlowProvider);
    final result = flow.result!;

    return Scaffold(
      appBar: AppBar(title: const Text('Cek Barang')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 88,
                height: 88,
                decoration: const BoxDecoration(
                  color: AppColors.amanBg,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check_circle, size: 44, color: AppColors.aman),
              ),
              const SizedBox(height: AppSpacing.xl),
              const Text(
                'Belum perlu diskon',
                style: AppTypography.h1,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                result.message ??
                    'Barang ini kemungkinan terjual normal sebelum kadaluarsa.',
                style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                textAlign: TextAlign.center,
              ),
              if (result.reassessInDays != null) ...[
                const SizedBox(height: AppSpacing.lg),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.lg,
                    vertical: AppSpacing.md,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.amanBg,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.event_repeat, size: 18, color: AppColors.aman),
                      const SizedBox(width: AppSpacing.sm),
                      Text(
                        'Cek lagi dalam ${result.reassessInDays} hari',
                        style: AppTypography.bodyStrong.copyWith(color: AppColors.aman),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: AppSpacing.lg),
              ItemSummary(draft: flow.draft),
              const SizedBox(height: AppSpacing.xxl),
              SizedBox(
                width: double.infinity,
                // §V-06: aksi primer adalah "Cek Barang Lain". Sengaja tidak
                // membawa draft lama — "barang lain" berarti barang berbeda,
                // jadi formnya harus kosong.
                child: ElevatedButton(
                  onPressed: () {
                    ref.read(recommendFlowProvider.notifier).reset();
                    context.pushReplacement(RoutePaths.vendorCheckItem);
                  },
                  child: const Text('Cek Barang Lain'),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              TextButton(
                onPressed: () {
                  ref.read(recommendFlowProvider.notifier).reset();
                  context.go(RoutePaths.vendorHome);
                },
                child: const Text('Kembali ke Beranda'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

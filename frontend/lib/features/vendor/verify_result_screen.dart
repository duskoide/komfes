import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/currency_formatter.dart';
import '../../state/verify_providers.dart';

class VerifyResultScreen extends ConsumerWidget {
  const VerifyResultScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(verifyProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Hasil Verifikasi')),
      body: state.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, st) => _resultBody(
          context, ref,
          icon: Icons.error_outline,
          color: AppColors.error,
          bg: AppColors.errorBg,
          title: 'Terjadi kesalahan',
          message: 'Coba verifikasi ulang.',
        ),
        data: (outcome) {
          if (outcome == null) return const SizedBox.shrink();
          switch (outcome.kind) {
            case VerifyOutcomeKind.berhasil:
              final claim = outcome.claim!;
              return _resultBody(
                context, ref,
                icon: Icons.check_circle,
                color: AppColors.aman,
                bg: AppColors.amanBg,
                title: 'Klaim berhasil diverifikasi',
                message: '${claim.itemName ?? ''} • ${claim.priceToPay != null ? CurrencyFormatter.format(claim.priceToPay!) : ''}\nKode ${claim.code}',
              );
            case VerifyOutcomeKind.sudahDipakai:
              return _resultBody(
                context, ref,
                icon: Icons.error_outline,
                color: AppColors.perhatian,
                bg: AppColors.perhatianBg,
                title: 'Kode sudah digunakan',
                message: outcome.message ?? 'Kode ini sudah pernah diverifikasi sebelumnya.',
              );
            case VerifyOutcomeKind.tidakDitemukan:
              return _resultBody(
                context, ref,
                icon: Icons.search_off,
                color: AppColors.error,
                bg: AppColors.errorBg,
                title: 'Kode tidak ditemukan',
                message: 'Cek lagi hurufnya, atau minta pembeli tunjukkan ulang kodenya.',
              );
            case VerifyOutcomeKind.dealDihapus:
              return _resultBody(
                context, ref,
                icon: Icons.block,
                color: AppColors.error,
                bg: AppColors.errorBg,
                title: 'Deal ini sudah dihapus',
                message: outcome.message ?? 'Deal terkait kode ini sudah tidak aktif.',
              );
          }
        },
      ),
    );
  }

  Widget _resultBody(
    BuildContext context,
    WidgetRef ref, {
    required IconData icon,
    required Color color,
    required Color bg,
    required String title,
    required String message,
  }) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 88,
              height: 88,
              decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
              child: Icon(icon, size: 44, color: color),
            ),
            const SizedBox(height: AppSpacing.xl),
            Text(title, style: AppTypography.h1, textAlign: TextAlign.center),
            const SizedBox(height: AppSpacing.sm),
            Text(
              message,
              style: AppTypography.body.copyWith(color: AppColors.textSecondary),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.xxl),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  ref.read(verifyProvider.notifier).resetToIdle();
                  context.pop();
                },
                child: const Text('Verifikasi Kode Lain'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

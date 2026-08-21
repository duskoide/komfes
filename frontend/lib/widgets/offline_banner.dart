import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../state/connectivity_providers.dart';

/// Banner persisten di atas konten saat offline. Dipasang sekali di level
/// shell (vendor/consumer), bukan per-halaman.
class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnlineAsync = ref.watch(isOnlineProvider);
    final isOffline = isOnlineAsync.maybeWhen(data: (v) => !v, orElse: () => false);

    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      child: isOffline
          ? Container(
              key: const ValueKey('offline'),
              width: double.infinity,
              color: AppColors.perhatianBg,
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
              child: Row(
                children: [
                  const Icon(Icons.cloud_off, size: 16, color: AppColors.perhatian),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      'Tidak ada koneksi. Menampilkan data terakhir.',
                      style: AppTypography.caption.copyWith(color: AppColors.perhatian),
                    ),
                  ),
                ],
              ),
            )
          : const SizedBox.shrink(key: ValueKey('online')),
    );
  }
}

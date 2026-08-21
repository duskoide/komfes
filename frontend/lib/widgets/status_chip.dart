import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';

enum DealStatusChipKind { aktif, habis, dihapus }

enum ClaimStatusChipKind { belumDiambil, sudahDiambil }

class StatusChip extends StatelessWidget {
  const StatusChip.deal(this.dealKind, {super.key}) : claimKind = null;
  const StatusChip.claim(this.claimKind, {super.key}) : dealKind = null;

  final DealStatusChipKind? dealKind;
  final ClaimStatusChipKind? claimKind;

  @override
  Widget build(BuildContext context) {
    final (bg, fg, icon, label) = dealKind != null
        ? switch (dealKind!) {
            DealStatusChipKind.aktif => (
                AppColors.statusAktifBg,
                AppColors.statusAktif,
                Icons.check_circle,
                'Aktif',
              ),
            DealStatusChipKind.habis => (
                AppColors.statusHabisBg,
                AppColors.statusHabis,
                Icons.block,
                'Habis',
              ),
            DealStatusChipKind.dihapus => (
                AppColors.statusDihapusBg,
                AppColors.statusDihapus,
                Icons.delete_outline,
                'Dihapus',
              ),
          }
        : switch (claimKind!) {
            ClaimStatusChipKind.belumDiambil => (
                AppColors.statusBelumDiambilBg,
                AppColors.statusBelumDiambil,
                Icons.schedule,
                'Belum diambil',
              ),
            ClaimStatusChipKind.sudahDiambil => (
                AppColors.statusSudahDigunakanBg,
                AppColors.statusSudahDigunakan,
                Icons.check_circle,
                'Sudah diambil',
              ),
          };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(AppSpacing.radiusPill)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: fg),
          const SizedBox(width: 4),
          Text(label, style: AppTypography.label.copyWith(color: fg)),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../models/enums.dart';

class UrgencyChip extends StatelessWidget {
  const UrgencyChip({super.key, required this.level, this.label});

  final UrgencyLevel level;

  /// Override label (mis. "HARI INI SAJA!" atau "Sisa 2 hari"). Kalau null,
  /// pakai label default level.
  final String? label;

  @override
  Widget build(BuildContext context) {
    final (bg, fg, icon, defaultLabel) = switch (level) {
      UrgencyLevel.aman => (AppColors.amanBg, AppColors.aman, Icons.check_circle, 'Aman'),
      UrgencyLevel.perhatian => (
          AppColors.perhatianBg,
          AppColors.perhatian,
          Icons.watch_later,
          'Perhatian',
        ),
      UrgencyLevel.kritis => (
          AppColors.kritisBg,
          AppColors.kritis,
          Icons.warning_rounded,
          'Kritis',
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
          Text(label ?? defaultLabel, style: AppTypography.label.copyWith(color: fg)),
        ],
      ),
    );
  }
}

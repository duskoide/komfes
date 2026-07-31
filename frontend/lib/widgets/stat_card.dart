import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';

class StatCard extends StatelessWidget {
  const StatCard({
    super.key,
    required this.value,
    required this.label,
    this.icon,
    this.valueColor,
  });

  final String value;
  final String label;
  final IconData? icon;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 20, color: AppColors.textSecondary),
            const SizedBox(height: AppSpacing.xs),
          ],
          Text(
            value,
            style: AppTypography.displayNumberMedium.copyWith(color: valueColor),
          ),
          const SizedBox(height: 2),
          Text(label, style: AppTypography.caption, maxLines: 2),
        ],
      ),
    );
  }
}

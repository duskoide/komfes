import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../models/recommendation.dart';

/// Ringkasan ringkas barang yang sedang/baru diproses — nama, stok, sisa
/// hari (§V-04 dan §V-06). Bagian yang belum diketahui, misalnya input
/// teks bebas yang belum diparsing, tidak ditampilkan sama sekali.
class ItemSummary extends StatelessWidget {
  const ItemSummary({super.key, required this.draft});

  final ItemInputDraft? draft;

  @override
  Widget build(BuildContext context) {
    final d = draft;
    if (d == null) return const SizedBox.shrink();

    final parts = <String>[
      if (d.stock != null) '${d.stock} pcs',
      if (d.daysRemaining != null)
        switch (d.daysRemaining!) {
          0 => 'kadaluarsa hari ini',
          1 => 'sisa 1 hari',
          final v => 'sisa $v hari',
        },
    ];

    final name = d.itemName?.trim();
    if ((name == null || name.isEmpty) && parts.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.md,
      ),
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (name != null && name.isNotEmpty)
            Text(name, style: AppTypography.bodyStrong, textAlign: TextAlign.center),
          if (parts.isNotEmpty)
            Text(
              parts.join(' · '),
              style: AppTypography.caption,
              textAlign: TextAlign.center,
            ),
        ],
      ),
    );
  }
}

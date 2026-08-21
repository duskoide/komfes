import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../core/utils/currency_formatter.dart';

/// Blok Harga — dipakai di semua varian Kartu Deal, V-05, dan C-02/C-03.
/// Harga besar di depan, harga coret jelas sebagai "bekas harga" (bukan abu
/// tipis), badge diskon menonjol.
class PriceBlock extends StatelessWidget {
  const PriceBlock({
    super.key,
    required this.dealPrice,
    required this.originalPrice,
    required this.discountPercent,
    this.size = PriceBlockSize.large,
  });

  final int dealPrice;
  final int originalPrice;
  final int discountPercent;
  final PriceBlockSize size;

  @override
  Widget build(BuildContext context) {
    final priceStyle = size == PriceBlockSize.large
        ? AppTypography.displayNumber
        : AppTypography.displayNumberMedium;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(CurrencyFormatter.format(dealPrice), style: priceStyle),
        const SizedBox(height: AppSpacing.xs),
        Wrap(
          spacing: AppSpacing.sm,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.primaryLight,
                borderRadius: BorderRadius.circular(AppSpacing.radiusPill),
              ),
              child: Text(
                'Diskon $discountPercent%',
                style: AppTypography.label.copyWith(color: AppColors.primaryDark),
              ),
            ),
            Text('harga asli ${CurrencyFormatter.format(originalPrice)}',
                style: AppTypography.strikethrough),
          ],
        ),
      ],
    );
  }
}

enum PriceBlockSize { large, medium }

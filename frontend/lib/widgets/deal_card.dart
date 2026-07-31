import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../core/utils/category_icons.dart';
import '../models/deal.dart';
import '../models/enums.dart';
import 'price_block.dart';
import 'status_chip.dart';
import 'urgency_chip.dart';

enum DealCardAudience { vendor, consumer }

enum DealCardDensity { ringkas, lengkap }

/// Kartu Deal — komponen paling sering dipakai di seluruh app (V-05, V-08,
/// V-09, V-10, C-01, C-02). Satu widget, beberapa parameter tampilan,
/// supaya style tidak pernah menyimpang antar halaman.
class DealCard extends StatelessWidget {
  const DealCard({
    super.key,
    required this.deal,
    required this.audience,
    this.density = DealCardDensity.ringkas,
    this.onTap,
    this.onClaimPressed,
    this.claimedNotYetPickedUpCount,
  });

  final Deal deal;
  final DealCardAudience audience;
  final DealCardDensity density;
  final VoidCallback? onTap;

  /// Hanya dipakai audience == consumer, density == ringkas (C-01).
  final VoidCallback? onClaimPressed;

  /// Hanya dipakai audience == vendor (V-09): jumlah klaim belum diambil.
  final int? claimedNotYetPickedUpCount;

  bool get _isDimmed => deal.status != DealStatus.active;

  @override
  Widget build(BuildContext context) {
    final card = Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
        border: Border.all(
          color: deal.urgency == UrgencyLevel.kritis && !_isDimmed
              ? AppColors.kritis.withOpacity(0.4)
              : AppColors.border,
          width: deal.urgency == UrgencyLevel.kritis && !_isDimmed ? 1.4 : 1,
        ),
      ),
      child: Opacity(
        opacity: _isDimmed ? 0.62 : 1,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _header(),
              const SizedBox(height: AppSpacing.md),
              PriceBlock(
                dealPrice: deal.dealPrice,
                originalPrice: deal.originalPrice,
                discountPercent: deal.discountPercent,
                size: density == DealCardDensity.lengkap
                    ? PriceBlockSize.large
                    : PriceBlockSize.medium,
              ),
              const SizedBox(height: AppSpacing.md),
              _metaRow(),
              if (density == DealCardDensity.lengkap && deal.promoCopy.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                Text(deal.promoCopy, style: AppTypography.body),
              ] else if (audience == DealCardAudience.consumer &&
                  density == DealCardDensity.ringkas &&
                  deal.promoCopy.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  deal.promoCopy,
                  style: AppTypography.caption,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
              if (audience == DealCardAudience.vendor && claimedNotYetPickedUpCount != null &&
                  claimedNotYetPickedUpCount! > 0) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  '${claimedNotYetPickedUpCount!} klaim belum diambil',
                  style: AppTypography.label.copyWith(color: AppColors.perhatian),
                ),
              ],
              if (audience == DealCardAudience.consumer &&
                  density == DealCardDensity.ringkas) ...[
                const SizedBox(height: AppSpacing.lg),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: deal.isSoldOut ? null : onClaimPressed,
                    child: Text(deal.isSoldOut ? 'Habis' : 'Klaim'),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );

    if (onTap == null) return card;
    return InkWell(
      borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
      onTap: onTap,
      child: card,
    );
  }

  Widget _header() {
    return Row(
      children: [
        Text(categoryEmoji(deal.category), style: const TextStyle(fontSize: 22)),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                deal.itemName,
                style: AppTypography.h3,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              Text(
                deal.shopName,
                style: AppTypography.caption,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        _statusChip(),
      ],
    );
  }

  Widget _statusChip() {
    switch (deal.status) {
      case DealStatus.active:
        return UrgencyChip(level: deal.urgency, label: deal.remainingLabel);
      case DealStatus.soldOut:
        return const StatusChip.deal(DealStatusChipKind.habis);
      case DealStatus.removed:
        return const StatusChip.deal(DealStatusChipKind.dihapus);
    }
  }

  Widget _metaRow() {
    if (audience == DealCardAudience.vendor) {
      return Row(
        children: [
          Icon(Icons.inventory_2_outlined, size: 16, color: AppColors.textSecondary),
          const SizedBox(width: 4),
          Text(
            '${deal.remainingStock} dari ${deal.initialStock}',
            style: AppTypography.bodyStrong,
          ),
          const SizedBox(width: AppSpacing.md),
          if (deal.status == DealStatus.active) StatusChip.deal(DealStatusChipKind.aktif),
        ],
      );
    }
    return Row(
      children: [
        Icon(Icons.inventory_2_outlined, size: 16, color: AppColors.textSecondary),
        const SizedBox(width: 4),
        Text('Stok ${deal.remainingStock}', style: AppTypography.caption),
      ],
    );
  }
}

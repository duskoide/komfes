import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../core/utils/currency_formatter.dart';
import '../models/recommendation.dart';

/// Label Bahasa Indonesia per field, memakai nama field kontrak sebagai kunci
/// supaya `missing_fields` dari server bisa dipetakan langsung.
const Map<String, String> consultationFieldLabels = {
  'item_name': 'Nama barang',
  'category': 'Kategori',
  'stock': 'Jumlah stok',
  'days_remaining': 'Sisa waktu',
  'original_price': 'Harga jual sekarang',
  'cost': 'Harga modal',
  'daily_sales': 'Rata-rata terjual per hari',
  'total_shelf_life': 'Umur simpan total',
  'shop_name': 'Nama toko',
};

/// Kartu "data yang sudah dicatat" di dalam percakapan.
///
/// Hanya menampilkan yang sudah terisi; yang belum ada disebut terpisah
/// sebagai daftar yang masih ditunggu, bukan sebagai baris kosong.
class KnownFieldsCard extends StatelessWidget {
  const KnownFieldsCard({
    super.key,
    required this.item,
    this.missingFields = const [],
    this.ambiguousFields = const [],
  });

  final ItemInputDraft item;
  final List<String> missingFields;
  final List<String> ambiguousFields;

  @override
  Widget build(BuildContext context) {
    final known = _knownEntries();
    if (known.isEmpty && missingFields.isEmpty) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Data yang sudah dicatat', style: AppTypography.label),
          const SizedBox(height: AppSpacing.md),
          for (final entry in known) ...[
            _Row(
              label: entry.$1,
              value: entry.$2,
              ambiguous: ambiguousFields.contains(entry.$3),
            ),
            const SizedBox(height: AppSpacing.xs),
          ],
          if (missingFields.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Masih ditunggu: ${_missingLabels().join(', ')}',
              style: AppTypography.caption.copyWith(color: AppColors.primary),
            ),
          ],
        ],
      ),
    );
  }

  List<String> _missingLabels() => [
        for (final f in missingFields) consultationFieldLabels[f] ?? f,
      ];

  /// (label, nilai tampil, nama field kontrak)
  List<(String, String, String)> _knownEntries() {
    const rp = CurrencyFormatter.format;
    return [
      if ((item.itemName ?? '').trim().isNotEmpty)
        ('Nama barang', item.itemName!.trim(), 'item_name'),
      if (item.category != null)
        ('Kategori', item.category!.label, 'category'),
      if (item.stock != null) ('Jumlah stok', '${item.stock} pcs', 'stock'),
      if (item.daysRemaining != null)
        ('Sisa waktu', _days(item.daysRemaining!), 'days_remaining'),
      if (item.originalPrice != null)
        ('Harga jual sekarang', rp(item.originalPrice!), 'original_price'),
      if (item.cost != null) ('Harga modal', rp(item.cost!), 'cost'),
      if (item.dailySales != null)
        ('Terjual per hari', '${item.dailySales} pcs', 'daily_sales'),
      if (item.totalShelfLife != null)
        ('Umur simpan total', '${item.totalShelfLife} hari', 'total_shelf_life'),
      if ((item.shopName ?? '').trim().isNotEmpty)
        ('Nama toko', item.shopName!.trim(), 'shop_name'),
    ];
  }

  static String _days(int days) => switch (days) {
        0 => 'kadaluarsa hari ini',
        1 => 'besok',
        _ => '$days hari lagi',
      };
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value, this.ambiguous = false});

  final String label;
  final String value;

  /// Terbaca tapi belum tentu benar — ditandai supaya vendor memeriksanya.
  final bool ambiguous;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Text(label, style: AppTypography.caption)),
        const SizedBox(width: AppSpacing.sm),
        Flexible(
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (ambiguous) ...[
                const Icon(Icons.help_outline, size: 14, color: AppColors.perhatian),
                const SizedBox(width: AppSpacing.xs),
              ],
              Flexible(
                child: Text(
                  value,
                  textAlign: TextAlign.right,
                  style: AppTypography.bodyStrong.copyWith(
                    color: ambiguous ? AppColors.perhatian : AppColors.textPrimary,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/currency_formatter.dart';
import '../../models/enums.dart';
import '../../models/recommendation.dart';
import '../../widgets/rupiah_field.dart';

/// Kartu konfirmasi di dalam percakapan.
///
/// Jaring pengaman terakhir sebelum tool pricing dipanggil: vendor melihat
/// seluruh data terstruktur dan bisa memperbaikinya tanpa mengulang cerita.
/// Hanya field yang benar-benar diubah dikirim sebagai patch — penggabungan
/// dan validasi tetap tugas server.
class ChatConfirmCard extends StatefulWidget {
  const ChatConfirmCard({
    super.key,
    required this.item,
    required this.busy,
    required this.onConfirm,
  });

  final ItemInputDraft item;
  final bool busy;

  /// null berarti tidak ada yang disunting.
  final void Function(ItemInputDraft? patch) onConfirm;

  @override
  State<ChatConfirmCard> createState() => _ChatConfirmCardState();
}

class _ChatConfirmCardState extends State<ChatConfirmCard> {
  bool _editing = false;

  late final TextEditingController _name;
  late final TextEditingController _stock;
  late final TextEditingController _days;
  late final TextEditingController _price;
  late final TextEditingController _cost;
  late final TextEditingController _dailySales;
  late final TextEditingController _shelfLife;
  ItemCategory? _category;

  @override
  void initState() {
    super.initState();
    final i = widget.item;
    _name = TextEditingController(text: i.itemName ?? '');
    _stock = TextEditingController(text: i.stock?.toString() ?? '');
    _days = TextEditingController(text: i.daysRemaining?.toString() ?? '');
    _price = TextEditingController(
      text: i.originalPrice != null
          ? CurrencyFormatter.formatDigitsOnly(i.originalPrice!)
          : '',
    );
    _cost = TextEditingController(
      text: i.cost != null ? CurrencyFormatter.formatDigitsOnly(i.cost!) : '',
    );
    _dailySales = TextEditingController(text: i.dailySales?.toString() ?? '');
    _shelfLife = TextEditingController(text: i.totalShelfLife?.toString() ?? '');
    _category = i.category;
  }

  @override
  void dispose() {
    _name.dispose();
    _stock.dispose();
    _days.dispose();
    _price.dispose();
    _cost.dispose();
    _dailySales.dispose();
    _shelfLife.dispose();
    super.dispose();
  }

  /// Hanya nilai yang berbeda dari state server yang dikirim.
  ItemInputDraft? _buildPatch() {
    final i = widget.item;
    String? name = _name.text.trim();
    if (name.isEmpty || name == i.itemName) name = null;

    int? diffInt(TextEditingController c, int? original) {
      final digits = c.text.replaceAll(RegExp(r'[^0-9]'), '');
      if (digits.isEmpty) return null;
      final value = int.tryParse(digits);
      return value == original ? null : value;
    }

    final patch = ItemInputDraft(
      itemName: name,
      category: _category == i.category ? null : _category,
      stock: diffInt(_stock, i.stock),
      daysRemaining: diffInt(_days, i.daysRemaining),
      originalPrice: diffInt(_price, i.originalPrice),
      cost: diffInt(_cost, i.cost),
      dailySales: diffInt(_dailySales, i.dailySales),
      totalShelfLife: diffInt(_shelfLife, i.totalShelfLife),
    );

    return patch.toStructuredJson().isEmpty ? null : patch;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
        border: Border.all(color: AppColors.primary, width: 1.4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Cek dulu sebelum dihitung', style: AppTypography.h3),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Kalau ada yang salah, perbaiki di sini.',
            style: AppTypography.caption.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: AppSpacing.lg),
          if (_editing) ..._editors() else ..._readOnlyRows(),
          const SizedBox(height: AppSpacing.lg),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: widget.busy
                      ? null
                      : () => setState(() => _editing = !_editing),
                  child: Text(_editing ? 'Selesai Ubah' : 'Ubah Data'),
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: ElevatedButton(
                  onPressed:
                      widget.busy ? null : () => widget.onConfirm(_buildPatch()),
                  child: widget.busy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Hitung Sekarang'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  List<Widget> _readOnlyRows() {
    final i = widget.item;
    final rows = <(String, String)>[
      if ((i.itemName ?? '').trim().isNotEmpty) ('Nama barang', i.itemName!),
      if (i.category != null) ('Kategori', i.category!.label),
      if (i.stock != null) ('Jumlah stok', '${i.stock} pcs'),
      if (i.daysRemaining != null) ('Sisa waktu', '${i.daysRemaining} hari'),
      if (i.originalPrice != null)
        ('Harga jual', CurrencyFormatter.format(i.originalPrice!)),
      if (i.cost != null) ('Harga modal', CurrencyFormatter.format(i.cost!)),
      if (i.dailySales != null) ('Terjual per hari', '${i.dailySales} pcs'),
      if (i.totalShelfLife != null)
        ('Umur simpan', '${i.totalShelfLife} hari'),
    ];

    return [
      for (final row in rows)
        Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.xs),
          child: Row(
            children: [
              Expanded(child: Text(row.$1, style: AppTypography.caption)),
              Text(row.$2, style: AppTypography.bodyStrong),
            ],
          ),
        ),
    ];
  }

  List<Widget> _editors() {
    return [
      TextField(
        controller: _name,
        decoration: const InputDecoration(labelText: 'Nama barang'),
      ),
      const SizedBox(height: AppSpacing.md),
      DropdownButtonFormField<ItemCategory>(
        initialValue: _category,
        decoration: const InputDecoration(labelText: 'Kategori'),
        items: ItemCategory.values
            .map((c) => DropdownMenuItem(value: c, child: Text(c.label)))
            .toList(),
        onChanged: (c) => setState(() => _category = c),
      ),
      const SizedBox(height: AppSpacing.md),
      TextField(
        controller: _stock,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(labelText: 'Jumlah stok'),
      ),
      const SizedBox(height: AppSpacing.md),
      TextField(
        controller: _days,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(
          labelText: 'Sisa waktu (hari)',
          hintText: '0 = hari ini',
        ),
      ),
      const SizedBox(height: AppSpacing.md),
      RupiahField(controller: _price, label: 'Harga jual sekarang'),
      const SizedBox(height: AppSpacing.md),
      RupiahField(
        controller: _cost,
        label: 'Harga modal',
        helperText: 'Berapa modal kamu per satu barang ini?',
      ),
      const SizedBox(height: AppSpacing.md),
      TextField(
        controller: _dailySales,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(
          labelText: 'Rata-rata terjual per hari',
          helperText: 'Kira-kira saja, tidak harus tepat.',
          helperMaxLines: 2,
        ),
      ),
      const SizedBox(height: AppSpacing.md),
      TextField(
        controller: _shelfLife,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(labelText: 'Umur simpan total (hari)'),
      ),
    ];
  }
}

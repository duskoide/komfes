import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/currency_formatter.dart';
import '../../models/enums.dart';
import '../../models/recommendation.dart';
import '../../state/recommend_providers.dart';
import '../../widgets/rupiah_field.dart';
import '../../widgets/sticky_bottom_bar.dart';

class ConfirmDataScreen extends ConsumerStatefulWidget {
  const ConfirmDataScreen({super.key});

  @override
  ConsumerState<ConfirmDataScreen> createState() => _ConfirmDataScreenState();
}

class _ConfirmDataScreenState extends ConsumerState<ConfirmDataScreen> {
  late ItemInputDraft _parsed;

  final _itemNameController = TextEditingController();
  ItemCategory? _category;
  final _stockController = TextEditingController();
  final _daysController = TextEditingController();
  final _priceController = TextEditingController();
  final _costController = TextEditingController();
  final _dailySalesController = TextEditingController();
  final _shelfLifeController = TextEditingController();
  bool _shelfLifeAuto = true;
  bool _submitting = false;

  /// Satu FocusNode per field teks, supaya fokus bisa dilempar ke field
  /// kosong pertama (§V-03).
  final _focusNodes = <String, FocusNode>{
    'item_name': FocusNode(),
    'stock': FocusNode(),
    'days_remaining': FocusNode(),
    'original_price': FocusNode(),
    'cost': FocusNode(),
    'daily_sales': FocusNode(),
    'total_shelf_life': FocusNode(),
  };

  @override
  void initState() {
    super.initState();
    final result = ref.read(recommendFlowProvider).result!;
    _parsed = result.parsedInput!;

    _itemNameController.text = _parsed.itemName ?? '';
    _category = _parsed.category;
    _stockController.text = _parsed.stock?.toString() ?? '';
    _daysController.text = _parsed.daysRemaining?.toString() ?? '';
    _priceController.text = _parsed.originalPrice != null
        ? CurrencyFormatter.formatDigitsOnly(_parsed.originalPrice!)
        : '';
    _costController.text =
        _parsed.cost != null ? CurrencyFormatter.formatDigitsOnly(_parsed.cost!) : '';
    _dailySalesController.text = _parsed.dailySales?.toString() ?? '';

    // Umur simpan tidak pernah dibiarkan kosong: kalau AI tidak membacanya,
    // pakai default kategori dan beri label "otomatis" (§V-03).
    final shelfLife = _parsed.totalShelfLife;
    if (shelfLife != null) {
      _shelfLifeController.text = shelfLife.toString();
      _shelfLifeAuto = false;
    } else if (_category != null) {
      _shelfLifeController.text = _category!.defaultShelfLifeDays.toString();
    }

    WidgetsBinding.instance.addPostFrameCallback((_) => _focusFirstEmpty());
  }

  @override
  void dispose() {
    _itemNameController.dispose();
    _stockController.dispose();
    _daysController.dispose();
    _priceController.dispose();
    _costController.dispose();
    _dailySalesController.dispose();
    _shelfLifeController.dispose();
    for (final node in _focusNodes.values) {
      node.dispose();
    }
    super.dispose();
  }

  void _focusFirstEmpty() {
    if (!mounted) return;
    for (final key in _focusNodes.keys) {
      if (!_wasParsed(key)) {
        _focusNodes[key]!.requestFocus();
        return;
      }
    }
  }

  /// Field yang berhasil dibaca AI. Dipakai untuk pembedaan visual, dan
  /// sengaja dibaca dari nilai hasil parsing — bukan dari missing_fields —
  /// supaya field yang tidak disebut server pun tetap tergolong benar.
  bool _wasParsed(String key) => switch (key) {
        'item_name' => (_parsed.itemName ?? '').trim().isNotEmpty,
        'category' => _parsed.category != null,
        'stock' => _parsed.stock != null,
        'days_remaining' => _parsed.daysRemaining != null,
        'original_price' => _parsed.originalPrice != null,
        'cost' => _parsed.cost != null,
        'daily_sales' => _parsed.dailySales != null,
        'total_shelf_life' => _parsed.totalShelfLife != null,
        _ => false,
      };

  bool get _isValid =>
      _itemNameController.text.trim().isNotEmpty &&
      _category != null &&
      _stockController.text.trim().isNotEmpty &&
      _daysController.text.trim().isNotEmpty &&
      CurrencyFormatter.parseDigits(_priceController.text) > 0 &&
      CurrencyFormatter.parseDigits(_costController.text) > 0 &&
      _dailySalesController.text.trim().isNotEmpty;

  Future<void> _confirm() async {
    setState(() => _submitting = true);
    final draft = ItemInputDraft(
      itemName: _itemNameController.text.trim(),
      category: _category,
      stock: int.tryParse(_stockController.text),
      daysRemaining: int.tryParse(_daysController.text),
      originalPrice: CurrencyFormatter.parseDigits(_priceController.text),
      cost: CurrencyFormatter.parseDigits(_costController.text),
      dailySales: int.tryParse(_dailySalesController.text),
      totalShelfLife:
          int.tryParse(_shelfLifeController.text) ?? _category?.defaultShelfLifeDays,
      shopName: _parsed.shopName,
    );
    // Layar ini digantikan V-04, jadi _submitting tidak perlu direset.
    context.pushReplacement(RoutePaths.vendorProcessing, extra: draft);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Lengkapi Data')),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Nada netral, bukan peringatan: kondisi ini normal dan
                  // sering terjadi, jadi tidak memakai warna urgensi (§V-03).
                  const Text('Lengkapi sedikit lagi', style: AppTypography.h1),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Kami sudah baca inputmu. Tinggal beberapa data ini.',
                    style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                  ),
                  if ((_parsed.freeText ?? '').trim().isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.lg),
                    _OriginalInputQuote(text: _parsed.freeText!.trim()),
                  ],
                  const SizedBox(height: AppSpacing.xl),
                  _field(
                    'item_name',
                    TextField(
                      controller: _itemNameController,
                      focusNode: _focusNodes['item_name'],
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(labelText: 'Nama barang'),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  _field(
                    'category',
                    DropdownButtonFormField<ItemCategory>(
                      initialValue: _category,
                      decoration: const InputDecoration(labelText: 'Kategori'),
                      items: ItemCategory.values
                          .map((c) => DropdownMenuItem(value: c, child: Text(c.label)))
                          .toList(),
                      onChanged: (c) => setState(() {
                        _category = c;
                        if (_shelfLifeAuto && c != null) {
                          _shelfLifeController.text = c.defaultShelfLifeDays.toString();
                        }
                      }),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  _field(
                    'stock',
                    TextField(
                      controller: _stockController,
                      focusNode: _focusNodes['stock'],
                      keyboardType: TextInputType.number,
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(labelText: 'Jumlah stok'),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  _field(
                    'days_remaining',
                    TextField(
                      controller: _daysController,
                      focusNode: _focusNodes['days_remaining'],
                      keyboardType: TextInputType.number,
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(
                        labelText: 'Sisa waktu (hari)',
                        hintText: '0 = hari ini',
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  _field(
                    'original_price',
                    RupiahField(
                      controller: _priceController,
                      focusNode: _focusNodes['original_price'],
                      label: 'Harga jual sekarang',
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  _field(
                    'cost',
                    RupiahField(
                      controller: _costController,
                      focusNode: _focusNodes['cost'],
                      label: 'Harga modal',
                      helperText: 'Berapa modal kamu per satu barang ini?',
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  _field(
                    'daily_sales',
                    TextField(
                      controller: _dailySalesController,
                      focusNode: _focusNodes['daily_sales'],
                      keyboardType: TextInputType.number,
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(
                        labelText: 'Rata-rata terjual per hari',
                        helperText: 'Kira-kira saja, tidak harus tepat.',
                        helperMaxLines: 2,
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  _field(
                    'total_shelf_life',
                    TextField(
                      controller: _shelfLifeController,
                      focusNode: _focusNodes['total_shelf_life'],
                      keyboardType: TextInputType.number,
                      onChanged: (_) => setState(() => _shelfLifeAuto = false),
                      decoration: InputDecoration(
                        labelText: 'Umur simpan total (hari)',
                        helperText: _shelfLifeAuto
                            ? 'Perkiraan umum untuk kategori ini. Ubah kalau berbeda. (otomatis)'
                            : null,
                        helperMaxLines: 2,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          StickyBottomBar(
            secondaryChild: TextButton(
              onPressed: _submitting
                  ? null
                  : () => context.pushReplacement(
                        RoutePaths.vendorCheckItem,
                        extra: _parsed,
                      ),
              child: const Text('Ubah Input'),
            ),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isValid && !_submitting ? _confirm : null,
                child: _submitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: Colors.white,
                        ),
                      )
                    : const Text('Hitung Sekarang'),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Pembedaan visual dua jenis field (§V-03). Keduanya tetap bisa diedit —
  /// vendor harus bisa memperbaiki bacaan AI yang salah tanpa mengulang.
  Widget _field(String key, Widget child) {
    if (_wasParsed(key)) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.check_circle, size: 15, color: AppColors.aman),
              const SizedBox(width: AppSpacing.xs),
              Text(
                'Terbaca dari kalimatmu',
                style: AppTypography.caption.copyWith(color: AppColors.aman),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          child,
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.edit_outlined, size: 15, color: AppColors.primary),
            const SizedBox(width: AppSpacing.xs),
            Text(
              'Perlu diisi',
              style: AppTypography.caption.copyWith(color: AppColors.primary),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        child,
      ],
    );
  }
}

/// Kutipan input asli vendor, bisa dilipat (§V-03) — supaya dia ingat
/// konteks kalimat yang tadi ditulis.
class _OriginalInputQuote extends StatelessWidget {
  const _OriginalInputQuote({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      ),
      child: Theme(
        // Buang garis pemisah bawaan ExpansionTile supaya tidak menabrak
        // sudut membulat kartunya.
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
          childrenPadding: const EdgeInsets.fromLTRB(
            AppSpacing.lg,
            0,
            AppSpacing.lg,
            AppSpacing.lg,
          ),
          title: const Text('Yang kamu tulis tadi', style: AppTypography.label),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Text(text, style: AppTypography.body),
            ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/breakpoints.dart';
import '../../core/utils/currency_formatter.dart';
import '../../models/enums.dart';
import '../../models/recommendation.dart';
import '../../state/recommend_providers.dart';
import '../../state/session_providers.dart';
import '../../widgets/rupiah_field.dart';
import '../../widgets/sticky_bottom_bar.dart';

const _freeTextExamples = [
  'roti tawar 10 biji exp 2 hari harga 15rb modal 10rb',
  'kue lapis 5 pcs exp besok harga 20rb modal 12rb',
  'susu uht 6 botol exp 3 hari harga 18rb modal 12rb',
];

class CheckItemScreen extends ConsumerStatefulWidget {
  const CheckItemScreen({super.key, this.prefill});

  final ItemInputDraft? prefill;

  @override
  ConsumerState<CheckItemScreen> createState() => _CheckItemScreenState();
}

class _CheckItemScreenState extends ConsumerState<CheckItemScreen> {
  bool _freeTextMode = true;
  final _freeTextController = TextEditingController();

  final _itemNameController = TextEditingController();
  ItemCategory? _category;
  final _stockController = TextEditingController();
  final _daysController = TextEditingController();
  final _priceController = TextEditingController();
  final _costController = TextEditingController();
  final _dailySalesController = TextEditingController();
  final _shelfLifeController = TextEditingController();
  bool _shelfLifeAuto = true;

  bool _submitted = false;

  @override
  void initState() {
    super.initState();
    final prefill = widget.prefill;
    if (prefill != null) {
      _freeTextMode = false;
      _itemNameController.text = prefill.itemName ?? '';
      _category = prefill.category;
      _stockController.text = prefill.stock?.toString() ?? '';
      _daysController.text = prefill.daysRemaining?.toString() ?? '';
      _priceController.text =
          prefill.originalPrice != null ? CurrencyFormatter.formatDigitsOnly(prefill.originalPrice!) : '';
      _costController.text =
          prefill.cost != null ? CurrencyFormatter.formatDigitsOnly(prefill.cost!) : '';
      _dailySalesController.text = prefill.dailySales?.toString() ?? '';
      if (prefill.totalShelfLife != null) {
        _shelfLifeController.text = prefill.totalShelfLife.toString();
        _shelfLifeAuto = false;
      }
    } else {
      final shop = ref.read(sessionProvider)?.shop;
      if (shop != null) {
        // shop_name terisi dari profil - disimpan tersembunyi, tidak
        // perlu field terpisah karena tidak ditampilkan ke vendor.
      }
    }
  }

  void _applyCategoryDefault(ItemCategory c) {
    setState(() {
      _category = c;
      if (_shelfLifeAuto) {
        _shelfLifeController.text = c.defaultShelfLifeDays.toString();
      }
    });
  }

  bool get _isFormValid {
    if (_freeTextMode) return _freeTextController.text.trim().isNotEmpty;
    return _itemNameController.text.trim().isNotEmpty &&
        _category != null &&
        _stockController.text.trim().isNotEmpty &&
        _daysController.text.trim().isNotEmpty &&
        CurrencyFormatter.parseDigits(_priceController.text) > 0 &&
        CurrencyFormatter.parseDigits(_costController.text) > 0 &&
        _dailySalesController.text.trim().isNotEmpty;
  }

  ItemInputDraft _buildDraft() {
    final shopName = ref.read(sessionProvider)?.shop?.shopName;
    if (_freeTextMode) {
      return ItemInputDraft(freeText: _freeTextController.text.trim());
    }
    return ItemInputDraft(
      itemName: _itemNameController.text.trim(),
      category: _category,
      stock: int.tryParse(_stockController.text),
      daysRemaining: int.tryParse(_daysController.text),
      originalPrice: CurrencyFormatter.parseDigits(_priceController.text),
      cost: CurrencyFormatter.parseDigits(_costController.text),
      dailySales: int.tryParse(_dailySalesController.text),
      totalShelfLife: int.tryParse(_shelfLifeController.text),
      shopName: shopName,
    );
  }

  Future<void> _submitAndGoToProcessing() async {
    // Alur nyata: V-02 -> V-04 (tampilkan animasi proses) -> hasil.
    context.push(RoutePaths.vendorProcessing, extra: _buildDraft());
  }

  @override
  Widget build(BuildContext context) {
    final isTablet = Breakpoints.isTabletOf(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Cek Barang')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl, vertical: AppSpacing.md),
            child: _ModeToggle(
              isFreeText: _freeTextMode,
              onChanged: (v) => setState(() => _freeTextMode = v),
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.xl, 0, AppSpacing.xl, AppSpacing.xxxl,
              ),
              child: _freeTextMode ? _freeTextForm() : _structuredForm(isTablet),
            ),
          ),
          StickyBottomBar(
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isFormValid && !_submitted ? _submitAndGoToProcessing : null,
                child: const Text('Dapatkan Rekomendasi'),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _freeTextForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: _freeTextController,
          maxLines: 4,
          minLines: 3,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
            hintText: 'roti tawar 10 biji exp 2 hari harga 15rb modal 10rb',
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: _freeTextExamples
              .map((e) => ActionChip(
                    label: Text(e, style: AppTypography.caption),
                    onPressed: () {
                      _freeTextController.text = e;
                      setState(() {});
                    },
                  ))
              .toList(),
        ),
      ],
    );
  }

  Widget _structuredForm(bool isTablet) {
    final nameField = TextField(
      controller: _itemNameController,
      onChanged: (_) => setState(() {}),
      decoration: const InputDecoration(labelText: 'Nama barang'),
    );

    final categoryField = DropdownButtonFormField<ItemCategory>(
      initialValue: _category,
      decoration: const InputDecoration(labelText: 'Kategori'),
      items: ItemCategory.values
          .map((c) => DropdownMenuItem(value: c, child: Text(c.apiValue)))
          .toList(),
      onChanged: (c) => c != null ? _applyCategoryDefault(c) : null,
    );

    final portionNote = _category?.needsPortionNote == true
        ? Padding(
            padding: const EdgeInsets.only(top: AppSpacing.xs),
            child: Text(
              'Hitung dalam porsi jadi, bukan bahan mentah. Contoh: 2 liter susu ≈ 20 gelas latte.',
              style: AppTypography.caption,
            ),
          )
        : const SizedBox.shrink();

    final stockField = TextField(
      controller: _stockController,
      keyboardType: TextInputType.number,
      onChanged: (_) => setState(() {}),
      decoration: const InputDecoration(labelText: 'Jumlah stok'),
    );

    final daysField = TextField(
      controller: _daysController,
      keyboardType: TextInputType.number,
      onChanged: (_) => setState(() {}),
      decoration: const InputDecoration(labelText: 'Sisa waktu (hari)', hintText: '0 = hari ini'),
    );

    final priceField = RupiahField(
      controller: _priceController,
      label: 'Harga jual sekarang',
      onChanged: (_) => setState(() {}),
    );

    final costField = Tooltip(
      message: 'Berapa modal kamu per satu barang ini?',
      child: RupiahField(
        controller: _costController,
        label: 'Harga modal',
        helperText: 'Berapa modal kamu per satu barang ini?',
        onChanged: (_) => setState(() {}),
      ),
    );

    final dailySalesField = TextField(
      controller: _dailySalesController,
      keyboardType: TextInputType.number,
      onChanged: (_) => setState(() {}),
      decoration: const InputDecoration(
        labelText: 'Rata-rata terjual per hari',
        helperText: 'Kira-kira saja, tidak harus tepat.',
        helperMaxLines: 2,
      ),
    );

    final shelfLifeField = TextField(
      controller: _shelfLifeController,
      keyboardType: TextInputType.number,
      onChanged: (_) => setState(() => _shelfLifeAuto = false),
      decoration: InputDecoration(
        labelText: 'Umur simpan total (hari)',
        helperText: _shelfLifeAuto
            ? 'Perkiraan umum untuk kategori ini. Ubah kalau berbeda. (otomatis)'
            : null,
        helperMaxLines: 2,
      ),
    );

    final fields = <Widget>[
      nameField,
      categoryField,
      portionNote,
      stockField,
      daysField,
      priceField,
      costField,
      dailySalesField,
      shelfLifeField,
    ];

    if (!isTablet) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final f in fields) ...[f, const SizedBox(height: AppSpacing.lg)],
        ],
      );
    }

    // Tablet: field pendek (angka) berdampingan.
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        nameField,
        const SizedBox(height: AppSpacing.lg),
        categoryField,
        portionNote,
        const SizedBox(height: AppSpacing.lg),
        Row(children: [
          Expanded(child: stockField),
          const SizedBox(width: AppSpacing.lg),
          Expanded(child: daysField),
        ]),
        const SizedBox(height: AppSpacing.lg),
        Row(children: [
          Expanded(child: priceField),
          const SizedBox(width: AppSpacing.lg),
          Expanded(child: costField),
        ]),
        const SizedBox(height: AppSpacing.lg),
        Row(children: [
          Expanded(child: dailySalesField),
          const SizedBox(width: AppSpacing.lg),
          Expanded(child: shelfLifeField),
        ]),
        const SizedBox(height: AppSpacing.xxl),
      ],
    );
  }
}

class _ModeToggle extends StatelessWidget {
  const _ModeToggle({required this.isFreeText, required this.onChanged});
  final bool isFreeText;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    Widget seg(String label, bool valueForThis) {
      final active = isFreeText == valueForThis;
      return Expanded(
        child: GestureDetector(
          onTap: () => onChanged(valueForThis),
          child: Container(
            height: AppSpacing.minTouchTarget,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: active ? AppColors.primary : Colors.transparent,
              borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
            ),
            child: Text(
              label,
              style: AppTypography.bodyStrong.copyWith(
                color: active ? Colors.white : AppColors.textSecondary,
              ),
            ),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      ),
      child: Row(children: [seg('Ketik Bebas', true), seg('Isi Form', false)]),
    );
  }
}

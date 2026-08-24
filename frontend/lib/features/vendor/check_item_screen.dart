import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
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

class CheckItemScreen extends ConsumerStatefulWidget {
  const CheckItemScreen({super.key, this.prefill});

  final ItemInputDraft? prefill;

  @override
  ConsumerState<CheckItemScreen> createState() => _CheckItemScreenState();
}

class _CheckItemScreenState extends ConsumerState<CheckItemScreen> {
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
    }
    // shop_name tidak punya field sendiri: diambil dari profil saat
    // draft dibangun (_buildDraft), karena tidak ditampilkan ke vendor.
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
    super.dispose();
  }

  void _applyCategoryDefault(ItemCategory c) {
    setState(() {
      _category = c;
      if (_shelfLifeAuto) {
        _shelfLifeController.text = c.defaultShelfLifeDays.toString();
      }
    });
  }

  bool get _isFormValid =>
      _itemNameController.text.trim().isNotEmpty &&
      _category != null &&
      _stockController.text.trim().isNotEmpty &&
      _daysController.text.trim().isNotEmpty &&
      CurrencyFormatter.parseDigits(_priceController.text) > 0 &&
      CurrencyFormatter.parseDigits(_costController.text) > 0 &&
      _dailySalesController.text.trim().isNotEmpty;

  ItemInputDraft _buildDraft() {
    final shopName = ref.read(sessionProvider)?.shop?.shopName;
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
    setState(() => _submitted = true);
    await ref.read(recommendFlowProvider.notifier).submit(_buildDraft());
    if (!mounted) return;
    final state = ref.read(recommendFlowProvider);
    if (state.error != null) {
      setState(() => _submitted = false);
      return;
    }
    switch (state.result!.status) {
      case RecommendResultStatus.needsConfirmation:
        context.pushReplacement(RoutePaths.vendorManualConfirm);
        break;
      case RecommendResultStatus.recommendation:
        context.pushReplacement(RoutePaths.vendorResult);
        break;
      case RecommendResultStatus.noAction:
        context.pushReplacement(RoutePaths.vendorNoAction);
        break;
      case RecommendResultStatus.invalidInput:
        context.pushReplacement(RoutePaths.vendorWarning);
        break;
      case RecommendResultStatus.modelUnavailable:
        setState(() => _submitted = false);
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isTablet = Breakpoints.isTabletOf(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Cek Barang')),
      body: Column(
        children: [
          Expanded(
            // Form dikunci selama pengiriman, bukan sekadar tombolnya.
            child: AbsorbPointer(
              absorbing: _submitted,
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.xl, 0, AppSpacing.xl, AppSpacing.xxxl,
                ),
                child: _structuredForm(isTablet),
              ),
            ),
          ),
          StickyBottomBar(
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isFormValid && !_submitted ? _submitAndGoToProcessing : null,
                child: _submitted
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: Colors.white,
                        ),
                      )
                    : const Text('Dapatkan Rekomendasi'),
              ),
            ),
          ),
        ],
      ),
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
          .map((c) => DropdownMenuItem(value: c, child: Text(c.label)))
          .toList(),
      onChanged: (c) => c != null ? _applyCategoryDefault(c) : null,
    );

    final portionNote = _category?.needsPortionNote == true
        ? const Padding(
            padding: EdgeInsets.only(top: AppSpacing.xs),
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

    // Penjelas ditulis sebagai helperText yang selalu terlihat, bukan
    // Tooltip — di ponsel tidak ada hover, dan §V-02 menyebut vendor
    // sering bingung antara modal per batch dan per unit.
    final costField = RupiahField(
      controller: _costController,
      label: 'Harga modal',
      helperText: 'Berapa modal kamu per satu barang ini?',
      onChanged: (_) => setState(() {}),
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

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
  late Set<String> _missing;

  final _itemNameController = TextEditingController();
  ItemCategory? _category;
  final _stockController = TextEditingController();
  final _daysController = TextEditingController();
  final _priceController = TextEditingController();
  final _costController = TextEditingController();
  final _dailySalesController = TextEditingController();
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    final result = ref.read(recommendFlowProvider).result!;
    _parsed = result.parsedInput!;
    _missing = (result.missingFields ?? []).toSet();

    _itemNameController.text = _parsed.itemName ?? '';
    _category = _parsed.category;
    _stockController.text = _parsed.stock?.toString() ?? '';
    _daysController.text = _parsed.daysRemaining?.toString() ?? '';
    _priceController.text =
        _parsed.originalPrice != null ? CurrencyFormatter.formatDigitsOnly(_parsed.originalPrice!) : '';
    _costController.text =
        _parsed.cost != null ? CurrencyFormatter.formatDigitsOnly(_parsed.cost!) : '';
    _dailySalesController.text = _parsed.dailySales?.toString() ?? '';
  }

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
      totalShelfLife: _parsed.totalShelfLife ?? _category?.defaultShelfLifeDays,
      shopName: _parsed.shopName,
    );
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
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(AppSpacing.md),
                    decoration: BoxDecoration(
                      color: AppColors.perhatianBg,
                      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                    ),
                    child: Text(
                      'Beberapa data belum terbaca dari kalimatmu. Lengkapi dulu, ya.',
                      style: AppTypography.body.copyWith(color: AppColors.perhatian),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  _field('item_name', TextField(
                    controller: _itemNameController,
                    onChanged: (_) => setState(() {}),
                    decoration: const InputDecoration(labelText: 'Nama barang'),
                  )),
                  const SizedBox(height: AppSpacing.lg),
                  _field('category', DropdownButtonFormField<ItemCategory>(
                    initialValue: _category,
                    decoration: const InputDecoration(labelText: 'Kategori'),
                    items: ItemCategory.values
                        .map((c) => DropdownMenuItem(value: c, child: Text(c.label)))
                        .toList(),
                    onChanged: (c) => setState(() => _category = c),
                  )),
                  const SizedBox(height: AppSpacing.lg),
                  _field('stock', TextField(
                    controller: _stockController,
                    keyboardType: TextInputType.number,
                    onChanged: (_) => setState(() {}),
                    decoration: const InputDecoration(labelText: 'Jumlah stok'),
                  )),
                  const SizedBox(height: AppSpacing.lg),
                  _field('days_remaining', TextField(
                    controller: _daysController,
                    keyboardType: TextInputType.number,
                    onChanged: (_) => setState(() {}),
                    decoration: const InputDecoration(labelText: 'Sisa waktu (hari)'),
                  )),
                  const SizedBox(height: AppSpacing.lg),
                  _field('original_price', RupiahField(
                    controller: _priceController,
                    label: 'Harga jual sekarang',
                    onChanged: (_) => setState(() {}),
                  )),
                  const SizedBox(height: AppSpacing.lg),
                  _field('cost', RupiahField(
                    controller: _costController,
                    label: 'Harga modal',
                    onChanged: (_) => setState(() {}),
                  )),
                  const SizedBox(height: AppSpacing.lg),
                  _field('daily_sales', TextField(
                    controller: _dailySalesController,
                    keyboardType: TextInputType.number,
                    onChanged: (_) => setState(() {}),
                    decoration: const InputDecoration(labelText: 'Rata-rata terjual per hari'),
                  )),
                ],
              ),
            ),
          ),
          StickyBottomBar(
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isValid && !_submitting ? _confirm : null,
                child: const Text('Konfirmasi & Lanjutkan'),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _field(String key, Widget child) {
    final isMissing = _missing.contains(key);
    if (!isMissing) return child;
    return Container(
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.perhatian, width: 1.4),
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd + 2),
      ),
      child: child,
    );
  }
}

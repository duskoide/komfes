import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/breakpoints.dart';
import '../../models/deal.dart';
import '../../models/enums.dart';
import '../../models/user.dart';
import '../../state/repository_providers.dart';
import '../../state/session_providers.dart';
import '../../widgets/deal_card.dart';

class SetupShopScreen extends ConsumerStatefulWidget {
  const SetupShopScreen({super.key});

  @override
  ConsumerState<SetupShopScreen> createState() => _SetupShopScreenState();
}

class _SetupShopScreenState extends ConsumerState<SetupShopScreen> {
  final _shopNameController = TextEditingController();
  final _addressController = TextEditingController();
  BusinessType _businessType = BusinessType.warungToko;
  bool _saving = false;

  bool get _isValid => _shopNameController.text.trim().isNotEmpty;

  Future<void> _save() async {
    if (!_isValid) return;
    setState(() => _saving = true);
    final profile = ShopProfile(
      shopName: _shopNameController.text.trim(),
      businessType: _businessType,
      shortAddress: _addressController.text.trim().isEmpty ? null : _addressController.text.trim(),
    );
    await ref.read(authRepositoryProvider).saveShopProfile(profile);
    if (!mounted) return;
    ref.read(sessionProvider.notifier).updateShop(profile);
    setState(() => _saving = false);
    context.go(RoutePaths.vendorHome);
  }

  Deal get _previewDeal => Deal(
        id: 'preview',
        itemName: 'Roti Tawar',
        shopName: _shopNameController.text.trim().isEmpty
            ? 'Nama tokomu di sini'
            : _shopNameController.text.trim(),
        category: ItemCategory.bakery,
        originalPrice: 15000,
        dealPrice: 10500,
        discountPercent: 30,
        daysRemaining: 1,
        initialStock: 10,
        remainingStock: 8,
        promoCopy: 'Contoh: roti tawar fresh, diskon karena mendekati kadaluarsa.',
        status: DealStatus.active,
        createdAt: DateTime.now(),
      );

  Widget _form() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Nama toko', style: AppTypography.label),
        const SizedBox(height: AppSpacing.sm),
        TextField(
          controller: _shopNameController,
          autofocus: true,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(hintText: 'Contoh: Toko Sari Bakery'),
        ),
        const SizedBox(height: AppSpacing.lg),
        Text('Jenis usaha', style: AppTypography.label),
        const SizedBox(height: AppSpacing.sm),
        DropdownButtonFormField<BusinessType>(
          initialValue: _businessType,
          items: BusinessType.values
              .map((b) => DropdownMenuItem(value: b, child: Text(b.label)))
              .toList(),
          onChanged: (v) => setState(() => _businessType = v ?? _businessType),
        ),
        const SizedBox(height: AppSpacing.lg),
        Text('Alamat singkat (opsional)', style: AppTypography.label),
        const SizedBox(height: AppSpacing.sm),
        TextField(
          controller: _addressController,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
            hintText: 'Contoh: Jl. Merdeka No. 12, dekat pasar',
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: _isValid && !_saving ? _save : null,
            child: _saving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Simpan & Lanjutkan'),
          ),
        ),
      ],
    );
  }

  Widget _previewSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Beginilah tampilannya untuk pembeli', style: AppTypography.label),
        const SizedBox(height: AppSpacing.sm),
        DealCard(deal: _previewDeal, audience: DealCardAudience.consumer, density: DealCardDensity.lengkap),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final isTablet = Breakpoints.isTabletOf(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Setup Toko')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: isTablet
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: _form()),
                    const SizedBox(width: AppSpacing.xxl),
                    Expanded(child: _previewSection()),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _form(),
                    const SizedBox(height: AppSpacing.xxl),
                    _previewSection(),
                  ],
                ),
        ),
      ),
    );
  }
}

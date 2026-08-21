import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../models/recommendation.dart';
import '../../state/recommend_providers.dart';

/// Tiga varian peringatan, satu layout (§V-07).
enum _WarningVariant {
  /// `cost >= original_price` — diskon apa pun akan merugikan vendor.
  costTooHigh,

  /// Barang sudah lewat tanggal; tidak ada jalan perbaikan input.
  expired,

  /// Angka lain yang tidak masuk akal.
  oddNumbers,
}

class InputWarningScreen extends ConsumerWidget {
  const InputWarningScreen({super.key});

  /// Varian ditentukan dari data yang dikirim vendor, bukan dari teks pesan
  /// server — mencocokkan string pesan akan rapuh begitu copy diubah.
  _WarningVariant _variantOf(ItemInputDraft? draft) {
    if (draft == null) return _WarningVariant.oddNumbers;

    final days = draft.daysRemaining;
    if (days != null && days < 0) return _WarningVariant.expired;

    final cost = draft.cost;
    final price = draft.originalPrice;
    if (cost != null && price != null && price > 0 && cost >= price) {
      return _WarningVariant.costTooHigh;
    }
    return _WarningVariant.oddNumbers;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flow = ref.watch(recommendFlowProvider);
    final result = flow.result!;
    final variant = _variantOf(flow.draft);

    final (title, fallback) = switch (variant) {
      _WarningVariant.costTooHigh => (
          'Cek harga modalmu',
          'Harga modal sama atau lebih besar dari harga jual. '
              'Diskon akan membuatmu rugi.',
        ),
      _WarningVariant.expired => (
          'Barang sudah kadaluarsa',
          'Sebaiknya tidak dijual. Pertimbangkan untuk dibuang atau didonasikan.',
        ),
      _WarningVariant.oddNumbers => (
          'Ada data yang aneh',
          'Ada angka yang tampak tidak sesuai. Coba periksa lagi isinya.',
        ),
    };

    // Barang kadaluarsa tidak bisa diperbaiki dengan mengedit input, jadi
    // aksi primernya mengarah ke barang lain (§V-07).
    final isExpired = variant == _WarningVariant.expired;

    return Scaffold(
      appBar: AppBar(title: const Text('Cek Barang')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 88,
                height: 88,
                decoration: const BoxDecoration(
                  color: AppColors.kritisBg,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  isExpired ? Icons.delete_outline : Icons.warning_rounded,
                  size: 44,
                  color: AppColors.kritis,
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              Text(title, style: AppTypography.h1, textAlign: TextAlign.center),
              const SizedBox(height: AppSpacing.sm),
              // Pesan server memuat angka yang bermasalah; fallback dipakai
              // hanya kalau server tidak mengirim apa pun.
              Text(
                result.message ?? fallback,
                style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.xxl),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    if (isExpired) {
                      ref.read(recommendFlowProvider.notifier).reset();
                      context.pushReplacement(RoutePaths.vendorCheckItem);
                    } else {
                      // Data vendor tidak boleh hilang saat kembali (§V-07).
                      context.pushReplacement(
                        RoutePaths.vendorCheckItem,
                        extra: flow.draft,
                      );
                    }
                  },
                  child: Text(isExpired ? 'Cek Barang Lain' : 'Perbaiki Input'),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              TextButton(
                onPressed: () {
                  ref.read(recommendFlowProvider.notifier).reset();
                  context.go(RoutePaths.vendorHome);
                },
                child: const Text('Kembali ke Beranda'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

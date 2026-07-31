import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../models/enums.dart';
import '../../models/recommendation.dart';
import '../../state/recommend_providers.dart';

class AiProcessingScreen extends ConsumerStatefulWidget {
  const AiProcessingScreen({super.key, required this.draft});

  final ItemInputDraft draft;

  @override
  ConsumerState<AiProcessingScreen> createState() => _AiProcessingScreenState();
}

class _AiProcessingScreenState extends ConsumerState<AiProcessingScreen> {
  static const _steps = [
    'Membaca data barang...',
    'Menghitung sisa waktu jual...',
    'Menyusun rekomendasi harga...',
  ];
  int _stepIndex = 0;

  @override
  void initState() {
    super.initState();
    _cycleSteps();
    _run();
  }

  Future<void> _cycleSteps() async {
    for (var i = 0; i < 40; i++) {
      await Future.delayed(const Duration(milliseconds: 700));
      if (!mounted) return;
      setState(() => _stepIndex = (_stepIndex + 1) % _steps.length);
    }
  }

  Future<void> _run() async {
    await ref.read(recommendFlowProvider.notifier).submit(widget.draft);
    if (!mounted) return;
    final state = ref.read(recommendFlowProvider);

    if (state.error != null) {
      return;
    }

    switch (state.result!.status) {
      case RecommendResultStatus.needsConfirmation:
        context.pushReplacement(RoutePaths.vendorConfirm);
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
        break; // ditangani lewat state.error di atas
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(recommendFlowProvider);
    final hasError = state.error != null;

    return Scaffold(
      appBar: AppBar(title: const Text('Cek Barang')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          child: hasError ? _errorContent(state) : _loadingContent(),
        ),
      ),
    );
  }

  Widget _loadingContent() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 96,
          height: 96,
          decoration: const BoxDecoration(color: AppColors.primaryLight, shape: BoxShape.circle),
          child: const Padding(
            padding: EdgeInsets.all(24),
            child: CircularProgressIndicator(strokeWidth: 3, color: AppColors.primary),
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        Text(
          _steps[_stepIndex],
          key: ValueKey(_stepIndex),
          style: AppTypography.h3,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Biasanya kurang dari 5 detik.',
          style: AppTypography.caption,
        ),
      ],
    );
  }

  Widget _errorContent(RecommendFlowState state) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.cloud_off, size: 56, color: AppColors.textSecondary),
        const SizedBox(height: AppSpacing.lg),
        Text('Sistem AI sedang tidak tersedia', style: AppTypography.h3, textAlign: TextAlign.center),
        const SizedBox(height: AppSpacing.sm),
        Text(
          state.error!.message,
          style: AppTypography.body.copyWith(color: AppColors.textSecondary),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: AppSpacing.xl),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(onPressed: _run, child: const Text('Coba Lagi')),
        ),
        const SizedBox(height: AppSpacing.sm),
        TextButton(
          onPressed: () => context.pop(),
          child: const Text('Ubah Input'),
        ),
      ],
    );
  }
}

import 'dart:async';

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
import '../../widgets/item_summary.dart';

class AiProcessingScreen extends ConsumerStatefulWidget {
  const AiProcessingScreen({super.key, required this.draft});

  final ItemInputDraft draft;

  @override
  ConsumerState<AiProcessingScreen> createState() => _AiProcessingScreenState();
}

class _AiProcessingScreenState extends ConsumerState<AiProcessingScreen> {
  /// Ambang waktu tombol "Batalkan" muncul (§V-04).
  static const _cancelAfter = Duration(seconds: 15);

  final _stopwatch = Stopwatch();
  Timer? _ticker;
  Duration _elapsed = Duration.zero;

  @override
  void initState() {
    super.initState();
    _stopwatch.start();
    _ticker = Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (!mounted) return;
      setState(() => _elapsed = _stopwatch.elapsed);
    });
    // submit() mengubah state provider secara sinkron di baris pertamanya.
    // Memanggilnya langsung dari initState memicu error Riverpod
    // "Tried to modify a provider while the widget tree was building",
    // sehingga proses berhenti dan layar macet di loading. Tunda sampai
    // frame pertama selesai dibangun.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _run();
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _stopwatch.stop();
    super.dispose();
  }

  /// Teks status maju bertahap mengikuti waktu berjalan dan berhenti di
  /// tahap terakhir — tidak berputar melingkar, karena teks yang kembali
  /// ke "Membaca data" terlihat seperti proses mengulang dari nol (§V-04).
  String get _statusText {
    final s = _elapsed.inSeconds;
    if (s >= 20) return 'Sedikit lebih lama dari biasanya, mohon tunggu...';
    if (s >= 7) return 'Menyiapkan rekomendasi...';
    if (s >= 3) return 'Menghitung harga terbaik...';
    return 'Membaca data barangmu...';
  }

  bool get _canCancel => _elapsed >= _cancelAfter;

  Future<void> _run() async {
    if (!_stopwatch.isRunning) {
      _stopwatch
        ..reset()
        ..start();
    }
    await ref.read(recommendFlowProvider.notifier).submit(widget.draft);
    if (!mounted) return;
    _stopwatch.stop();
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

  /// Kembali ke V-02 tanpa membuang apa pun yang sudah diisi vendor.
  void _backToInput() {
    context.pushReplacement(RoutePaths.vendorManualForm, extra: widget.draft);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(recommendFlowProvider);
    final hasError = state.error != null;

    return Scaffold(
      appBar: AppBar(title: const Text('Cek Barang')),
      body: Center(
        child: SingleChildScrollView(
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
          decoration: const BoxDecoration(
            color: AppColors.primaryLight,
            shape: BoxShape.circle,
          ),
          child: const Padding(
            padding: EdgeInsets.all(24),
            // Indeterminate: durasi tidak bisa diprediksi, dan progress bar
            // berpersentase yang macet lebih buruk daripada tanpa bar (§V-04).
            child: CircularProgressIndicator(strokeWidth: 3, color: AppColors.primary),
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 220),
          child: Text(
            _statusText,
            key: ValueKey(_statusText),
            style: AppTypography.h3,
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        const Text('Biasanya kurang dari 5 detik.', style: AppTypography.caption),
        const SizedBox(height: AppSpacing.xl),
        ItemSummary(draft: widget.draft),
        // Tombol batal sengaja disembunyikan sebelum detik ke-15 supaya
        // vendor tidak membatalkan proses yang sebenarnya normal (§V-04).
        if (_canCancel) ...[
          const SizedBox(height: AppSpacing.xl),
          TextButton(onPressed: _backToInput, child: const Text('Batalkan')),
        ],
      ],
    );
  }

  Widget _errorContent(RecommendFlowState state) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.cloud_off, size: 56, color: AppColors.textSecondary),
        const SizedBox(height: AppSpacing.lg),
        const Text(
          'Sistem AI sedang tidak tersedia',
          style: AppTypography.h3,
          textAlign: TextAlign.center,
        ),
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
        SizedBox(
          width: double.infinity,
          // §V-04: saat model mati, tawarkan jalur manual — bukan hanya
          // menyuruh vendor mencoba lagi terus-menerus.
          child: OutlinedButton(
            onPressed: _backToInput,
            child: const Text('Isi Form Manual'),
          ),
        ),
      ],
    );
  }
}

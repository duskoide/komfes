import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../models/recommendation.dart';
import '../../state/chat_providers.dart';
import '../../widgets/chat_bubble.dart';
import '../../widgets/known_fields_card.dart';
import 'chat_confirm_card.dart';
import 'chat_result_card.dart';

/// V-02 versi baru: konsultasi percakapan berpagar (SRS Penyisihan v2.0).
///
/// Layar ini tidak pernah menghitung apa pun. Setiap angka datang dari hasil
/// tool pricing di server, dan setiap keputusan alur diambil dari `action`
/// yang dikembalikan orchestrator — bukan dari menebak isi kalimat asisten.
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _composer = TextEditingController();
  final _scroll = ScrollController();

  @override
  void dispose() {
    _composer.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _send() async {
    final text = _composer.text;
    if (text.trim().isEmpty) return;
    _composer.clear();
    _scrollToBottom();
    await ref.read(chatFlowProvider.notifier).sendMessage(text);
    _scrollToBottom();
  }

  Future<void> _confirmAndCalculate(ItemInputDraft? patch) async {
    final notifier = ref.read(chatFlowProvider.notifier);
    await notifier.confirm(patch: patch);
    if (!mounted) return;

    final flow = ref.read(chatFlowProvider);
    // Server boleh langsung menghitung begitu revisinya dikonfirmasi. Kalau
    // hasilnya sudah datang, jangan minta calculate lagi — itu tidak memicu
    // perhitungan kedua, tapi menghasilkan pesan asisten yang kembar.
    if (flow.stateOrEmpty.confirmed && !flow.hasResult) {
      await notifier.calculate();
    }
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final flow = ref.watch(chatFlowProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Konsultasi Harga'),
        actions: [
          IconButton(
            tooltip: 'Mulai konsultasi baru',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: flow.isSending
                ? null
                : () => ref.read(chatFlowProvider.notifier).reset(),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              controller: _scroll,
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                AppSpacing.lg,
                AppSpacing.lg,
                AppSpacing.xl,
              ),
              children: [
                if (flow.messages.isEmpty) const _Opening(),
                for (final message in flow.messages) ChatBubble(message: message),
                if (flow.consultation != null)
                  KnownFieldsCard(
                    item: flow.stateOrEmpty.item,
                    missingFields: flow.missingFields,
                    ambiguousFields: flow.ambiguousFields,
                  ),
                if (flow.showConfirmation)
                  ChatConfirmCard(
                    item: flow.stateOrEmpty.item,
                    busy: flow.isSending,
                    onConfirm: _confirmAndCalculate,
                  ),
                if (flow.result != null) ChatResultCard(result: flow.result!),
                if (flow.error != null)
                  _ErrorBanner(
                    message: flow.error!.message,
                    busy: flow.isSending,
                    onRetry: () => ref.read(chatFlowProvider.notifier).retry(),
                  ),
              ],
            ),
          ),
          _Composer(
            controller: _composer,
            busy: flow.isSending,
            onSend: _send,
            onManualForm: () => context.push(RoutePaths.vendorCheckItem),
          ),
        ],
      ),
    );
  }
}

class _Opening extends StatelessWidget {
  const _Opening();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Cerita saja barangmu', style: AppTypography.h2),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Tulis apa adanya, tidak harus lengkap. Kalau ada yang kurang, '
            'nanti aku tanya.',
            style: AppTypography.body.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: AppSpacing.lg),
          Container(
            padding: const EdgeInsets.all(AppSpacing.lg),
            decoration: BoxDecoration(
              color: AppColors.surfaceAlt,
              borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
            ),
            child: const Text(
              'roti tawar 10 biji exp 2 hari harga 15rb modal 10rb',
              style: AppTypography.caption,
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({
    required this.message,
    required this.busy,
    required this.onRetry,
  });

  final String message;
  final bool busy;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.errorBg,
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            message,
            style: AppTypography.body.copyWith(color: AppColors.error),
          ),
          const SizedBox(height: AppSpacing.sm),
          // Input vendor tidak hilang: permintaan terakhir diingat controller,
          // jadi "Coba Lagi" tidak menyuruh dia mengetik ulang.
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: busy ? null : onRetry,
              child: const Text('Coba Lagi'),
            ),
          ),
        ],
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.busy,
    required this.onSend,
    required this.onManualForm,
  });

  final TextEditingController controller;
  final bool busy;
  final VoidCallback onSend;
  final VoidCallback onManualForm;

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;
    return Container(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.md,
        AppSpacing.lg,
        AppSpacing.md +
            (bottomInset > 0 ? 0 : MediaQuery.paddingOf(context).bottom),
      ),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.send,
                  onSubmitted: busy ? null : (_) => onSend(),
                  decoration: const InputDecoration(
                    hintText: 'Tulis di sini...',
                    isDense: true,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              SizedBox(
                width: AppSpacing.minTouchTarget,
                height: AppSpacing.minTouchTarget,
                child: IconButton.filled(
                  onPressed: busy ? null : onSend,
                  icon: busy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.arrow_upward_rounded),
                ),
              ),
            ],
          ),
          // Jalur cadangan wajib: kalau model mati atau vendor lebih nyaman
          // mengisi form, jalannya tetap ada — tapi bukan pintu utama.
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              onPressed: busy ? null : onManualForm,
              child: const Text('Isi form manual'),
            ),
          ),
        ],
      ),
    );
  }
}

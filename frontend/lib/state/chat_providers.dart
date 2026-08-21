import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/chat.dart';
import '../models/recommendation.dart';
import '../services/app_exception.dart';
import '../services/chat_repository.dart';
import 'repository_providers.dart';

/// Siapa yang berbicara. `system` dipakai untuk pemberitahuan klien seperti
/// sesi berakhir — dibedakan supaya tidak terlihat seolah model yang bicara.
enum ChatAuthor { vendor, assistant, system }

class ChatMessage {
  const ChatMessage({
    required this.author,
    required this.text,
    this.action,
    this.isPending = false,
  });

  final ChatAuthor author;
  final String text;

  /// Aksi orchestrator yang menghasilkan pesan ini, kalau ada.
  final ChatAction? action;

  /// Pesan vendor yang belum dikonfirmasi server.
  final bool isPending;

  ChatMessage settled() => ChatMessage(
        author: author,
        text: text,
        action: action,
        isPending: false,
      );
}

class ChatFlowState {
  const ChatFlowState({
    this.sessionId,
    this.messages = const [],
    this.consultation,
    this.missingFields = const [],
    this.ambiguousFields = const [],
    this.lastAction,
    this.result,
    this.isSending = false,
    this.error,
  });

  final String? sessionId;
  final List<ChatMessage> messages;
  final ConsultationState? consultation;
  final List<String> missingFields;
  final List<String> ambiguousFields;
  final ChatAction? lastAction;
  final RecommendResult? result;
  final bool isSending;
  final AppException? error;

  ConsultationState get stateOrEmpty => consultation ?? ConsultationState.empty();

  /// Kartu konfirmasi hanya relevan saat orchestrator memintanya.
  bool get showConfirmation => lastAction == ChatAction.showConfirmation;

  bool get hasResult => result != null;

  ChatFlowState copyWith({
    String? sessionId,
    List<ChatMessage>? messages,
    ConsultationState? consultation,
    List<String>? missingFields,
    List<String>? ambiguousFields,
    ChatAction? lastAction,
    RecommendResult? result,
    bool clearResult = false,
    bool? isSending,
    AppException? error,
    bool clearError = false,
  }) {
    return ChatFlowState(
      sessionId: sessionId ?? this.sessionId,
      messages: messages ?? this.messages,
      consultation: consultation ?? this.consultation,
      missingFields: missingFields ?? this.missingFields,
      ambiguousFields: ambiguousFields ?? this.ambiguousFields,
      lastAction: lastAction ?? this.lastAction,
      result: clearResult ? null : (result ?? this.result),
      isSending: isSending ?? this.isSending,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class ChatFlowNotifier extends StateNotifier<ChatFlowState> {
  ChatFlowNotifier(this._ref) : super(const ChatFlowState());

  final Ref _ref;

  ChatRepository get _repo => _ref.read(chatRepositoryProvider);

  /// Teks terakhir yang dikirim vendor, dipakai untuk "Coba Lagi" tanpa
  /// membuat dia mengetik ulang.
  String? _lastText;
  ChatRequestAction? _lastAction;
  ItemInputDraft? _lastPatch;

  Future<void> sendMessage(String text) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return Future.value();
    _appendVendor(trimmed);
    return _run(ChatRequestAction.message, text: trimmed);
  }

  /// Vendor menekan konfirmasi. [patch] berisi field yang dia sunting di
  /// kartu konfirmasi, boleh kosong kalau tidak ada yang diubah.
  Future<void> confirm({ItemInputDraft? patch}) =>
      _run(ChatRequestAction.confirm, patch: patch);

  Future<void> calculate() => _run(ChatRequestAction.calculate);

  Future<void> explain() => _run(ChatRequestAction.explain);

  Future<void> revisePromo(String instruction) =>
      _run(ChatRequestAction.revisePromo, text: instruction);

  /// Mulai konsultasi baru. Server diberi tahu supaya sesinya ikut dibuang,
  /// tapi kalau gagal pun state klien tetap dibersihkan.
  Future<void> reset() async {
    final sessionId = state.sessionId;
    state = const ChatFlowState();
    _lastText = null;
    _lastAction = null;
    _lastPatch = null;
    if (sessionId == null) return;
    try {
      await _repo.send(action: ChatRequestAction.reset, sessionId: sessionId);
    } on AppException catch (_) {
      // Diabaikan dengan sengaja: sesi baru sudah dimulai di sisi klien.
    }
  }

  /// Ulangi permintaan terakhir yang gagal.
  Future<void> retry() {
    final action = _lastAction;
    if (action == null) return Future.value();
    return _run(action, text: _lastText, patch: _lastPatch);
  }

  void _appendVendor(String text) {
    state = state.copyWith(
      messages: [
        ...state.messages,
        ChatMessage(author: ChatAuthor.vendor, text: text, isPending: true),
      ],
      clearError: true,
    );
  }

  void _appendSystem(String text) {
    state = state.copyWith(
      messages: [
        ...state.messages,
        ChatMessage(author: ChatAuthor.system, text: text),
      ],
    );
  }

  Future<void> _run(
    ChatRequestAction action, {
    String? text,
    ItemInputDraft? patch,
  }) async {
    _lastAction = action;
    _lastText = text;
    _lastPatch = patch;

    state = state.copyWith(isSending: true, clearError: true);
    try {
      final turn = await _repo.send(
        action: action,
        sessionId: state.sessionId,
        text: text,
        patch: patch,
      );
      _applyTurn(turn);
    } on SessionExpiredException catch (e) {
      // Sesi hilang di server: bersihkan dan katakan, jangan diam-diam gagal.
      state = const ChatFlowState();
      _appendSystem(e.message);
    } on AppException catch (e) {
      state = state.copyWith(isSending: false, error: e);
    } catch (e) {
      state = state.copyWith(
        isSending: false,
        error: const RequestFailedException(),
      );
      if (kDebugMode) print('chat error: $e');
    }
  }

  void _applyTurn(ChatTurn turn) {
    final settled = [
      for (final m in state.messages) m.isPending ? m.settled() : m,
      if (turn.assistantMessage.trim().isNotEmpty)
        ChatMessage(
          author: ChatAuthor.assistant,
          text: turn.assistantMessage.trim(),
          action: turn.action,
        ),
    ];

    // freshResult sudah menolak hasil yang revisinya tidak lagi cocok, jadi
    // koreksi vendor otomatis membuat hasil lama hilang dari layar.
    final fresh = turn.freshResult;

    state = state.copyWith(
      sessionId: turn.sessionId.isEmpty ? state.sessionId : turn.sessionId,
      messages: settled,
      consultation: turn.state,
      missingFields: turn.missingFields,
      ambiguousFields: turn.ambiguousFields,
      lastAction: turn.action,
      result: fresh,
      clearResult: fresh == null,
      isSending: false,
      clearError: true,
    );
  }
}

final chatFlowProvider =
    StateNotifierProvider<ChatFlowNotifier, ChatFlowState>(
  (ref) => ChatFlowNotifier(ref),
);

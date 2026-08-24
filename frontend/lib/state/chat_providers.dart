import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/chat.dart';
import '../models/chat_attachment.dart';
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
  final ChatAction? action;
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
    this.attachment,
    this.uploadProgress = 0,
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
  final ChatAttachment? attachment;
  final double uploadProgress;

  ConsultationState get stateOrEmpty =>
      consultation ?? ConsultationState.empty();
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
    ChatAttachment? attachment,
    bool clearAttachment = false,
    double? uploadProgress,
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
      attachment: clearAttachment ? null : (attachment ?? this.attachment),
      uploadProgress: uploadProgress ?? this.uploadProgress,
    );
  }
}

class ChatFlowNotifier extends StateNotifier<ChatFlowState> {
  ChatFlowNotifier(this._ref) : super(const ChatFlowState());

  final Ref _ref;
  ChatRepository get _repo => _ref.read(chatRepositoryProvider);

  String? _lastText;
  ChatRequestAction? _lastAction;
  ItemInputDraft? _lastPatch;
  ChatAttachment? _lastAttachment;

  Future<void> selectAttachment(ChatAttachment attachment) async {
    final error = ChatAttachmentValidator.errorFor(attachment);
    if (error != null) {
      state = state.copyWith(error: InvalidInputException(error));
      return;
    }
    if (state.attachment != null || state.isSending) return;
    state = state.copyWith(
      attachment: attachment,
      clearError: true,
      uploadProgress: 0,
    );
  }

  void removeAttachment() {
    if (!state.isSending) {
      _lastAttachment = null;
      state = state.copyWith(clearAttachment: true);
    }
  }

  Future<void> sendAttachment({String? text, bool appendMessage = true}) async {
    final attachment = state.attachment;
    if (attachment == null || state.isSending) return;
    _lastAttachment = attachment;
    _lastText = text?.trim();
    state = state.copyWith(
      isSending: true,
      clearError: true,
      uploadProgress: 0,
      messages: appendMessage
          ? [
              ...state.messages,
              ChatMessage(
                author: ChatAuthor.vendor,
                text: _lastText?.isNotEmpty == true
                    ? _lastText!
                    : 'Lampiran gambar',
                isPending: true,
              ),
            ]
          : state.messages,
    );
    try {
      final turn = await _repo.sendImage(
        attachment: attachment,
        sessionId: state.sessionId,
        text: _lastText,
        onProgress: (sent, total) {
          if (total > 0) {
            state = state.copyWith(uploadProgress: sent / total);
          }
        },
      );
      _applyTurn(turn);
      _lastAttachment = null;
      state = state.copyWith(clearAttachment: true, uploadProgress: 0);
    } on AppException catch (e) {
      state = state.copyWith(
        isSending: false,
        uploadProgress: 0,
        error: e,
      );
    } catch (e) {
      state = state.copyWith(
        isSending: false,
        uploadProgress: 0,
        error: const RequestFailedException(),
      );
      if (kDebugMode) print('chat image error: $e');
    }
  }

  Future<void> retryAttachment() async {
    if (_lastAttachment == null || state.isSending) return;
    state = state.copyWith(attachment: _lastAttachment, clearError: true);
    await sendAttachment(text: _lastText, appendMessage: false);
  }

  Future<void> sendMessage(String text) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return Future.value();
    _appendVendor(trimmed);
    return _run(ChatRequestAction.message, text: trimmed);
  }

  Future<void> confirm({ItemInputDraft? patch}) =>
      _run(ChatRequestAction.confirm, patch: patch);
  Future<void> calculate() => _run(ChatRequestAction.calculate);
  Future<void> explain() => _run(ChatRequestAction.explain);
  Future<void> revisePromo(String instruction) =>
      _run(ChatRequestAction.revisePromo, text: instruction);

  Future<void> reset() async {
    final sessionId = state.sessionId;
    state = const ChatFlowState();
    _lastText = null;
    _lastAction = null;
    _lastPatch = null;
    _lastAttachment = null;
    if (sessionId == null) return;
    try {
      await _repo.send(action: ChatRequestAction.reset, sessionId: sessionId);
    } on AppException catch (_) {}
  }

  Future<void> retry() {
    if (_lastAttachment != null) return retryAttachment();
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

final chatFlowProvider = StateNotifierProvider<ChatFlowNotifier, ChatFlowState>(
  (ref) => ChatFlowNotifier(ref),
);

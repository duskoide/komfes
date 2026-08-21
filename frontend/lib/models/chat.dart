import 'recommendation.dart';

/// Aksi yang boleh dilakukan orchestrator, sesuai allowlist §3.1 Agentic
/// Workflow Plan. Klien merender berdasarkan nilai ini, bukan dengan
/// menebak isi kalimat asisten.
enum ChatAction {
  askForMissingFields('ASK_FOR_MISSING_FIELDS'),
  showConfirmation('SHOW_CONFIRMATION'),
  callPricingTool('CALL_PRICING_TOOL'),
  explainResult('EXPLAIN_RESULT'),
  revisePromoCopy('REVISE_PROMO_COPY'),
  outOfScope('OUT_OF_SCOPE'),
  safeFailure('SAFE_FAILURE');

  const ChatAction(this.wireValue);

  final String wireValue;

  /// Aksi yang tidak dikenal diperlakukan sebagai kegagalan aman, bukan
  /// dilempar sebagai exception — state vendor tidak boleh hilang hanya
  /// karena server mengirim nilai yang belum dikenal klien.
  static ChatAction fromWire(String value) {
    for (final action in ChatAction.values) {
      if (action.wireValue == value) return action;
    }
    return ChatAction.safeFailure;
  }
}

/// Aksi yang dikirim klien. Tidak sama dengan [ChatAction]: ini permintaan,
/// itu keputusan orchestrator.
enum ChatRequestAction {
  message('message'),
  confirm('confirm'),
  calculate('calculate'),
  explain('explain'),
  revisePromo('revise_promo'),
  reset('reset');

  const ChatRequestAction(this.wireValue);

  final String wireValue;
}

/// State percakapan (§3.2). Sembilan field barang dipakai ulang lewat
/// [ItemInputDraft] karena kuncinya identik dengan `/api/recommend`.
class ConsultationState {
  const ConsultationState({
    required this.item,
    required this.confirmed,
    required this.revision,
    this.resultRevision,
  });

  final ItemInputDraft item;
  final bool confirmed;
  final int revision;
  final int? resultRevision;

  /// Hasil hanya boleh dirender kalau revisinya sama dengan revisi state.
  /// Inilah yang membuat hasil basi otomatis hilang setelah koreksi.
  bool get hasFreshResult => resultRevision != null && resultRevision == revision;

  factory ConsultationState.fromJson(Map<String, dynamic> json) {
    return ConsultationState(
      item: ItemInputDraft.fromJson(json),
      confirmed: json['confirmed'] as bool? ?? false,
      revision: (json['revision'] as num?)?.toInt() ?? 0,
      resultRevision: (json['result_revision'] as num?)?.toInt(),
    );
  }

  static ConsultationState empty() => ConsultationState(
        item: ItemInputDraft(),
        confirmed: false,
        revision: 0,
      );
}

/// Satu balasan dari `POST /api/chat`.
class ChatTurn {
  const ChatTurn({
    required this.sessionId,
    required this.action,
    required this.assistantMessage,
    required this.state,
    this.missingFields = const [],
    this.ambiguousFields = const [],
    this.result,
    this.resultRevision,
  });

  final String sessionId;
  final ChatAction action;
  final String assistantMessage;
  final ConsultationState state;
  final List<String> missingFields;
  final List<String> ambiguousFields;
  final RecommendResult? result;
  final int? resultRevision;

  /// Hasil yang boleh ditampilkan: ada, dan revisinya masih sesuai.
  RecommendResult? get freshResult {
    if (result == null) return null;
    if (resultRevision != null && resultRevision != state.revision) return null;
    return result;
  }

  factory ChatTurn.fromJson(Map<String, dynamic> json) {
    final resultJson = json['result'] as Map<String, dynamic>?;
    return ChatTurn(
      sessionId: json['session_id'] as String? ?? '',
      action: ChatAction.fromWire(json['action'] as String? ?? ''),
      assistantMessage: json['assistant_message'] as String? ?? '',
      state: ConsultationState.fromJson(
        (json['state'] as Map<String, dynamic>?) ?? const {},
      ),
      missingFields: _stringList(json['missing_fields']),
      ambiguousFields: _stringList(json['ambiguous_fields']),
      result: resultJson == null ? null : RecommendResult.fromJson(resultJson),
      resultRevision: resultJson == null
          ? null
          : (resultJson['revision'] as num?)?.toInt(),
    );
  }

  static List<String> _stringList(Object? raw) {
    if (raw is! List) return const [];
    return raw.whereType<String>().toList(growable: false);
  }
}

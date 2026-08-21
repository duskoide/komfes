import 'dart:async';

import 'package:hargaturun/models/chat.dart';
import 'package:hargaturun/models/recommendation.dart';
import 'package:hargaturun/services/chat_repository.dart';

/// Satu panggilan yang tercatat, supaya test bisa memastikan aksi apa yang
/// benar-benar dikirim ke server — bukan hanya apa yang tampak di layar.
class RecordedCall {
  RecordedCall({
    required this.action,
    this.sessionId,
    this.text,
    this.patch,
  });

  final ChatRequestAction action;
  final String? sessionId;
  final String? text;
  final ItemInputDraft? patch;
}

/// Test double untuk [ChatRepository].
///
/// Tidak meniru logika server sama sekali: dia hanya mengembalikan payload
/// yang sudah disiapkan test. Tidak ada perhitungan harga di sini, karena
/// angka apa pun yang dihitung di sisi klien akan menyesatkan.
class FakeChatRepository implements ChatRepository {
  final List<RecordedCall> calls = [];

  /// Kalau diisi, panggilan berikutnya menggantung sampai completer selesai —
  /// dipakai untuk menguji state loading.
  Completer<ChatTurn>? pending;

  /// Kalau diisi, panggilan berikutnya melempar ini.
  Object? error;

  ChatTurn? nextTurn;

  @override
  Future<ChatTurn> send({
    required ChatRequestAction action,
    String? sessionId,
    String? text,
    ItemInputDraft? patch,
  }) {
    calls.add(RecordedCall(
      action: action,
      sessionId: sessionId,
      text: text,
      patch: patch,
    ));

    final gate = pending;
    if (gate != null) {
      pending = null;
      return gate.future;
    }
    final failure = error;
    if (failure != null) {
      error = null;
      return Future<ChatTurn>.error(failure);
    }
    return Future.value(nextTurn);
  }
}

/// Payload sengaja dibangun sebagai JSON dan dilewatkan `fromJson`, supaya
/// pemetaan kontrak yang sebenarnya ikut teruji, bukan dilangkahi.
ChatTurn askForMissingTurn({String sessionId = 'sesi-1'}) {
  return ChatTurn.fromJson({
    'session_id': sessionId,
    'action': 'ASK_FOR_MISSING_FIELDS',
    'assistant_message':
        'Sudah kucatat rotinya. Rata-rata terjual berapa per hari?',
    'state': {
      'item_name': 'Roti Tawar',
      'category': 'Bakery',
      'original_price': 15000,
      'cost': 10000,
      'stock': 10,
      'days_remaining': 2,
      'daily_sales': null,
      'total_shelf_life': 4,
      'shop_name': null,
      'confirmed': false,
      'revision': 1,
      'result_revision': null,
    },
    'missing_fields': ['daily_sales'],
    'ambiguous_fields': <String>[],
    'result': null,
  });
}

ChatTurn showConfirmationTurn({String sessionId = 'sesi-1'}) {
  return ChatTurn.fromJson({
    'session_id': sessionId,
    'action': 'SHOW_CONFIRMATION',
    'assistant_message': 'Semua sudah lengkap. Cek dulu, ya.',
    'state': _completeState(revision: 2, confirmed: false),
    'missing_fields': <String>[],
    'ambiguous_fields': <String>[],
    'result': null,
  });
}

ChatTurn confirmedTurn({String sessionId = 'sesi-1'}) {
  return ChatTurn.fromJson({
    'session_id': sessionId,
    'action': 'SHOW_CONFIRMATION',
    'assistant_message': 'Terkonfirmasi.',
    'state': _completeState(revision: 2, confirmed: true),
    'missing_fields': <String>[],
    'ambiguous_fields': <String>[],
    'result': null,
  });
}

ChatTurn recommendationTurn({
  String sessionId = 'sesi-1',
  int revision = 2,
  int resultRevision = 2,
}) {
  return ChatTurn.fromJson({
    'session_id': sessionId,
    'action': 'EXPLAIN_RESULT',
    'assistant_message': 'Ini rekomendasinya.',
    'state': _completeState(
      revision: revision,
      confirmed: true,
      resultRevision: resultRevision,
    ),
    'missing_fields': <String>[],
    'ambiguous_fields': <String>[],
    'result': {
      'status': 'recommendation',
      'revision': resultRevision,
      'normalized_input': _itemJson(),
      'recommendation': {
        'discount_percent': 30,
        'recommended_price': 10500,
        'timing': 'Mulai diskon hari ini',
        'expected_sell_through': '8 dari 10 pcs',
        'expected_revenue': 84000,
        'expected_loss_no_action': 50000,
        'confidence': 'Cukup yakin',
      },
      'explanation': 'Sisa dua hari dan stok sepuluh, diskon dibutuhkan.',
      'promo_copy': 'Roti tawar diskon 30% hari ini saja!',
      'preview': {
        'item_name': 'Roti Tawar',
        'shop_name': 'Toko Sari',
        'original_price': 15000,
        'deal_price': 10500,
        'discount_percent': 30,
        'days_remaining': 2,
        'stock': 10,
      },
    },
  });
}

ChatTurn noActionTurn({String sessionId = 'sesi-1'}) {
  return ChatTurn.fromJson({
    'session_id': sessionId,
    'action': 'EXPLAIN_RESULT',
    'assistant_message': 'Belum perlu diskon.',
    'state': _completeState(revision: 2, confirmed: true, resultRevision: 2),
    'missing_fields': <String>[],
    'ambiguous_fields': <String>[],
    'result': {
      'status': 'no_action',
      'revision': 2,
      'message': 'Barang ini kemungkinan terjual normal sebelum kadaluarsa.',
      'reassess_in_days': 5,
    },
  });
}

ChatTurn invalidInputTurn({String sessionId = 'sesi-1'}) {
  return ChatTurn.fromJson({
    'session_id': sessionId,
    'action': 'SAFE_FAILURE',
    'assistant_message': 'Harga modalmu perlu dicek.',
    'state': _completeState(revision: 2, confirmed: false, resultRevision: 2),
    'missing_fields': <String>[],
    'ambiguous_fields': <String>[],
    'result': {
      'status': 'invalid_input',
      'revision': 2,
      'message':
          'Harga modal (Rp15.000) sama atau lebih besar dari harga jual (Rp12.000).',
    },
  });
}

Map<String, dynamic> _itemJson() => {
      'item_name': 'Roti Tawar',
      'category': 'Bakery',
      'original_price': 15000,
      'cost': 10000,
      'stock': 10,
      'days_remaining': 2,
      'daily_sales': 5,
      'total_shelf_life': 4,
      'shop_name': 'Toko Sari',
    };

Map<String, dynamic> _completeState({
  required int revision,
  required bool confirmed,
  int? resultRevision,
}) =>
    {
      ..._itemJson(),
      'confirmed': confirmed,
      'revision': revision,
      'result_revision': resultRevision,
    };

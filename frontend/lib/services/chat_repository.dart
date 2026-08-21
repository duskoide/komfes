import '../models/chat.dart';
import '../models/recommendation.dart';
import 'api_client.dart';
import 'app_exception.dart';

/// Satu-satunya tempat bentuk kawat `POST /api/chat` diterjemahkan.
///
/// Kontraknya masih proposal (`docs/HargaTurun_Chat_API_Proposal.md`) dan
/// menunggu konfirmasi backend. Semua pemetaan sengaja dikurung di file ini
/// supaya perubahan kontrak hanya menyentuh satu file, bukan layar chat.
abstract class ChatRepository {
  /// [sessionId] null berarti mulai sesi baru; server mengembalikan id-nya.
  Future<ChatTurn> send({
    required ChatRequestAction action,
    String? sessionId,
    String? text,
    ItemInputDraft? patch,
  });
}

class HttpChatRepository implements ChatRepository {
  const HttpChatRepository(this._api);

  final ApiClient _api;

  @override
  Future<ChatTurn> send({
    required ChatRequestAction action,
    String? sessionId,
    String? text,
    ItemInputDraft? patch,
  }) async {
    final response = await _api.post('/api/chat', body: {
      'session_id': sessionId,
      'action': action.wireValue,
      'text': text,
      'patch': patch?.toStructuredJson(),
    });

    switch (response.statusCode) {
      case 200:
        if (response.data is! Map) {
          throw const RequestFailedException('Respons chat tidak valid.');
        }
        // SAFE_FAILURE juga datang sebagai 200: turn-nya tertangani dan state
        // vendor selamat, jadi tidak boleh diperlakukan sebagai error transport.
        return ChatTurn.fromJson(response.object);
      case 404:
        throw SessionExpiredException(response.message);
      case 422:
        throw InvalidInputException(response.message);
      case 502:
        throw ModelUnavailableException(response.message);
      default:
        throw RequestFailedException(response.message);
    }
  }
}

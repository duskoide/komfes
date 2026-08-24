import '../models/chat.dart';
import '../models/chat_attachment.dart';
import '../models/recommendation.dart';
import 'api_client.dart';
import 'app_exception.dart';

/// Satu-satunya tempat bentuk kawat chat diterjemahkan.
abstract class ChatRepository {
  Future<ChatTurn> send({
    required ChatRequestAction action,
    String? sessionId,
    String? text,
    ItemInputDraft? patch,
  });

  Future<ChatTurn> sendImage({
    required ChatAttachment attachment,
    String? sessionId,
    String? text,
    void Function(int sent, int total)? onProgress,
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
    return _parseResponse(response);
  }

  @override
  Future<ChatTurn> sendImage({
    required ChatAttachment attachment,
    String? sessionId,
    String? text,
    void Function(int sent, int total)? onProgress,
  }) async {
    final response = await _api.postMultipart(
      '/api/chat/image',
      fields: {
        'session_id': sessionId,
        'action': ChatRequestAction.message.wireValue,
        'text': text,
      },
      fileField: 'image',
      fileName: attachment.fileName,
      bytes: attachment.bytes,
      contentType: attachment.mimeType,
      onProgress: onProgress,
    );
    return _parseResponse(response);
  }

  ChatTurn _parseResponse(ApiResponse response) {
    switch (response.statusCode) {
      case 200:
        if (response.data is! Map) {
          throw const RequestFailedException('Respons chat tidak valid.');
        }
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

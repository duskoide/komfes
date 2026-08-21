import '../models/enums.dart';
import '../models/recommendation.dart';
import 'api_client.dart';
import 'app_exception.dart';

abstract class RecommendRepository {
  Future<RecommendResult> recommend(ItemInputDraft input);
}

class HttpRecommendRepository implements RecommendRepository {
  const HttpRecommendRepository(this._api);

  final ApiClient _api;

  @override
  Future<RecommendResult> recommend(ItemInputDraft input) async {
    final response = await _api.post('/api/recommend', body: input.toJson());
    if (response.data is! Map) {
      throw const RequestFailedException('Respons rekomendasi tidak valid.');
    }

    final result = RecommendResult.fromJson(response.object);
    switch (response.statusCode) {
      case 200:
        return result;
      case 422:
        // Kedua outcome ini adalah bagian dari state machine UI, bukan kegagalan
        // transport. Screen berikutnya dipilih dari status hasil.
        if (result.status == RecommendResultStatus.needsConfirmation ||
            result.status == RecommendResultStatus.invalidInput) {
          return result;
        }
        throw InvalidInputException(response.message);
      case 502:
        throw ModelUnavailableException(response.message);
      default:
        throw RequestFailedException(response.message);
    }
  }
}

/// Tetap tersedia untuk device-preview atau demo UI tanpa backend.
class SimulatedModelDownRepository implements RecommendRepository {
  @override
  Future<RecommendResult> recommend(ItemInputDraft input) async {
    await Future.delayed(const Duration(milliseconds: 1500));
    throw const ModelUnavailableException();
  }
}

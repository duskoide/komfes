import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/api_client.dart';
import '../services/auth_repository.dart';
import '../services/chat_repository.dart';
import '../services/connectivity_service.dart';
import '../services/deal_repository.dart';
import '../services/recommend_repository.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  final client = ApiClient();
  ref.onDispose(client.close);
  return client;
});

final recommendRepositoryProvider = Provider<RecommendRepository>((ref) {
  return HttpRecommendRepository(ref.watch(apiClientProvider));
});

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  return HttpChatRepository(ref.watch(apiClientProvider));
});

final dealRepositoryProvider = Provider<DealRepository>((ref) {
  return HttpDealRepository(ref.watch(apiClientProvider));
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return HttpAuthRepository(ref.watch(apiClientProvider));
});

final connectivityServiceProvider = Provider<ConnectivityService>((ref) {
  return MockConnectivityService();
});

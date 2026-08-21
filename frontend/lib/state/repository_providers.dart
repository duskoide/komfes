import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/auth_repository.dart';
import '../services/connectivity_service.dart';
import '../services/deal_repository.dart';
import '../services/recommend_repository.dart';

final recommendRepositoryProvider = Provider<RecommendRepository>((ref) {
  return MockRecommendRepository();
});

final dealRepositoryProvider = Provider<DealRepository>((ref) {
  return MockDealRepository();
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return MockAuthRepository();
});

final connectivityServiceProvider = Provider<ConnectivityService>((ref) {
  return MockConnectivityService();
});

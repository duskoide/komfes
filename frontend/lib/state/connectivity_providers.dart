import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'repository_providers.dart';

final isOnlineProvider = StreamProvider<bool>((ref) {
  return ref.watch(connectivityServiceProvider).onlineStatusStream;
});

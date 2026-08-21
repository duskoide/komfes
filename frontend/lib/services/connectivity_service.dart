import 'dart:async';

/// Abstraksi status koneksi.
abstract class ConnectivityService {
  Stream<bool> get onlineStatusStream;
  bool get isOnlineNow;
}

/// Mock: selalu online oleh default, dengan method `setOnline` untuk
/// disimulasikan lewat toggle debug (mis. di Profil) saat menguji Banner
/// Offline tanpa perlu mematikan Wi-Fi sungguhan.
class MockConnectivityService implements ConnectivityService {
  bool _online = true;
  final List<void Function(bool)> _listeners = [];

  @override
  bool get isOnlineNow => _online;

  @override
  Stream<bool> get onlineStatusStream {
    late final StreamController<bool> sc;
    sc = StreamController<bool>(onListen: () => sc.add(_online));
    _listeners.add((v) => sc.add(v));
    return sc.stream;
  }

  void setOnline(bool online) {
    _online = online;
    for (final l in _listeners) {
      l(online);
    }
  }
}

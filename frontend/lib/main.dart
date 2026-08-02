import 'package:device_preview/device_preview.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';

/// Frame HP simulasi hanya untuk preview di browser desktop saat development.
/// Di build release, dan saat jalan di perangkat Android sungguhan, ini mati.
const bool kUseDevicePreview = kDebugMode && kIsWeb;

void main() {
  runApp(
    DevicePreview(
      enabled: kUseDevicePreview,
      builder: (_) => const ProviderScope(child: HargaTurun()),
    ),
  );
}

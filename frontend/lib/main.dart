import 'package:device_preview/device_preview.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';

/// Frame HP simulasi untuk preview di browser desktop.
///
/// Debug web mengaktifkannya secara default. Build release dapat mengaktifkannya
/// dengan `--dart-define=DEVICE_PREVIEW=true`, sehingga demo tidak perlu memuat
/// ratusan modul debug sebelum frame pertama.
const bool kUseDevicePreview =
    kIsWeb &&
    (kDebugMode ||
        bool.fromEnvironment('DEVICE_PREVIEW', defaultValue: false));

void main() {
  runApp(
    DevicePreview(
      enabled: kUseDevicePreview,
      builder: (_) => const ProviderScope(child: HargaTurun()),
    ),
  );
}

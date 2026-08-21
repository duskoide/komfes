import 'package:flutter/widgets.dart';

/// Kelas perangkat
enum DeviceClass {
  phoneSmall, // 320-359 dp
  phone, // 360-429 dp - desain utama
  phoneLarge, // 430-599 dp
  tabletPortrait, // 600-904 dp
  tabletLandscape, // >= 905 dp
}

class Breakpoints {
  Breakpoints._();

  static DeviceClass classify(double width) {
    if (width >= 905) return DeviceClass.tabletLandscape;
    if (width >= 600) return DeviceClass.tabletPortrait;
    if (width >= 430) return DeviceClass.phoneLarge;
    if (width >= 360) return DeviceClass.phone;
    return DeviceClass.phoneSmall;
  }

  static bool isTablet(double width) => width >= 600;

  static bool isTabletLandscape(double width) => width >= 905;

  static DeviceClass of(BuildContext context) =>
      classify(MediaQuery.sizeOf(context).width);

  static bool isTabletOf(BuildContext context) =>
      isTablet(MediaQuery.sizeOf(context).width);

  static bool isTabletLandscapeOf(BuildContext context) =>
      isTabletLandscape(MediaQuery.sizeOf(context).width);
}

class ResponsiveLayout extends StatelessWidget {
  const ResponsiveLayout({
    super.key,
    required this.phone,
    this.tabletPortrait,
    this.tabletLandscape,
  });

  final WidgetBuilder phone;
  final WidgetBuilder? tabletPortrait;
  final WidgetBuilder? tabletLandscape;

  @override
  Widget build(BuildContext context) {
    final cls = Breakpoints.of(context);
    switch (cls) {
      case DeviceClass.tabletLandscape:
        return (tabletLandscape ?? tabletPortrait ?? phone)(context);
      case DeviceClass.tabletPortrait:
        return (tabletPortrait ?? phone)(context);
      case DeviceClass.phoneSmall:
      case DeviceClass.phone:
      case DeviceClass.phoneLarge:
        return phone(context);
    }
  }
}

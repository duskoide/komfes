import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hargaturun/app.dart';

void main() {
  testWidgets('HargaTurun starts on the splash screen', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: HargaTurun()));
    await tester.pump();

    expect(find.text('HargaTurun'), findsOneWidget);
    expect(find.text('Jangan buang, turunkan harganya.'), findsOneWidget);

    await tester.pump(const Duration(seconds: 2));
    await tester.pump();
  });
}

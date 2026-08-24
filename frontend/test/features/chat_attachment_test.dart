import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hargaturun/core/theme/app_theme.dart';
import 'package:hargaturun/features/vendor/chat_screen.dart';
import 'package:hargaturun/models/chat.dart';
import 'package:hargaturun/models/chat_attachment.dart';
import 'package:hargaturun/services/app_exception.dart';
import 'package:hargaturun/state/chat_providers.dart';
import 'package:hargaturun/state/repository_providers.dart';

import '../support/chat_fixtures.dart';

void main() {
  late FakeChatRepository repository;

  final attachment = ChatAttachment(
    fileName: 'stok.png',
    bytes: Uint8List.fromList(List<int>.filled(12, 1)),
    mimeType: 'image/png',
  );

  Future<void> pumpChat(WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      ProviderScope(
        overrides: [chatRepositoryProvider.overrideWithValue(repository)],
        child: MaterialApp(theme: AppTheme.light, home: const ChatScreen()),
      ),
    );
    await tester.pump();
  }

  setUp(() => repository = FakeChatRepository());

  test('rejects an attachment over the backend byte limit before upload', () {
    final tooLarge = ChatAttachment(
      fileName: 'stok.png',
      bytes: Uint8List(ChatAttachmentValidator.maxBytes + 1),
      mimeType: 'image/png',
    );
    expect(ChatAttachmentValidator.errorFor(tooLarge), isNotNull);
    expect(ChatAttachmentValidator.errorFor(attachment), isNull);
  });

  testWidgets('preview renders thumbnail and meaningful semantic label',
      (tester) async {
    final semantics = tester.ensureSemantics();
    await pumpChat(tester);
    final container = ProviderScope.containerOf(
      tester.element(find.byType(ChatScreen)),
    );

    await container
        .read(chatFlowProvider.notifier)
        .selectAttachment(attachment);
    await tester.pump();

    expect(find.byType(Image), findsOneWidget);
    expect(
      find.byWidgetPredicate(
        (widget) =>
            widget is Semantics &&
            widget.properties.label == 'Lampiran gambar stok.png',
      ),
      findsOneWidget,
    );
    expect(find.byTooltip('Hapus lampiran'), findsOneWidget);
    semantics.dispose();
  });

  testWidgets('oversized selection is rejected through UI state before upload',
      (tester) async {
    await pumpChat(tester);
    final container = ProviderScope.containerOf(
      tester.element(find.byType(ChatScreen)),
    );
    final tooLarge = ChatAttachment(
      fileName: 'stok.png',
      bytes: Uint8List(ChatAttachmentValidator.maxBytes + 1),
      mimeType: 'image/png',
    );

    await container.read(chatFlowProvider.notifier).selectAttachment(tooLarge);
    await tester.pump();

    expect(find.text(ChatAttachmentValidator.invalidMessage), findsOneWidget);
    expect(container.read(chatFlowProvider).attachment, isNull);
    expect(repository.calls, isEmpty);
  });

  testWidgets('failed upload resets progress and retry sends exactly twice',
      (tester) async {
    repository.pending = Completer<ChatTurn>();
    await pumpChat(tester);
    final container = ProviderScope.containerOf(
      tester.element(find.byType(ChatScreen)),
    );
    final notifier = container.read(chatFlowProvider.notifier);
    await notifier.selectAttachment(attachment);
    await tester.pump();
    final gate = repository.pending!;

    unawaited(notifier.sendAttachment());
    expect(repository.calls.length, 1);
    gate.completeError(const RequestFailedException('Gagal mengunggah.'));
    await tester.pump();
    await tester.pump();

    expect(container.read(chatFlowProvider).uploadProgress, 0);
    expect(find.text('Gagal mengunggah.'), findsOneWidget);
    expect(find.text('Coba Lagi'), findsOneWidget);

    repository.nextTurn = askForMissingTurn();
    await tester.tap(find.text('Coba Lagi'));
    await tester.pump();
    await tester.pump();

    expect(repository.calls.length, 2);
    expect(repository.lastAttachment, same(attachment));
    expect(find.text('Gagal mengunggah.'), findsNothing);
  });

  testWidgets('removing after failure prevents retry and detaches attachment',
      (tester) async {
    repository.pending = Completer<ChatTurn>();
    await pumpChat(tester);
    final container = ProviderScope.containerOf(
      tester.element(find.byType(ChatScreen)),
    );
    final notifier = container.read(chatFlowProvider.notifier);
    await notifier.selectAttachment(attachment);
    await tester.pump();
    final gate = repository.pending!;

    unawaited(notifier.sendAttachment());
    gate.completeError(const RequestFailedException('Gagal mengunggah.'));
    await tester.pump();
    await tester.pump();
    expect(repository.calls.length, 1);

    notifier.removeAttachment();
    await tester.pump();
    expect(container.read(chatFlowProvider).attachment, isNull);
    expect(find.text('Gagal mengunggah.'), findsOneWidget);

    await tester.tap(find.text('Coba Lagi'));
    await tester.pump();
    expect(repository.calls.length, 1);
  });

  testWidgets('attachment reaches confirmation and calculate actions',
      (tester) async {
    repository.nextTurn = showConfirmationTurn();
    await pumpChat(tester);
    final container = ProviderScope.containerOf(
      tester.element(find.byType(ChatScreen)),
    );
    final notifier = container.read(chatFlowProvider.notifier);
    await notifier.selectAttachment(attachment);
    await tester.pump();
    unawaited(notifier.sendAttachment());
    await tester.pump();
    await tester.pump();
    expect(find.text('Cek dulu sebelum dihitung'), findsOneWidget);

    await notifier.confirm();
    await tester.pump();
    await tester.pump();
    await notifier.calculate();
    await tester.pump();
    await tester.pump();

    expect(
      repository.calls.map((call) => call.action),
      containsAllInOrder([
        ChatRequestAction.message,
        ChatRequestAction.confirm,
        ChatRequestAction.calculate,
      ]),
    );
  });
}

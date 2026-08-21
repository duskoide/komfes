import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hargaturun/core/theme/app_theme.dart';
import 'package:hargaturun/features/vendor/chat_screen.dart';
import 'package:hargaturun/models/chat.dart';
import 'package:hargaturun/services/app_exception.dart';
import 'package:hargaturun/state/repository_providers.dart';

import '../support/chat_fixtures.dart';

void main() {
  late FakeChatRepository repo;

  setUp(() => repo = FakeChatRepository());

  Future<void> pumpChat(WidgetTester tester) async {
    // Permukaan dibuat tinggi supaya seluruh transkrip plus kartu konfirmasi
    // ikut terbangun. ListView tidak membangun anak di luar layar, jadi
    // finder tidak akan menemukannya pada viewport test bawaan.
    await tester.binding.setSurfaceSize(const Size(500, 2200));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [chatRepositoryProvider.overrideWithValue(repo)],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const ChatScreen(),
        ),
      ),
    );
    await tester.pump();
  }

  Future<void> sendText(WidgetTester tester, String text) async {
    await tester.enterText(find.byType(TextField).first, text);
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
  }

  group('pengiriman pesan', () {
    testWidgets('menampilkan pesan vendor lalu balasan asisten', (tester) async {
      repo.nextTurn = askForMissingTurn();
      await pumpChat(tester);

      await sendText(tester, 'roti tawar 10 biji exp 2 hari');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('roti tawar 10 biji exp 2 hari'), findsOneWidget);
      expect(
        find.text('Sudah kucatat rotinya. Rata-rata terjual berapa per hari?'),
        findsOneWidget,
      );
      expect(repo.calls.single.action, ChatRequestAction.message);
    });

    testWidgets('mengabaikan pesan kosong tanpa memanggil server',
        (tester) async {
      await pumpChat(tester);

      await sendText(tester, '   ');
      await tester.pump();

      expect(repo.calls, isEmpty);
    });

    testWidgets('mengirim session_id yang diterima pada turn berikutnya',
        (tester) async {
      repo.nextTurn = askForMissingTurn(sessionId: 'sesi-abc');
      await pumpChat(tester);

      await sendText(tester, 'pesan pertama');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      repo.nextTurn = askForMissingTurn(sessionId: 'sesi-abc');
      await sendText(tester, 'pesan kedua');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(repo.calls.first.sessionId, isNull);
      expect(repo.calls.last.sessionId, 'sesi-abc');
    });
  });

  group('state loading', () {
    testWidgets('tombol kirim jadi indikator selama menunggu balasan',
        (tester) async {
      final gate = Completer<ChatTurn>();
      repo.pending = gate;
      await pumpChat(tester);

      await sendText(tester, 'roti tawar');
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsWidgets);
      expect(find.byIcon(Icons.arrow_upward_rounded), findsNothing);

      gate.complete(askForMissingTurn());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.byIcon(Icons.arrow_upward_rounded), findsOneWidget);
    });
  });

  group('kegagalan dan coba lagi', () {
    testWidgets('menampilkan pesan error dan mengulang tanpa mengetik ulang',
        (tester) async {
      repo.error = const ModelUnavailableException('Sistem AI sedang sibuk.');
      await pumpChat(tester);

      await sendText(tester, 'roti tawar 10 biji');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Sistem AI sedang sibuk.'), findsOneWidget);
      expect(find.text('Coba Lagi'), findsOneWidget);

      repo.nextTurn = askForMissingTurn();
      await tester.tap(find.text('Coba Lagi'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Percobaan kedua harus membawa teks yang sama, bukan kosong.
      expect(repo.calls.length, 2);
      expect(repo.calls.last.text, 'roti tawar 10 biji');
      expect(find.text('Sistem AI sedang sibuk.'), findsNothing);
    });

    testWidgets('sesi kedaluwarsa membersihkan percakapan dan memberi tahu',
        (tester) async {
      repo.nextTurn = askForMissingTurn();
      await pumpChat(tester);
      await sendText(tester, 'roti tawar');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      repo.error = const SessionExpiredException();
      await sendText(tester, 'lanjut');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('roti tawar'), findsNothing);
      expect(
        find.textContaining('Sesi konsultasi sudah berakhir'),
        findsOneWidget,
      );
    });
  });

  group('data tercatat', () {
    testWidgets('menampilkan yang sudah terbaca dan yang masih ditunggu',
        (tester) async {
      repo.nextTurn = askForMissingTurn();
      await pumpChat(tester);

      await sendText(tester, 'roti tawar 10 biji harga 15rb modal 10rb');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Data yang sudah dicatat'), findsOneWidget);
      expect(find.text('Roti Tawar'), findsOneWidget);
      expect(find.text('Rp15.000'), findsOneWidget);
      // Field yang belum ada disebut sebagai satu baris gabungan, bukan
      // baris kosong per field.
      expect(
        find.text('Masih ditunggu: Rata-rata terjual per hari'),
        findsOneWidget,
      );
    });
  });

  group('alur konfirmasi', () {
    testWidgets('kartu konfirmasi muncul hanya saat aksinya SHOW_CONFIRMATION',
        (tester) async {
      repo.nextTurn = askForMissingTurn();
      await pumpChat(tester);
      await sendText(tester, 'roti tawar');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Cek dulu sebelum dihitung'), findsNothing);

      repo.nextTurn = showConfirmationTurn();
      await sendText(tester, 'sehari 5');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Cek dulu sebelum dihitung'), findsOneWidget);
    });

    testWidgets('konfirmasi memanggil confirm lalu calculate, dua aksi terpisah',
        (tester) async {
      repo.nextTurn = showConfirmationTurn();
      await pumpChat(tester);
      await sendText(tester, 'roti tawar lengkap');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      repo.nextTurn = confirmedTurn();
      await tester.tap(find.text('Hitung Sekarang'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      repo.nextTurn = recommendationTurn();
      await tester.pump(const Duration(milliseconds: 300));

      final actions = repo.calls.map((c) => c.action).toList();
      expect(actions, contains(ChatRequestAction.confirm));
      expect(actions.indexOf(ChatRequestAction.confirm),
          lessThan(actions.indexOf(ChatRequestAction.calculate)));
    });

    testWidgets('tanpa konfirmasi server, calculate tidak pernah dipanggil',
        (tester) async {
      repo.nextTurn = showConfirmationTurn();
      await pumpChat(tester);
      await sendText(tester, 'roti tawar lengkap');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Server menolak konfirmasi: state tetap confirmed=false.
      repo.nextTurn = showConfirmationTurn();
      await tester.tap(find.text('Hitung Sekarang'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(
        repo.calls.map((c) => c.action),
        isNot(contains(ChatRequestAction.calculate)),
      );
    });

    testWidgets('suntingan dikirim sebagai patch berisi field yang diubah saja',
        (tester) async {
      repo.nextTurn = showConfirmationTurn();
      await pumpChat(tester);
      await sendText(tester, 'roti tawar lengkap');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      await tester.tap(find.text('Ubah Data'));
      await tester.pump();

      final stockField = find.widgetWithText(TextField, 'Jumlah stok');
      await tester.enterText(stockField, '24');
      await tester.pump();

      repo.nextTurn = confirmedTurn();
      await tester.tap(find.text('Hitung Sekarang'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      final patch = repo.calls
          .firstWhere((c) => c.action == ChatRequestAction.confirm)
          .patch;
      expect(patch, isNotNull);
      expect(patch!.stock, 24);
      // Nilai yang tidak disentuh tidak dikirim ulang.
      expect(patch.cost, isNull);
      expect(patch.originalPrice, isNull);
    });
  });
}

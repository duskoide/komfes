import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'app_exception.dart';

class ApiClient {
  ApiClient({
    http.Client? client,
    String baseUrl = const String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://127.0.0.1:8000',
    ),
  })  : _client = client ?? http.Client(),
        baseUrl = baseUrl.replaceFirst(RegExp(r'/$'), '');

  final http.Client _client;
  final String baseUrl;
  String? bearerToken;

  Future<ApiResponse> get(String path,
      {Map<String, String?> query = const {}}) {
    return _send('GET', path, query: query);
  }

  Future<ApiResponse> post(String path, {Map<String, dynamic>? body}) {
    return _send('POST', path, body: body);
  }

  Future<ApiResponse> postMultipart(
    String path, {
    required Map<String, String?> fields,
    required String fileField,
    required String fileName,
    required Uint8List bytes,
    required String contentType,
    void Function(int sent, int total)? onProgress,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl$path'))
      ..headers.addAll({
        'Accept': 'application/json',
        if (bearerToken != null) 'Authorization': 'Bearer $bearerToken',
      })
      ..fields.addAll({
        for (final entry in fields.entries)
          if (entry.value != null) entry.key: entry.value!,
      })
      ..files.add(http.MultipartFile(
        fileField,
        _progressStream(bytes, onProgress),
        bytes.length,
        filename: fileName,
        contentType: _mediaType(contentType),
      ));

    try {
      final streamed = await _client.send(request);
      final chunks = <int>[];
      await for (final chunk in streamed.stream) {
        chunks.addAll(chunk);
      }
      final response = http.Response.bytes(
        Uint8List.fromList(chunks),
        streamed.statusCode,
        headers: streamed.headers,
        request: request,
      );
      final decoded = response.body.isEmpty ? null : jsonDecode(response.body);
      return ApiResponse(response.statusCode, decoded);
    } on SocketException {
      throw const NetworkOfflineException();
    } on HttpException {
      throw const RequestFailedException();
    } on FormatException {
      throw const RequestFailedException('Respons server tidak valid.');
    } on http.ClientException {
      throw const RequestFailedException('Tidak dapat terhubung ke server.');
    }
  }

  Future<ApiResponse> delete(String path) => _send('DELETE', path);

  Future<ApiResponse> _send(
    String method,
    String path, {
    Map<String, String?> query = const {},
    Map<String, dynamic>? body,
  }) async {
    final filteredQuery = <String, String>{
      for (final entry in query.entries)
        if (entry.value != null) entry.key: entry.value!,
    };
    final uri = Uri.parse('$baseUrl$path').replace(
      queryParameters: filteredQuery.isEmpty ? null : filteredQuery,
    );
    final headers = <String, String>{
      'Accept': 'application/json',
      if (body != null) 'Content-Type': 'application/json',
      if (bearerToken != null) 'Authorization': 'Bearer $bearerToken',
    };

    try {
      late http.Response response;
      switch (method) {
        case 'GET':
          response = await _client.get(uri, headers: headers);
          break;
        case 'POST':
          response = await _client.post(
            uri,
            headers: headers,
            body: body == null ? null : jsonEncode(body),
          );
          break;
        case 'DELETE':
          response = await _client.delete(uri, headers: headers);
          break;
        default:
          throw ArgumentError.value(method, 'method');
      }
      final decoded = response.body.isEmpty ? null : jsonDecode(response.body);
      return ApiResponse(response.statusCode, decoded);
    } on SocketException {
      throw const NetworkOfflineException();
    } on HttpException {
      throw const RequestFailedException();
    } on FormatException {
      throw const RequestFailedException('Respons server tidak valid.');
    } on http.ClientException {
      throw const RequestFailedException('Tidak dapat terhubung ke server.');
    }
  }

  void close() => _client.close();

  Stream<List<int>> _progressStream(
    Uint8List bytes,
    void Function(int sent, int total)? onProgress,
  ) async* {
    const chunkSize = 16 * 1024;
    var sent = 0;
    for (var offset = 0; offset < bytes.length; offset += chunkSize) {
      final end = (offset + chunkSize).clamp(0, bytes.length);
      final chunk = bytes.sublist(offset, end);
      sent += chunk.length;
      onProgress?.call(sent, bytes.length);
      yield chunk;
    }
  }

  http.MediaType _mediaType(String value) {
    final parts = value.split('/');
    return parts.length == 2
        ? http.MediaType(parts[0], parts[1])
        : http.MediaType('application', 'octet-stream');
  }
}

class ApiResponse {
  const ApiResponse(this.statusCode, this.data);

  final int statusCode;
  final dynamic data;

  bool get isSuccess => statusCode >= 200 && statusCode < 300;

  Map<String, dynamic> get object => (data as Map).cast<String, dynamic>();
  List<dynamic> get list => data as List<dynamic>;

  String get message {
    if (data is Map) {
      final map = data as Map;
      final detail = map['detail'];
      if (detail is String) return detail;
      final message = map['message'];
      if (message is String) return message;
    }
    return 'Terjadi kesalahan. Coba lagi.';
  }
}

import 'dart:convert';
import 'dart:io';

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

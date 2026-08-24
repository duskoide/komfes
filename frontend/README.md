# hargaturun

## Chat image attachments

The chat composer accepts camera, gallery, and file attachments through the
`image_picker` and `file_picker` Flutter plugins. The client validates JPEG,
PNG, and WebP extensions/MIME hints and a 5 MiB byte limit before upload, but
the backend remains the authoritative validation gate.

The current checked-in frontend scope is the shared Dart/web-compatible UI and
widget-test coverage. Native platform directories are not currently checked
into this worktree. When Android/iOS scaffolding is added or enabled:

- iOS must provide `NSCameraUsageDescription` and
  `NSPhotoLibraryUsageDescription` in the app's `Info.plist` for camera and
  photo-library access.
- Android should use the permission and scoped-storage configuration required
  by the selected `image_picker`/`file_picker` plugin versions. Camera access
  and file/photo access may require runtime permissions depending on the
  Android API level and plugin implementation; verify the generated manifest
  and request flow on target devices.
- Web uses browser file/camera picker capabilities and browser permission
  prompts; native `Info.plist` and Android manifest entries do not apply.

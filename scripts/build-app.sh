#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
app="Air Painter.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources" .cache/clang
cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>AirPainter</string>
<key>CFBundleIdentifier</key><string>local.codex.air-painter</string>
<key>CFBundleName</key><string>Air Painter</string>
<key>CFBundleDisplayName</key><string>AI 隔空绘画</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSMinimumSystemVersion</key><string>13.0</string>
<key>NSCameraUsageDescription</key><string>使用摄像头在本机识别手指动作，帮助你隔空绘画。画面不会上传。</string>
<key>NSDocumentsFolderUsageDescription</key><string>读取文稿文件夹中的本地绘画程序、模型和依赖，并将画作保存在本地项目中。</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
xcrun clang -fobjc-arc -fmodules -fmodules-cache-path="$PWD/.cache/clang" -framework Cocoa -framework AVFoundation scripts/Launcher.m -o "$app/Contents/MacOS/AirPainter"
# Preserve the local app identity across rebuilds instead of binding it to a
# changing binary hash. macOS still requires the user's initial permission.
codesign --force --sign - --requirements '=designated => identifier "local.codex.air-painter"' "$app"
echo "已构建 $app"

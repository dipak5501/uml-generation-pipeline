#!/usr/bin/env bash
# Install a portable Temurin JRE into tools/jdk for local PlantUML rendering (macOS Apple Silicon).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/tools"
mkdir -p "$TOOLS"

if command -v java >/dev/null 2>&1; then
  if java -version 2>&1 | grep -qv "Unable to locate a Java Runtime"; then
    echo "System Java already works:"
    java -version
    exit 0
  fi
fi

ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  PLATFORM="mac/aarch64"
elif [[ "$ARCH" == "x86_64" ]]; then
  PLATFORM="mac/x64"
else
  echo "Unsupported architecture: $ARCH"
  exit 1
fi

URL="https://api.adoptium.net/v3/binary/latest/17/ga/${PLATFORM}/jre/hotspot/normal/eclipse?project=jdk"
TMP="$TOOLS/jdk-download.tar.gz"
echo "Downloading Temurin 17 JRE for $PLATFORM ..."
curl -fsSL "$URL" -o "$TMP"
rm -rf "$TOOLS/jdk-17" "$TOOLS/jdk-17.jdk" "$TOOLS/jdk-17.jre"
tar -xzf "$TMP" -C "$TOOLS"
rm -f "$TMP"

# Normalize extracted folder name
if [[ -d "$TOOLS/jdk-17.jre/Contents/Home" ]]; then
  JAVA_HOME="$TOOLS/jdk-17.jre/Contents/Home"
elif [[ -d "$TOOLS/jdk-17.jdk/Contents/Home" ]]; then
  JAVA_HOME="$TOOLS/jdk-17.jdk/Contents/Home"
else
  JAVA_BIN="$(find "$TOOLS" -maxdepth 5 -type f -path '*/bin/java' 2>/dev/null | head -1 || true)"
  if [[ -n "$JAVA_BIN" ]]; then
    JAVA_HOME="$(dirname "$(dirname "$JAVA_BIN")")"
  fi
fi

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "Failed to locate java after extract"
  exit 1
fi

echo "Installed portable Java at: $JAVA_HOME"
"$JAVA_HOME/bin/java" -version
echo ""
echo "Add to .env (optional):"
echo "JAVA_HOME=$JAVA_HOME"

#!/usr/bin/env bash
set -e

zip_file="ytptube-extension.zip"
extension_dir="./src"
if [ -f "$zip_file" ]; then
    echo "Removing existing zip file: $zip_file"
    rm "$zip_file"
fi

INCLUDE_FILES=(
    "*.html"
    "*.js"
    "manifest.json"
    "_locales/*/messages.json"
    "css/*.css"
    "icons/*.png"
)

echo "Creating zip file: $zip_file"

(
    cd "$extension_dir" || exit 1
    zip -r "../$zip_file" . -i "${INCLUDE_FILES[@]}"
)

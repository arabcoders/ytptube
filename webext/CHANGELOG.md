# CHANGELOG

## 1.5.2 - 2026-09-13

- **Added**: Support for Firefox on Android 142 and newer.
- **Changed**: Firefox desktop now requires version 140 or newer.

## 1.5.1 - 2026-08-23

- **Fixed**: Saving options in Firefox no longer closes the browser window.

## 1.5.0 - 2026-08-21

- **Added**: Live YTPTube background preview in Options, including real-time background visibility control.
- **Changed**: Popup and Options now share the same resized background renderer and YTPTube shell layering.
- **Fixed**: Popup and Options shell spacing now fills the page cleanly without body or viewport padding issues.

## 1.4.0 - 2026-08-21

- **Added**: Internationalization for supported languages.

## 1.3.1 - 2026-08-21

- **Fixed**: Firefox no longer rejects duplicate host-permission prompts during option saves.

## 1.3.0 - 2026-08-20

- **Added**: Popup preset management with custom-preset filtering, refresh, metadata caching, stale-cache fallback, and selection persistence for context-menu quick adds.
- **Added**: Optional YTPTube backgrounds with configurable visibility, responsive shell rendering, and System, Light, or Dark themes.
- **Changed**: Popup and Options now use a YTPTube-inspired indigo, amber, stone, and dark-shell design instead of Bulma.
- **Changed**: Preset configuration is managed from the popup, while the documented paginated API and `default` fallback are supported.
- **Changed**: Options now use API-key or legacy Basic authentication consistently, with authenticated connection testing and safer credential migration.
- **Changed**: Options display the extension icon, use larger readable controls, and save settings before testing the connection.
- **Fixed**: Options loading no longer overwrites fields while they are being edited.

## 1.2.1 - 2026-08-18

- **Fixed**: Connection testing now supports YTPTube versions released before the full authentication API.

## 1.2.0 - 2026-08-17

- **Added**: API key authentication with legacy username/password migration and authenticated connection testing.

## 1.1.0 - 2026-01-25

- **Added**: Support for YTPTube API changes where presets are returned in an "items" array.
- **Removed**: Output template and folder setting. You can set them via preset server-side.

## 1.0.4 - 2025-11-01

- **Fixed**: Issue with saving options for firefox.

## 1.0.3 - 2025-11-01

- **Added**: Runtime optional host permission flow so users can authorize their own YTPTube servers without manual manifest edits.
- **Improved**: Options page now normalizes instance URLs, records granted origins, and cleans up old host permissions when the server changes.
- **Fixed**: Background requests to user-managed servers no longer hit CORS/address-space blocks after permissions are granted.

## 1.0.2 - 2025-08-12

- **Fixed**: Selected preset was not being sent to YTPTube API - now properly includes preset in requests
- **Fixed**: Output template and download folder were not being sent - now automatically includes configured template and folder options
- **Added**: Loading indicator with Bulma's built-in spinner for better user feedback during requests
- **Added**: Status messages in popup showing success/error feedback after sending URLs
- **Added**: Button disabling during request processing to prevent multiple submissions
- **Improved**: Enhanced error handling and user feedback throughout the extension


## 1.0.1 - 2025-05-28

- Fix issue prevent adding urls via Chromium browsers.

## 1.0.0 - 2025-05-23

- Switch to bulma and remove pure css. 
- Improve the messaging to users.

## 0.0.3 - 2025-03-10

- Automatically load presets from the YTPTube instance.
- Once the preset is selected, update the default preset in the extension options.

## 0.0.1 - 2025-03-08

- Initial release version

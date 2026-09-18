# App icons

Tauri needs bundle icons before `npm run tauri build` will succeed. Generate them
from a single square PNG with:

    npm run tauri icon path/to/icon.png

That writes 32x32.png, 128x128.png, 128x128@2x.png, icon.icns, and icon.ico here.

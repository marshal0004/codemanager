const fs = require("fs");
const path = require("path");

class ExtensionWatcher {
  constructor(extensionPath) {
    this.extensionPath = extensionPath;
    this.watchers = new Map();
    this.debounceTimer = null;
    this.lastReloadTime = 0;
    this.signalFile = path.join(this.extensionPath, ".reload-signal");

    // Create initial signal file
    this.createInitialSignal();
  }

  createInitialSignal() {
    try {
      // Create initial signal with current timestamp
      fs.writeFileSync(this.signalFile, Date.now().toString());
      console.log("📝 Initial reload signal created");
    } catch (error) {
      console.error("❌ Failed to create signal file:", error);
    }
  }

  watchFile(filePath) {
    if (this.watchers.has(filePath)) return;

    try {
      const watcher = fs.watch(filePath, (eventType, filename) => {
        if (eventType === "change") {
          this.handleFileChange(filePath);
        }
      });

      watcher.on("error", (error) => {
        console.error(`❌ Error watching ${filePath}:`, error);
      });

      this.watchers.set(filePath, watcher);
      console.log(
        `👀 Watching: ${path.relative(this.extensionPath, filePath)}`
      );
    } catch (error) {
      console.error(`❌ Failed to watch ${filePath}:`, error);
    }
  }

  handleFileChange(filePath) {
    const now = Date.now();

    // Debounce rapid changes
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      // Only reload if it's been at least 2 seconds since last reload
      if (now - this.lastReloadTime > 2000) {
        console.log(
          `\n🔄 File changed: ${path.relative(this.extensionPath, filePath)}`
        );
        console.log(`⏰ Time: ${new Date().toLocaleTimeString()}`);
        this.reloadExtension();
        this.lastReloadTime = now;
      } else {
        console.log(`⏭️  Skipping reload (too soon after last change)`);
      }
    }, 500); // 500ms debounce
  }

  reloadExtension() {
    try {
      // Write new timestamp to signal file
      const timestamp = Date.now();
      fs.writeFileSync(this.signalFile, timestamp.toString());
      console.log("✅ Extension reload signal sent");
      console.log(
        "📡 Signal timestamp:",
        new Date(timestamp).toLocaleTimeString()
      );
      console.log("---");
    } catch (error) {
      console.error("❌ Failed to write reload signal:", error);
    }
  }

  startWatching() {
    const filesToWatch = [
      "background.js",
      "popup.html",
      "popup.js",
      "content-script.js",
      "manifest.json",
      "styles.css", // Add any CSS files
      // Add other files you want to watch
    ];

    console.log("🚀 Starting Extension File Watcher");
    console.log("📁 Extension path:", this.extensionPath);
    console.log("");

    let watchedCount = 0;
    filesToWatch.forEach((file) => {
      const fullPath = path.join(this.extensionPath, file);
      if (fs.existsSync(fullPath)) {
        this.watchFile(fullPath);
        watchedCount++;
      } else {
        console.log(`⚠️  File not found (skipping): ${file}`);
      }
    });

    console.log("");
    console.log(`✅ Watching ${watchedCount} files for changes`);
    console.log("📝 Make changes to your files to trigger auto-reload");
    console.log("🛑 Press Ctrl+C to stop watching");
    console.log("---");
  }

  stop() {
    // Clear debounce timer
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    // Close all watchers
    this.watchers.forEach((watcher, filePath) => {
      try {
        watcher.close();
      } catch (error) {
        console.error(`Error closing watcher for ${filePath}:`, error);
      }
    });
    this.watchers.clear();

    // Clean up signal file
    try {
      if (fs.existsSync(this.signalFile)) {
        fs.unlinkSync(this.signalFile);
      }
    } catch (error) {
      console.error("Error cleaning up signal file:", error);
    }

    console.log("🛑 File watcher stopped and cleaned up");
  }
}

// Usage
const watcher = new ExtensionWatcher(__dirname);
watcher.startWatching();

// Graceful shutdown
process.on("SIGINT", () => {
  console.log("\n🛑 Shutting down file watcher...");
  watcher.stop();
  process.exit(0);
});

process.on("SIGTERM", () => {
  watcher.stop();
  process.exit(0);
});

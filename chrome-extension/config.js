// Chrome Extension Configuration
// Global configuration for the Code Snippet Manager extension

const CONFIG = {
  // API Configuration
  API: {
    SERVER: {
      BASE_URL: "http://localhost:5000",
      API_BASE: "http://localhost:5000/api",
      WEBSOCKET_URL: "ws://localhost:5000/socket.io/",

      // Production URLs (uncomment for production)
      // BASE_URL: 'https://your-domain.com',
      // API_BASE: 'https://your-domain.com/api',
      // WEBSOCKET_URL: 'wss://your-domain.com/ws',
    },
    // Development endpoints
    DEV: {
      BASE_URL: "http://localhost:5000",
      WS_URL: "ws://localhost:5000",
      API_VERSION: "v1",
    },
    // WebSocket Configuration
    WEBSOCKET: {
      RECONNECT_INTERVAL: 3000, // 3 seconds
      MAX_RECONNECT_ATTEMPTS: 5,
      HEARTBEAT_INTERVAL: 30000, // 30 seconds
      CONNECTION_TIMEOUT: 10000, // 10 seconds
    },

    // Production endpoints (update when deployed)
    PROD: {
      BASE_URL: "https://your-domain.com",
      WS_URL: "wss://your-domain.com",
      API_VERSION: "v1",
    },

    // Current environment (will be set based on build)
    get CURRENT() {
      return this.isDevelopment() ? this.DEV : this.PROD;
    },

    // Environment detection
    isDevelopment() {
      return (
        chrome.runtime.getManifest().version.includes("dev") ||
        !("update_url" in chrome.runtime.getManifest())
      );
    },
  },

  // Extension Settings
  EXTENSION: {
    POPUP_WIDTH: 400,
    POPUP_HEIGHT: 600,
    MAX_SNIPPET_PREVIEW: 200, // characters
    AUTO_SAVE_DELAY: 2000, // 2 seconds
    OFFLINE_QUEUE_LIMIT: 50, // max offline snippets
    NAME: "Code Snippet Manager",
    SHORT_NAME: "SnipManager",
    VERSION: chrome.runtime.getManifest().version,

    // Storage keys
    STORAGE_KEYS: {
      USER_TOKEN: "user_token",
      USER_DATA: "user_data",
      SETTINGS: "extension_settings",
      CACHED_SNIPPETS: "cached_snippets",
      SYNC_QUEUE: "sync_queue",
      LAST_SYNC: "last_sync_timestamp",
    },

    // Default settings
    DEFAULT_SETTINGS: {
      autoSave: true,
      showNotifications: true,
      keyboardShortcuts: true,
      syncOnStartup: true,
      maxCachedSnippets: 100,
      theme: "auto", // 'light', 'dark', 'auto'
      language: "en",
      defaultCollection: "unsorted",
    },
  },

  // Code Detection Configuration
  CODE_DETECTION: {
    MIN_CODE_LENGTH: 10, // minimum characters to detect as code
    // Selectors for code blocks on different websites
    SITE_SPECIFIC: {
      "github.com": [".blob-code", ".highlight", ".js-file-line"],
      "stackoverflow.com": ["pre", "code", ".s-code-block"],
      "codepen.io": [".CodeMirror-line", "pre"],
      "jsfiddle.net": [".CodeMirror-line", "pre"],
      "medium.com": ["pre", ".graf--code"],
      "dev.to": ["pre", "code", ".highlight"],
    },
    SELECTORS: {
      // Generic code selectors
      GENERIC: [
        "pre code",
        "pre",
        'code[class*="language-"]',
        ".highlight pre",
        ".sourceCode",
        ".language-*",
        '[class*="lang-"]',
        ".highlight",
        ".code-block",
        ".codehilite pre",
        ".snippet",
      ],

      // GitHub specific
      GITHUB: [
        ".blob-code-inner",
        ".highlight pre",
        "pre[lang]",
        ".js-file-line-container",
      ],

      // Stack Overflow specific
      STACKOVERFLOW: ["pre code", ".s-code-block pre", ".snippet-code pre"],

      // CodePen specific
      CODEPEN: [".CodeMirror-code", 'pre[class*="language-"]'],

      // JSFiddle specific
      JSFIDDLE: [".CodeMirror-code", "#code pre"],
    },
    // Language Detection
    LANGUAGES: {
      // Common file extensions to language mapping
      EXTENSIONS: {
        js: "javascript",
        ts: "typescript",
        py: "python",
        java: "java",
        cpp: "cpp",
        c: "c",
        cs: "csharp",
        php: "php",
        rb: "ruby",
        go: "go",
        rs: "rust",
        swift: "swift",
        kt: "kotlin",
        dart: "dart",
        html: "html",
        css: "css",
        scss: "scss",
        sql: "sql",
        sh: "bash",
        yml: "yaml",
        yaml: "yaml",
        json: "json",
        xml: "xml",
        md: "markdown",
      },
      KEYWORDS: {
        javascript: ["function", "const", "let", "var", "=>", "console.log"],
        python: ["def", "import", "from", "print", "if __name__"],
        java: ["public class", "private", "public", "System.out"],
        cpp: ["#include", "std::", "cout", "cin", "namespace"],
        html: ["<html>", "<div>", "<script>", "<!DOCTYPE"],
        css: ["{", "}", ":", ";", "px", "color:", "background:"],
        sql: ["SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE"],
        bash: ["#!/bin/bash", "echo", "grep", "awk", "sed"],
      },
    },

    // Language keywords for detection
    // Language detection patterns
    LANGUAGE_PATTERNS: {
      javascript: /\b(function|const|let|var|=>|async|await)\b/,
      python: /\b(def|import|from|class|if __name__|print)\b/,
      java: /\b(public class|private|protected|static void)\b/,
      cpp: /\b(#include|using namespace|std::)\b/,
      csharp: /\b(using System|namespace|public class)\b/,
      php: /<\?php|\b(function|class|\$\w+)\b/,
      ruby: /\b(def|class|require|puts)\b/,
      go: /\b(package|import|func|var)\b/,
      rust: /\b(fn|let|mut|impl|struct)\b/,
      swift: /\b(import|func|var|let|class)\b/,
      kotlin: /\b(fun|val|var|class|import)\b/,
      typescript: /\b(interface|type|enum|namespace)\b/,
      sql: /\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER)\b/i,
      css: /\{[^}]*\}|@media|@import/,
      html: /<[^>]+>/,
      json: /^\s*[\{\[]/,
      yaml: /^\s*\w+:\s*$/m,
      xml: /<\?xml|<\/\w+>/,
    },

    // Minimum code length to consider as snippet
    MIN_CODE_LENGTH: 10,

    // Maximum code length for auto-detection
    MAX_CODE_LENGTH: 10000,
  },

  // UI Configuration
  UI: {
    // Animation durations (in ms)
    ANIMATIONS: {
      FAST: 150,
      NORMAL: 300,
      SLOW: 500,
    },

    // Colors and themes
    THEMES: {
      DEFAULT: "light",
      AVAILABLE: ["light", "dark", "auto"],
      SYNTAX_THEMES: [
        "github",
        "monokai",
        "dracula",
        "atom-dark",
        "atom-light",
      ],
      LIGHT: {
        primary: "#667eea",
        secondary: "#764ba2",
        background: "#ffffff",
        surface: "#f8fafc",
        text: "#1a202c",
      },
      DARK: {
        primary: "#667eea",
        secondary: "#764ba2",
        background: "#1a202c",
        surface: "#2d3748",
        text: "#f7fafc",
      },
    },

    // Popup dimensions
    POPUP: {
      WIDTH: 380,
      HEIGHT: 600,
      MIN_HEIGHT: 400,
    },

    // Content script overlay
    OVERLAY: {
      Z_INDEX: 999999,
      FADE_DURATION: 200,
    },
  },

  // API Endpoints
  ENDPOINTS: {
    AUTH: {
      LOGIN: "/auth/login",
      LOGOUT: "/auth/logout",
      REGISTER: "/auth/register",
      REFRESH: "/auth/refresh",
    },
    SNIPPETS: {
      LIST: "/snippets",
      CREATE: "/snippets",
      UPDATE: "/snippets/:id",
      DELETE: "/snippets/:id",
      SEARCH: "/snippets/search",
    },
    COLLECTIONS: {
      LIST: "/collections",
      CREATE: "/collections",
      UPDATE: "/collections/:id",
      DELETE: "/collections/:id",
    },
    SYNC: {
      WEBSOCKET: "/ws",
      STATUS: "/sync/status",
      FORCE: "/sync/force",
    },
  },

  // Storage Configuration
  STORAGE: {
    SYNC_KEYS: ["snippets", "collections", "settings", "auth_token"],
    LOCAL_KEYS: ["offline_queue", "last_sync", "websocket_status"],
  },

  // Sync Configuration
  SYNC: {
    // Retry configuration
    RETRY: {
      MAX_ATTEMPTS: 3,
      DELAY_MS: 1000,
      BACKOFF_MULTIPLIER: 2,
    },

    // Batch sync settings
    BATCH: {
      SIZE: 10,
      INTERVAL_MS: 30000, // 30 seconds
    },

    // WebSocket configuration
    WEBSOCKET: {
      RECONNECT_INTERVAL: 5000,
      MAX_RECONNECT_ATTEMPTS: 5,
      HEARTBEAT_INTERVAL: 30000,
    },
  },

  // Analytics and Tracking (for future use)
  ANALYTICS: {
    EVENTS: {
      SNIPPET_SAVED: "snippet_saved",
      SNIPPET_ACCESSED: "snippet_accessed",
      SEARCH_PERFORMED: "search_performed",
      COLLECTION_CREATED: "collection_created",
      SYNC_COMPLETED: "sync_completed",
    },
  },

  // Feature Flags
  FEATURES: {
    // Phase 2 features
    REAL_TIME_SYNC: true,
    CONTEXT_MENU: true,
    KEYBOARD_SHORTCUTS: true,

    // Phase 3+ features (to be enabled later)
    TEAM_COLLABORATION: false,
    AI_SUGGESTIONS: false,
    CODE_EXECUTION: false,
    GITHUB_INTEGRATION: false,
  },

  // Error Messages
  ERRORS: {
    NETWORK_ERROR:
      "Unable to connect to server. Please check your internet connection.",
    AUTH_ERROR: "Authentication failed. Please log in again.",
    SYNC_ERROR: "Failed to sync snippets. Will retry automatically.",
    SAVE_ERROR: "Failed to save snippet. Please try again.",
    INVALID_CODE: "Selected text doesn't appear to be code.",
    QUOTA_EXCEEDED:
      "You've reached your snippet limit. Upgrade to Pro for unlimited snippets.",
  },

  // Success Messages
  SUCCESS: {
    SNIPPET_SAVED: "Code snippet saved successfully!",
    SYNC_COMPLETED: "Snippets synced successfully!",
    LOGIN_SUCCESS: "Logged in successfully!",
    LOGOUT_SUCCESS: "Logged out successfully!",
  },
};

// Make config available to service worker
self.CONFIG = CONFIG;
// For content scripts, store in local storage
try {
  if (chrome && chrome.storage) {
    chrome.storage.local.set({ extension_config: CONFIG });
  }
} catch (e) {
  // Silently fail if chrome APIs not available
  console.error("Failed to store config:", e);
}

// Utility functions
CONFIG.UTILS = {
  // Get current API base URL
  getApiUrl(endpoint = "") {
    const base = CONFIG.API.CURRENT.BASE_URL;
    const version = CONFIG.API.CURRENT.API_VERSION;
    return `${base}/api/${version}/${endpoint}`.replace(/\/+$/, "");
  },

  // Get WebSocket URL
  getWsUrl() {
    return CONFIG.API.CURRENT.WS_URL;
  },

  // Check if feature is enabled
  isFeatureEnabled(feature) {
    return CONFIG.FEATURES[feature] === true;
  },
  

  // Get storage key
  getStorageKey(key) {
    return CONFIG.EXTENSION.STORAGE_KEYS[key];
  },

  // Get default settings
  getDefaultSettings() {
    return { ...CONFIG.EXTENSION.DEFAULT_SETTINGS };
  },

  // Detect code language from content
  detectLanguage(code) {
    const patterns = CONFIG.CODE_DETECTION.LANGUAGE_PATTERNS;

    for (const [language, pattern] of Object.entries(patterns)) {
      if (pattern.test(code)) {
        return language;
      }
    }

    return "text"; // fallback
  },

  // Validate code snippet
  isValidCode(text) {
    if (!text || typeof text !== "string") return false;

    const cleanText = text.trim();
    const minLength = CONFIG.CODE_DETECTION.MIN_CODE_LENGTH;
    const maxLength = CONFIG.CODE_DETECTION.MAX_CODE_LENGTH;

    // Check length constraints
    if (cleanText.length < minLength || cleanText.length > maxLength) {
      return false;
    }

    // Check if it looks like code (has programming language patterns)
    const patterns = CONFIG.CODE_DETECTION.LANGUAGE_PATTERNS;
    const hasCodePattern = Object.values(patterns).some((pattern) =>
      pattern.test(cleanText)
    );

    // Additional heuristics for code detection
    const hasSpecialChars = /[{}();[\]=><]/.test(cleanText);
    const hasIndentation = /^\s{2,}/m.test(cleanText);
    const hasComments = /\/\/|\/\*|\*\/|#|<!--/.test(cleanText);

    return hasCodePattern || hasSpecialChars || hasIndentation || hasComments;
  },

  // Format error message
  formatError(error, context = "") {
    console.error(`[${CONFIG.EXTENSION.NAME}] Error in ${context}:`, error);
    return CONFIG.ERRORS.NETWORK_ERROR; // Default fallback
  },

  // Generate unique ID
  generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  },

  // Sanitize HTML
  sanitizeHtml(html) {
    const div = document.createElement("div");
    div.textContent = html;
    return div.innerHTML;
  },

  // Debounce function
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  // Throttle function
  throttle(func, limit) {
    let inThrottle;
    return function () {
      const args = arguments;
      const context = this;
      if (!inThrottle) {
        func.apply(context, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  },

  // Format file size
  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  },

  // Format date
  formatDate(date) {
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(date));
  },

  // Get domain from URL
  getDomain(url) {
    try {
      return new URL(url).hostname;
    } catch (e) {
      return "unknown";
    }
  },

  // Check if URL is supported for code detection
  isSupportedSite(url) {
    const supportedDomains = [
      "github.com",
      "stackoverflow.com",
      "codepen.io",
      "jsfiddle.net",
      "repl.it",
      "codesandbox.io",
      "glitch.com",
      "jsbin.com",
      "plnkr.co",
    ];

    const domain = this.getDomain(url);
    return supportedDomains.some((supported) => domain.includes(supported));
  },
};

// Development helpers (only available in dev mode)
if (CONFIG.API.isDevelopment()) {
  CONFIG.DEV = {
    // Enable debug logging
    DEBUG: {
      ENABLED: true, // Set to false in production
      LOG_LEVELS: ["info", "warn", "error"],
      WEBSOCKET_LOGS: true,
      API_LOGS: true,
    },
    // Mock data for testing
    MOCK_SNIPPETS: [
      {
        id: "mock-1",
        title: "React Hook Example",
        code: "const [count, setCount] = useState(0);",
        language: "javascript",
        tags: ["react", "hooks"],
        createdAt: new Date().toISOString(),
      },
      {
        id: "mock-2",
        title: "Python List Comprehension",
        code: "squares = [x**2 for x in range(10)]",
        language: "python",
        tags: ["python", "list-comprehension"],
        createdAt: new Date().toISOString(),
      },
    ],

    // Debug logging function
    log(...args) {
      if (this.DEBUG) {
        console.log(`[${CONFIG.EXTENSION.NAME} DEBUG]`, ...args);
      }
    },

    // Performance timing
    time(label) {
      if (this.DEBUG) {
        console.time(`[${CONFIG.EXTENSION.NAME}] ${label}`);
      }
    },

    timeEnd(label) {
      if (this.DEBUG) {
        console.timeEnd(`[${CONFIG.EXTENSION.NAME}] ${label}`);
      }
    },
  };
}

// Export configuration
if (typeof module !== "undefined" && module.exports) {
  module.exports = CONFIG;
} else if (typeof window !== "undefined") {
  window.CONFIG = CONFIG;
}

// Make config available to content scripts and popup
try {
  chrome.storage.local.set({ extension_config: CONFIG });
} catch (e) {
  // Silently fail if chrome APIs not available
}

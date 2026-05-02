/**
 * Universal Chrome Extension - Enhanced Background Script
 * Code Snippet Manager with Authentication & Offline Support
 */

// Global variables
// Add this with other global variables at the top of background.js
let pendingResponses = {};
let pendingAuth = null;
let devToolsPort = null;
let webSocket = null;
let serverUrl = "http://localhost:5000";
let isConnected = false;
let reconnectAttempts = 0;
let maxReconnectAttempts = 3;
let reconnectDelay = 3000;
let reconnectTimer = null;

// Authentication & User Management
let currentUser = null;
let authToken = null;
let isAuthenticated = false;

// Snippet Management
let offlineQueue = [];
let pendingSnippets = [];
let snippetCache = new Map();
let collections = [];
// Keep-alive mechanism for Chrome extension service workers
let keepAliveTimer = null;
let lastActivity = Date.now();
const KEEP_ALIVE_INTERVAL = 26000; // 25 seconds
const MAX_IDLE_TIME = 240000; // 4 minutes

function startKeepAlive() {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer);
  }

  keepAliveTimer = setInterval(() => {
    const now = Date.now();

    // Update activity timestamp
    lastActivity = now;

    // Send ping if connected
    if (webSocket && webSocket.readyState === WebSocket.OPEN) {
      try {
        webSocket.send("2"); // Socket.IO ping
        logWithTimestamp("Keep-alive ping sent");
      } catch (error) {
        logWithTimestamp("Keep-alive ping failed:", error);
      }
    }

    // Force service worker to stay active
    chrome.storage.local.get("keepAlive").catch(() => {});
  }, KEEP_ALIVE_INTERVAL);
}

function stopKeepAlive() {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer);
    keepAliveTimer = null;
  }
}

// Add this after line 30 with other global variables
let pingCount = 0;
const MAX_CACHE_SIZE = 1000; // Limit cache size
const MAX_OFFLINE_QUEUE = 100; // Limit offline queue
const CLEANUP_INTERVAL = 300000; // 5 minutes
let cleanupTimer = null;
let messageQueue = [];
let isProcessingQueue = false;
let authTimeout = null;
const AUTH_TIMEOUT_DURATION = 20000; // 15 seconds

// Auto-reload for development - Add this after line 77
if (typeof chrome !== "undefined" && chrome.management) {
  chrome.management.getSelf((self) => {
    if (self.installType === "development") {
      let lastSignalTime = 0;
      let isCheckingSignal = false;

      const checkReloadSignal = async () => {
        if (isCheckingSignal) return; // Prevent multiple simultaneous checks
        isCheckingSignal = true;

        try {
          // Try to read the signal file
          const response = await fetch(chrome.runtime.getURL(".reload-signal"));
          if (response.ok) {
            const signalContent = await response.text();
            const signalTime = parseInt(signalContent.trim());

            // Only reload if this is a NEW signal (timestamp is newer)
            if (signalTime > lastSignalTime && lastSignalTime > 0) {
              console.log("🔄 File change detected - Reloading extension...");
              chrome.runtime.reload();
              return;
            }

            // Update last signal time
            if (signalTime > lastSignalTime) {
              lastSignalTime = signalTime;
              console.log(
                "📝 Initial signal time recorded:",
                new Date(signalTime).toLocaleTimeString()
              );
            }
          }
        } catch (error) {
          // Signal file doesn't exist or can't be read - this is normal
          // Don't log this as it's expected when no changes have been made
        }

        isCheckingSignal = false;
      };

      // Check less frequently to reduce load
      const intervalId = setInterval(checkReloadSignal, 3000); // Every 3 seconds instead of 2

      // Initial check after a delay
      setTimeout(() => {
        console.log("🛠️ Development mode: File change monitoring started");
        checkReloadSignal();
      }, 1000);

      // Cleanup on extension unload
      chrome.runtime.onSuspend?.addListener(() => {
        clearInterval(intervalId);
      });
    }
  });
}
function startAuthTimeout(type, email) {
  // Clear any existing timeout first
  if (authTimeout) {
    clearTimeout(authTimeout);
  }

  authTimeout = setTimeout(() => {
    logWithTimestamp(`Authentication timeout for ${type}: ${email}`);

    if (
      pendingAuth &&
      pendingAuth.email === email &&
      pendingAuth.type === type
    ) {
      // Clear pending auth
      pendingAuth = null;

      // Notify popup of timeout
      notifyPopup(`${type.toUpperCase()}_FAILED`, {
        error: `${type} request timed out. Please try again.`,
      });
    }

    authTimeout = null;
  }, AUTH_TIMEOUT_DURATION);
}

function clearAuthTimeout() {
  if (authTimeout) {
    clearTimeout(authTimeout);
    authTimeout = null;
  }
}

// Storage Keys
const STORAGE_KEYS = {
  AUTH_TOKEN: "authToken",
  CURRENT_USER: "currentUser",
  OFFLINE_QUEUE: "offlineQueue",
  SNIPPET_CACHE: "snippetCache",
  COLLECTIONS: "collections",
  SERVER_URL: "serverUrl",
};

function performMemoryCleanup() {
  try {
    // Clear excessive cache entries
    if (snippetCache.size > MAX_CACHE_SIZE) {
      const entries = Array.from(snippetCache.entries());
      const sorted = entries.sort(
        (a, b) => new Date(b[1].createdAt) - new Date(a[1].createdAt)
      );
      snippetCache.clear();

      // Keep only recent entries
      sorted.slice(0, MAX_CACHE_SIZE * 0.8).forEach(([key, value]) => {
        snippetCache.set(key, value);
      });

      logWithTimestamp(
        `Cleaned cache: ${entries.length} -> ${snippetCache.size} entries`
      );
    }

    // Limit offline queue
    if (offlineQueue.length > MAX_OFFLINE_QUEUE) {
      offlineQueue = offlineQueue.slice(-MAX_OFFLINE_QUEUE);
      logWithTimestamp(`Trimmed offline queue to ${MAX_OFFLINE_QUEUE} items`);
    }

    // Clear old pending snippets
    const fiveMinutesAgo = Date.now() - 300000;
    pendingSnippets = pendingSnippets.filter(
      (snippet) => snippet.tempId > fiveMinutesAgo
    );

    // Force garbage collection if available
    if (window.gc) {
      window.gc();
    }

    logWithTimestamp("Memory cleanup completed");
  } catch (error) {
    logWithTimestamp("Memory cleanup failed:", error);
  }
}

const logQueue = [];
const MAX_LOG_ENTRIES = 50;

function logWithTimestamp(message, data) {
  const timestamp = new Date().toISOString();
  const logEntry = { timestamp, message, data };

  // Maintain log queue size
  logQueue.push(logEntry);
  if (logQueue.length > MAX_LOG_ENTRIES) {
    logQueue.shift();
  }

  // Only log to console in development or for errors
  if (data && (message.includes("error") || message.includes("Error"))) {
    console.log(`[${timestamp}] ${message}`, data);
  } else if (!data) {
    console.log(`[${timestamp}] ${message}`);
  }
}
async function createCollection(name, sendResponse) {
  logWithTimestamp("🔵 CREATE COLLECTION - Starting process", {
    name: name,
    isAuthenticated: isAuthenticated,
    hasAuthToken: !!authToken,
    hasCurrentUser: !!currentUser,
    isConnected: isConnected,
    webSocketState: webSocket?.readyState,
    serverUrl: serverUrl,
  });

  // First verify current authentication
  if (!isAuthenticated || !authToken || !currentUser) {
    logWithTimestamp("❌ CREATE COLLECTION - Authentication check failed", {
      isAuthenticated,
      hasAuthToken: !!authToken,
      hasCurrentUser: !!currentUser,
    });
    sendResponse({ success: false, error: "Not authenticated" });
    return false;
  }

  // Verify with server if connected
  if (isConnected) {
    try {
      logWithTimestamp("🔍 CREATE COLLECTION - Verifying auth with server", {
        serverUrl: serverUrl,
        endpoint: `${serverUrl}/api/auth/verify`,
        userEmail: currentUser.email,
        tokenPreview: authToken
          ? authToken.substring(0, 20) + "..."
          : "NO TOKEN",
      });

      const authCheckStartTime = Date.now();

      // Double-check auth with server before creating collection
      const authCheck = await fetch(`${serverUrl}/api/auth/verify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ email: currentUser.email }),
      });

      const authCheckDuration = Date.now() - authCheckStartTime;

      logWithTimestamp(
        "📡 CREATE COLLECTION - Auth verification response received",
        {
          status: authCheck.status,
          ok: authCheck.ok,
          statusText: authCheck.statusText,
          duration: `${authCheckDuration}ms`,
          headers: Object.fromEntries(authCheck.headers.entries()),
        }
      );

      if (!authCheck.ok) {
        logWithTimestamp("❌ CREATE COLLECTION - Auth verification failed", {
          status: authCheck.status,
          statusText: authCheck.statusText,
        });

        // Try to get error response body
        try {
          const errorText = await authCheck.text();
          logWithTimestamp("❌ Auth verification error body:", errorText);
        } catch (e) {
          logWithTimestamp("❌ Could not read error response body");
        }

        await clearAuthData();
        sendResponse({
          success: false,
          error: "Authentication expired. Please login again.",
        });
        return false;
      }

      const authData = await authCheck.json();
      logWithTimestamp("✅ CREATE COLLECTION - Auth data received", {
        valid: authData.valid,
        hasUser: !!authData.user,
        authDataKeys: Object.keys(authData),
      });

      if (!authData.valid) {
        logWithTimestamp("❌ CREATE COLLECTION - Auth token invalid");
        await clearAuthData();
        sendResponse({
          success: false,
          error: "Authentication expired. Please login again.",
        });
        return false;
      }

      // Check WebSocket connection state
      if (!webSocket || webSocket.readyState !== WebSocket.OPEN) {
        logWithTimestamp("❌ CREATE COLLECTION - WebSocket not ready", {
          hasWebSocket: !!webSocket,
          readyState: webSocket?.readyState,
          readyStateText: getWebSocketStateText(webSocket?.readyState),
        });
        sendResponse({ success: false, error: "Connection not ready" });
        return false;
      }

      const createMsg = JSON.stringify([
        "create_collection",
        {
          name: name,
          userId: currentUser?.id,
          token: authToken,
        },
      ]);

      logWithTimestamp("📤 CREATE COLLECTION - Sending WebSocket message", {
        messageType: "create_collection",
        collectionName: name,
        userId: currentUser?.id,
        hasToken: !!authToken,
        messageLength: createMsg.length,
        webSocketReadyState: webSocket.readyState,
      });

      webSocket.send("42" + createMsg);

      // Store the sendResponse callback with timeout
      pendingResponses = pendingResponses || {};
      pendingResponses["create_collection"] = {
        callback: sendResponse,
        timestamp: Date.now(),
        collectionName: name,
        timeout: setTimeout(() => {
          logWithTimestamp("⏰ CREATE COLLECTION - Request timeout", {
            collectionName: name,
            waitTime:
              Date.now() - pendingResponses["create_collection"].timestamp,
          });

          if (pendingResponses["create_collection"]) {
            pendingResponses["create_collection"].callback({
              success: false,
              error: "Request timeout - server did not respond",
            });
            delete pendingResponses["create_collection"];
          }
        }, 10000), // 10 second timeout
      };

      logWithTimestamp("✅ CREATE COLLECTION - Request sent successfully", {
        pendingResponsesCount: Object.keys(pendingResponses).length,
      });

      return true;
    } catch (error) {
      logWithTimestamp("❌ CREATE COLLECTION - Exception occurred", {
        error: error.message,
        stack: error.stack,
        name: error.name,
        type: error.constructor.name,
      });

      // Check if it's a network error
      if (error.name === "TypeError" && error.message.includes("fetch")) {
        logWithTimestamp("🌐 Network error detected - server might be down", {
          serverUrl: serverUrl,
          endpoint: `${serverUrl}/api/auth/verify`,
        });
      }

      sendResponse({ success: false, error: error.message });
      return false;
    }
  } else {
    logWithTimestamp("❌ CREATE COLLECTION - Not connected to server", {
      isConnected,
      serverUrl,
    });
    sendResponse({ success: false, error: "Not connected to server" });
    return false;
  }
}

// Helper function to get readable WebSocket state
function getWebSocketStateText(readyState) {
  switch (readyState) {
    case 0:
      return "CONNECTING";
    case 1:
      return "OPEN";
    case 2:
      return "CLOSING";
    case 3:
      return "CLOSED";
    default:
      return "UNKNOWN";
  }
}

// Add this function for testing
async function testAuthEndpoint() {
  try {
    logWithTimestamp("🧪 TESTING AUTH ENDPOINT", {
      serverUrl: serverUrl,
      endpoint: `${serverUrl}/api/auth/verify`,
      hasToken: !!authToken,
      hasCurrentUser: !!currentUser,
    });

    const response = await fetch(`${serverUrl}/api/auth/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ email: currentUser?.email }),
    });

    logWithTimestamp("🧪 AUTH ENDPOINT TEST RESULT", {
      status: response.status,
      ok: response.ok,
      statusText: response.statusText,
      headers: Object.fromEntries(response.headers.entries()),
    });

    const responseText = await response.text();
    logWithTimestamp("🧪 AUTH ENDPOINT RESPONSE BODY", responseText);
  } catch (error) {
    logWithTimestamp("🧪 AUTH ENDPOINT TEST FAILED", {
      error: error.message,
      stack: error.stack,
    });
  }
}

// Call this function in your console to test
testAuthEndpoint();

// Helper function to get readable WebSocket state
function getWebSocketStateText(readyState) {
  switch (readyState) {
    case 0:
      return "CONNECTING";
    case 1:
      return "OPEN";
    case 2:
      return "CLOSING";
    case 3:
      return "CLOSED";
    default:
      return "UNKNOWN";
  }
}

// Show notification to user
function showNotification(title, message, type = "basic") {
  // Ensure required properties are present
  const notificationOptions = {
    type: type,
    iconUrl: chrome.runtime.getURL("icon48.png"), // Add required iconUrl
    title: title,
    message: message,
  };

  // Create notification with error handling
  chrome.notifications.create(notificationOptions, (notificationId) => {
    if (chrome.runtime.lastError) {
      logWithTimestamp(
        "Notification creation failed:",
        chrome.runtime.lastError.message
      );
      // Fallback: try with a generic icon path
      chrome.notifications.create({
        type: "basic",
        iconUrl:
          "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", // 1x1 transparent PNG as fallback
        title: title,
        message: message,
      });
    }
  });
}

// Initialize extension with stored data
async function initializeExtension() {
  try {
    const result = await chrome.storage.local.get([
      STORAGE_KEYS.AUTH_TOKEN,
      STORAGE_KEYS.CURRENT_USER,
      STORAGE_KEYS.OFFLINE_QUEUE,
      STORAGE_KEYS.SNIPPET_CACHE,
      STORAGE_KEYS.COLLECTIONS,
      STORAGE_KEYS.SERVER_URL,
    ]);

    // Restore authentication state
    if (result[STORAGE_KEYS.AUTH_TOKEN] && result[STORAGE_KEYS.CURRENT_USER]) {
      authToken = result[STORAGE_KEYS.AUTH_TOKEN];
      currentUser = result[STORAGE_KEYS.CURRENT_USER];
      isAuthenticated = true;
      logWithTimestamp(
        "Authentication restored for user:",
        currentUser?.email || "Unknown"
      );
    }

    // With this:
    // Verify stored authentication with server
    // Restore authentication state
    const authRestored = await verifyStoredAuthentication();
    if (authRestored) {
      logWithTimestamp("Authentication state restored successfully");
      // CRITICAL: Broadcast auth state to any listening components
      setTimeout(() => {
        notifyPopup("AUTH_STATE_CHANGED", {
          isAuthenticated: true,
          user: currentUser,
          token: authToken,
        });
      }, 500);
    } else {
      logWithTimestamp("No valid authentication found");
      setTimeout(() => {
        notifyPopup("AUTH_STATE_CHANGED", {
          isAuthenticated: false,
          user: null,
          token: null,
        });
      }, 500);
    }

    // Restore server URL
    if (result[STORAGE_KEYS.SERVER_URL]) {
      serverUrl = result[STORAGE_KEYS.SERVER_URL];
    }

    // Restore offline queue
    if (result[STORAGE_KEYS.OFFLINE_QUEUE]) {
      offlineQueue = result[STORAGE_KEYS.OFFLINE_QUEUE];
      logWithTimestamp(
        `Restored ${offlineQueue.length} queued snippets from storage`
      );
    }

    // Restore snippet cache
    if (result[STORAGE_KEYS.SNIPPET_CACHE]) {
      snippetCache = new Map(
        Object.entries(result[STORAGE_KEYS.SNIPPET_CACHE])
      );
      logWithTimestamp(`Restored ${snippetCache.size} cached snippets`);
    }

    // Restore collections
    if (result[STORAGE_KEYS.COLLECTIONS]) {
      collections = result[STORAGE_KEYS.COLLECTIONS];
      logWithTimestamp(`Restored ${collections.length} collections`);
    }

    // Connect to WebSocket
    // Don't auto-connect to WebSocket - wait for user action
    logWithTimestamp("Extension initialized - waiting for user to connect");
    if (cleanupTimer) {
      clearInterval(cleanupTimer);
    }
    cleanupTimer = setInterval(performMemoryCleanup, CLEANUP_INTERVAL);

    logWithTimestamp("Extension initialized with memory optimization");
    setInterval(cleanupPendingResponses, 60000); // Check every minute
  } catch (error) {
    logWithTimestamp("Failed to initialize extension:", error);
  }
}

// Add comprehensive authentication verification
// Enhanced authentication verification with better error handling
async function verifyStoredAuthentication() {
  try {
    const result = await chrome.storage.local.get([
      STORAGE_KEYS.AUTH_TOKEN,
      STORAGE_KEYS.CURRENT_USER,
    ]);

    if (
      !result[STORAGE_KEYS.AUTH_TOKEN] ||
      !result[STORAGE_KEYS.CURRENT_USER]
    ) {
      logWithTimestamp("No stored auth data found");
      return false;
    }

    // Set auth data immediately from storage
    authToken = result[STORAGE_KEYS.AUTH_TOKEN];
    currentUser = result[STORAGE_KEYS.CURRENT_USER];
    isAuthenticated = true;

    logWithTimestamp("Auth data restored from storage:", currentUser.email);
    // CRITICAL: Notify popup immediately about auth state
    setTimeout(() => {
      notifyPopup("AUTH_STATE_CHANGED", {
        isAuthenticated: true,
        user: currentUser,
        token: authToken,
      });
    }, 100);

    // Verify with server only if connected, but don't clear auth on failure
    if (isConnected) {
      try {
        const response = await fetch(`${serverUrl}/api/auth/verify`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${authToken}`,
          },
          body: JSON.stringify({ email: currentUser.email }),
          timeout: 5000, // 5 second timeout
        });

        if (response.ok) {
          const data = await response.json();
          if (!data.valid) {
            logWithTimestamp("Server says token is invalid, clearing auth");
            await clearAuthData();
            notifyPopup("AUTH_STATE_CHANGED", {
              isAuthenticated: false,
              user: null,
              token: null,
            });
            return false;
          }
          logWithTimestamp("Server confirmed authentication is valid");
        } else {
          logWithTimestamp(
            "Server verification failed, but keeping local auth"
          );
          // Don't clear auth on server errors - keep local state
        }
      } catch (error) {
        logWithTimestamp(
          "Server verification error (keeping local auth):",
          error.message
        );
        // Don't clear auth on network errors - server might be down temporarily
      }
    } else {
      logWithTimestamp("Not connected to server, using cached auth");
    }

    return true;
  } catch (error) {
    logWithTimestamp("Auth verification failed:", error);
    return false;
  }
}

// Helper function to clear auth data
async function clearAuthData() {
  authToken = null;
  currentUser = null;
  isAuthenticated = false;

  await chrome.storage.local.remove([
    STORAGE_KEYS.AUTH_TOKEN,
    STORAGE_KEYS.CURRENT_USER,
  ]);
}

// Enhanced auth check that doesn't clear data unnecessarily
async function checkAuthStatus() {
  try {
    const result = await chrome.storage.local.get([
      STORAGE_KEYS.AUTH_TOKEN,
      STORAGE_KEYS.CURRENT_USER,
    ]);

    const hasStoredAuth =
      result[STORAGE_KEYS.AUTH_TOKEN] && result[STORAGE_KEYS.CURRENT_USER];

    logWithTimestamp("checkAuthStatus - Storage result:", {
      hasToken: !!result[STORAGE_KEYS.AUTH_TOKEN],
      hasUser: !!result[STORAGE_KEYS.CURRENT_USER],
      tokenPreview: result[STORAGE_KEYS.AUTH_TOKEN]
        ? result[STORAGE_KEYS.AUTH_TOKEN].substring(0, 10) + "..."
        : "none",
    });

    if (hasStoredAuth && !isAuthenticated) {
      // Restore auth state
      authToken = result[STORAGE_KEYS.AUTH_TOKEN];
      currentUser = result[STORAGE_KEYS.CURRENT_USER];
      isAuthenticated = true;
      logWithTimestamp("Auth state restored on demand:", currentUser.email);
    }

    return {
      isAuthenticated,
      user: currentUser,
      token: authToken,
      hasStoredAuth,
    };
  } catch (error) {
    logWithTimestamp("Auth status check failed:", error);
    return {
      isAuthenticated: false,
      user: null,
      token: null,
      hasStoredAuth: false,
    };
  }
}

// Connect to WebSocket server
function connectToWebSocket() {
  // Clear any existing timer
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  if (webSocket) {
    webSocket.close();
  }

  try {
    // Start keep-alive mechanism
    startKeepAlive();

    // Simplified server check
    fetch(serverUrl + "/api/status", { timeout: 5000 })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        logWithTimestamp("Server is running");

        // Connect if not already connected
        if (!webSocket || webSocket.readyState === WebSocket.CLOSED) {
          initiateSocketIOConnection();
        }
      })
      .catch((error) => {
        logWithTimestamp("Server status check failed:", error.message);
        stopKeepAlive();

        if (devToolsPort) {
          devToolsPort.postMessage({
            type: "CONNECTION_STATUS",
            status: "error",
            error: error.message,
          });
        }

        if (reconnectAttempts < maxReconnectAttempts) {
          scheduleReconnect();
        }
      });
  } catch (error) {
    logWithTimestamp("Connection failed:", error.message);
    stopKeepAlive();
    if (reconnectAttempts < maxReconnectAttempts) {
      scheduleReconnect();
    }
  }
}

// Add this new function after connectToWebSocket():
// Replace the existing initiateSocketIOConnection function with this:
function initiateSocketIOConnection() {
  // Simplified Socket.IO handshake
  fetch(serverUrl + "/socket.io/?EIO=4&transport=polling", {
    method: "GET",
    headers: {
      Accept: "*/*",
      Origin: "chrome-extension://" + chrome.runtime.id,
    },
  })
    .then((response) => response.text())
    .then((data) => {
      logWithTimestamp("Socket.IO handshake response received");

      // Extract session ID
      const match = data.match(/"sid":"([^"]+)"/);
      if (!match) {
        throw new Error("Could not extract session ID from handshake");
      }

      const sessionId = match[1];
      const wsUrl =
        serverUrl.replace(/^http/, "ws") +
        `/socket.io/?EIO=4&transport=websocket&sid=${sessionId}`;

      logWithTimestamp("Connecting to WebSocket:", wsUrl);
      webSocket = new WebSocket(wsUrl);

      webSocket.onopen = () => {
        logWithTimestamp("WebSocket connection established");
        isConnected = true;
        reconnectAttempts = 0;

        showNotification(
          "Code Snippet Manager",
          "Connected to server successfully!"
        );

        // SIMPLIFIED: Direct connection sequence
        webSocket.send("2probe");
        webSocket.send("5");
        webSocket.send("40");

        // Register client immediately
        const registerMsg = JSON.stringify([
          "register_client",
          {
            clientType: "chrome",
            userId: currentUser?.id || null,
            token: authToken || null,
          },
        ]);
        webSocket.send("42" + registerMsg);
        logWithTimestamp("Client registered with server");

        // Process offline queue if authenticated
        if (isAuthenticated) {
          processOfflineQueue();
        }

        if (devToolsPort) {
          devToolsPort.postMessage({
            type: "CONNECTION_STATUS",
            status: "connected",
          });
        }
      };

      // ADD MISSING EVENT HANDLERS
      webSocket.onmessage = (event) => {
        handleWebSocketMessage(event.data);
      };

      webSocket.onerror = (error) => {
        logWithTimestamp("WebSocket error:", error);
        isConnected = false;

        if (devToolsPort) {
          devToolsPort.postMessage({
            type: "CONNECTION_STATUS",
            status: "error",
            error: "WebSocket error occurred",
          });
        }
      };

      webSocket.onclose = (event) => {
        logWithTimestamp("WebSocket closed:", {
          code: event.code,
          reason: event.reason,
        });
        isConnected = false;

        if (devToolsPort) {
          devToolsPort.postMessage({
            type: "CONNECTION_STATUS",
            status: "disconnected",
          });
        }

        // Only attempt reconnect if not intentionally closed
        if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
          scheduleReconnect();
        }
      };
    })
    .catch((error) => {
      logWithTimestamp("Socket.IO handshake failed:", error);
      if (reconnectAttempts < maxReconnectAttempts) {
        scheduleReconnect();
      }
    });
}

// Schedule WebSocket reconnection
function scheduleReconnect() {
  if (reconnectAttempts >= maxReconnectAttempts) {
    logWithTimestamp("Maximum reconnect attempts reached");
    showNotification(
      "Code Snippet Manager",
      "Connection failed. Please restart the server and try again.",
      "basic"
    );
    return;
  }

  reconnectAttempts++;
  logWithTimestamp(
    `Scheduling reconnect attempt ${reconnectAttempts}/${maxReconnectAttempts} in ${reconnectDelay}ms`
  );

  reconnectTimer = setTimeout(() => {
    logWithTimestamp(
      `Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`
    );
    connectToWebSocket();
  }, reconnectDelay);
}

// Enhanced disconnect handling
function handleDisconnect(intentional = false) {
  isConnected = false;

  if (webSocket) {
    webSocket.close(intentional ? 1000 : 1001);
    webSocket = null;
  }

  stopKeepAlive();

  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  if (!intentional && reconnectAttempts < maxReconnectAttempts) {
    logWithTimestamp("Unexpected disconnect - attempting to reconnect");
    scheduleReconnect();
  }

  logWithTimestamp(
    intentional ? "Intentionally disconnected" : "Connection lost"
  );
}
// Add these new handler functions:

function handleLoginSuccess(data) {
  console.log("🟢 LOGIN SUCCESS - Server confirmed authentication");
  console.log("📦 FULL LOGIN RESPONSE DATA:", JSON.stringify(data, null, 2));

  // Clear timeout immediately
  clearAuthTimeout();

  // Extract token with multiple fallbacks and enhanced logging
  authToken =
    data.token || data.authToken || data.access_token || data.jwt || null;
  currentUser = data.user || data.userData || null;

  console.log("🔍 TOKEN EXTRACTION ANALYSIS:", {
    dataKeys: Object.keys(data),
    tokenFound: !!authToken,
    tokenSource: data.token
      ? "data.token"
      : data.authToken
      ? "data.authToken"
      : data.access_token
      ? "data.access_token"
      : data.jwt
      ? "data.jwt"
      : "NONE",
    tokenPreview: authToken ? authToken.substring(0, 20) + "..." : "NO TOKEN",
    tokenLength: authToken ? authToken.length : 0,
    userFound: !!currentUser,
    userEmail: currentUser?.email || "NO EMAIL",
  });

  if (!authToken || !currentUser) {
    console.log("❌ LOGIN SUCCESS but missing critical data:", {
      hasToken: !!authToken,
      hasUser: !!currentUser,
      availableFields: Object.keys(data),
      fullData: data,
    });
    handleLoginFailed({ message: "Incomplete authentication data received" });
    return;
  }

  isAuthenticated = true;
  console.log("✅ TOKEN RECEIVED SUCCESSFULLY:", {
    tokenLength: authToken.length,
    userEmail: currentUser.email,
    userId: currentUser.id,
  });

  // Save to storage with enhanced logging
  chrome.storage.local
    .set({
      [STORAGE_KEYS.AUTH_TOKEN]: authToken,
      [STORAGE_KEYS.CURRENT_USER]: currentUser,
    })
    .then(() => {
      console.log(
        "✅ Login auth data saved successfully to chrome.storage.local"
      );
      console.log("💾 STORED DATA:", {
        tokenKey: STORAGE_KEYS.AUTH_TOKEN,
        userKey: STORAGE_KEYS.CURRENT_USER,
        storedTokenLength: authToken.length,
        storedUserEmail: currentUser.email,
      });

      // CRITICAL FIX: Notify popup with proper auth state
      notifyPopup("LOGIN_SUCCESS", {
        user: currentUser,
        token: authToken,
        isAuthenticated: true,
      });

      // Also send direct auth update
      notifyPopup("AUTH_STATE_CHANGED", {
        isAuthenticated: true,
        user: currentUser,
        token: authToken,
      });

      showNotification(
        "Login Successful",
        `Welcome back, ${currentUser.email}!`
      );
    })
    .catch((error) => {
      console.error("❌ FAILED TO SAVE AUTH DATA:", error);
    });

  // Clear pending auth
  pendingAuth = null;
}

function handleLoginFailed(data) {
  console.log(
    "🔴 LOGIN FAILED - Server rejected authentication:",
    data.message
  );

  // Clear timeout and pending auth
  clearAuthTimeout();
  pendingAuth = null;

  notifyPopup("LOGIN_FAILED", { error: data.message || "Login failed" });
}

function handleRegisterSuccess(data) {
  console.log("🟢 REGISTER SUCCESS - Server confirmed registration");
  console.log("📦 FULL REGISTER RESPONSE DATA:", JSON.stringify(data, null, 2));

  // Clear timeout immediately
  clearAuthTimeout();

  // Extract token with multiple fallbacks and enhanced logging
  authToken =
    data.token || data.authToken || data.access_token || data.jwt || null;
  currentUser = data.user || data.userData || null;

  console.log("🔍 REGISTER TOKEN EXTRACTION:", {
    dataKeys: Object.keys(data),
    tokenFound: !!authToken,
    tokenSource: data.token
      ? "data.token"
      : data.authToken
      ? "data.authToken"
      : data.access_token
      ? "data.access_token"
      : data.jwt
      ? "data.jwt"
      : "NONE",
    tokenPreview: authToken ? authToken.substring(0, 20) + "..." : "NO TOKEN",
    tokenLength: authToken ? authToken.length : 0,
    userFound: !!currentUser,
    userEmail: currentUser?.email || "NO EMAIL",
  });

  if (!authToken || !currentUser) {
    console.log("❌ REGISTER SUCCESS but missing critical data:", {
      hasToken: !!authToken,
      hasUser: !!currentUser,
      availableFields: Object.keys(data),
      fullData: data,
    });
    handleRegisterFailed({ message: "Incomplete registration data received" });
    return;
  }

  isAuthenticated = true;
  console.log("✅ REGISTER TOKEN RECEIVED SUCCESSFULLY:", {
    tokenLength: authToken.length,
    userEmail: currentUser.email,
    userId: currentUser.id,
  });

  // Save to storage with enhanced logging
  chrome.storage.local
    .set({
      [STORAGE_KEYS.AUTH_TOKEN]: authToken,
      [STORAGE_KEYS.CURRENT_USER]: currentUser,
    })
    .then(() => {
      console.log(
        "✅ Registration auth data saved successfully to chrome.storage.local"
      );
      console.log("💾 REGISTER STORED DATA:", {
        tokenKey: STORAGE_KEYS.AUTH_TOKEN,
        userKey: STORAGE_KEYS.CURRENT_USER,
        storedTokenLength: authToken.length,
        storedUserEmail: currentUser.email,
      });

      notifyPopup("REGISTER_SUCCESS", { user: currentUser, token: authToken });
      showNotification(
        "Registration Successful",
        `Welcome, ${currentUser.email}!`
      );
    })
    .catch((error) => {
      console.error("❌ FAILED TO SAVE REGISTER AUTH DATA:", error);
    });

  // Clear pending auth
  pendingAuth = null;
}

function handleRegisterFailed(data) {
  console.log(
    "🔴 REGISTER FAILED - Server rejected registration:",
    data.message
  );

  // Clear timeout and pending auth
  clearAuthTimeout();
  pendingAuth = null;

  notifyPopup("REGISTER_FAILED", {
    error: data.message || "Registration failed",
  });
}

// Replace your existing handleCollectionCreated function
function handleCollectionCreated(data) {
  logWithTimestamp("✅ COLLECTION CREATED - Processing response", {
    hasCollections: !!data.collections,
    hasCollection: !!data.collection,
    collectionName: data.collection?.name,
    collectionsCount: data.collections?.length,
    hasPendingResponse: !!(
      pendingResponses && pendingResponses["create_collection"]
    ),
  });

  if (data.collections) {
    collections = data.collections;
    saveCollections();
    logWithTimestamp("💾 Collections saved to storage", {
      count: collections.length,
    });
  }

  // Notify popup
  notifyPopup("COLLECTION_CREATED", data);

  // Call the stored callback if it exists
  if (pendingResponses && pendingResponses["create_collection"]) {
    logWithTimestamp("📞 Calling pending response callback");

    // Clear timeout
    if (pendingResponses["create_collection"].timeout) {
      clearTimeout(pendingResponses["create_collection"].timeout);
    }

    pendingResponses["create_collection"].callback({
      success: true,
      collection: data.collection,
    });
    delete pendingResponses["create_collection"];

    logWithTimestamp("✅ Pending response resolved successfully");
  } else {
    logWithTimestamp(
      "⚠️ No pending response callback found for collection creation"
    );
  }

  showNotification(
    "Collection Created",
    `"${data.collection?.name}" created successfully!`
  );
}

function handleCollectionCreationFailed(data) {
  logWithTimestamp("❌ COLLECTION CREATION FAILED - Processing error", {
    error: data.message,
    errorCode: data.code,
    errorType: data.error_type,
    hasPendingResponse: !!(
      pendingResponses && pendingResponses["create_collection"]
    ),
  });

  // Call the stored callback if it exists
  if (pendingResponses && pendingResponses["create_collection"]) {
    logWithTimestamp("📞 Calling pending error callback");

    // Clear timeout
    if (pendingResponses["create_collection"].timeout) {
      clearTimeout(pendingResponses["create_collection"].timeout);
    }

    pendingResponses["create_collection"].callback({
      success: false,
      error: data.message || "Failed to create collection",
      errorType: data.error_type || "general",
    });
    delete pendingResponses["create_collection"];

    logWithTimestamp("✅ Pending error response resolved");
  } else {
    logWithTimestamp(
      "⚠️ No pending response callback found for collection creation failure"
    );
  }

  notifyPopup("COLLECTION_CREATION_FAILED", {
    error: data.message || "Failed to create collection",
    errorType: data.error_type || "general",
  });
}

// Helper function to notify popup
function notifyPopup(type, data) {
  const message = {
    type: type,
    data: data,
    timestamp: Date.now(),
  };

  console.log("📤 Sending message to popup:", message);

  chrome.runtime
    .sendMessage(message)
    .then(() => {
      console.log("✅ Message sent to popup successfully");
    })
    .catch((error) => {
      // Only log if it's not the common "no receiver" error
      if (!error.message.includes("Could not establish connection")) {
        console.log(
          "⚠️ Popup message failed (popup may be closed):",
          error.message
        );
      }
    });
}

// Handle messages from the WebSocket server
function handleWebSocketMessage(data) {
  // ✅ ADD PERFORMANCE OPTIMIZATION
  const startTime = performance.now();

  try {
    // Handle Socket.IO protocol messages efficiently
    if (typeof data === "string") {
      // Ping/pong optimization - minimal logging
      if (data === "2") {
        webSocket.send("3");
        if (pingCount < 2) {
          logWithTimestamp("Socket.IO ping/pong");
          pingCount++;
        }
        return;
      }

      // Quick protocol message handling
      if (data === "3probe" || data === "6" || data.startsWith("40")) {
        return;
      }

      // Socket.IO event message
      if (data.startsWith("42")) {
        const jsonStart = data.indexOf("[");
        if (jsonStart !== -1) {
          try {
            const parsed = JSON.parse(data.substring(jsonStart));
            const eventName = parsed[0];
            const eventData = parsed[1];

            // ✅ ADD ENHANCED LOGGING FOR SNIPPET EVENTS
            if (eventName === "snippet_save_response") {
              console.log("🎯 SNIPPET_SAVE_RESPONSE - FULL ANALYSIS:", {
                eventName: eventName,
                eventData: eventData,
                success: eventData?.success,
                error: eventData?.error,
                snippet: eventData?.snippet,
                message: eventData?.message,
                processingTime: performance.now() - startTime,
                timestamp: new Date().toISOString(),
              });
            }

            // Enhanced logging for collection events
            if (
              eventName === "collection_created" ||
              eventName === "collection_creation_failed"
            ) {
              logWithTimestamp(`🎯 COLLECTION EVENT RECEIVED: ${eventName}`, {
                rawMessage: data,
                eventName: eventName,
                eventData: eventData,
                hasPendingResponse: !!(
                  pendingResponses && pendingResponses["create_collection"]
                ),
                timestamp: new Date().toISOString(),
              });
            }

            // Add this enhanced logging for auth events
            if (
              eventName === "login_success" ||
              eventName === "register_success" ||
              eventName === "login_response"
            ) {
              console.log(`🚨 WEBSOCKET AUTH EVENT RECEIVED: ${eventName}`);
              console.log("📡 RAW WEBSOCKET DATA:", data);
              console.log(
                "🔍 PARSED EVENT DATA:",
                JSON.stringify(eventData, null, 2)
              );

              logWithTimestamp(`${eventName} received - Complete analysis:`, {
                rawMessage: data,
                eventName: eventName,
                fullEventData: eventData,
                hasToken: !!eventData.token,
                hasAuthToken: !!eventData.authToken,
                hasAccessToken: !!eventData.access_token,
                hasJWT: !!eventData.jwt,
                hasUser: !!eventData.user,
                hasUserData: !!eventData.userData,
                tokenPreview: eventData.token
                  ? eventData.token.substring(0, 15) + "..."
                  : "NO TOKEN FIELD",
                userEmail:
                  eventData.user?.email ||
                  eventData.userData?.email ||
                  "missing",
                allKeys: Object.keys(eventData),
                dataType: typeof eventData,
                timestamp: new Date().toISOString(),
              });
            }

            // ✅ OPTIMIZE: Use message queue for heavy operations only
            if (
              ["sync_snippets", "snippet_updated"].includes(eventName) &&
              eventData &&
              Object.keys(eventData).length > 10
            ) {
              queueMessage(eventName, eventData);
              return;
            }

            // Handle lightweight events immediately
            handleSocketEvent(eventName, eventData);

            // ✅ ADD PERFORMANCE LOGGING
            const processingTime = performance.now() - startTime;
            if (processingTime > 10) {
              // Log slow operations
              console.log(
                `⚡ SLOW MESSAGE PROCESSING: ${eventName} took ${processingTime.toFixed(
                  2
                )}ms`
              );
            }
          } catch (parseError) {
            logWithTimestamp("❌ WebSocket JSON parse error", {
              error: parseError.message,
              rawData: data.substring(0, 200) + "...",
              processingTime: performance.now() - startTime,
            });
            return;
          }
        }
        return;
      }
    }
  } catch (error) {
    logWithTimestamp("❌ WebSocket message processing failed:", {
      error: error.message,
      stack: error.stack,
      processingTime: performance.now() - startTime,
    });
  }
}

function queueMessage(eventName, eventData) {
  messageQueue.push({ eventName, eventData, timestamp: Date.now() });

  // Limit queue size
  if (messageQueue.length > 20) {
    messageQueue.shift();
  }

  processMessageQueue();
}
async function processMessageQueue() {
  if (isProcessingQueue || messageQueue.length === 0) return;

  isProcessingQueue = true;

  try {
    while (messageQueue.length > 0) {
      const message = messageQueue.shift();
      await handleSocketEvent(message.eventName, message.eventData);

      // Small delay to prevent blocking
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  } catch (error) {
    logWithTimestamp("Message queue processing failed:", error);
  } finally {
    isProcessingQueue = false;
  }
}

async function handleSocketEvent(eventName, eventData) {
  switch (eventName) {
    case "registration_success":
      logWithTimestamp("Chrome extension registered");
      break;
    case "snippet_save_response":
      console.log("🎯 SNIPPET_SAVE_RESPONSE received:", eventData);
      if (eventData.success) {
        // ✅ CORRECT VARIABLE
        showNotification(
          "Snippet Saved",
          eventData.message || "Snippet saved successfully!"
        );
        updateChangeStats();
        loadRecentSnippets();
      } else {
        showNotification(
          "Save Failed",
          eventData.error || "Failed to save snippet",
          "error"
        );
      }
      break;

    case "snippet_saved":
      handleSnippetSaved(eventData);
      break;
    case "snippet_updated":
      handleSnippetUpdated(eventData);
      break;
    case "login_success":
      handleLoginSuccess(eventData);
      break;
    case "login_response":
      console.log("🔵 RECEIVED login_response event");
      if (eventData.success === true) {
        handleLoginSuccess(eventData);
      } else {
        handleLoginFailed(eventData);
      }
      break;
    case "login_failed":
      handleLoginFailed(eventData);
      break;
    case "register_success":
      handleRegisterSuccess(eventData);
      break;
    case "register_failed":
      handleRegisterFailed(eventData);
      break;
    case "collection_created":
      handleCollectionCreated(eventData);
      break;
    case "collection_create_response":
      logWithTimestamp("✅ COLLECTION CREATE RESPONSE - Processing", {
        success: eventData.success,
        error: eventData.error,
        collectionName: eventData.collection?.name,
        hasPendingResponse: !!(
          pendingResponses && pendingResponses["create_collection"]
        ),
      });

      // Call the stored callback if it exists
      if (pendingResponses && pendingResponses["create_collection"]) {
        logWithTimestamp("📞 Calling pending response callback");

        // Clear timeout
        if (pendingResponses["create_collection"].timeout) {
          clearTimeout(pendingResponses["create_collection"].timeout);
        }

        pendingResponses["create_collection"].callback({
          success: eventData.success,
          collection: eventData.collection,
          error: eventData.error,
        });
        delete pendingResponses["create_collection"];

        logWithTimestamp("✅ Pending response resolved successfully");
      }

      // Also notify popup
      if (eventData.success) {
        notifyPopup("COLLECTION_CREATED", eventData);
        showNotification(
          "Collection Created",
          `"${eventData.collection?.name}" created successfully!`
        );
      } else {
        notifyPopup("COLLECTION_CREATION_FAILED", eventData);
      }
      break;
    case "collection_creation_failed":
      handleCollectionCreationFailed(eventData);
      break;
    case "snippet_deleted":
      handleSnippetDeleted(eventData);
      break;
    case "collection_updated":
      handleCollectionUpdated(eventData);
      break;
    case "sync_snippets":
      await handleSnippetSync(eventData);
      break;
    case "error":
      handleServerError(eventData);
      break;
    default:
      // Ignore unknown events to reduce memory usage
      break;
  }
}

// Handle registration success
function handleRegistrationSuccess(data) {
  logWithTimestamp("Registration successful:", data);
  showNotification(
    "Code Snippet Manager",
    `Chrome extension registered successfully! Welcome ${
      currentUser?.email || "User"
    }!`
  );
}

// Handle snippet saved confirmation
function handleSnippetSaved(data) {
  logWithTimestamp("Snippet saved on server:", data);

  // Update local cache
  if (data.snippet) {
    snippetCache.set(data.snippet.id, data.snippet);
    saveSnippetCache();
  }

  // Remove from pending queue
  pendingSnippets = pendingSnippets.filter((s) => s.tempId !== data.tempId);

  // Notify content script/popup
  notifySnippetUpdate("SNIPPET_SAVED", data.snippet);

  showNotification(
    "Snippet Saved",
    `"${data.snippet.title}" saved successfully!`
  );
}

// Handle snippet updated
function handleSnippetUpdated(data) {
  logWithTimestamp("Snippet updated:", data);

  if (data.snippet) {
    snippetCache.set(data.snippet.id, data.snippet);
    saveSnippetCache();
  }

  notifySnippetUpdate("SNIPPET_UPDATED", data.snippet);
}

// Handle snippet deleted
function handleSnippetDeleted(data) {
  logWithTimestamp("Snippet deleted:", data);

  if (data.snippetId) {
    snippetCache.delete(data.snippetId);
    saveSnippetCache();
  }

  notifySnippetUpdate("SNIPPET_DELETED", { id: data.snippetId });
}

// Handle collection updated
function handleCollectionUpdated(data) {
  logWithTimestamp("Collection updated:", data);

  if (data.collections) {
    collections = data.collections;
    saveCollections();
  }

  notifySnippetUpdate("COLLECTIONS_UPDATED", data.collections);
}

// Handle snippet sync
async function handleSnippetSync(data) {
  logWithTimestamp("Syncing snippets");

  if (data.snippets && Array.isArray(data.snippets)) {
    // Clear cache first to free memory
    snippetCache.clear();

    // Add snippets in batches to prevent memory spikes
    const batchSize = 50;
    for (let i = 0; i < data.snippets.length; i += batchSize) {
      const batch = data.snippets.slice(i, i + batchSize);
      batch.forEach((snippet) => {
        if (snippet && snippet.id) {
          snippetCache.set(snippet.id, snippet);
        }
      });

      // Small delay between batches
      if (i + batchSize < data.snippets.length) {
        await new Promise((resolve) => setTimeout(resolve, 5));
      }
    }

    // Save cache asynchronously
    setTimeout(() => saveSnippetCache(), 100);
  }

  if (data.collections) {
    collections = Array.isArray(data.collections) ? data.collections : [];
    setTimeout(() => saveCollections(), 150);
  }

  notifySnippetUpdate("SNIPPETS_SYNCED", {
    snippets: data.snippets?.length || 0,
    collections: collections.length,
  });
}
// Handle server errors
function handleServerError(data) {
  logWithTimestamp("Server error:", data);
  showNotification(
    "Error",
    data.message || "An error occurred on the server",
    "basic"
  );
}

// Save snippet to server or offline queue
async function saveSnippet(snippetData) {
  const snippet = {
    tempId: Date.now() + Math.random(), // Temporary ID for tracking
    title: snippetData.title,
    code: snippetData.code,
    language: snippetData.language,
    sourceUrl: snippetData.sourceUrl,
    tags: snippetData.tags || [],
    collectionId: snippetData.collectionId || null,
    createdAt: new Date().toISOString(),
    userId: currentUser?.id,
  };

  logWithTimestamp("Saving snippet:", {
    title: snippet.title,
    language: snippet.language,
  });

  if (isConnected && isAuthenticated) {
    // Send to server immediately
    try {
      const message = JSON.stringify([
        "save_snippet",
        {
          snippet: snippet,
          token: authToken,
        },
      ]);
      webSocket.send("42" + message);

      // Add to pending queue
      pendingSnippets.push(snippet);

      logWithTimestamp("Snippet sent to server");
      return { success: true, queued: false };
    } catch (error) {
      logWithTimestamp("Failed to send snippet to server:", error);
      // Fall back to offline queue
      return await queueSnippetOffline(snippet);
    }
  } else {
    // Queue offline
    return await queueSnippetOffline(snippet);
  }
}

// Queue snippet for offline processing
async function queueSnippetOffline(snippet) {
  try {
    offlineQueue.push(snippet);
    await saveOfflineQueue();

    logWithTimestamp("Snippet queued offline:", snippet.title);
    showNotification(
      "Snippet Queued",
      `"${snippet.title}" saved offline. Will sync when connected.`
    );

    return { success: true, queued: true };
  } catch (error) {
    logWithTimestamp("Failed to queue snippet offline:", error);
    return { success: false, error: error.message };
  }
}

// Process offline queue when connection is restored
async function processOfflineQueue() {
  if (offlineQueue.length === 0) return;

  logWithTimestamp(`Processing ${offlineQueue.length} offline snippets`);

  const processed = [];

  for (const snippet of offlineQueue) {
    try {
      const message = JSON.stringify([
        "save_snippet",
        {
          snippet: snippet,
          token: authToken,
        },
      ]);
      webSocket.send("42" + message);
      processed.push(snippet);

      // Small delay between sends
      await new Promise((resolve) => setTimeout(resolve, 100));
    } catch (error) {
      logWithTimestamp("Failed to process offline snippet:", error);
      break; // Stop processing on first error
    }
  }

  // Remove processed snippets from queue
  offlineQueue = offlineQueue.filter((s) => !processed.includes(s));
  await saveOfflineQueue();

  if (processed.length > 0) {
    showNotification(
      "Snippets Synced",
      `${processed.length} offline snippets synced successfully!`
    );
  }
}
// Add this function near your other cleanup functions
// Replace the existing cleanupPendingResponses function:
function cleanupPendingResponses() {
  const now = Date.now();
  const timeout = 30000; // 30 seconds

  if (pendingResponses) {
    Object.keys(pendingResponses).forEach((key) => {
      const response = pendingResponses[key];
      const timestamp = response.timestamp || 0;
      if (now - timestamp > timeout) {
        // Call with error if it's been too long
        try {
          if (typeof response.callback === "function") {
            response.callback({
              success: false,
              error: "Request timed out",
            });
          } else if (typeof response === "function") {
            response({
              success: false,
              error: "Request timed out",
            });
          }
        } catch (e) {
          // Ignore errors from calling the callback
        }
        delete pendingResponses[key];
      }
    });
  }
}

// Search snippets in cache
function searchSnippets(query, filters = {}) {
  const results = [];
  const searchLower = query.toLowerCase();

  for (const [id, snippet] of snippetCache) {
    let matches = false;

    // Search in title, code, and tags
    if (
      snippet.title.toLowerCase().includes(searchLower) ||
      snippet.code.toLowerCase().includes(searchLower) ||
      snippet.tags.some((tag) => tag.toLowerCase().includes(searchLower))
    ) {
      matches = true;
    }

    // Apply filters
    if (matches) {
      if (filters.language && snippet.language !== filters.language) {
        matches = false;
      }
      if (
        filters.collectionId &&
        snippet.collectionId !== filters.collectionId
      ) {
        matches = false;
      }
      if (
        filters.tags &&
        !filters.tags.every((tag) => snippet.tags.includes(tag))
      ) {
        matches = false;
      }
    }

    if (matches) {
      results.push(snippet);
    }
  }

  return results.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
}

// Storage management functions
async function saveOfflineQueue() {
  try {
    await chrome.storage.local.set({
      [STORAGE_KEYS.OFFLINE_QUEUE]: offlineQueue,
    });
  } catch (error) {
    logWithTimestamp("Failed to save offline queue:", error);
  }
}

async function saveSnippetCache() {
  try {
    const cacheObject = Object.fromEntries(snippetCache);
    await chrome.storage.local.set({
      [STORAGE_KEYS.SNIPPET_CACHE]: cacheObject,
    });
  } catch (error) {
    logWithTimestamp("Failed to save snippet cache:", error);
  }
}

async function saveCollections() {
  try {
    await chrome.storage.local.set({ [STORAGE_KEYS.COLLECTIONS]: collections });
  } catch (error) {
    logWithTimestamp("Failed to save collections:", error);
  }
}

// Notify other parts of extension about snippet updates

let notificationQueue = new Map();
let notificationTimer = null;

// Replace the existing notifySnippetUpdate function with this enhanced version:
function notifySnippetUpdate(type, data) {
  // Throttle notifications to prevent spam
  notificationQueue.set(type, { data, timestamp: Date.now() });

  if (!notificationTimer) {
    notificationTimer = setTimeout(() => {
      for (const [notificationType, notification] of notificationQueue) {
        const message = {
          type: notificationType,
          data: notification.data,
          timestamp: new Date().toISOString(),
        };

        // Notify popup (ignore failures)
        chrome.runtime.sendMessage(message).catch(() => {});

        // Notify DevTools panel
        if (devToolsPort) {
          devToolsPort.postMessage(message);
        }
      }

      notificationQueue.clear();
      notificationTimer = null;
    }, 100); // Batch notifications every 100ms
  }
}

// Forward VS Code status to DevTools panel
function forwardVsCodeStatus(message) {
  if (devToolsPort) {
    devToolsPort.postMessage({
      type: "VS_CODE_STATUS",
      status: message.status,
      details: message.details,
    });
  }
}

// Test server connection
function testServerConnection(url) {
  logWithTimestamp("Testing connection to:", url);

  fetch(url + "/api/status", {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(
          `Server returned ${response.status} ${response.statusText}`
        );
      }
      return response.json();
    })
    .then((data) => {
      logWithTimestamp("Server connection successful:", data);

      // Update server URL if connection was successful
      serverUrl = url;
      chrome.storage.local.set({ [STORAGE_KEYS.SERVER_URL]: url });

      // Connect to WebSocket
      connectToWebSocket();

      // Notify DevTools panel if connected
      if (devToolsPort) {
        devToolsPort.postMessage({
          type: "CONNECTION_TEST",
          success: true,
          details: data,
        });
      }
    })
    .catch((error) => {
      logWithTimestamp("Server connection failed:", error);

      if (devToolsPort) {
        devToolsPort.postMessage({
          type: "CONNECTION_TEST",
          success: false,
          error: error.message,
        });
      }
    });
}

// Add missing functions that are called but don't exist
function updateChangeStats() {
  try {
    // Update snippet statistics
    const stats = {
      totalSnippets: snippetCache.size,
      collections: collections.length,
      offlineQueue: offlineQueue.length,
      lastUpdated: new Date().toISOString()
    };
    
    console.log("📊 STATS UPDATED:", stats);
    
    // Notify popup if it's listening
    notifyPopup("STATS_UPDATED", stats);
    
    // Save stats to storage for persistence
    chrome.storage.local.set({ snippetStats: stats }).catch(error => {
      console.error("❌ Failed to save stats:", error);
    });
    
  } catch (error) {
    console.error("❌ updateChangeStats failed:", error);
  }
}

function loadRecentSnippets() {
  try {
    const recentSnippets = Array.from(snippetCache.values())
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
      .slice(0, 10);
    
    console.log("📚 RECENT SNIPPETS LOADED:", {
      count: recentSnippets.length,
      snippets: recentSnippets.map(s => ({ id: s.id, title: s.title }))
    });
    
    // Notify popup with recent snippets
    notifyPopup("RECENT_SNIPPETS_LOADED", { snippets: recentSnippets });
    
  } catch (error) {
    console.error("❌ loadRecentSnippets failed:", error);
  }
}

// Listen for messages from popup, content scripts, and other parts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  logWithTimestamp("Message received in background:", message);

  switch (message.action || message.type) {
    // Connection management
    case "connect":
      // Update server URL if provided
      if (message.serverUrl) {
        serverUrl = message.serverUrl;
        chrome.storage.local.set({ [STORAGE_KEYS.SERVER_URL]: serverUrl });
      }

      // Reset reconnect attempts for fresh connection
      reconnectAttempts = 0;

      // Connect to WebSocket
      connectToWebSocket();
      sendResponse({ success: true });
      return true;

    // Add this case to your chrome.runtime.onMessage.addListener
    case "testAuthEndpoint":
      testAuthEndpoint().then((result) => {
        sendResponse(result);
      });
      return true; // Keep message channel open for async response

    // Add this case in the switch statement:
    case "checkAuth":
      checkAuthStatus()
        .then((authStatus) => {
          sendResponse({
            success: true,
            isAuthenticated: authStatus.isAuthenticated,
            user: authStatus.user,
            token: authStatus.token,
          });
        })
        .catch((error) => {
          sendResponse({
            success: false,
            error: error.message,
          });
        });
      return true; // Async response

    case "refreshAuth":
      verifyStoredAuthentication()
        .then((verified) => {
          sendResponse({
            success: true,
            isAuthenticated: verified,
            user: currentUser,
            token: authToken,
          });
        })
        .catch((error) => {
          sendResponse({
            success: false,
            error: error.message,
          });
        });
      return true; // Async response

    case "verifyAuth":
      console.log("🔵 Verifying auth token for:", message.email); // ✅ FIXED: changed request to message

      if (!message.token || !message.email) {
        // ✅ FIXED: changed request to message
        sendResponse({
          success: false,
          valid: false,
          error: "Missing token or email",
        });
        return;
      }

      // Make API call to verify token
      fetch(`${serverUrl}/api/auth/verify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${message.token}`, // ✅ FIXED: changed request to message
        },
        body: JSON.stringify({
          email: message.email, // ✅ FIXED: changed request to message
          token: message.token, // ✅ FIXED: changed request to message
        }),
      })
        .then((response) => {
          if (response.status === 404) {
            console.log(
              "🔴 Auth verification endpoint not found - assuming valid for now"
            );
            sendResponse({
              success: true,
              valid: true,
              message: "Endpoint not available, maintaining session",
            });
            return;
          }
          return response.json();
        })
        .then((data) => {
          if (data) {
            console.log("🔵 Auth verification response:", data);
            sendResponse({
              success: true,
              valid: data.valid || data.success || false,
              user: data.user,
            });
          }
        })
        .catch((error) => {
          console.error("🔴 Auth verification error:", error);
          // Don't fail auth on network errors - keep user logged in
          sendResponse({
            success: true,
            valid: true,
            message: "Network error, maintaining session",
          });
        });

      return true; // Keep message channel open for async response

    case "disconnect":
      handleDisconnect(true); // Intentional disconnect
      reconnectAttempts = maxReconnectAttempts; // Prevent auto-reconnect
      sendResponse({ success: true });
      break;
    case "getStatus":
      sendResponse({
        connected: isConnected,
        authenticated: isAuthenticated,
        user: currentUser,
        reconnectAttempts: reconnectAttempts,
        maxReconnectAttempts: maxReconnectAttempts,
        offlineQueueSize: offlineQueue.length,
        cacheSize: snippetCache.size,
      });
      break;

    // Authentication (from auth-content-script.js)
    case "AUTH_SUCCESS":
      authToken = message.token;
      currentUser = message.user;
      isAuthenticated = true;

      logWithTimestamp("User authenticated:", currentUser.email);

      // Save to storage
      chrome.storage.local.set({
        [STORAGE_KEYS.AUTH_TOKEN]: authToken,
        [STORAGE_KEYS.CURRENT_USER]: currentUser,
      });

      // Reconnect WebSocket with auth
      if (isConnected) {
        const registerMsg = JSON.stringify([
          "register_client",
          {
            clientType: "chrome",
            userId: currentUser.id,
            token: authToken,
          },
        ]);
        webSocket.send("42" + registerMsg);
      }

      // Process offline queue
      processOfflineQueue();

      sendResponse({ success: true });
      break;

    case "LOGOUT":
      authToken = null;
      currentUser = null;
      isAuthenticated = false;

      // Clear storage
      chrome.storage.local.remove([
        STORAGE_KEYS.AUTH_TOKEN,
        STORAGE_KEYS.CURRENT_USER,
        STORAGE_KEYS.SNIPPET_CACHE,
        STORAGE_KEYS.COLLECTIONS,
      ]);

      // Clear cache
      snippetCache.clear();
      collections = [];

      logWithTimestamp("User logged out");
      sendResponse({ success: true });
      break;

    case "SAVE_SNIPPET":
      console.log("🔍 SAVE_SNIPPET DEBUG - FULL ANALYSIS:", {
        messageReceived: !!message,
        hasSnippet: !!message.snippet,
        snippetKeys: message.snippet ? Object.keys(message.snippet) : [],
        snippetData: message.snippet,
        hasCode: !!message.snippet?.code,
        codeLength: message.snippet?.code?.length,
        codePreview: message.snippet?.code
          ? message.snippet.code.substring(0, 100) + "..."
          : "NO CODE",
        hasTitle: !!message.snippet?.title,
        title: message.snippet?.title,
        hasLanguage: !!message.snippet?.language,
        language: message.snippet?.language,
        collectionId: message.snippet?.collection_id,
        sourceUrl: message.snippet?.source_url,
        tags: message.snippet?.tags,
        connectionState: {
          isConnected: isConnected,
          isAuthenticated: isAuthenticated,
          hasToken: !!authToken,
          hasCurrentUser: !!currentUser,
          webSocketState: webSocket?.readyState,
          webSocketStateText: getWebSocketStateText(webSocket?.readyState),
        },
        timestamp: new Date().toISOString(),
      });

      // Validate snippet data first
      if (!message.snippet) {
        console.error("❌ SAVE_SNIPPET - No snippet data provided");
        sendResponse({ success: false, error: "No snippet data provided" });
        return true;
      }

      if (!message.snippet.code || !message.snippet.title) {
        console.error("❌ SAVE_SNIPPET - Missing required fields:", {
          hasCode: !!message.snippet.code,
          hasTitle: !!message.snippet.title,
          providedFields: Object.keys(message.snippet),
        });
        sendResponse({
          success: false,
          error: "Missing required fields: code and title are required",
        });
        return true;
      }

      if (isConnected && isAuthenticated && authToken) {
        try {
          const snippetData = {
            code: message.snippet.code,
            language: message.snippet.language || "text",
            title: message.snippet.title,
            source_url: message.snippet.source_url || window.location?.href,
            tags: Array.isArray(message.snippet.tags)
              ? message.snippet.tags
              : [],
            collection_id: message.snippet.collection_id || null,
            userId: currentUser?.id,
            token: authToken,
          };

          console.log("🚀 SENDING SNIPPET TO SERVER:", {
            snippetData: snippetData,
            dataSize: JSON.stringify(snippetData).length,
            webSocketReady: webSocket?.readyState === 1,
            timestamp: new Date().toISOString(),
          });

          const saveMsg = JSON.stringify(["save_snippet", snippetData]);
          webSocket.send("42" + saveMsg);

          console.log("✅ SNIPPET WEBSOCKET MESSAGE SENT SUCCESSFULLY");
          logWithTimestamp("Snippet save request sent to server", {
            title: snippetData.title,
            language: snippetData.language,
            codeLength: snippetData.code.length,
          });

          sendResponse({ success: true, pending: true });
        } catch (error) {
          console.error("❌ SNIPPET SEND ERROR - FULL DETAILS:", {
            error: error.message,
            stack: error.stack,
            errorType: error.constructor.name,
            webSocketState: webSocket?.readyState,
            timestamp: new Date().toISOString(),
          });

          logWithTimestamp("Failed to send snippet to server:", error);
          sendResponse({ success: false, error: error.message });
        }
      } else {
        const connectionIssues = {
          notConnected: !isConnected,
          notAuthenticated: !isAuthenticated,
          noToken: !authToken,
          noUser: !currentUser,
        };

        const errorMsg = !isConnected
          ? "Not connected to server"
          : !isAuthenticated
          ? "Not authenticated"
          : "Missing authentication data";

        console.error("❌ SNIPPET SAVE FAILED - CONNECTION ISSUES:", {
          errorMsg: errorMsg,
          issues: connectionIssues,
          serverUrl: serverUrl,
          timestamp: new Date().toISOString(),
        });

        sendResponse({ success: false, error: errorMsg });
      }
      return true;

    case "SEARCH_SNIPPETS":
      const results = searchSnippets(message.query, message.filters);
      sendResponse({ success: true, results });
      break;

    case "GET_SNIPPETS":
      const snippets = Array.from(snippetCache.values());
      sendResponse({
        success: true,
        snippets: snippets.sort(
          (a, b) => new Date(b.createdAt) - new Date(a.createdAt)
        ),
      });
      break;

    case "getCollections":
      // Fetch collections from server if connected and authenticated
      if (isConnected && isAuthenticated && authToken) {
        try {
          fetch(`${serverUrl}/api/collections/`, {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${authToken}`,
            },
          })
            .then((response) => response.json())
            .then((data) => {
              if (data.success && data.collections) {
                collections = data.collections;
                // Save to storage
                chrome.storage.local.set({
                  [STORAGE_KEYS.COLLECTIONS]: collections,
                });
                sendResponse({ success: true, collections: collections });
              } else {
                sendResponse({ success: true, collections: [] });
              }
            })
            .catch((error) => {
              console.error("Error fetching collections:", error);
              sendResponse({ success: true, collections: [] });
            });
        } catch (error) {
          sendResponse({ success: true, collections: [] });
        }
      } else {
        // Return cached collections if not connected
        sendResponse({ success: true, collections: collections || [] });
      }
      return true; // Async response

    case "DELETE_SNIPPET":
      if (isConnected && isAuthenticated) {
        const deleteMsg = JSON.stringify([
          "delete_snippet",
          {
            snippetId: message.snippetId,
            token: authToken,
          },
        ]);
        webSocket.send("42" + deleteMsg);
      }
      sendResponse({ success: true });
      break;
    // Add these cases in the switch statement around line 650:

    case "getStats":
      sendResponse({
        success: true,
        stats: {
          totalSnippets: snippetCache.size,
          collections: collections.length,
          offlineQueue: offlineQueue.length,
          pendingSnippets: pendingSnippets.length,
        },
      });
      break;

    case "getRecentSnippets":
      const recentSnippets = Array.from(snippetCache.values())
        .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
        .slice(0, 10);
      sendResponse({ success: true, snippets: recentSnippets });
      break;

    case "syncSnippets":
      if (isConnected && isAuthenticated) {
        try {
          const syncMsg = JSON.stringify([
            "sync_request",
            {
              userId: currentUser?.id,
              token: authToken,
            },
          ]);
          webSocket.send("42" + syncMsg);

          // Process offline queue
          processOfflineQueue();

          logWithTimestamp("Manual sync requested");
          sendResponse({ success: true });
        } catch (error) {
          logWithTimestamp("Manual sync failed:", error);
          sendResponse({ success: false, error: error.message });
        }
      } else {
        const errorMsg = !isConnected
          ? "Not connected to server"
          : "Not authenticated";
        logWithTimestamp("Sync failed:", errorMsg);
        sendResponse({ success: false, error: errorMsg });
      }
      break;
    case "logError":
      logWithTimestamp(`Error from ${message.source}:`, {
        error: message.error,
        timestamp: message.timestamp,
        stack: message.stack,
      });
      sendResponse({ success: true });
      break;
    // Replace the existing "createCollection" case in your switch statement
    case "createCollection":
      if (!message.name || !message.name.trim()) {
        sendResponse({
          success: false,
          error: "Collection name is required plz fill it",
        });
        return false;
      }

      createCollection(message.name.trim(), sendResponse);
      return true; // Keep message channel open for async response

    case "searchSnippets":
      try {
        const searchResults = searchSnippets(message.query, message.filters);
        logWithTimestamp(
          `Search completed: ${searchResults.length} results for "${message.query}"`
        );
        sendResponse({ success: true, snippets: searchResults });
      } catch (error) {
        logWithTimestamp("Search failed:", error);
        sendResponse({ success: false, error: error.message });
      }
      break;

    case "login":
      if (isConnected) {
        try {
          // Clear any existing auth timeout
          clearAuthTimeout();

          const loginData = {
            email: message.email,
            password: message.password,
          };

          // Verify message format before sending
          const loginMsg = JSON.stringify(["login", loginData]);

          console.log("🔵 SENDING LOGIN DATA TO SERVER:", {
            email: message.email,
            passwordLength: message.password?.length || 0,
            messageFormat: "Socket.IO format: 42 + JSON",
            socketState: webSocket.readyState === 1 ? "OPEN" : "NOT_OPEN",
            timestamp: new Date().toISOString(),
          });

          // Send with Socket.IO format
          webSocket.send("42" + loginMsg);
          console.log("✅ LOGIN DATA SENT SUCCESSFULLY to Flask server");

          // Store pending auth with timeout
          pendingAuth = {
            email: message.email,
            type: "login",
            timestamp: Date.now(),
          };

          // Start timeout
          startAuthTimeout("login", message.email);

          logWithTimestamp("Login attempt for:", message.email);
          sendResponse({ success: true, pending: true });
        } catch (error) {
          console.log("❌ FAILED TO SEND LOGIN DATA:", error);
          clearAuthTimeout();
          pendingAuth = null;
          sendResponse({ success: false, error: error.message });
        }
      } else {
        console.log("❌ LOGIN FAILED: WebSocket not connected");
        sendResponse({ success: false, error: "Not connected to server" });
      }
      return true;

    case "getAuthState":
      // Immediate auth state check
      checkAuthStatus()
        .then((authStatus) => {
          console.log("🔍 Auth state requested:", authStatus);
          sendResponse({
            success: true,
            isAuthenticated: authStatus.isAuthenticated,
            user: authStatus.user,
            token: authStatus.token,
            hasStoredAuth: authStatus.hasStoredAuth,
          });
        })
        .catch((error) => {
          console.error("❌ Auth state check failed:", error);
          sendResponse({
            success: false,
            error: error.message,
            isAuthenticated: false,
          });
        });
      return true; // Async response
    case "register":
      if (isConnected) {
        try {
          // Clear any existing auth timeout
          clearAuthTimeout();

          const registerData = {
            email: message.email,
            password: message.password,
          };

          // Verify message format before sending
          const registerMsg = JSON.stringify(["register", registerData]);

          console.log("🔵 SENDING REGISTER DATA TO SERVER:", {
            email: message.email,
            passwordLength: message.password?.length || 0,
            messageFormat: "Socket.IO format: 42 + JSON",
            socketState: webSocket.readyState === 1 ? "OPEN" : "NOT_OPEN",
            timestamp: new Date().toISOString(),
          });

          // Send with Socket.IO format
          webSocket.send("42" + registerMsg);
          console.log("✅ REGISTER DATA SENT SUCCESSFULLY to Flask server");

          // Store pending auth with timeout
          pendingAuth = {
            email: message.email,
            type: "register",
            timestamp: Date.now(),
          };

          // Start timeout
          startAuthTimeout("register", message.email);

          logWithTimestamp("Registration attempt for:", message.email);
          sendResponse({ success: true, pending: true });
        } catch (error) {
          console.log("❌ FAILED TO SEND REGISTER DATA:", error);
          clearAuthTimeout();
          pendingAuth = null;
          sendResponse({ success: false, error: error.message });
        }
      } else {
        console.log("❌ REGISTER FAILED: WebSocket not connected");
        sendResponse({ success: false, error: "Not connected to server" });
      }
      return true;
    default:
      logWithTimestamp("Unknown action:", message.action || message.type);
      sendResponse({ success: false, error: "Unknown action" });
  }
});

// Listen for DevTools panel connections
chrome.runtime.onConnect.addListener((port) => {
  if (port.name === "devtools") {
    devToolsPort = port;

    port.onDisconnect.addListener(() => {
      devToolsPort = null;
    });

    // Send current status to DevTools
    port.postMessage({
      type: "INIT_STATUS",
      status: {
        connected: isConnected,
        authenticated: isAuthenticated,
        user: currentUser,
        offlineQueueSize: offlineQueue.length,
        cacheSize: snippetCache.size,
        serverUrl: serverUrl,
      },
    });
  }
});
// Service worker keep-alive and auth persistence
chrome.runtime.onStartup.addListener(async () => {
  logWithTimestamp("Service worker restarted - checking auth persistence");
  await verifyStoredAuthentication();
});

// Initialize extension on install/update
chrome.runtime.onInstalled.addListener((details) => {
  logWithTimestamp("Extension installed or updated:", details.reason);
  // Don't initialize again if already initialized
  if (!isConnected) {
    initializeExtension();
  }
});

// Initialize immediately only if not already done
// Initialize extension without auto-connecting
initializeExtension();
// 10. ADD CLEANUP ON EXTENSION SHUTDOWN - Add this at the very end of your file:
// Cleanup on extension shutdown/suspend
// Enhanced cleanup on extension shutdown/suspend
chrome.runtime.onSuspend.addListener(async () => {
  logWithTimestamp("Service worker suspending - ensuring auth is saved");

  if (isAuthenticated && authToken && currentUser) {
    await chrome.storage.local.set({
      [STORAGE_KEYS.AUTH_TOKEN]: authToken,
      [STORAGE_KEYS.CURRENT_USER]: currentUser,
    });
  }

  // Stop keep-alive
  stopKeepAlive();

  // Clear all timers
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  if (notificationTimer) {
    clearTimeout(notificationTimer);
    notificationTimer = null;
  }

  if (cleanupTimer) {
    clearInterval(cleanupTimer);
    cleanupTimer = null;
  }

  // Close WebSocket cleanly
  if (webSocket && webSocket.readyState === WebSocket.OPEN) {
    webSocket.close(1000, "Extension suspending");
  }

  // Clear caches to free memory
  snippetCache.clear();
  messageQueue.length = 0;
  logQueue.length = 0;
  notificationQueue.clear();

  performMemoryCleanup();
});

// Also handle when extension context becomes invalid
chrome.runtime.onConnect.addListener((port) => {
  if (port.name === "devtools") {
    devToolsPort = port;

    port.onDisconnect.addListener(() => {
      devToolsPort = null;
      // Don't disconnect WebSocket when DevTools closes
    });

    // Send enhanced status to DevTools
    port.postMessage({
      type: "INIT_STATUS",
      status: {
        connected: isConnected,
        authenticated: isAuthenticated,
        user: currentUser,
        offlineQueueSize: offlineQueue.length,
        cacheSize: snippetCache.size,
        serverUrl: serverUrl,
        keepAliveActive: !!keepAliveTimer,
        lastActivity: lastActivity,
      },
    });
  }
});

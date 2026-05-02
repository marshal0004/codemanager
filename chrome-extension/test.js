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
const AUTH_TIMEOUT_DURATION = 15000; // 15 seconds
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


  
async function createCollection(name, sendResponse) {
  // First verify current authentication
  if (!isAuthenticated || !authToken || !currentUser) {
    logWithTimestamp("Create collection failed: Not authenticated locally");
    sendResponse({ success: false, error: "Not authenticated" });
    return false;
  }

  // Verify with server if connected
  if (isConnected) {
    try {
      // Double-check auth with server before creating collection
      const authCheck = await fetch(`${serverUrl}/api/auth/verify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ email: currentUser.email }),
      });

      if (!authCheck.ok) {
        await clearAuthData();
        sendResponse({
          success: false,
          error: "Authentication expired. Please login again.",
        });
        return false;
      }

      const authData = await authCheck.json();
      if (!authData.valid) {
        await clearAuthData();
        sendResponse({
          success: false,
          error: "Authentication expired. Please login again.",
        });
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
      webSocket.send("42" + createMsg);
      logWithTimestamp("Collection creation requested:", name);

      // Store the sendResponse callback
      pendingResponses = pendingResponses || {};
      pendingResponses["create_collection"] = {
        callback: sendResponse,
        timestamp: Date.now(),
      };

      return true;
    } catch (error) {
      logWithTimestamp("Failed to create collection:", error);
      sendResponse({ success: false, error: error.message });
      return false;
    }
  } else {
    sendResponse({ success: false, error: "Not connected to server" });
    return false;
  }
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
    } else {
      logWithTimestamp("No valid authentication found");
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

      notifyPopup("LOGIN_SUCCESS", { user: currentUser, token: authToken });
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
  logWithTimestamp("Collection created:", data);

  if (data.collections) {
    collections = data.collections;
    saveCollections();
  }

  // Notify popup
  notifyPopup("COLLECTION_CREATED", data);

  // Call the stored callback if it exists
  if (pendingResponses && pendingResponses["create_collection"]) {
    pendingResponses["create_collection"].callback({
      success: true,
      collection: data.collection,
    });
    delete pendingResponses["create_collection"];
  }

  showNotification(
    "Collection Created",
    `"${data.collection?.name}" created successfully!`
  );
}

function handleCollectionCreationFailed(data) {
  logWithTimestamp("Collection creation failed:", data);

  // Call the stored callback if it exists
  if (pendingResponses && pendingResponses["create_collection"]) {
    pendingResponses["create_collection"].callback({
      success: false,
      error: data.message || "Failed to create collection",
    });
    delete pendingResponses["create_collection"];
  }

  notifyPopup("COLLECTION_CREATION_FAILED", {
    error: data.message || "Failed to create collection",
  });
}

// Helper function to notify popup
function notifyPopup(type, data) {
  chrome.runtime
    .sendMessage({
      type: type,
      data: data,
    })
    .catch(() => {
      // Ignore errors if popup is not open
      logWithTimestamp("Popup not open, message not delivered:", type);
    });
}

// Handle messages from the WebSocket server
function handleWebSocketMessage(data) {
  try {
    // Handle Socket.IO protocol messages efficiently
    if (typeof data === "string") {
      // Ping/pong optimization - minimal logging
      if (data === "2") {
        webSocket.send("3");
        if (pingCount < 2) {
          // Reduced from 3 to 2
          logWithTimestamp("Socket.IO ping/pong");
          pingCount++;
        }
        return;
      }

      // Quick protocol message handling
      if (data === "3probe" || data === "6" || data.startsWith("40")) {
        return; // Skip processing for protocol messages
      }

      // Socket.IO event message
      if (data.startsWith("42")) {
        const jsonStart = data.indexOf("[");
        if (jsonStart !== -1) {
          try {
            const parsed = JSON.parse(data.substring(jsonStart));
            const eventName = parsed[0];
            const eventData = parsed[1];
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

            // Use message queue for heavy operations
            if (
              ["sync_snippets", "snippet_saved", "snippet_updated"].includes(
                eventName
              )
            ) {
              queueMessage(eventName, eventData);
              return;
            }

            // Handle lightweight events immediately
            handleSocketEvent(eventName, eventData);
          } catch (parseError) {
            // Silently ignore parse errors to reduce memory pressure
            return;
          }
        }
        return;
      }
    }
  } catch (error) {
    logWithTimestamp("WebSocket message processing failed:", error);
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
      console.log("🔵 Verifying auth token for user:", request.email);
      // Make a request to your Flask server to verify the token
      fetch(`${serverUrl}/api/auth/verify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${request.token}`,
        },
        body: JSON.stringify({ email: request.email }),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log("🔵 Server auth verification:", data);
          sendResponse({ success: true, valid: data.valid });
        })
        .catch((error) => {
          console.error("🔴 Auth verification failed:", error);
          sendResponse({ success: false, valid: false, error: error.message });
        });
      return true; // Keep the message channel open for async response

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

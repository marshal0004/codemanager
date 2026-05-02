// auth-content-script.js
// Complete authentication handler for Code Snippet Manager Chrome Extension
// Handles token capture, authentication sync, and WebSocket communication setup

(function () {
  "use strict";

  console.log("🔵 [AUTH-CONTENT] Script loaded successfully");
  console.log("🔵 [AUTH-CONTENT] URL:", window.location.href);
  console.log("🔵 [AUTH-CONTENT] Timestamp:", new Date().toISOString());

  // Configuration
  const CONFIG = {
    AUTH_ENDPOINTS: [
      "/auth/login",
      "/auth/register",
      "/api/login",
      "/api/register",
    ],
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY: 1000,
    HEARTBEAT_INTERVAL: 30000,
    DEBUG_MODE: true,
  };

  // State management
  let interceptorActive = false;
  let authState = {
    isAuthenticated: false,
    token: null,
    user: null,
    lastSync: null,
  };

  // Enhanced logging function
  function log(level, message, data = null) {
    const timestamp = new Date().toISOString();
    const prefix = `🔵 [AUTH-CONTENT-${level.toUpperCase()}]`;

    if (data) {
      console[level.toLowerCase()](`${prefix} ${message}`, data);
    } else {
      console[level.toLowerCase()](`${prefix} ${message}`);
    }

    // Send logs to background script for centralized logging
    try {
      chrome.runtime
        .sendMessage({
          action: "logMessage",
          level: level,
          message: message,
          data: data,
          source: "auth-content-script",
          timestamp: timestamp,
          url: window.location.href,
        })
        .catch(() => {}); // Ignore if background is not available
    } catch (e) {
      // Silent fail for logging
    }
  }

  // Error handler with retry mechanism
  function handleError(error, context, retryFunction = null, retryCount = 0) {
    log("error", `Error in ${context}:`, {
      error: error.message || error,
      stack: error.stack,
      retryCount: retryCount,
      canRetry: retryFunction && retryCount < CONFIG.RETRY_ATTEMPTS,
    });

    if (retryFunction && retryCount < CONFIG.RETRY_ATTEMPTS) {
      setTimeout(() => {
        log("info", `Retrying ${context} (attempt ${retryCount + 1})`);
        retryFunction(retryCount + 1);
      }, CONFIG.RETRY_DELAY * (retryCount + 1));
    }
  }

  // Check if URL contains auth endpoints
  function isAuthEndpoint(url) {
    return CONFIG.AUTH_ENDPOINTS.some((endpoint) => url.includes(endpoint));
  }

  // Validate authentication response
  function validateAuthResponse(data) {
    if (!data) {
      log("warn", "Auth response is null or undefined");
      return false;
    }

    if (typeof data !== "object") {
      log("warn", "Auth response is not an object", { type: typeof data });
      return false;
    }

    const hasSuccess = data.hasOwnProperty("success") && data.success === true;
    const hasToken =
      data.hasOwnProperty("token") &&
      typeof data.token === "string" &&
      data.token.length > 0;

    log("info", "Auth response validation:", {
      hasSuccess: hasSuccess,
      hasToken: hasToken,
      tokenLength: data.token ? data.token.length : 0,
      hasUser: !!data.user,
    });

    return hasSuccess && hasToken;
  }

  // Store authentication data securely
  function storeAuthData(token, user, retryCount = 0) {
    try {
      log("info", "Storing authentication data", {
        tokenLength: token ? token.length : 0,
        userEmail: user ? user.email : "N/A",
        retryCount: retryCount,
      });

      chrome.storage.local.set(
        {
          authToken: token,
          currentUser: user,
          userEmail: user ? user.email : null,
          authTimestamp: Date.now(),
          lastAuthSource: "content-script",
        },
        function () {
          if (chrome.runtime.lastError) {
            handleError(
              new Error(chrome.runtime.lastError.message),
              "storeAuthData",
              () => storeAuthData(token, user, retryCount),
              retryCount
            );
            return;
          }

          log("info", "Authentication data stored successfully");
          authState.isAuthenticated = true;
          authState.token = token;
          authState.user = user;
          authState.lastSync = Date.now();

          // Notify background script about successful authentication
          notifyBackgroundAuth(token, user);

          // Notify popup about auth success
          notifyPopupAuth(token, user);
        }
      );
    } catch (error) {
      handleError(
        error,
        "storeAuthData",
        () => storeAuthData(token, user, retryCount),
        retryCount
      );
    }
  }

  // Notify background script about authentication
  function notifyBackgroundAuth(token, user, retryCount = 0) {
    try {
      const message = {
        type: "AUTH_SUCCESS",
        action: "authenticationComplete",
        token: token,
        user: user,
        timestamp: Date.now(),
        source: window.location.href,
      };

      log("info", "Notifying background script about authentication", {
        tokenLength: token.length,
        userEmail: user ? user.email : "N/A",
      });

      chrome.runtime.sendMessage(message, function (response) {
        if (chrome.runtime.lastError) {
          handleError(
            new Error(chrome.runtime.lastError.message),
            "notifyBackgroundAuth",
            () => notifyBackgroundAuth(token, user, retryCount),
            retryCount
          );
          return;
        }

        log("info", "Background script notified successfully", response);
      });
    } catch (error) {
      handleError(
        error,
        "notifyBackgroundAuth",
        () => notifyBackgroundAuth(token, user, retryCount),
        retryCount
      );
    }
  }

  // Notify popup about authentication
  function notifyPopupAuth(token, user) {
    try {
      // Send message to popup if it's open
      chrome.runtime
        .sendMessage({
          type: "LOGIN_SUCCESS",
          data: {
            token: token,
            user: user,
            source: "content-script",
          },
        })
        .catch(() => {
          log("info", "Popup not open - auth notification skipped");
        });
    } catch (error) {
      log("warn", "Failed to notify popup about authentication", error.message);
    }
  }

  // Process authentication response
  function processAuthResponse(data, url) {
    log("info", "Processing authentication response", {
      url: url,
      dataKeys: Object.keys(data || {}),
      success: data ? data.success : false,
    });

    if (!validateAuthResponse(data)) {
      log("warn", "Invalid authentication response", data);
      return;
    }

    log("info", "Valid authentication response detected", {
      tokenLength: data.token.length,
      userEmail: data.user ? data.user.email : "N/A",
      hasPermissions: data.user ? !!data.user.permissions : false,
    });

    // Store the authentication data
    storeAuthData(data.token, data.user);

    // Show success notification
    showNotification("Authentication successful!", "success");
  }

  // Show notification to user
  function showNotification(message, type = "info") {
    log("info", `Showing ${type} notification: ${message}`);

    // Create notification element
    const notification = document.createElement("div");
    notification.id = "snippet-manager-notification";
    notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${
              type === "success"
                ? "#4CAF50"
                : type === "error"
                ? "#f44336"
                : "#2196F3"
            };
            color: white;
            border-radius: 4px;
            z-index: 10000;
            font-family: Arial, sans-serif;
            font-size: 14px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            animation: slideIn 0.3s ease-out;
        `;
    notification.textContent = message;

    // Add animation styles
    if (!document.getElementById("snippet-manager-styles")) {
      const styles = document.createElement("style");
      styles.id = "snippet-manager-styles";
      styles.textContent = `
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
      document.head.appendChild(styles);
    }

    // Remove existing notifications
    const existing = document.getElementById("snippet-manager-notification");
    if (existing) {
      existing.remove();
    }

    document.body.appendChild(notification);

    // Auto-remove after 3 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.style.animation = "slideOut 0.3s ease-in forwards";
        setTimeout(() => {
          if (notification.parentNode) {
            notification.remove();
          }
        }, 300);
      }
    }, 3000);
  }

  // Main fetch interceptor function
  function setupFetchInterceptor(retryCount = 0) {
    if (interceptorActive) {
      log("info", "Fetch interceptor already active");
      return;
    }

    try {
      log("info", "Setting up fetch interceptor", { retryCount: retryCount });

      // Store original fetch function
      const originalFetch = window.fetch;

      // Create our interceptor
      window.fetch = async function (url, options) {
        log("info", "Fetch intercepted", {
          url: typeof url === "string" ? url : url.toString(),
          method: options ? options.method : "GET",
          hasBody: options ? !!options.body : false,
        });

        try {
          // Call original fetch
          const response = await originalFetch(url, options);

          // Check if this is an auth endpoint
          const urlString = typeof url === "string" ? url : url.toString();
          if (isAuthEndpoint(urlString)) {
            log("info", "Authentication endpoint detected", {
              url: urlString,
              status: response.status,
              ok: response.ok,
            });

            // Clone response to avoid consuming it
            const responseClone = response.clone();

            // Process the response
            try {
              const data = await responseClone.json();
              processAuthResponse(data, urlString);
            } catch (jsonError) {
              log("warn", "Failed to parse JSON response", {
                error: jsonError.message,
                url: urlString,
              });
            }
          }

          return response;
        } catch (fetchError) {
          log("error", "Fetch error", {
            error: fetchError.message,
            url: typeof url === "string" ? url : url.toString(),
          });
          throw fetchError;
        }
      };

      interceptorActive = true;
      log("info", "Fetch interceptor installed successfully");
    } catch (error) {
      handleError(
        error,
        "setupFetchInterceptor",
        () => setupFetchInterceptor(retryCount),
        retryCount
      );
    }
  }

  // Setup XMLHttpRequest interceptor as backup
  function setupXHRInterceptor() {
    try {
      log("info", "Setting up XMLHttpRequest interceptor");

      const originalXHROpen = XMLHttpRequest.prototype.open;
      const originalXHRSend = XMLHttpRequest.prototype.send;

      XMLHttpRequest.prototype.open = function (method, url, ...args) {
        this._url = url;
        this._method = method;
        return originalXHROpen.apply(this, [method, url, ...args]);
      };

      XMLHttpRequest.prototype.send = function (data) {
        const xhr = this;

        if (isAuthEndpoint(this._url)) {
          log("info", "XHR Auth endpoint detected", {
            url: this._url,
            method: this._method,
          });

          const originalOnReadyStateChange = xhr.onreadystatechange;
          xhr.onreadystatechange = function () {
            if (xhr.readyState === 4 && xhr.status === 200) {
              try {
                const responseData = JSON.parse(xhr.responseText);
                processAuthResponse(responseData, xhr._url);
              } catch (error) {
                log("warn", "Failed to parse XHR response", error.message);
              }
            }

            if (originalOnReadyStateChange) {
              originalOnReadyStateChange.apply(this, arguments);
            }
          };
        }

        return originalXHRSend.apply(this, arguments);
      };

      log("info", "XMLHttpRequest interceptor installed successfully");
    } catch (error) {
      log("error", "Failed to setup XHR interceptor", error.message);
    }
  }

  // Listen for messages from popup and background
  function setupMessageListeners() {
    log("info", "Setting up message listeners");

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      log("info", "Message received", {
        type: message.type,
        action: message.action,
        sender: sender.tab ? "tab" : "extension",
      });

      switch (message.type) {
        case "AUTH_SYNC":
          log("info", "Auth sync request received");
          syncAuthState(message.token, message.user);
          sendResponse({ success: true });
          break;

        case "GET_AUTH_STATE":
          log("info", "Auth state request received");
          sendResponse({
            success: true,
            authState: authState,
          });
          break;

        case "LOGOUT":
          log("info", "Logout request received");
          clearAuthState();
          sendResponse({ success: true });
          break;

        default:
          log("info", "Unknown message type received", message.type);
      }

      return true; // Keep message channel open
    });
  }

  // Sync authentication state
  function syncAuthState(token, user) {
    log("info", "Syncing authentication state", {
      hasToken: !!token,
      hasUser: !!user,
    });

    authState.isAuthenticated = !!(token && user);
    authState.token = token;
    authState.user = user;
    authState.lastSync = Date.now();

    if (token && user) {
      showNotification("Authentication synchronized!", "success");
    }
  }

  // Clear authentication state
  function clearAuthState() {
    log("info", "Clearing authentication state");

    authState = {
      isAuthenticated: false,
      token: null,
      user: null,
      lastSync: Date.now(),
    };

    chrome.storage.local.remove(
      ["authToken", "currentUser", "userEmail", "authTimestamp"],
      function () {
        if (chrome.runtime.lastError) {
          log(
            "error",
            "Failed to clear auth storage",
            chrome.runtime.lastError.message
          );
        } else {
          log("info", "Authentication state cleared successfully");
          showNotification("Logged out successfully!", "info");
        }
      }
    );
  }

  // Initialize auth state from storage
  function initializeAuthState() {
    log("info", "Initializing authentication state from storage");

    chrome.storage.local.get(
      ["authToken", "currentUser", "authTimestamp"],
      function (result) {
        if (chrome.runtime.lastError) {
          log(
            "error",
            "Failed to load auth state from storage",
            chrome.runtime.lastError.message
          );
          return;
        }

        log("info", "Loaded auth state from storage", {
          hasToken: !!result.authToken,
          hasUser: !!result.currentUser,
          timestamp: result.authTimestamp,
        });

        if (result.authToken && result.currentUser) {
          authState.isAuthenticated = true;
          authState.token = result.authToken;
          authState.user = result.currentUser;
          authState.lastSync = result.authTimestamp || Date.now();
        }
      }
    );
  }

  // Setup heartbeat to maintain connection
  function setupHeartbeat() {
    setInterval(() => {
      if (authState.isAuthenticated) {
        chrome.runtime
          .sendMessage({
            type: "HEARTBEAT",
            authState: authState,
            timestamp: Date.now(),
          })
          .catch(() => {
            // Background script might not be available
          });
      }
    }, CONFIG.HEARTBEAT_INTERVAL);
  }

  // Main initialization function
  function initialize() {
    log("info", "Initializing auth content script");

    try {
      // Initialize components
      initializeAuthState();
      setupMessageListeners();
      setupFetchInterceptor();
      setupXHRInterceptor();
      setupHeartbeat();

      log("info", "Auth content script initialized successfully");

      // Notify background that content script is ready
      chrome.runtime
        .sendMessage({
          type: "CONTENT_SCRIPT_READY",
          url: window.location.href,
          timestamp: Date.now(),
        })
        .catch(() => {
          log("info", "Background script not available during initialization");
        });
    } catch (error) {
      log("error", "Failed to initialize auth content script", error.message);
    }
  }

  // Handle page unload
  window.addEventListener("beforeunload", function () {
    log("info", "Page unloading - cleaning up");

    // Send final state to background
    if (authState.isAuthenticated) {
      chrome.runtime
        .sendMessage({
          type: "PAGE_UNLOAD",
          authState: authState,
          timestamp: Date.now(),
        })
        .catch(() => {});
    }
  });

  // Start initialization when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }

  log("info", "Auth content script setup complete");
})();

/**
 * Real-time WebSocket Client - Modern Futuristic Implementation
 * Features: Auto-reconnection, Queue management, Event handling, Sync status
 */

class WebSocketClient {
  constructor(options = {}) {
    this.options = {
      url: options.url || "ws://localhost:5000",
      reconnectInterval: 3000,
      maxReconnectAttempts: 10,
      heartbeatInterval: 30000,
      debug: options.debug || false,
      ...options,
    };

    this.ws = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.messageQueue = [];
    this.eventHandlers = new Map();
    this.heartbeatTimer = null;
    this.reconnectTimer = null;
    this.connectionId = null;
    this.syncStatus = "disconnected";

    this.init();
  }

  init() {
    this.createStatusIndicator();
    this.connect();
    this.setupEventHandlers();
    this.createSocketIOCompatibility(); // ADD THIS LINE
  }

  // Add Socket.IO compatibility layer
  createSocketIOCompatibility() {
    // Create socket property for compatibility
    this.socket = {
      emit: (event, data) => {
        console.log(`📤 Socket.IO emit: ${event}`, data);

        // Convert Socket.IO format to native WebSocket format
        const message = {
          type: event,
          ...data,
        };

        return this.send(message);
      },

      on: (event, handler) => {
        console.log(`🎧 Socket.IO on: ${event}`);
        this.on(event, handler);
      },

      off: (event, handler) => {
        console.log(`🔇 Socket.IO off: ${event}`);
        this.off(event, handler);
      },
    };
  }

  createStatusIndicator() {
    // Create floating sync status indicator
    const statusIndicator = document.createElement("div");
    statusIndicator.className = "sync-status-indicator";
    statusIndicator.innerHTML = `
            <div class="sync-status-content">
                <div class="sync-icon">
                    <div class="pulse-ring"></div>
                    <i class="icon-wifi"></i>
                </div>
                <div class="sync-info">
                    <div class="sync-text">Connecting...</div>
                    <div class="sync-details">Establishing connection</div>
                </div>
                <div class="sync-actions">
                    <button class="btn-icon reconnect-btn" title="Reconnect">
                        <i class="icon-refresh"></i>
                    </button>
                    <button class="btn-icon close-status" title="Close">
                        <i class="icon-x"></i>
                    </button>
                </div>
            </div>
            <div class="sync-progress">
                <div class="progress-bar"></div>
            </div>
        `;

    document.body.appendChild(statusIndicator);
    this.statusIndicator = statusIndicator;

    // Setup status indicator events
    statusIndicator
      .querySelector(".reconnect-btn")
      .addEventListener("click", () => {
        this.reconnect();
      });

    statusIndicator
      .querySelector(".close-status")
      .addEventListener("click", () => {
        this.hideStatusIndicator();
      });
  }

  connect() {
    try {
      this.updateSyncStatus("connecting", "Establishing connection...");

      this.ws = new WebSocket(this.options.url);

      this.ws.onopen = (event) => {
        this.handleOpen(event);
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event);
      };

      this.ws.onclose = (event) => {
        this.handleClose(event);
      };

      this.ws.onerror = (event) => {
        this.handleError(event);
      };
    } catch (error) {
      this.log("Connection error:", error);
      this.scheduleReconnect();
    }
  }

  handleOpen(event) {
    this.log("WebSocket connected");
    this.isConnected = true;
    this.reconnectAttempts = 0;
    this.updateSyncStatus("connected", "Connected to server");

    // Send authentication if available
    const authToken = localStorage.getItem("authToken");
    if (authToken) {
      this.send({
        type: "authenticate",
        token: authToken,
      });
    }

    // Process queued messages
    this.processMessageQueue();

    // Start heartbeat
    this.startHeartbeat();

    // Emit connected event
    this.emit("connected", { event });
  }

  handleMessage(event) {
    try {
      let data;
      const rawMessage = event.data;

      this.log("🔄 Raw message received:", rawMessage);

      // ✅ FIXED: Parse Socket.IO format
      if (typeof rawMessage === "string") {
        if (rawMessage.startsWith("42[")) {
          // Socket.IO event format: 42["event_name", {data}]
          try {
            const jsonPart = rawMessage.substring(2); // Remove "42"
            const parsed = JSON.parse(jsonPart);

            if (Array.isArray(parsed) && parsed.length >= 2) {
              const eventName = parsed[0];
              const eventData = parsed[1] || {};

              data = {
                type: eventName,
                ...eventData,
              };

              this.log("✅ Parsed Socket.IO event:", {
                eventName,
                eventData,
                converted: data,
              });
            } else {
              throw new Error("Invalid Socket.IO event format");
            }
          } catch (parseError) {
            this.log("❌ Error parsing Socket.IO event:", parseError);
            return;
          }
        } else if (rawMessage === "2") {
          // Socket.IO ping
          this.log("🏓 Socket.IO ping received, sending pong");
          this.ws.send("3"); // Send pong
          return;
        } else if (rawMessage === "3") {
          // Socket.IO pong
          this.log("🏓 Socket.IO pong received");
          return;
        } else if (rawMessage.startsWith("0")) {
          // Socket.IO connection message
          this.log("🔌 Socket.IO connection message:", rawMessage);
          return;
        } else {
          // Try parsing as regular JSON
          try {
            data = JSON.parse(rawMessage);
            this.log("✅ Parsed as regular JSON:", data);
          } catch (jsonError) {
            this.log("❌ Unable to parse message:", rawMessage);
            return;
          }
        }
      } else {
        this.log("⚠️ Non-string message received:", rawMessage);
        return;
      }

      // Handle system messages
      switch (data.type) {
        case "authenticated":
          this.connectionId = data.connectionId;
          this.updateSyncStatus("authenticated", "Authenticated successfully");
          break;

        case "heartbeat":
          this.send({ type: "heartbeat_response" });
          break;

        case "error":
          this.handleServerError(data);
          break;

        case "snippet_updated":
          this.handleSnippetUpdate(data);
          break;

        case "snippet_deleted":
          this.handleSnippetDelete(data);
          break;

        case "collection_updated":
          this.handleCollectionUpdate(data);
          break;

        case "sync_status":
          this.handleSyncStatus(data);
          break;

        default:
          // Emit custom event
          this.emit(data.type, data);
          break;
      }

      // Update last activity
      this.lastActivity = Date.now();
    } catch (error) {
      this.log("❌ Error in handleMessage:", error);
    }
  }

  handleClose(event) {
    this.log("WebSocket closed:", event.code, event.reason);
    this.isConnected = false;
    this.stopHeartbeat();

    if (event.code !== 1000) {
      // Not a normal closure
      this.updateSyncStatus("disconnected", "Connection lost");
      this.scheduleReconnect();
    } else {
      this.updateSyncStatus("disconnected", "Disconnected");
    }

    this.emit("disconnected", { event });
  }

  handleError(event) {
    this.log("WebSocket error:", event);
    this.updateSyncStatus("error", "Connection error");
    this.emit("error", { event });
  }

  send(data) {
    if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
      try {
        // ✅ FIXED: Convert to Socket.IO format
        let socketIOMessage;

        if (data.type) {
          // Convert {type: "event", ...data} to Socket.IO format
          const eventName = data.type;
          const eventData = { ...data };
          delete eventData.type;

          // Socket.IO format: 42["event_name", {data}]
          socketIOMessage = `42["${eventName}",${JSON.stringify(eventData)}]`;
          this.log("🔄 Converting to Socket.IO format:", {
            original: data,
            converted: socketIOMessage,
          });
        } else {
          // Fallback for other message types
          socketIOMessage = JSON.stringify(data);
          this.log("⚠️ Sending raw JSON (no type field):", data);
        }

        this.ws.send(socketIOMessage);
        this.log("✅ Sent Socket.IO message:", socketIOMessage);
        return true;
      } catch (error) {
        this.log("❌ Error sending message:", error);
        this.queueMessage(data);
        return false;
      }
    } else {
      this.log("⚠️ WebSocket not ready, queueing message:", data);
      this.queueMessage(data);
      return false;
    }
  }

  queueMessage(data) {
    this.messageQueue.push({
      data,
      timestamp: Date.now(),
    });

    // Limit queue size
    if (this.messageQueue.length > 100) {
      this.messageQueue.shift();
    }

    this.log("Message queued:", data);
  }

  processMessageQueue() {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();

      // Check if message is not too old (5 minutes)
      if (Date.now() - message.timestamp < 300000) {
        this.send(message.data);
      }
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      this.updateSyncStatus("failed", "Max reconnection attempts reached");
      this.emit("reconnect_failed");
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      this.options.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
      30000
    );

    this.updateSyncStatus(
      "reconnecting",
      `Reconnecting in ${Math.ceil(delay / 1000)}s... (${
        this.reconnectAttempts
      }/${this.options.maxReconnectAttempts})`
    );

    this.reconnectTimer = setTimeout(() => {
      this.log(`Reconnection attempt ${this.reconnectAttempts}`);
      this.connect();
    }, delay);
  }

  reconnect() {
    this.disconnect();
    this.reconnectAttempts = 0;
    this.connect();
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, "Manual disconnect");
    }

    this.stopHeartbeat();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected) {
        this.send({ type: "heartbeat" });
      }
    }, this.options.heartbeatInterval);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  updateSyncStatus(status, message) {
    this.syncStatus = status;

    const indicator = this.statusIndicator;
    const icon = indicator.querySelector(".sync-icon i");
    const text = indicator.querySelector(".sync-text");
    const details = indicator.querySelector(".sync-details");
    const progressBar = indicator.querySelector(".progress-bar");

    // Update status class
    indicator.className = `sync-status-indicator status-${status}`;

    // Update icon
    const iconMap = {
      connecting: "icon-wifi",
      connected: "icon-check-circle",
      authenticated: "icon-shield-check",
      disconnected: "icon-wifi-off",
      reconnecting: "icon-refresh-cw",
      error: "icon-alert-circle",
      failed: "icon-x-circle",
      syncing: "icon-sync",
    };

    icon.className = iconMap[status] || "icon-wifi";

    // Update text
    const statusTexts = {
      connecting: "Connecting",
      connected: "Connected",
      authenticated: "Authenticated",
      disconnected: "Offline",
      reconnecting: "Reconnecting",
      error: "Connection Error",
      failed: "Connection Failed",
      syncing: "Syncing",
    };

    text.textContent = statusTexts[status] || "Unknown";
    details.textContent = message;

    // Update progress bar
    if (status === "connecting" || status === "reconnecting") {
      progressBar.style.display = "block";
      progressBar.classList.add("indeterminate");
    } else {
      progressBar.style.display = "none";
      progressBar.classList.remove("indeterminate");
    }

    // Auto-hide success states
    if (status === "connected" || status === "authenticated") {
      setTimeout(() => {
        this.hideStatusIndicator();
      }, 3000);
    } else {
      this.showStatusIndicator();
    }
  }

  showStatusIndicator() {
    this.statusIndicator.classList.add("visible");
  }

  hideStatusIndicator() {
    this.statusIndicator.classList.remove("visible");
  }

  // Event handling system
  on(event, handler) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, []);
    }
    this.eventHandlers.get(event).push(handler);
  }

  off(event, handler) {
    if (this.eventHandlers.has(event)) {
      const handlers = this.eventHandlers.get(event);
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.eventHandlers.has(event)) {
      this.eventHandlers.get(event).forEach((handler) => {
        try {
          handler(data);
        } catch (error) {
          this.log("Error in event handler:", error);
        }
      });
    }
  }

  // Snippet synchronization methods
  saveSnippet(snippetData) {
    const message = {
      type: "save_snippet",
      data: {
        ...snippetData,
        timestamp: Date.now(),
        clientId: this.connectionId,
      },
    };

    this.send(message);
    this.updateSyncStatus("syncing", "Saving snippet...");
  }

  deleteSnippet(snippetId) {
    const message = {
      type: "delete_snippet",
      data: {
        id: snippetId,
        timestamp: Date.now(),
        clientId: this.connectionId,
      },
    };

    this.send(message);
    this.updateSyncStatus("syncing", "Deleting snippet...");
  }

  updateCollection(collectionData) {
    const message = {
      type: "update_collection",
      data: {
        ...collectionData,
        timestamp: Date.now(),
        clientId: this.connectionId,
      },
    };

    this.send(message);
    this.updateSyncStatus("syncing", "Updating collection...");
  }

  syncData() {
    const message = {
      type: "sync_request",
      data: {
        lastSync: localStorage.getItem("lastSyncTime") || 0,
        clientId: this.connectionId,
      },
    };

    this.send(message);
    this.updateSyncStatus("syncing", "Synchronizing data...");
  }

  // Handle server events
  handleSnippetUpdate(data) {
    this.updateSyncStatus("connected", "Snippet updated");

    // Update local storage or state
    this.updateLocalSnippet(data.snippet);

    // Emit event for UI update
    this.emit("snippet_updated", data);

    // Update last sync time
    localStorage.setItem("lastSyncTime", Date.now());
  }

  handleSnippetDelete(data) {
    this.updateSyncStatus("connected", "Snippet deleted");

    // Remove from local storage or state
    this.removeLocalSnippet(data.snippetId);

    // Emit event for UI update
    this.emit("snippet_deleted", data);

    // Update last sync time
    localStorage.setItem("lastSyncTime", Date.now());
  }

  handleCollectionUpdate(data) {
    this.updateSyncStatus("connected", "Collection updated");

    // Update local collection
    this.updateLocalCollection(data.collection);

    // Emit event for UI update
    this.emit("collection_updated", data);

    // Update last sync time
    localStorage.setItem("lastSyncTime", Date.now());
  }

  handleSyncStatus(data) {
    if (data.status === "complete") {
      this.updateSyncStatus("connected", "Sync complete");
      localStorage.setItem("lastSyncTime", Date.now());
    }
  }

  handleServerError(data) {
    this.log("Server error:", data.error);
    this.updateSyncStatus("error", data.error.message || "Server error");
    this.emit("server_error", data.error);
  }

  // Local data management (simplified - replace with proper state management)
  updateLocalSnippet(snippet) {
    const snippets = JSON.parse(localStorage.getItem("snippets") || "[]");
    const index = snippets.findIndex((s) => s.id === snippet.id);

    if (index >= 0) {
      snippets[index] = snippet;
    } else {
      snippets.push(snippet);
    }

    localStorage.setItem("snippets", JSON.stringify(snippets));
  }

  removeLocalSnippet(snippetId) {
    const snippets = JSON.parse(localStorage.getItem("snippets") || "[]");
    const filtered = snippets.filter((s) => s.id !== snippetId);
    localStorage.setItem("snippets", JSON.stringify(filtered));
  }

  updateLocalCollection(collection) {
    const collections = JSON.parse(localStorage.getItem("collections") || "[]");
    const index = collections.findIndex((c) => c.id === collection.id);

    if (index >= 0) {
      collections[index] = collection;
    } else {
      collections.push(collection);
    }

    localStorage.setItem("collections", JSON.stringify(collections));
  }

  // Setup default event handlers
  setupEventHandlers() {
    // Handle browser events
    window.addEventListener("online", () => {
      this.log("Browser back online");
      if (!this.isConnected) {
        this.reconnect();
      }
    });

    window.addEventListener("offline", () => {
      this.log("Browser went offline");
      this.updateSyncStatus("disconnected", "Browser offline");
    });

    // Handle page visibility
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && !this.isConnected) {
        this.reconnect();
      }
    });

    // Handle beforeunload
    window.addEventListener("beforeunload", () => {
      this.disconnect();
    });
  }

  // Utility methods
  log(...args) {
    if (this.options.debug) {
      console.log("[WebSocket]", ...args);
    }
  }

  getConnectionInfo() {
    return {
      isConnected: this.isConnected,
      connectionId: this.connectionId,
      reconnectAttempts: this.reconnectAttempts,
      syncStatus: this.syncStatus,
      queuedMessages: this.messageQueue.length,
    };
  }

  // Public API methods
  isOnline() {
    return this.isConnected;
  }

  getQueuedMessagesCount() {
    return this.messageQueue.length;
  }

  clearQueue() {
    this.messageQueue = [];
  }

  destroy() {
    this.disconnect();

    if (this.statusIndicator) {
      this.statusIndicator.remove();
    }

    // Clear all event handlers
    this.eventHandlers.clear();
  }
}

// Real-time sync manager
class SyncManager {
  constructor(wsClient) {
    this.wsClient = wsClient;
    this.syncQueue = [];
    this.isOnline = navigator.onLine;

    this.setupEventListeners();
  }

  setupEventListeners() {
    // Listen to WebSocket events
    this.wsClient.on("connected", () => {
      this.processPendingSync();
    });

    this.wsClient.on("snippet_updated", (data) => {
      this.handleRemoteSnippetUpdate(data);
    });

    // Listen to browser events
    window.addEventListener("online", () => {
      this.isOnline = true;
      this.processPendingSync();
    });

    window.addEventListener("offline", () => {
      this.isOnline = false;
    });
  }

  queueSync(action, data) {
    this.syncQueue.push({
      action,
      data,
      timestamp: Date.now(),
    });

    if (this.wsClient.isOnline()) {
      this.processPendingSync();
    }
  }

  processPendingSync() {
    while (this.syncQueue.length > 0) {
      const syncItem = this.syncQueue.shift();

      switch (syncItem.action) {
        case "save_snippet":
          this.wsClient.saveSnippet(syncItem.data);
          break;
        case "delete_snippet":
          this.wsClient.deleteSnippet(syncItem.data.id);
          break;
        case "update_collection":
          this.wsClient.updateCollection(syncItem.data);
          break;
      }
    }
  }

  handleRemoteSnippetUpdate(data) {
    // Handle conflicts, merge changes, etc.
    // This is a simplified version

    if (data.clientId !== this.wsClient.connectionId) {
      // Update came from another client
      this.showSyncNotification("Snippet updated from another device");
    }
  }

  showSyncNotification(message) {
    // Show a subtle notification about sync activity
    const notification = document.createElement("div");
    notification.className = "sync-notification";
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
      notification.classList.add("show");
    }, 100);

    setTimeout(() => {
      notification.classList.remove("show");
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }
}

// Initialize and export
window.WebSocketClient = WebSocketClient;
window.SyncManager = SyncManager;

// Auto-initialize if config is available
if (window.wsConfig) {
  window.wsClient = new WebSocketClient(window.wsConfig);
  window.syncManager = new SyncManager(window.wsClient);
}

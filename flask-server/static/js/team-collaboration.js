// Real-time Team Collaboration Features
// Modern, Dynamic UI with Futuristic Design

class TeamCollaboration {
  constructor() {
    this.socket = null;
    this.currentRoom = null;
    this.activeUsers = new Map();
    this.cursors = new Map();
    this.notifications = [];
    this.collaborativeEditor = null;
    this.activityFeed = [];

    // Add these new properties
    this.errorLog = [];
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.isInitialized = false;

    this.init();
  }

  logError(context, error, additionalData = {}) {
    const errorEntry = {
      timestamp: new Date().toISOString(),
      context: context,
      error: error.toString(),
      error_type: error.constructor.name,
      stack: error.stack || "No stack trace",
      additionalData: additionalData,
      url: window.location.href,
      userAgent: navigator.userAgent,
      userId: this.getCurrentUserId(),
    };

    this.errorLog.push(errorEntry);

    // Enhanced console logging based on error type
    if (error.message && error.message.includes("Unexpected token")) {
      console.error(
        `🔥 TEAM_COLLABORATION ERROR [${context}] - JSON PARSE ERROR:`,
        {
          message: "Server returned HTML instead of JSON (likely 500 error)",
          suggestion: "Check Flask backend logs for Python errors",
          error: errorEntry,
        }
      );
    } else {
      console.error(`🔥 TEAM_COLLABORATION ERROR [${context}]:`, errorEntry);
    }

    // Keep only last 100 errors
    if (this.errorLog.length > 100) {
      this.errorLog.splice(0, this.errorLog.length - 100);
    }

    // Store in localStorage for debugging
    try {
      localStorage.setItem(
        "teamCollaborationErrors",
        JSON.stringify(this.errorLog)
      );
    } catch (storageError) {
      console.error("🔥 Failed to store error log:", storageError);
    }

    // Send to server if critical
    if (context.includes("CRITICAL") || context.includes("WEBSOCKET")) {
      this.sendErrorToServer(errorEntry);
    }
  }

  // ADD ENHANCED LOGGING METHOD after logError()
  logTeamAction(action, teamId, additionalData = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      action: action,
      teamId: teamId,
      userId: this.getCurrentUserId(),
      url: window.location.href,
      additionalData: additionalData,
    };

    console.log(`🎯 TEAM_ACTION [${action}]:`, logEntry);

    // Store team actions separately
    const teamActions = JSON.parse(localStorage.getItem("teamActions") || "[]");
    teamActions.push(logEntry);

    // Keep only last 100 actions
    if (teamActions.length > 100) {
      teamActions.splice(0, teamActions.length - 100);
    }

    localStorage.setItem("teamActions", JSON.stringify(teamActions));
  }

  // ADD ENHANCED FUNCTION TRACKING after logTeamAction()
  logFunctionCall(functionName, params = {}, result = null, error = null) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      function: functionName,
      params: params,
      result: result ? "SUCCESS" : "FAILED",
      error: error ? error.toString() : null,
      userId: this.getCurrentUserId(),
      url: window.location.href,
    };

    console.log(`🔧 FUNCTION_CALL [${functionName}]:`, logEntry);

    // Store function calls separately
    const functionCalls = JSON.parse(
      localStorage.getItem("functionCalls") || "[]"
    );
    functionCalls.push(logEntry);

    // Keep only last 50 calls
    if (functionCalls.length > 50) {
      functionCalls.splice(0, functionCalls.length - 50);
    }

    localStorage.setItem("functionCalls", JSON.stringify(functionCalls));
  }

  async sendErrorToServer(errorEntry) {
    try {
      await fetch("/api/errors/collaboration", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(errorEntry),
      });
    } catch (error) {
      console.error("🔥 Failed to send error to server:", error);
    }
  }

  init() {
    this.initWebSocket();
    this.initCollaborativeEditor();
    this.setupEventListeners();
    this.initializeUI();
    this.startHeartbeat();
    // ADD this line at the end of the init() method:
    this.setupTeamChatIntegration();
  }

  setupTeamChatIntegration() {
    // Auto-join team chat room when on team detail page
    if (window.location.pathname.includes("/teams/")) {
      const teamId = window.location.pathname.split("/").pop();
      if (teamId) {
        setTimeout(() => {
          this.sendTeamChatJoin(teamId);
        }, 1000);
      }
    }

    // Leave team chat room when navigating away
    window.addEventListener("beforeunload", () => {
      if (window.location.pathname.includes("/teams/")) {
        const teamId = window.location.pathname.split("/").pop();
        if (teamId) {
          this.sendTeamChatLeave(teamId);
        }
      }
    });
  }

  initWebSocket() {
    try {
      // Skip WebSocket for Step 1 testing - not critical for team creation
      // WITH this corrected condition:
      if (
        window.location.pathname.includes("/teams") &&
        !window.location.pathname.includes("/teams/detail/")
      ) {
        console.log(
          "ℹ️ WEBSOCKET: Skipping WebSocket connection for teams list page"
        );
        this.showConnectionStatus("offline");
        return;
      }

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/teams`;

      console.log(`🔗 WEBSOCKET: Connecting to ${wsUrl}`);
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log("✅ WEBSOCKET: Collaboration WebSocket connected");
        this.showConnectionStatus("connected");
        this.reconnectAttempts = 0;
        this.isInitialized = true;

        // Send authentication
        this.authenticateUser();
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("📨 WEBSOCKET: Message received:", data);
          this.handleWebSocketMessage(data);
        } catch (error) {
          this.logError("WEBSOCKET_MESSAGE_PARSE", error, {
            rawMessage: event.data,
          });
        }
      };

      this.socket.onclose = (event) => {
        console.log(
          `❌ WEBSOCKET: Connection closed - Code: ${event.code}, Reason: ${event.reason}`
        );
        this.showConnectionStatus("disconnected");
        this.isInitialized = false;
        this.attemptReconnection();
      };

      this.socket.onerror = (error) => {
        console.error("🔥 WEBSOCKET: Connection error:", error);
        this.logError("WEBSOCKET_ERROR", error);
        this.showConnectionStatus("error");
      };
    } catch (error) {
      this.logError("WEBSOCKET_INIT_CRITICAL", error);
      this.showConnectionStatus("error");
    }
  }

  // Add this new method after initWebSocket
  authenticateUser() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const authData = {
        type: "authenticate",
        userId: this.getCurrentUserId(),
        timestamp: Date.now(),
        userAgent: navigator.userAgent,
      };

      console.log("🔐 WEBSOCKET: Sending authentication:", authData);
      this.socket.send(JSON.stringify(authData));
    }
  }

  // ADD THESE CASES in handleWebSocketMessage method (around line 110):
  handleWebSocketMessage(data) {
    switch (data.type) {
      // ADD THESE NEW CASES:
      case "team_created_success":
        this.handleTeamCreatedSuccess(data);
        break;
      case "team_creation_error":
        this.handleTeamCreationError(data);
        break;
      case "auth_success":
        this.handleAuthSuccess(data);
        break;
      case "auth_error":
        this.handleAuthError(data);
        break;
      case "user_joined_team":
        this.handleUserJoinedTeam(data);
        break;
      case "team_joined_success":
        this.handleTeamJoinedSuccess(data);
        break;
      case "snippet_shared":
        this.handleSnippetShared(data);
        break;
      case "snippet_updated":
        this.handleSnippetUpdated(data);
        break;
      case "snippet_permissions_changed":
        this.handleSnippetPermissionsChanged(data);
        break;
      case "team_snippet_activity":
        this.handleTeamSnippetActivity(data);
        break;
      // EXISTING CASES:
      case "user_joined":
        this.handleUserJoined(data);
        break;
      // EXISTING CASES:
      case "user_joined":
        this.handleUserJoined(data);
        break;
      case "user_left":
        this.handleUserLeft(data);
        break;
      case "cursor_update":
        this.handleCursorUpdate(data);
        break;
      case "text_change":
        this.handleTextChange(data);
        break;
      case "activity_update":
        this.handleActivityUpdate(data);
        break;
      case "notification":
        this.handleNotification(data);
        break;

      case "team_chat_history":
        this.handleTeamChatHistory(data);
        break;
      case "team_chat_message_received":
        this.handleTeamChatMessageReceived(data);
        break;
      case "team_chat_cleared":
        this.handleTeamChatCleared(data);
        break;
      case "user_joined_team_chat":
        this.handleUserJoinedTeamChat(data);
        break;
      case "user_left_team_chat":
        this.handleUserLeftTeamChat(data);
        break;
      case "team_chat_joined":
        this.handleTeamChatJoined(data);
        break;
      case "team_chat_error":
        this.handleTeamChatError(data);
        break;
    }
  }

  // ADD these corrected handler methods:
  handleTeamChatHistory(data) {
    try {
      console.log("📜 WEBSOCKET: Team chat history received:", data);

      if (
        window.teamChatManager &&
        window.location.pathname.includes("/teams/")
      ) {
        window.teamChatManager.handleChatHistory(data);
      }
    } catch (error) {
      this.logError("HANDLE_TEAM_CHAT_HISTORY", error, { data });
    }
  }

  handleTeamChatMessageReceived(data) {
    try {
      console.log("💬 WEBSOCKET: Team chat message received:", data);

      // Update team chat manager if on team detail page
      if (
        window.teamChatManager &&
        window.location.pathname.includes("/teams/detail/")
      ) {
        window.teamChatManager.handleNewMessage(data);
      }

      // Show notification if not on team chat tab or window not focused
      const teamChatTab = document.querySelector('[data-tab="teamchat"]');
      const isChatTabActive =
        teamChatTab && teamChatTab.classList.contains("active");

      if (!isChatTabActive || !document.hasFocus()) {
        this.showNotification({
          type: "info",
          icon: "message-circle",
          title: "New Team Message",
          message: `${
            data.chat.user?.username || "Someone"
          }: ${data.chat.message.substring(0, 50)}...`,
        });
      }
    } catch (error) {
      this.logError("HANDLE_TEAM_CHAT_MESSAGE_RECEIVED", error, { data });
    }
  }

  handleTeamChatCleared(data) {
    try {
      console.log("🧹 WEBSOCKET: Team chat cleared:", data);

      // Update team chat manager if on team detail page
      if (
        window.teamChatManager &&
        window.location.pathname.includes("/teams/detail/")
      ) {
        window.teamChatManager.handleChatCleared(data);
      }

      // Show notification to all users
      this.showNotification({
        type: "info",
        icon: "trash",
        title: "Chat Cleared",
        message: `Admin cleared the team chat`,
      });
    } catch (error) {
      this.logError("HANDLE_TEAM_CHAT_CLEARED", error, { data });
    }
  }

  handleUserJoinedTeamChat(data) {
    try {
      console.log("👥 WEBSOCKET: User joined team chat:", data);

      if (window.teamChatManager) {
        window.teamChatManager.handleUserJoined(data);
      }
    } catch (error) {
      this.logError("HANDLE_USER_JOINED_TEAM_CHAT", error, { data });
    }
  }

  handleUserLeftTeamChat(data) {
    try {
      console.log("👋 WEBSOCKET: User left team chat:", data);

      if (window.teamChatManager) {
        window.teamChatManager.handleUserLeft(data);
      }
    } catch (error) {
      this.logError("HANDLE_USER_LEFT_TEAM_CHAT", error, { data });
    }
  }

  handleTeamChatJoined(data) {
    try {
      console.log("✅ WEBSOCKET: Team chat joined:", data);

      this.showNotification({
        type: "success",
        icon: "check-circle",
        title: "Chat Connected",
        message: "Connected to team chat",
      });
    } catch (error) {
      this.logError("HANDLE_TEAM_CHAT_JOINED", error, { data });
    }
  }

  handleTeamChatError(data) {
    try {
      console.error("❌ WEBSOCKET: Team chat error:", data);

      this.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Chat Error",
        message: data.error || "Team chat error occurred",
      });
    } catch (error) {
      this.logError("HANDLE_TEAM_CHAT_ERROR", error, { data });
    }
  }

  // CORRECTED WebSocket senders:
  sendTeamChatJoin(teamId) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const joinData = {
          type: "join_team_chat",
          team_id: teamId,
          user_id: this.getCurrentUserId(),
        };

        console.log("📤 WEBSOCKET: Joining team chat:", joinData);
        this.socket.send(JSON.stringify(joinData));
      }
    } catch (error) {
      this.logError("SEND_TEAM_CHAT_JOIN", error, { teamId });
    }
  }

  sendTeamChatLeave(teamId) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const leaveData = {
          type: "leave_team_chat",
          team_id: teamId,
          user_id: this.getCurrentUserId(),
        };

        console.log("📤 WEBSOCKET: Leaving team chat:", leaveData);
        this.socket.send(JSON.stringify(leaveData));
      }
    } catch (error) {
      this.logError("SEND_TEAM_CHAT_LEAVE", error, { teamId });
    }
  }

  initCollaborativeEditor() {
    // Initialize collaborative editor with real-time sync
    this.collaborativeEditor = {
      element: document.getElementById("collaborative-editor"),
      cursors: new Map(),
      selections: new Map(),
      changeBuffer: [],
      lastSync: Date.now(),
    };

    if (this.collaborativeEditor.element) {
      this.setupEditorEvents();
    }
  }

  setupEditorEvents() {
    const editor = this.collaborativeEditor.element;

    // Real-time text changes
    editor.addEventListener(
      "input",
      this.debounce((e) => {
        this.broadcastTextChange({
          content: e.target.value,
          position: e.target.selectionStart,
          timestamp: Date.now(),
        });
      }, 300)
    );

    // Cursor position tracking
    editor.addEventListener("selectionchange", () => {
      this.broadcastCursorPosition({
        start: editor.selectionStart,
        end: editor.selectionEnd,
        timestamp: Date.now(),
      });
    });

    // Focus/blur events
    editor.addEventListener("focus", () => {
      this.broadcastUserActivity("editing");
    });

    editor.addEventListener("blur", () => {
      this.broadcastUserActivity("idle");
    });
  }

  setupEventListeners() {
    // Remove any existing event listeners first to prevent duplicates
    const createTeamForm = document.getElementById("createTeamForm");
    if (createTeamForm) {
      // Remove the form submission prevention
      createTeamForm.onsubmit = null;

      // Clone the form and replace it to remove all event listeners
      const newForm = createTeamForm.cloneNode(true);
      createTeamForm.parentNode.replaceChild(newForm, createTeamForm);

      // Add a single event listener to the new form
      // In setupEventListeners method, update the form submission handler:
      newForm.addEventListener(
        "submit",
        async (e) => {
          e.preventDefault();
          e.stopPropagation();

          // Check if already submitting
          if (newForm.dataset.submitting === "true") {
            console.log(
              "🚫 Form already submitting, ignoring duplicate submission"
            );
            return;
          }

          // ADD THIS EXTRA CHECK:
          const submitBtn = newForm.querySelector('button[type="submit"]');
          if (submitBtn && submitBtn.disabled) {
            console.log(
              "🚫 Submit button already disabled, ignoring submission"
            );
            return;
          }

          // Mark as submitting IMMEDIATELY
          newForm.dataset.submitting = "true";

          // Disable the form to prevent multiple submissions
          if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Creating...";
            // ADD THIS: Prevent any clicks on the button
            submitBtn.style.pointerEvents = "none";
          }

          // ADD THIS: Disable the entire form
          const formInputs = newForm.querySelectorAll(
            "input, textarea, select, button"
          );
          formInputs.forEach((input) => (input.disabled = true));

          const formData = new FormData(e.target);
          const teamData = {
            name: formData.get("name").trim(),
            description: formData.get("description").trim(),
            avatar:
              formData.get("avatar").trim() ||
              formData.get("name").substring(0, 2).toUpperCase(),
          };

          console.log("🎯 GLOBAL: Creating team with data:", teamData);

          try {
            await this.handleCreateTeam(teamData);
          } catch (error) {
            // Only re-enable on error (success will reload page anyway)
            console.error("❌ Team creation failed:", error);

            // Re-enable the form after error
            newForm.dataset.submitting = "false";
            formInputs.forEach((input) => (input.disabled = false));

            if (submitBtn) {
              submitBtn.disabled = false;
              submitBtn.textContent = "Create Team";
              submitBtn.style.pointerEvents = "auto";
            }
          }
        },
        { once: true }
      );
    }

    // Rest of your event listeners...
  }

  initializeUI() {
    try {
      this.createCollaborationInterface();
      this.setupFloatingCursors();
      this.setupNotificationCenter();
      console.log("✅ COLLABORATION: UI initialized successfully");
    } catch (error) {
      this.logError("UI_INITIALIZATION", error);
      console.warn(
        "⚠️ COLLABORATION: UI initialization failed, continuing without UI"
      );
    }
  }

  // ADD THIS METHOD after the other missing methods you just added:

  openCreateTeamModal() {
    console.log("🎯 COLLABORATION: Opening create team modal");

    // Find the modal in the DOM
    const modal = document.getElementById("createTeamModal");
    if (modal) {
      modal.classList.add("active");
      console.log("✅ COLLABORATION: Modal opened successfully");
    } else {
      console.error("❌ COLLABORATION: Create team modal not found");
    }
  }

  closeCreateTeamModal() {
    console.log("🎯 COLLABORATION: Closing create team modal");

    const modal = document.getElementById("createTeamModal");
    if (modal) {
      modal.classList.remove("active");
      const form = document.getElementById("createTeamForm");
      if (form) {
        form.reset();
      }
      console.log("✅ COLLABORATION: Modal closed successfully");
    }
  }

  // ADD THESE METHODS TO TeamCollaboration CLASS:

  startCollaborativeEditing(snippetId) {
    console.log(
      `🤝 COLLABORATION: Starting collaborative editing for snippet ${snippetId}`
    );

    this.socket.emit("start_collaboration", {
      snippet_id: snippetId,
      user_id: this.getCurrentUserId(),
    });
  }

  joinCollaborativeSession(sessionId) {
    console.log(`🤝 COLLABORATION: Joining session ${sessionId}`);

    this.socket.emit("join_collaboration", {
      session_id: sessionId,
      user_id: this.getCurrentUserId(),
    });
  }

  sendCollaborativeEdit(sessionId, operation) {
    console.log(`✏️ COLLABORATION: Sending edit operation`);

    this.socket.emit("collaborative_edit", {
      session_id: sessionId,
      operation: operation,
    });
  }

  // ADD THESE NEW METHODS after existing handlers (around line 200):

  handleTeamCreatedSuccess(data) {
    try {
      console.log("✅ TEAM CREATED SUCCESS:", data);

      this.showNotification({
        type: "success",
        icon: "check-circle",
        title: "Team Created!",
        message:
          data.message || `Team "${data.team.name}" created successfully`,
      });

      // Join the new team room
      if (data.room_joined) {
        this.currentRoom = data.room_joined;
        console.log(`🏢 TEAM: Joined new team room: ${data.room_joined}`);
      }

      this.addActivityItem({
        type: "create",
        user: this.getCurrentUserName(),
        timestamp: Date.now(),
        message: `Created team "${data.team.name}"`,
      });
    } catch (error) {
      this.logError("HANDLE_TEAM_CREATED_SUCCESS", error, { data });
    }
  }

  handleTeamCreationError(data) {
    try {
      console.error("❌ TEAM CREATION ERROR:", data);

      this.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Team Creation Failed",
        message: data.error || "Failed to create team",
      });
    } catch (error) {
      this.logError("HANDLE_TEAM_CREATION_ERROR", error, { data });
    }
  }

  handleAuthSuccess(data) {
    try {
      console.log("✅ AUTH SUCCESS:", data);

      // Update current user info
      if (data.user_id) {
        localStorage.setItem("userId", data.user_id);
      }
      if (data.username) {
        localStorage.setItem("userName", data.username);
      }

      // Join user's team rooms
      if (data.rooms_joined && data.rooms_joined.length > 0) {
        console.log(`🏢 TEAM: Joined ${data.rooms_joined.length} rooms`);
      }
    } catch (error) {
      this.logError("HANDLE_AUTH_SUCCESS", error, { data });
    }
  }

  handleAuthError(data) {
    try {
      console.error("❌ AUTH ERROR:", data);

      this.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Authentication Failed",
        message: data.error || "Failed to authenticate",
      });
    } catch (error) {
      this.logError("HANDLE_AUTH_ERROR", error, { data });
    }
  }

  handleUserJoinedTeam(data) {
    try {
      console.log("👥 USER JOINED TEAM:", data);

      this.addActivityItem({
        type: "user_joined",
        user: data.username,
        timestamp: Date.now(),
        message: `${data.username} joined the team`,
      });

      this.showNotification({
        type: "info",
        icon: "user-plus",
        title: "New Team Member",
        message: `${data.username} joined the team`,
      });
    } catch (error) {
      this.logError("HANDLE_USER_JOINED_TEAM", error, { data });
    }
  }

  handleTeamJoinedSuccess(data) {
    try {
      console.log("✅ TEAM JOINED SUCCESS:", data);

      this.currentRoom = data.room;

      this.showNotification({
        type: "success",
        icon: "check-circle",
        title: "Team Joined",
        message: data.message || `Joined team "${data.team_name}"`,
      });
    } catch (error) {
      this.logError("HANDLE_TEAM_JOINED_SUCCESS", error, { data });
    }
  }

  // ===== SNIPPET SHARING EVENT HANDLERS =====

  handleSnippetShared(data) {
    try {
      console.log("📝 SNIPPET_SHARED:", data);

      this.addActivityItem({
        type: "snippet_shared",
        user: data.shared_by,
        timestamp: Date.now(),
        message: `${data.shared_by} shared snippet "${data.snippet_title}" with the team`,
      });

      this.showNotification({
        type: "info",
        icon: "share",
        title: "New Shared Snippet",
        message: `${data.shared_by} shared "${data.snippet_title}"`,
      });

      // Refresh team snippets if on team detail page
      if (window.location.pathname.includes("/teams/")) {
        this.refreshTeamSnippetsDisplay();
      }
    } catch (error) {
      this.logError("HANDLE_SNIPPET_SHARED", error, { data });
    }
  }

  handleSnippetUpdated(data) {
    try {
      console.log("✏️ SNIPPET_UPDATED:", data);

      this.addActivityItem({
        type: "snippet_updated",
        user: data.updated_by,
        timestamp: Date.now(),
        message: `${data.updated_by} updated snippet "${data.snippet_title}"`,
      });

      // Show live update indicator
      this.showLiveUpdateIndicator(data.snippet_id);
    } catch (error) {
      this.logError("HANDLE_SNIPPET_UPDATED", error, { data });
    }
  }

  handleSnippetPermissionsChanged(data) {
    try {
      console.log("🔧 SNIPPET_PERMISSIONS_CHANGED:", data);

      this.addActivityItem({
        type: "permissions_changed",
        user: data.changed_by,
        timestamp: Date.now(),
        message: `${data.changed_by} updated permissions for "${data.snippet_title}"`,
      });
    } catch (error) {
      this.logError("HANDLE_SNIPPET_PERMISSIONS_CHANGED", error, { data });
    }
  }

  handleTeamSnippetActivity(data) {
    try {
      console.log("📊 TEAM_SNIPPET_ACTIVITY:", data);

      // Update real-time activity indicators
      this.updateSnippetActivityIndicator(data.snippet_id, data.activity_type);
    } catch (error) {
      this.logError("HANDLE_TEAM_SNIPPET_ACTIVITY", error, { data });
    }
  }

  async loadTeamAnalytics(teamId) {
    try {
      console.log(`📊 ANALYTICS: Loading analytics for team ${teamId}`);

      const response = await fetch(`/api/v1/teams/${teamId}/analytics`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success) {
        console.log("✅ ANALYTICS: Data loaded successfully:", data.analytics);
        this.displayTeamAnalytics(teamId, data.analytics);
        return data.analytics;
      } else {
        throw new Error(data.message || "Analytics request failed");
      }
    } catch (error) {
      this.logError("LOAD_TEAM_ANALYTICS", error, { teamId });

      // Fallback to mock data
      const mockAnalytics = this.generateMockAnalytics();
      this.displayTeamAnalytics(teamId, mockAnalytics);
      return mockAnalytics;
    }
  }

  // ===== TEAM SNIPPET SHARING METHODS =====

  async shareSnippetWithTeam(snippetId, teamId, permissions = {}) {
    try {
      console.log(`🔗 SHARING: Snippet ${snippetId} with team ${teamId}`);

      const shareData = {
        snippet_id: snippetId,
        team_id: teamId,
        permissions: {
          allow_editing: permissions.allow_editing || true,
          allow_comments: permissions.allow_comments || true,
          require_approval: permissions.require_approval || false,
        },
      };

      const response = await fetch(`/api/snippets/${snippetId}/share`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "include",
        body: JSON.stringify(shareData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const result = await response.json();
      console.log("✅ SHARING: Snippet shared successfully:", result);

      // Send WebSocket notification
      this.sendSnippetSharedEvent(snippetId, teamId, shareData.permissions);

      this.showNotification({
        type: "success",
        icon: "share",
        title: "Snippet Shared",
        message: `Snippet shared with team successfully`,
      });

      return result;
    } catch (error) {
      this.logError("SHARE_SNIPPET_WITH_TEAM", error, { snippetId, teamId });

      this.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Share Failed",
        message: error.message || "Failed to share snippet",
      });

      throw error;
    }
  }

  async getTeamSnippets(teamId) {
    try {
      console.log(`📝 TEAM_SNIPPETS: Loading snippets for team ${teamId}`);

      const response = await fetch(`/api/teams/${teamId}/snippets`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success) {
        console.log(
          `✅ TEAM_SNIPPETS: Loaded ${data.snippets.length} snippets`
        );
        return data.snippets;
      } else {
        throw new Error(data.message || "Failed to load team snippets");
      }
    } catch (error) {
      this.logError("GET_TEAM_SNIPPETS", error, { teamId });
      return [];
    }
  }

  async updateSnippetPermissions(snippetId, teamId, permissions) {
    try {
      console.log(`🔧 PERMISSIONS: Updating snippet ${snippetId} permissions`);

      const response = await fetch(
        `/api/snippets/${snippetId}/teams/${teamId}/permissions`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
          credentials: "include",
          body: JSON.stringify({ permissions }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const result = await response.json();
      console.log("✅ PERMISSIONS: Updated successfully:", result);

      this.showNotification({
        type: "success",
        icon: "settings",
        title: "Permissions Updated",
        message: "Snippet permissions updated successfully",
      });

      return result;
    } catch (error) {
      this.logError("UPDATE_SNIPPET_PERMISSIONS", error, { snippetId, teamId });

      this.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Update Failed",
        message: error.message || "Failed to update permissions",
      });

      throw error;
    }
  }

  generateMockAnalytics() {
    return {
      overview: {
        snippet_count: Math.floor(Math.random() * 200) + 50,
        member_count: Math.floor(Math.random() * 10) + 3,
        collection_count: Math.floor(Math.random() * 20) + 5,
      },
      productivity_metrics: {
        efficiency: {
          snippets_per_day: Math.floor(Math.random() * 10) + 2,
        },
      },
      activity_data: Array.from({ length: 7 }, (_, i) => ({
        day: i,
        activity: Math.floor(Math.random() * 50) + 10,
      })),
    };
  }

  displayTeamAnalytics(analytics) {
    console.log("📊 ANALYTICS: Displaying team analytics:", analytics);

    // Update analytics dashboard
    const analyticsContainer = document.querySelector(".team-analytics");
    if (analyticsContainer) {
      analyticsContainer.innerHTML = `
            <div class="analytics-overview">
                <h3>Team Performance</h3>
                <div class="metrics-grid">
                    <div class="metric">
                        <span class="metric-value">${analytics.overview.snippet_count}</span>
                        <span class="metric-label">Total Snippets</span>
                    </div>
                    <div class="metric">
                        <span class="metric-value">${analytics.overview.member_count}</span>
                        <span class="metric-label">Active Members</span>
                    </div>
                    <div class="metric">
                        <span class="metric-value">${analytics.productivity_metrics.efficiency.snippets_per_day}</span>
                        <span class="metric-label">Snippets/Day</span>
                    </div>
                </div>
            </div>
        `;
    }
  }

  // WITH THIS:
  createCollaborationInterface() {
    // Skip UI creation on teams page - not needed for Step 1
    console.log("ℹ️ COLLABORATION: Skipping UI creation for teams page");
    return;
  }

  setupFloatingCursors() {
    this.cursorContainer = document.createElement("div");
    this.cursorContainer.className = "floating-cursors-container";
    document.body.appendChild(this.cursorContainer);
  }

  handleUserJoined(data) {
    this.activeUsers.set(data.userId, {
      id: data.userId,
      name: data.userName,
      avatar: data.userAvatar,
      color: data.userColor,
      status: "active",
      joinedAt: Date.now(),
    });

    this.updateActiveUsersList();
    this.showUserJoinedAnimation(data);
    this.addActivityItem({
      type: "user_joined",
      user: data.userName,
      timestamp: Date.now(),
      message: `${data.userName} joined the collaboration`,
    });
  }

  handleUserLeft(data) {
    this.activeUsers.delete(data.userId);
    this.cursors.delete(data.userId);
    this.updateActiveUsersList();
    this.removeUserCursor(data.userId);

    this.addActivityItem({
      type: "user_left",
      user: data.userName,
      timestamp: Date.now(),
      message: `${data.userName} left the collaboration`,
    });
  }

  handleCursorUpdate(data) {
    this.updateUserCursor(data.userId, data.position, data.selection);
  }

  handleTextChange(data) {
    if (data.userId !== this.getCurrentUserId()) {
      this.applyRemoteTextChange(data);
      this.showChangeIndicator(data.position);
    }
  }

  updateActiveUsersList() {
    const usersList = document.querySelector(".active-users-list");
    const userCount = document.querySelector(".user-count");

    userCount.textContent = this.activeUsers.size;

    usersList.innerHTML = "";
    this.activeUsers.forEach((user) => {
      const userElement = this.createUserAvatar(user);
      usersList.appendChild(userElement);
    });
  }

  createUserAvatar(user) {
    const avatar = document.createElement("div");
    avatar.className = "user-avatar active-user";
    avatar.style.setProperty("--user-color", user.color);
    avatar.innerHTML = `
            <div class="avatar-ring">
                <img src="${user.avatar}" alt="${user.name}" class="avatar-img">
                <div class="status-indicator ${user.status}"></div>
            </div>
            <div class="user-tooltip">
                <span class="user-name">${user.name}</span>
                <span class="user-status">${user.status}</span>
            </div>
        `;

    // Add hover effects
    avatar.addEventListener("mouseenter", () => {
      this.showUserTooltip(avatar, user);
    });

    return avatar;
  }

  updateUserCursor(userId, position, selection) {
    let cursor = this.cursors.get(userId);
    const user = this.activeUsers.get(userId);

    if (!cursor && user) {
      cursor = this.createFloatingCursor(user);
      this.cursors.set(userId, cursor);
    }

    if (cursor) {
      this.animateCursorTo(cursor, position);
      if (selection) {
        this.updateCursorSelection(cursor, selection);
      }
    }
  }

  createFloatingCursor(user) {
    const cursor = document.createElement("div");
    cursor.className = "floating-cursor";
    cursor.style.setProperty("--cursor-color", user.color);
    cursor.innerHTML = `
            <div class="cursor-line"></div>
            <div class="cursor-label">
                <span class="cursor-name">${user.name}</span>
                <div class="cursor-status"></div>
            </div>
        `;

    this.cursorContainer.appendChild(cursor);
    return cursor;
  }

  animateCursorTo(cursor, position) {
    // Convert text position to screen coordinates
    const coords = this.getScreenCoordinates(position);

    cursor.style.transform = `translate(${coords.x}px, ${coords.y}px)`;
    cursor.style.opacity = "1";

    // Auto-hide after inactivity
    clearTimeout(cursor.hideTimer);
    cursor.hideTimer = setTimeout(() => {
      cursor.style.opacity = "0.3";
    }, 3000);
  }

  // Add this method to handle team creation response properly
  addTeamCardToDOM(team) {
    console.log("🎯 COLLABORATION: Adding team card to DOM:", team);

    const teamsGrid = document.querySelector(".teams-grid");
    if (!teamsGrid) {
      console.error("❌ Teams grid not found");
      return;
    }

    // Validate team data to prevent undefined cards
    if (!team || !team.id || !team.name) {
      console.error("❌ Invalid team data - missing required fields:", team);
      this.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Display Error",
        message:
          "Team created but display data incomplete. Please refresh page.",
      });
      return;
    }

    // Create team card with complete data validation
    const teamCard = document.createElement("div");
    teamCard.className = "team-card hologram-effect";
    teamCard.setAttribute("data-team-id", team.id);

    // Ensure all data has fallbacks
    const teamData = {
      id: team.id,
      name: team.name || "Unnamed Team",
      description: team.description || "No description provided",
      avatar: team.avatar || team.name?.substring(0, 2).toUpperCase() || "TM",
      snippet_count: team.snippet_count || 0,
      member_count: team.member_count || 1,
      collection_count: team.collection_count || 0,
      user_role: team.user_role || "admin",
    };

    teamCard.innerHTML = `
        <div class="cyber-grid"></div>
        <div class="real-time-indicator"></div>
        <div class="team-header">
            <div class="team-avatar">${teamData.avatar}</div>
            <div class="team-menu" onclick="toggleTeamMenu(this, '${
              teamData.id
            }')">⚙️</div>
        </div>
        <h3 class="team-name">${teamData.name}</h3>
        <p class="team-description">${teamData.description}</p>
        
        <div class="team-stats">
            <div class="stat-item">
                <span class="stat-number">${teamData.snippet_count}</span>
                <span class="stat-label">Snippets</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${teamData.member_count}</span>
                <span class="stat-label">Members</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${teamData.collection_count}</span>
                <span class="stat-label">Collections</span>
            </div>
        </div>
        
        <div class="team-analytics-chart" id="chart-${teamData.id}"></div>
        
        <div class="collaboration-status">
            <div class="status-dot"></div>
            <span style="color: rgba(255,255,255,0.8); font-size: 0.8rem;">
                Role: ${teamData.user_role}
            </span>
        </div>
        
        <div class="team-members">
            <div class="member-avatar">${this.getCurrentUserInitials()}</div>
        </div>
        
        <div class="team-actions">
            <button class="action-btn" onclick="viewTeamSnippets('${
              teamData.id
            }')">View Snippets</button>
            <button class="action-btn primary" onclick="enterTeam('${
              teamData.id
            }')">Enter Team</button>
            <button class="action-btn danger" onclick="deleteTeam('${
              teamData.id
            }')" 
                    style="background: linear-gradient(135deg, #ff4757 0%, #ff3742 100%); border-color: #ff4757;">
                🗑️ Delete
            </button>
        </div>
    `;

    // Add cyberpunk effects
    this.addCyberpunkEffectsToCard(teamCard);

    // Insert at the beginning of the grid
    teamsGrid.insertBefore(teamCard, teamsGrid.firstChild);

    // Create chart with delay
    setTimeout(() => {
      this.createTeamChart(teamData.id);
    }, 100);

    console.log(`✅ Team card added successfully: ${teamData.name}`);
  }

  // In team-collaboration.js, update the handleCreateTeam method:

  async handleCreateTeam(teamData) {
    try {
      console.log("🏗️ Creating team:", teamData);

      const response = await fetch("/api/teams/auth", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "include",
        body: JSON.stringify(teamData),
      });

      console.log("📡 API Response status:", response.status);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          `HTTP ${response.status}: ${errorData.error || response.statusText}`
        );
      }

      const result = await response.json();
      console.log("✅ Team created successfully:", result);

      // Enhanced validation of response data
      if (result.success && result.data && result.data.team) {
        const teamData = result.data.team;
        console.log("✅ Team data for display:", teamData);

        // Add the new team card to DOM immediately
        this.addTeamCardToDOM(teamData);

        this.showNotification({
          type: "success",
          icon: "check-circle",
          title: "Team Created!",
          message: `Team "${teamData.name}" created successfully`,
        });

        this.closeCreateTeamModal();

        // Refresh the page after a short delay to ensure proper loading
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      } else {
        console.error("❌ Invalid response format:", result);
        throw new Error("Invalid response format from server");
      }

      return result;
    } catch (error) {
      this.logError("TEAM_CREATION", error, { teamData });

      this.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Team Creation Failed",
        message: error.message || "Failed to create team",
      });

      throw error;
    }
  }

  // Add this method to refresh teams list
  async refreshTeamsList() {
    try {
      console.log("🔄 Refreshing teams list...");

      const response = await fetch("/api/teams/auth", {
        method: "GET",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success && data.data && data.data.teams) {
        console.log(`✅ Refreshed teams list: ${data.data.teams.length} teams`);
        this.updateTeamsDisplay(data.data.teams);
      }
    } catch (error) {
      this.logError("REFRESH_TEAMS_LIST", error);
      console.warn("⚠️ Failed to refresh teams list:", error.message);
    }
  }

  // Add this method to update teams display
  updateTeamsDisplay(teams) {
    const teamsGrid = document.querySelector(".teams-grid");
    if (!teamsGrid) return;

    // Clear existing team cards (but keep any non-team elements)
    const existingCards = teamsGrid.querySelectorAll(".team-card");
    existingCards.forEach((card) => card.remove());

    if (teams.length === 0) {
      teamsGrid.innerHTML = `
            <div class="team-card" style="text-align: center; padding: 3rem;">
                <h3 style="color: white; margin-bottom: 1rem;">No Teams Yet</h3>
                <p style="color: rgba(255,255,255,0.7);">Create your first team to get started!</p>
                <button class="create-team-btn" onclick="openCreateTeamModal()" style="margin-top: 1rem;">
                    ➕ Create Your First Team
                </button>
            </div>
        `;
      return;
    }

    // Add all teams to display
    teams.forEach((team) => {
      this.addTeamCardToDOM(team);
    });
  }

  // Add this method to get current user initials
  getCurrentUserInitials() {
    try {
      const userName = this.getCurrentUserName();
      return userName
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .substring(0, 2);
    } catch (error) {
      return "U";
    }
  }

  // Add this method to add cyberpunk effects to cards
  addCyberpunkEffectsToCard(card) {
    card.addEventListener("mouseenter", () => {
      card.style.animation = "glitch 0.3s ease-in-out";
    });

    card.addEventListener("mouseleave", () => {
      card.style.animation = "";
    });

    // Add mouse tracking glow
    card.addEventListener("mousemove", function (e) {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      card.style.background = `
            radial-gradient(circle at ${x}px ${y}px, 
                rgba(0, 212, 255, 0.2) 0%, 
                rgba(255, 255, 255, 0.1) 50%, 
                transparent 100%),
            linear-gradient(135deg, 
                rgba(255, 255, 255, 0.1) 0%, 
                rgba(0, 212, 255, 0.05) 50%, 
                rgba(255, 255, 255, 0.1) 100%)
        `;
    });

    card.addEventListener("mouseleave", function () {
      card.style.background = `
            linear-gradient(135deg, 
                rgba(255, 255, 255, 0.1) 0%, 
                rgba(0, 212, 255, 0.05) 50%, 
                rgba(255, 255, 255, 0.1) 100%)
        `;
    });
  }

  // Add this method to create team charts
  createTeamChart(teamId) {
    const chartContainer = document.getElementById(`chart-${teamId}`);
    if (!chartContainer) {
      console.warn(`⚠️ Chart container not found for team ${teamId}`);
      return;
    }

    try {
      // Check if D3 is available
      if (typeof d3 === "undefined") {
        console.warn("⚠️ D3.js not loaded, skipping chart creation");
        chartContainer.innerHTML =
          '<div style="text-align: center; color: rgba(255,255,255,0.5); padding: 20px;">Chart loading...</div>';
        return;
      }

      const data = Array.from({ length: 7 }, (_, i) => ({
        day: i,
        activity: Math.floor(Math.random() * 50) + 10,
      }));

      const width = chartContainer.offsetWidth;
      const height = 100;
      const margin = { top: 10, right: 10, bottom: 20, left: 10 };

      // Clear existing chart
      d3.select(chartContainer).selectAll("*").remove();

      const svg = d3
        .select(chartContainer)
        .append("svg")
        .attr("width", width)
        .attr("height", height);

      const xScale = d3
        .scaleLinear()
        .domain([0, 6])
        .range([margin.left, width - margin.right]);

      const yScale = d3
        .scaleLinear()
        .domain([0, d3.max(data, (d) => d.activity)])
        .range([height - margin.bottom, margin.top]);

      const line = d3
        .line()
        .x((d) => xScale(d.day))
        .y((d) => yScale(d.activity))
        .curve(d3.curveCardinal);

      const gradient = svg
        .append("defs")
        .append("linearGradient")
        .attr("id", `gradient-${teamId}`)
        .attr("gradientUnits", "userSpaceOnUse")
        .attr("x1", 0)
        .attr("y1", height)
        .attr("x2", 0)
        .attr("y2", 0);

      gradient
        .append("stop")
        .attr("offset", "0%")
        .attr("stop-color", "#00d4ff")
        .attr("stop-opacity", 0);

      gradient
        .append("stop")
        .attr("offset", "100%")
        .attr("stop-color", "#00d4ff")
        .attr("stop-opacity", 0.8);

      const area = d3
        .area()
        .x((d) => xScale(d.day))
        .y0(height - margin.bottom)
        .y1((d) => yScale(d.activity))
        .curve(d3.curveCardinal);

      svg
        .append("path")
        .datum(data)
        .attr("fill", `url(#gradient-${teamId})`)
        .attr("d", area);

      svg
        .append("path")
        .datum(data)
        .attr("fill", "none")
        .attr("stroke", "#00d4ff")
        .attr("stroke-width", 2)
        .attr("d", line);

      console.log(`✅ Chart created for team ${teamId}`);
    } catch (error) {
      this.logError("CREATE_TEAM_CHART", error, { teamId });
      chartContainer.innerHTML =
        '<div style="text-align: center; color: rgba(255,255,255,0.5); padding: 20px;">Chart unavailable</div>';
    }
  }

  showInviteMemberModal() {
    const modal = document.createElement("div");
    modal.className = "modal-overlay active";
    modal.innerHTML = `
            <div class="modal-content modern-card">
                <div class="modal-header">
                    <h2>Invite Team Member</h2>
                    <button class="btn-close" onclick="this.closest('.modal-overlay').remove()">
                        <i class="icon-x"></i>
                    </button>
                </div>
                
                <div class="modal-body">
                    <div class="invite-methods">
                        <div class="invite-method active" data-method="email">
                            <i class="icon-mail"></i>
                            <span>Email Invitation</span>
                        </div>
                        <div class="invite-method" data-method="link">
                            <i class="icon-link"></i>
                            <span>Share Link</span>
                        </div>
                    </div>
                    
                    <div class="invite-form" id="email-invite">
                        <div class="form-group">
                            <label>Email Address</label>
                            <input type="email" placeholder="colleague@company.com" class="form-input">
                        </div>
                        <div class="form-group">
                            <label>Permission Level</label>
                            <select class="form-select">
                                <option value="view">View Only</option>
                                <option value="edit">Can Edit</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Personal Message (Optional)</label>
                            <textarea placeholder="Join our team collaboration..." class="form-textarea"></textarea>
                        </div>
                    </div>
                    
                    <div class="invite-form hidden" id="link-invite">
                        <div class="share-link-container">
                            <input type="text" readonly value="https://app.snippetmanager.com/invite/abc123" 
                                   class="share-link-input">
                            <button class="btn-copy" onclick="this.previousElementSibling.select(); document.execCommand('copy')">
                                <i class="icon-copy"></i>
                            </button>
                        </div>
                        <div class="link-settings">
                            <label class="checkbox-label">
                                <input type="checkbox" checked>
                                <span class="checkbox-custom"></span>
                                Link expires in 7 days
                            </label>
                        </div>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn-primary" onclick="teamCollaboration.sendInvitation()">
                        <i class="icon-send"></i>
                        Send Invitation
                    </button>
                </div>
            </div>
        `;

    document.body.appendChild(modal);
    this.setupInviteModalEvents(modal);
  }

  addActivityItem(activity) {
    this.activityFeed.unshift(activity);
    const timeline = document.querySelector(".timeline-content");

    const activityElement = document.createElement("div");
    activityElement.className = `activity-item ${activity.type}`;
    activityElement.innerHTML = `
            <div class="activity-avatar">
                <div class="activity-icon">
                    <i class="icon-${this.getActivityIcon(activity.type)}"></i>
                </div>
            </div>
            <div class="activity-content">
                <div class="activity-message">${activity.message}</div>
                <div class="activity-time">${this.formatRelativeTime(
                  activity.timestamp
                )}</div>
            </div>
        `;

    timeline.insertBefore(activityElement, timeline.firstChild);
    this.animateElementIn(activityElement);

    // Remove old activities (keep last 50)
    if (this.activityFeed.length > 50) {
      this.activityFeed.splice(50);
      const oldElements = timeline.querySelectorAll(".activity-item");
      if (oldElements.length > 50) {
        oldElements[oldElements.length - 1].remove();
      }
    }
  }

  setupNotificationCenter() {
    const notificationCenter = document.createElement("div");
    notificationCenter.className = "notification-center";
    notificationCenter.id = "notification-center";
    document.body.appendChild(notificationCenter);
  }

  // ADD THESE METHODS after existing integration methods (around line 700):

  sendTeamCreatedEvent(teamData) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = {
          type: "team_created",
          team: teamData,
          userId: this.getCurrentUserId(),
          timestamp: Date.now(),
        };

        console.log("📤 WEBSOCKET: Sending team created event:", message);
        this.socket.send(JSON.stringify(message));
      } else {
        this.logError(
          "SEND_TEAM_CREATED",
          new Error("WebSocket not connected"),
          { teamData }
        );
      }
    } catch (error) {
      this.logError("SEND_TEAM_CREATED", error, { teamData });
    }
  }

  sendJoinTeamEvent(teamId) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = {
          type: "join_team",
          teamId: teamId,
          userId: this.getCurrentUserId(),
          timestamp: Date.now(),
        };

        console.log("📤 WEBSOCKET: Sending join team event:", message);
        this.socket.send(JSON.stringify(message));
      } else {
        this.logError("SEND_JOIN_TEAM", new Error("WebSocket not connected"), {
          teamId,
        });
      }
    } catch (error) {
      this.logError("SEND_JOIN_TEAM", error, { teamId });
    }
  }

  getDebugInfo() {
    return {
      isInitialized: this.isInitialized,
      socketState: this.socket ? this.socket.readyState : "null",
      currentRoom: this.currentRoom,
      activeUsers: this.activeUsers.size,
      reconnectAttempts: this.reconnectAttempts,
      errorCount: this.errorLog.length,
      lastErrors: this.errorLog.slice(-5),
    };
  }

  exportErrorLog() {
    const blob = new Blob([JSON.stringify(this.errorLog, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `team-collaboration-errors-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  showNotification(notification) {
    const notif = document.createElement("div");
    notif.className = `notification ${notification.type} slide-in`;
    notif.innerHTML = `
            <div class="notification-content">
                <div class="notification-icon">
                    <i class="icon-${notification.icon}"></i>
                </div>
                <div class="notification-text">
                    <div class="notification-title">${notification.title}</div>
                    <div class="notification-message">${notification.message}</div>
                </div>
            </div>
            <button class="notification-close" onclick="this.parentElement.remove()">
                <i class="icon-x"></i>
            </button>
        `;

    document.getElementById("notification-center").appendChild(notif);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (notif.parentElement) {
        notif.classList.add("slide-out");
        setTimeout(() => notif.remove(), 300);
      }
    }, 5000);
  }

  // Utility functions
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
  }

  animateElementIn(element) {
    element.style.opacity = "0";
    element.style.transform = "translateY(20px) scale(0.95)";

    requestAnimationFrame(() => {
      element.style.transition = "all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)";
      element.style.opacity = "1";
      element.style.transform = "translateY(0) scale(1)";
    });
  }

  formatRelativeTime(timestamp) {
    const now = Date.now();
    const diff = now - timestamp;

    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return `${Math.floor(diff / 86400000)}d ago`;
  }

  getCurrentUserId() {
    try {
      // Try multiple sources for user ID
      return (
        localStorage.getItem("userId") ||
        sessionStorage.getItem("userId") ||
        document.querySelector('meta[name="user-id"]')?.content ||
        "anonymous_" + Math.random().toString(36).substr(2, 9)
      );
    } catch (error) {
      this.logError("GET_USER_ID", error);
      return "anonymous_" + Math.random().toString(36).substr(2, 9);
    }
  }

  getCurrentUserName() {
    try {
      return (
        localStorage.getItem("userName") ||
        sessionStorage.getItem("userName") ||
        "Anonymous User"
      );
    } catch (error) {
      this.logError("GET_USER_NAME", error);
      return "Anonymous User";
    }
  } // ===== SNIPPET SHARING HELPER METHODS =====

  refreshTeamSnippetsDisplay() {
    // Refresh team snippets display if on team detail page
    if (typeof loadTeamSnippets === "function") {
      loadTeamSnippets();
    }
  }

  showLiveUpdateIndicator(snippetId) {
    const snippetElement = document.querySelector(
      `[data-snippet-id="${snippetId}"]`
    );
    if (snippetElement) {
      const indicator = document.createElement("div");
      indicator.className = "live-update-indicator";
      indicator.innerHTML = "🔴 Live Update";
      indicator.style.cssText = `
      position: absolute;
      top: 10px;
      right: 10px;
      background: #ff4757;
      color: white;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 0.8rem;
      z-index: 10;
    `;

      snippetElement.style.position = "relative";
      snippetElement.appendChild(indicator);

      // Remove after 3 seconds
      setTimeout(() => indicator.remove(), 3000);
    }
  }

  updateSnippetActivityIndicator(snippetId, activityType) {
    const snippetElement = document.querySelector(
      `[data-snippet-id="${snippetId}"]`
    );
    if (snippetElement) {
      const activityDot =
        snippetElement.querySelector(".activity-dot") ||
        document.createElement("div");

      activityDot.className = "activity-dot";
      activityDot.style.cssText = `
      width: 8px;
      height: 8px;
      background: #00d4ff;
      border-radius: 50%;
      position: absolute;
      top: 5px;
      left: 5px;
      animation: pulse 1s infinite;
    `;

      if (!snippetElement.querySelector(".activity-dot")) {
        snippetElement.appendChild(activityDot);
      }

      // Remove after 5 seconds
      setTimeout(() => activityDot.remove(), 5000);
    }
  }

  getActivityIcon(type) {
    const icons = {
      user_joined: "user-plus",
      user_left: "user-minus",
      text_change: "edit",
      comment: "message-circle",
      share: "share",
      create: "plus",
      delete: "trash",
    };
    return icons[type] || "activity";
  }

  broadcastTextChange(data) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = {
          type: "text_change",
          roomId: this.currentRoom,
          userId: this.getCurrentUserId(),
          timestamp: Date.now(),
          ...data,
        };

        console.log("📤 WEBSOCKET: Broadcasting text change:", message);
        this.socket.send(JSON.stringify(message));
      } else {
        this.logError(
          "BROADCAST_TEXT_CHANGE",
          new Error("WebSocket not connected"),
          { data }
        );
      }
    } catch (error) {
      this.logError("BROADCAST_TEXT_CHANGE", error, { data });
    }
  }

  broadcastCursorPosition(data) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = {
          type: "cursor_update",
          roomId: this.currentRoom,
          userId: this.getCurrentUserId(),
          timestamp: Date.now(),
          ...data,
        };

        this.socket.send(JSON.stringify(message));
      } else {
        console.warn("⚠️ WEBSOCKET: Cannot broadcast cursor - not connected");
      }
    } catch (error) {
      this.logError("BROADCAST_CURSOR", error, { data });
    }
  }

  broadcastUserActivity(activity) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = {
          type: "user_activity",
          roomId: this.currentRoom,
          userId: this.getCurrentUserId(),
          activity: activity,
          timestamp: Date.now(),
        };

        console.log("📤 WEBSOCKET: Broadcasting user activity:", message);
        this.socket.send(JSON.stringify(message));
      }
    } catch (error) {
      this.logError("BROADCAST_ACTIVITY", error, { activity });
    }
  }
  // ===== SNIPPET SHARING WEBSOCKET METHODS =====

  sendSnippetSharedEvent(snippetId, teamId, permissions) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = {
          type: "snippet_shared",
          snippet_id: snippetId,
          team_id: teamId,
          permissions: permissions,
          shared_by: this.getCurrentUserName(),
          user_id: this.getCurrentUserId(),
          timestamp: Date.now(),
        };

        console.log("📤 WEBSOCKET: Sending snippet shared event:", message);
        this.socket.send(JSON.stringify(message));
      }
    } catch (error) {
      this.logError("SEND_SNIPPET_SHARED_EVENT", error, { snippetId, teamId });
    }
  }

  sendSnippetUpdateEvent(snippetId, teamId, updateType) {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = {
          type: "snippet_updated",
          snippet_id: snippetId,
          team_id: teamId,
          update_type: updateType,
          updated_by: this.getCurrentUserName(),
          user_id: this.getCurrentUserId(),
          timestamp: Date.now(),
        };

        console.log("📤 WEBSOCKET: Sending snippet update event:", message);
        this.socket.send(JSON.stringify(message));
      }
    } catch (error) {
      this.logError("SEND_SNIPPET_UPDATE_EVENT", error, { snippetId, teamId });
    }
  }

  showConnectionStatus(status) {
    const indicator = document.querySelector(".pulse-dot");
    if (indicator) {
      indicator.className = `pulse-dot ${status}`;
    }
  }

  attemptReconnection() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("❌ WEBSOCKET: Max reconnection attempts reached");
      this.logError(
        "WEBSOCKET_RECONNECT_FAILED",
        new Error("Max attempts reached"),
        {
          attempts: this.reconnectAttempts,
        }
      );
      this.showConnectionStatus("failed");
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000); // Exponential backoff, max 30s

    console.log(
      `🔄 WEBSOCKET: Attempting reconnection ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`
    );

    setTimeout(() => {
      if (!this.isInitialized) {
        this.initWebSocket();
      }
    }, delay);
  }

  startHeartbeat() {
    setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);
  }

  // Integration methods for teams.html
  joinTeamRoom(teamId) {
    try {
      console.log(`🏢 TEAM: Joining team room ${teamId}`);
      this.currentRoom = `team_${teamId}`;

      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(
          JSON.stringify({
            type: "join_room",
            roomId: this.currentRoom,
            teamId: teamId,
            userId: this.getCurrentUserId(),
            userName: this.getCurrentUserName(),
            timestamp: Date.now(),
          })
        );
      } else {
        this.logError("JOIN_TEAM_ROOM", new Error("WebSocket not connected"), {
          teamId,
        });
      }
    } catch (error) {
      this.logError("JOIN_TEAM_ROOM", error, { teamId });
    }
  }

  leaveTeamRoom() {
    try {
      if (
        this.currentRoom &&
        this.socket &&
        this.socket.readyState === WebSocket.OPEN
      ) {
        console.log(`🚪 TEAM: Leaving room ${this.currentRoom}`);

        this.socket.send(
          JSON.stringify({
            type: "leave_room",
            roomId: this.currentRoom,
            userId: this.getCurrentUserId(),
            timestamp: Date.now(),
          })
        );

        this.currentRoom = null;
      }
    } catch (error) {
      this.logError("LEAVE_TEAM_ROOM", error);
    }
  }

  updateTeamPresence(teamId, status = "active") {
    try {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(
          JSON.stringify({
            type: "presence_update",
            teamId: teamId,
            userId: this.getCurrentUserId(),
            status: status,
            timestamp: Date.now(),
          })
        );
      }
    } catch (error) {
      this.logError("UPDATE_TEAM_PRESENCE", error, { teamId, status });
    }
  }

  // ADD ALL THE MISSING METHODS HERE:
  initActivityFeed() {
    // Skip for teams page
    console.log("ℹ️ COLLABORATION: Activity feed not needed for teams page");
  }

  createPresenceIndicators() {
    // Skip for teams page
    console.log(
      "ℹ️ COLLABORATION: Presence indicators not needed for teams page"
    );
  }

  setupInviteModalEvents(modal) {
    // Basic modal event setup
    const methods = modal.querySelectorAll(".invite-method");
    methods.forEach((method) => {
      method.addEventListener("click", () => {
        methods.forEach((m) => m.classList.remove("active"));
        method.classList.add("active");
      });
    });
  }

  sendInvitation() {
    console.log("📧 COLLABORATION: Send invitation clicked");
    this.showNotification({
      type: "info",
      icon: "mail",
      title: "Feature Coming Soon",
      message: "Team invitations will be available in Step 2",
    });
  }

  getJWTToken() {
    try {
      // Method 1: Check meta tag
      const metaToken = document.querySelector(
        'meta[name="csrf-token"]'
      )?.content;
      if (metaToken) return metaToken;

      // Method 2: Check cookies for Flask-JWT token
      const cookies = document.cookie.split(";");
      for (let cookie of cookies) {
        const [name, value] = cookie.trim().split("=");
        if (name === "access_token_cookie" || name === "csrf_access_token") {
          return decodeURIComponent(value);
        }
      }

      // Method 3: Extract from session cookie
      const sessionCookie = cookies.find((c) =>
        c.trim().startsWith("session=")
      );
      if (sessionCookie) {
        console.log("🔐 Using session-based auth");
        return "session_auth";
      }

      console.warn("⚠️ No JWT token found");
      return null;
    } catch (error) {
      this.logError("GET_JWT_TOKEN", error);
      return null;
    }
  }

  getScreenCoordinates(position) {
    // Mock implementation for cursor positioning
    return { x: 0, y: 0 };
  }

  applyRemoteTextChange(data) {
    console.log("📝 COLLABORATION: Remote text change received:", data);
  }

  showChangeIndicator(position) {
    console.log("💫 COLLABORATION: Change indicator at position:", position);
  }

  removeUserCursor(userId) {
    console.log("🖱️ COLLABORATION: Removing cursor for user:", userId);
  }

  showUserJoinedAnimation(data) {
    console.log("🎉 COLLABORATION: User joined animation:", data.userName);
  }

  showUserTooltip(avatar, user) {
    console.log("💬 COLLABORATION: Showing tooltip for:", user.name);
  }

  updateCursorSelection(cursor, selection) {
    console.log("🖱️ COLLABORATION: Updating cursor selection:", selection);
  }
}

// ADD THESE FUNCTIONS TO HANDLE MEMBER MANAGEMENT

async function updateMemberRole(teamId, memberId, newRole) {
  try {
    console.log(
      `🔧 UPDATE_ROLE JS: Team ${teamId}, Member ${memberId}, Role ${newRole}`
    );

    const response = await fetch(
      `/api/teams/${teamId}/members/${memberId}/role`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "include",
        body: JSON.stringify({ role: newRole }),
      }
    );

    console.log(`📡 UPDATE_ROLE JS: Response status ${response.status}`);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    const result = await response.json();
    console.log("✅ UPDATE_ROLE JS: Success:", result);

    // Show success notification
    if (window.teamCollaboration) {
      window.teamCollaboration.showNotification(
        `Member role updated to ${newRole.toUpperCase()}`,
        "success"
      );
    }

    // 🔥 CRITICAL: Refresh the members list to show updated role
    await loadTeamMembers(teamId);

    // Remove any open dropdown
    document.querySelector(".role-change-dropdown")?.remove();
    document.querySelector(".modal-overlay")?.remove();

    return result;
  } catch (error) {
    console.error("❌ UPDATE_ROLE JS ERROR:", error);

    if (window.teamCollaboration) {
      window.teamCollaboration.showNotification(
        error.message || "Failed to update member role",
        "error"
      );
    }

    throw error;
  }
}

async function removeMember(teamId, userId) {
  try {
    console.log(
      `🗑️ REMOVE_MEMBER: Removing user ${userId} from team ${teamId}`
    );

    const response = await fetch(`/api/teams/${teamId}/members/${userId}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "include",
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    const result = await response.json();
    console.log("✅ REMOVE_MEMBER: Success:", result);

    // 🔥 REFRESH THE MEMBERS LIST IMMEDIATELY
    await refreshTeamMembers(teamId);

    // Show success notification
    if (window.teamCollaboration) {
      window.teamCollaboration.showNotification({
        type: "success",
        icon: "check-circle",
        title: "Member Removed",
        message: "Team member removed successfully",
      });
    }

    return result;
  } catch (error) {
    console.error("❌ REMOVE_MEMBER ERROR:", error);

    if (window.teamCollaboration) {
      window.teamCollaboration.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Remove Failed",
        message: error.message || "Failed to remove team member",
      });
    }

    throw error;
  }
}

async function refreshTeamMembers(teamId) {
  try {
    console.log(`🔄 REFRESH_MEMBERS: Refreshing members for team ${teamId}`);

    const response = await fetch(`/api/teams/${teamId}/members`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "include",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (data.success && data.data && data.data.members) {
      console.log(
        `✅ REFRESH_MEMBERS: Got ${data.data.members.length} members`
      );
      updateMembersDisplay(data.data.members);
    }
  } catch (error) {
    console.error("❌ REFRESH_MEMBERS ERROR:", error);
  }
}

function updateMembersDisplay(members) {
  const membersList = document.querySelector(".team-members-list");
  if (!membersList) {
    console.warn("⚠️ Members list container not found");
    return;
  }

  membersList.innerHTML = "";

  members.forEach((member) => {
    const memberElement = document.createElement("div");
    memberElement.className = "team-member-item";
    memberElement.innerHTML = `
            <div class="member-info">
                <div class="member-avatar">${member.name
                  .substring(0, 2)
                  .toUpperCase()}</div>
                <div class="member-details">
                    <div class="member-name">${member.name}</div>
                    <div class="member-email">${member.email}</div>
                </div>
            </div>
            <div class="member-role">
                <span class="role-badge ${member.role.toLowerCase()}">${
      member.role
    }</span>
            </div>
            <div class="member-actions">
                ${
                  member.role !== "OWNER"
                    ? `
                    <button class="btn-edit-role" onclick="showEditRoleModal('${
                      member.user_id
                    }', '${member.role}')">
                        Edit Role
                    </button>
                    <button class="btn-remove-member" onclick="removeMember('${getCurrentTeamId()}', '${
                        member.user_id
                      }')">
                        Remove
                    </button>
                `
                    : '<span class="owner-label">Team Owner</span>'
                }
            </div>
        `;

    membersList.appendChild(memberElement);
  });

  console.log(
    `✅ MEMBERS_DISPLAY: Updated display with ${members.length} members`
  );
}

function getCurrentTeamId() {
  // Extract team ID from URL or data attribute
  const urlParts = window.location.pathname.split("/");
  const teamIndex = urlParts.indexOf("teams");
  if (teamIndex !== -1 && urlParts[teamIndex + 1]) {
    return urlParts[teamIndex + 1];
  }

  // Fallback: check data attribute
  const teamElement = document.querySelector("[data-team-id]");
  return teamElement ? teamElement.dataset.teamId : null;
}

// ADD THIS FUNCTION - Missing enterTeam function
function enterTeam(teamId) {
  try {
    console.log(`🚀 ENTER_TEAM: Navigating to team ${teamId}`);

    if (!teamId) {
      console.error("❌ ENTER_TEAM: No team ID provided");
      if (window.teamCollaboration) {
        window.teamCollaboration.showNotification({
          type: "error",
          icon: "alert-circle",
          title: "Navigation Error",
          message: "Invalid team ID",
        });
      }
      return;
    }

    // Navigate to team detail page
    const targetUrl = `/api/teams/detail/${teamId}`;
    console.log(`🎯 ENTER_TEAM: Navigating to ${targetUrl}`);

    window.location.href = targetUrl;
  } catch (error) {
    console.error("❌ ENTER_TEAM ERROR:", error);
    if (window.teamCollaboration) {
      window.teamCollaboration.logError("ENTER_TEAM_FUNCTION", error, {
        teamId,
      });
      window.teamCollaboration.showNotification({
        type: "error",
        icon: "alert-circle",
        title: "Navigation Failed",
        message: "Failed to enter team",
      });
    }
  }
}

// Add this function to fix loading delays
function preloadTeamMembers() {
  console.log("🔄 PRELOADING: Starting team members preload...");

  fetch("/api/teams/preload-members", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        console.log("✅ PRELOADING: Team members preloaded successfully");
        // Trigger teams reload after preloading
        if (typeof loadUserTeams === "function") {
          setTimeout(() => loadUserTeams(), 500);
        }
      } else {
        console.error("❌ PRELOADING: Failed to preload team members");
      }
    })
    .catch((error) => {
      console.error("❌ PRELOADING ERROR:", error);
    });
}

// Auto-preload on page load
document.addEventListener("DOMContentLoaded", function () {
  // Preload team members when page loads
  setTimeout(() => preloadTeamMembers(), 1000);
});

// Make enterTeam globally available
window.enterTeam = enterTeam;
// Fix: Check if functions exist before assignment
window.viewTeamSnippets =
  window.viewTeamSnippets ||
  function (teamId) {
    try {
      console.log(`📝 VIEW_SNIPPETS: Team ${teamId}`);
      if (window.teamCollaboration) {
        window.teamCollaboration.logTeamAction("VIEW_SNIPPETS", teamId);
      }
      // Placeholder for future implementation
      alert(`View snippets for team: ${teamId} - Feature coming soon!`);
    } catch (error) {
      console.error("❌ VIEW_SNIPPETS ERROR:", error);
      if (window.teamCollaboration) {
        window.teamCollaboration.logError("VIEW_SNIPPETS_FUNCTION", error, {
          teamId,
        });
      }
    }
  };

window.deleteTeam =
  window.deleteTeam ||
  function (teamId) {
    try {
      console.log(`🗑️ DELETE_TEAM: Team ${teamId}`);
      if (window.teamCollaboration) {
        window.teamCollaboration.logTeamAction("DELETE_TEAM", teamId);
      }

      if (confirm(`Are you sure you want to delete this team?`)) {
        // Placeholder for future implementation
        alert(`Delete team: ${teamId} - Feature coming soon!`);
      }
    } catch (error) {
      console.error("❌ DELETE_TEAM ERROR:", error);
      if (window.teamCollaboration) {
        window.teamCollaboration.logError("DELETE_TEAM_FUNCTION", error, {
          teamId,
        });
      }
    }
  };

// Make functions globally available
window.updateMemberRole = updateMemberRole;
window.removeMember = removeMember;
window.refreshTeamMembers = refreshTeamMembers;

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.teamCollaboration = new TeamCollaboration();
});
// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  try {
    window.teamCollaboration = new TeamCollaboration();
    console.log("✅ TEAM_COLLABORATION: Successfully initialized");

    // Add global debug access
    window.debugTeamCollaboration = () => {
      console.log(
        "🔍 TEAM_COLLABORATION DEBUG INFO:",
        window.teamCollaboration.getDebugInfo()
      );
    };

    window.exportTeamCollaborationErrors = () => {
      window.teamCollaboration.exportErrorLog();
    };
  } catch (error) {
    console.error("❌ TEAM_COLLABORATION: Initialization failed:", error);
  }
});

// CSS Variables for dynamic theming
document.documentElement.style.setProperty(
  "--collaboration-primary",
  "#6366f1"
);
document.documentElement.style.setProperty(
  "--collaboration-secondary",
  "#8b5cf6"
);
document.documentElement.style.setProperty(
  "--collaboration-success",
  "#10b981"
);
document.documentElement.style.setProperty(
  "--collaboration-warning",
  "#f59e0b"
);
document.documentElement.style.setProperty("--collaboration-error", "#ef4444");

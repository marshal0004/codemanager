/**
 * Collaborative Editor - Real-time Multi-user Code Editing
 * Handles: Text synchronization, Cursor tracking, User presence, Comments
 */

class CollaborativeEditor {
  constructor(editorElement, options = {}) {
    this.editor = editorElement;
    this.socket = options.socket;
    this.snippetId = options.snippetId;
    this.teamId = options.teamId;
    this.userId = options.userId;
    this.username = options.username;

    // Collaboration state
    this.activeUsers = new Map();
    this.userCursors = new Map();
    this.isTyping = false;
    this.typingTimeout = null;
    this.lastContent = "";
    this.userColor = options.userColor || "#FF6B6B";

    // Debounce timers
    this.changeTimeout = null;
    this.cursorTimeout = null;

    this.init();
  }

  init() {
    console.log("🚀 Initializing Collaborative Editor");
    this.setupEventListeners();
    this.setupSocketEvents();
    this.joinEditingSession();
    this.optimizePerformance(); // ✅ ADD THIS LINE
    this.startTimestampUpdater(); // ✅ ADD THIS LINE
    this.setupDOMProtection(); // ✅ ADD THIS LINE
  }

  // ===== SOCKET EVENTS =====
  setupSocketEvents() {
    if (!this.socket) {
      console.error("❌ No socket provided to collaborative editor");
      return;
    }

    // ✅ NEW: Only essential events for smart state system
    this.socket.on("user_joined_editing", (data) => {
      console.log("👤 User joined editing:", data);
      this.handleUserJoined(data);
    });

    this.socket.on("user_left_editing", (data) => {
      console.log("👋 User left editing:", data);
      this.handleUserLeft(data);
    });

    // ✅ NEW: Smart state updates (replaces live_code_updated, typing_status_updated)
    this.socket.on("user_state_updated", (data) => {
      console.log("🔄 User state updated:", data);
      this.handleUserStateUpdate(data);
    });

    // Comments
    this.socket.on("comment_added", (data) => {
      console.log("💬 Comment added:", data);
      this.handleCommentAdded(data);
    });

    // Snippet content sync
    this.socket.on("snippet_content_sync", (data) => {
      console.log("🔄 Content sync:", data);
      this.handleContentSync(data);
    });
  }

  // ===== ENHANCED: HANDLE USER STATE UPDATES =====
  handleUserStateUpdate(data) {
    if (data.user_id === this.userId) return; // Ignore self

    const userId = data.user_id;
    const username = data.username;
    const state = data.state;
    const line = data.line;

    console.log(`🔄 Processing state: ${username} is ${state}`);

    // ✅ ENHANCED DEBUG: Check DOM state thoroughly
    const usersBefore = document.querySelectorAll(".user-item").length;
    console.log(`🔍 DEBUG: Users in sidebar BEFORE: ${usersBefore}`);

    // ✅ NEW: Check if element exists but is detached
    const userElement = document.getElementById(`user-${userId}`);
    console.log(`🔍 DEBUG: Element exists: ${!!userElement}`);

    if (userElement) {
      console.log(
        `🔍 DEBUG: Element parent: ${userElement.parentElement?.className}`
      );
      console.log(
        `🔍 DEBUG: Element in document: ${document.contains(userElement)}`
      );
      console.log(`🔍 DEBUG: Element classes: ${userElement.className}`);
      console.log(
        `🔍 DEBUG: Element style display: ${userElement.style.display}`
      );

      // ✅ CRITICAL FIX: Re-attach if detached
      if (!document.contains(userElement)) {
        console.log(`🚨 Element detached! Re-attaching...`);
        const usersSection = document.querySelector(".users-section");
        if (usersSection) {
          usersSection.appendChild(userElement);
          console.log(`✅ Re-attached user ${username}`);
        }
      }

      // ✅ FIXED: Update user activity in sidebar
      const activityElement = userElement.querySelector(".user-activity");
      if (activityElement) {
        if (state === "typing") {
          activityElement.textContent = `⌨️ Typing on line ${line}`;
          activityElement.style.color = "#00ff80";
        } else if (state === "editing") {
          activityElement.textContent = "🔴 Currently editing";
          activityElement.style.color = "#ff6b6b";
        } else if (state === "viewing") {
          activityElement.textContent = "👁️ Viewing";
          activityElement.style.color = "#68a2eb";
        }
      }

      // ✅ FIXED: Update user status indicator
      const statusElement = userElement.querySelector(".user-status");
      if (statusElement) {
        if (state === "typing") {
          statusElement.classList.add("typing-animation");
        } else {
          statusElement.classList.remove("typing-animation");
        }
      }
    } else {
      // ✅ CRITICAL FIX: Re-create missing user
      console.log(`🚨 User ${username} missing! Re-creating...`);
      this.addUserToSidebar({
        user_id: userId,
        username: username,
        color: "#FF6B6B",
      });
    }

    // ✅ ENHANCED DEBUG: List all users with their DOM state
    document.querySelectorAll(".user-item").forEach((user, index) => {
      const userName = user.querySelector(".user-name")?.textContent;
      const isInDocument = document.contains(user);
      const hasParent = !!user.parentElement;
      console.log(
        `🔍 DEBUG: User ${index}: ${userName}, InDoc: ${isInDocument}, HasParent: ${hasParent}`
      );
    });

    const usersAfter = document.querySelectorAll(".user-item").length;
    console.log(`🔍 DEBUG: Users in sidebar AFTER: ${usersAfter}`);

    // ✅ DEBUG: Check if any users were removed
    if (usersBefore !== usersAfter) {
      console.log(
        `🚨 DEBUG: USER COUNT CHANGED! Before: ${usersBefore}, After: ${usersAfter}`
      );
    }

    // ✅ FIXED: Update activity feed (but don't let it interfere with sidebar)
    let activityText;
    let icon;
    let autoRemove = false;

    if (state === "typing") {
      activityText = `${username} is typing on line ${line}`;
      icon = "⌨️";
      autoRemove = 3000;
    } else if (state === "editing") {
      activityText = `${username} is editing`;
      icon = "✏️";
    } else if (state === "viewing") {
      activityText = `${username} is viewing`;
      icon = "👁️";
    }

    if (activityText) {
      this.updateSingleUserActivity(userId, icon, activityText, autoRemove);
    }

    console.log(`✅ Updated ${username} status: ${state}`);
  }
  // ===== EDITOR EVENT LISTENERS =====
  // ===== ENHANCED EDITOR EVENT LISTENERS =====
  setupEventListeners() {
    if (!this.editor) {
      console.error("❌ No editor element provided");
      return;
    }

    // ✅ NEW: State tracking variables
    this.currentState = "viewing"; // typing, editing, viewing
    this.stateTimeout = null;
    this.lastContent = this.editor.value;

    // Text changes - TYPING detection
    this.editor.addEventListener("input", (e) => {
      this.handleTextChange(e);
    });

    // Cursor/selection changes
    this.editor.addEventListener("selectionchange", () => {
      this.handleCursorChange();
    });

    this.editor.addEventListener("click", () => {
      this.handleCursorChange();
    });

    this.editor.addEventListener("keyup", () => {
      this.handleCursorChange();
    });

    // ✅ NEW: Smart focus/blur handling
    this.editor.addEventListener("focus", () => {
      this.setState("editing");
      console.log("📝 Editor focused - user is editing");
    });

    this.editor.addEventListener("blur", () => {
      this.setState("viewing");
      console.log("📝 Editor blurred - user is viewing");
    });
  }

  // ===== NEW: SMART STATE MANAGEMENT =====
  setState(newState, lineNumber = null) {
    const previousState = this.currentState;

    // Don't update if state hasn't changed
    if (previousState === newState && newState !== "typing") {
      return;
    }

    this.currentState = newState;

    // Clear any existing timeout
    clearTimeout(this.stateTimeout);

    // Send state to backend
    this.sendUserState(newState, lineNumber);

    // ✅ AUTO-CLEANUP: Set timeout for state expiry
    if (newState === "typing") {
      // Typing state expires after 2 seconds of no activity
      this.stateTimeout = setTimeout(() => {
        if (this.currentState === "typing") {
          this.setState("editing");
        }
      }, 2000);
    } else if (newState === "editing") {
      // Editing state expires after 30 seconds of no activity
      this.stateTimeout = setTimeout(() => {
        if (this.currentState === "editing") {
          this.setState("viewing");
        }
      }, 30000);
    }

    console.log(`🔄 State changed: ${previousState} → ${newState}`);
  }

  sendUserState(state, lineNumber = null) {
    if (!this.socket || !this.socket.connected) return;

    const stateData = {
      snippet_id: this.snippetId,
      user_id: this.userId,
      state: state,
      line: lineNumber || this.getCurrentLine(),
      timestamp: Date.now(),
    };

    this.socket.emit("user_state_change", stateData);
    console.log(`📤 Sent state: ${state}`, stateData);
  }

  handleTextChange(event) {
    const currentContent = this.editor.value;

    // ✅ ENHANCED: Only trigger typing if content actually changed
    if (currentContent !== this.lastContent) {
      const currentLine = this.getCurrentLine();
      this.setState("typing", currentLine);
      this.lastContent = currentContent;

      // Debounce actual content sync
      clearTimeout(this.changeTimeout);
      this.changeTimeout = setTimeout(() => {
        this.sendLiveChange(currentContent);
      }, 300);
    }
  }

  sendLiveChange(content) {
    if (!this.socket || !this.socket.connected) return;

    const changeData = {
      snippet_id: this.snippetId,
      user_id: this.userId,
      changes: {
        content: content,
        length: content.length,
        timestamp: Date.now(),
      },
      cursor_position: this.editor.selectionStart,
    };

    this.socket.emit("live_code_change", changeData);
    console.log("📤 Sent live change:", changeData);
  }

  handleLiveCodeUpdate(data) {
    // Don't update if it's from current user
    if (data.user_id === this.userId) return;

    // Update activity feed
    this.updateActivityFeed("⌨️", `${data.username} is editing`, "now");

    // Update user status in sidebar
    this.updateUserActivity(
      data.user_id,
      `🔴 Editing line ${this.getLineFromPosition(data.cursor_position)}`
    );

    // Show live typing indicator
    this.showTypingIndicator(data);
  }

  // ===== CURSOR TRACKING =====
  handleCursorChange() {
    // ✅ ENHANCED: Faster cursor tracking with throttling
    clearTimeout(this.cursorTimeout);
    this.cursorTimeout = setTimeout(() => {
      this.sendCursorPosition();
    }, 50); // ✅ REDUCED: From 100ms to 50ms for faster tracking
  }

  sendCursorPosition() {
    if (!this.socket || !this.socket.connected) return;

    const position = this.editor.selectionStart;
    const line = this.getLineFromPosition(position);

    const cursorData = {
      snippet_id: this.snippetId,
      user_id: this.userId,
      position: position,
      line: line,
    };

    this.socket.emit("cursor_position_change", cursorData);
  }

  handleCursorUpdate(data) {
    if (data.user_id === this.userId) return;

    // Update cursor display
    this.updateUserCursor(data);

    // Update user activity
    this.updateUserActivity(data.user_id, `👆 Line ${data.line}`);
  }

  updateUserCursor(data) {
    const cursorId = `cursor-${data.user_id}`;
    let cursor = document.getElementById(cursorId);

    if (!cursor) {
      cursor = this.createUserCursor(data);
    }

    // Position cursor based on text position
    const position = this.getPixelPositionFromTextPosition(data.position);
    cursor.style.left = position.x + "px";
    cursor.style.top = position.y + "px";
    cursor.style.borderColor = data.color || "#FF6B6B";

    // Show cursor briefly
    cursor.classList.add("visible");
    setTimeout(() => {
      cursor.classList.remove("visible");
    }, 3000);
  }

  createUserCursor(data) {
    const cursor = document.createElement("div");
    cursor.id = `cursor-${data.user_id}`;
    cursor.className = "collaborative-cursor";
    cursor.innerHTML = `
            <div class="cursor-line"></div>
            <div class="cursor-label">${data.username}</div>
        `;

    const editorContainer = this.editor.parentElement;
    editorContainer.appendChild(cursor);

    return cursor;
  }

  // ===== USER PRESENCE MANAGEMENT =====
  joinEditingSession() {
    if (!this.socket || !this.socket.connected) {
      console.error("❌ Cannot join editing session - socket not connected");
      return;
    }

    const joinData = {
      snippet_id: this.snippetId,
      team_id: this.teamId,
      user_id: this.userId,
    };

    this.socket.emit("join_editing_session", joinData);
    console.log("🔗 Joining editing session:", joinData);
  }

  handleUserJoined(data) {
    const userId = data.user_id;
    const username = data.username;

    console.log(`👤 Processing user joined: ${username} (ID: ${userId})`);

    // ✅ FIXED: Always add user to active list (including current user)
    this.activeUsers.set(userId, {
      username: username,
      color: data.color,
      isTyping: false,
    });

    // ✅ FIXED: Always update UI (this will now handle all users properly)
    this.addUserToSidebar(data);

    // ✅ FIXED: Only add activity feed for OTHER users (not current user)
    if (userId !== this.userId) {
      const activityId = `join-${userId}-${Date.now()}`;
      this.updateActivityFeedWithId(
        activityId,
        "👤",
        `${username} joined editing`,
        this.getSmartTimestamp()
      );
    }

    console.log(`✅ User ${username} processed successfully`);
  }

  // ✅ FIXED (CORRECT):
  updateSingleUserActivity(userId, icon, text, autoRemove = false) {
    // ✅ CRITICAL FIX: Use different prefix for activities vs users
    const activityId =
      icon === "💬" ? `comment-${userId}-${Date.now()}` : `activity-${userId}`; // ← CHANGED: Different prefix!

    // ✅ FIXED: Remove existing activity, not user
    if (icon !== "💬") {
      this.removeActivityById(`activity-${userId}`); // ← CHANGED: Different prefix!
    }

    // Add new activity with smart timestamp
    const timestamp = this.getSmartTimestamp();
    this.updateActivityFeedWithId(
      activityId,
      icon,
      text,
      timestamp,
      autoRemove
    );

    // ✅ FIXED: Store activity for timestamp updates
    if (!this.userActivities) this.userActivities = new Map();

    // ✅ FIXED: Use activityId as key for comments
    const activityKey = icon === "💬" ? activityId : userId;

    this.userActivities.set(activityKey, {
      id: activityId, // ← This will now be activity-${userId}
      icon: icon,
      text: text,
      timestamp: Date.now(),
      autoRemove: autoRemove,
      userId: userId,
    });

    console.log(`✅ Stored activity for timestamp updates: ${activityKey}`);
  }

  // ===== NEW: SMART TIMESTAMP SYSTEM =====
  getSmartTimestamp() {
    return "now"; // Initial timestamp
  }

  // ===== FIXED: TIMESTAMP UPDATER =====
  updateTimestamps() {
    if (!this.userActivities || this.userActivities.size === 0) {
      return;
    }

    const now = Date.now();
    console.log(
      `🕒 Updating timestamps for ${this.userActivities.size} activities`
    );

    this.userActivities.forEach((activity, activityKey) => {
      const elapsed = now - activity.timestamp;
      let displayTime;

      if (elapsed < 30000) {
        // Less than 30 seconds
        displayTime = "now";
      } else if (elapsed < 60000) {
        // 30-60 seconds
        displayTime = "30 sec";
      } else {
        // More than 60 seconds
        const minutes = Math.floor(elapsed / 60000);
        displayTime = `${minutes} min`;
      }

      // Update the timestamp in DOM
      const activityElement = document.getElementById(activity.id);
      if (activityElement) {
        const timeElement = activityElement.querySelector(".activity-time");
        if (timeElement && timeElement.textContent !== displayTime) {
          timeElement.textContent = displayTime;
          console.log(
            `🕒 Updated ${activityKey}: ${activity.timestamp} → ${displayTime}`
          );
        }
      } else {
        // ✅ CLEANUP: Remove activities that no longer exist in DOM
        console.log(`🧹 Removing stale activity: ${activityKey}`);
        this.userActivities.delete(activityKey);
      }
    });
  }

  // ===== FIXED: TIMESTAMP UPDATER =====
  startTimestampUpdater() {
    // Initialize userActivities if not exists
    if (!this.userActivities) {
      this.userActivities = new Map();
    }

    // Update timestamps every 30 seconds
    this.timestampInterval = setInterval(() => {
      this.updateTimestamps();
    }, 30000);

    console.log("✅ Timestamp updater started");
  }

  updateTimestamps() {
    if (!this.userActivities || this.userActivities.size === 0) {
      return;
    }

    const now = Date.now();
    console.log(
      `🕒 Updating timestamps for ${this.userActivities.size} activities`
    );

    this.userActivities.forEach((activity, userId) => {
      const elapsed = now - activity.timestamp;
      let displayTime;

      if (elapsed < 30000) {
        // Less than 30 seconds
        displayTime = "now";
      } else if (elapsed < 60000) {
        // 30-60 seconds
        displayTime = "30 sec";
      } else {
        // More than 60 seconds
        const minutes = Math.floor(elapsed / 60000);
        displayTime = `${minutes} min`;
      }

      // Update the timestamp in DOM
      const activityElement = document.getElementById(activity.id);
      if (activityElement) {
        const timeElement = activityElement.querySelector(".activity-time");
        if (timeElement && timeElement.textContent !== displayTime) {
          timeElement.textContent = displayTime;
          console.log(
            `🕒 Updated ${userId}: ${activity.timestamp} → ${displayTime}`
          );
        }
      }
    });
  }

  // ✅ REPLACE WITH (PREVENTS DUPLICATES):
  handleUserLeft(data) {
    // ✅ FIXED: Don't process your own leave events
    if (data.user_id === this.userId) {
      console.log("✅ Ignoring self-leave event");
      return;
    }

    // Remove user from active users
    this.activeUsers.delete(data.user_id);

    // Remove user cursor
    const cursor = document.getElementById(`cursor-${data.user_id}`);
    if (cursor) cursor.remove();

    const username = data.username || `User_${data.user_id}`;

    // Update UI
    this.removeUserFromSidebar(data.user_id);

    // ✅ FIXED: Only add activity feed ONCE with unique ID
    const activityId = `leave-${data.user_id}-${Date.now()}`;
    this.updateActivityFeedWithId(
      activityId,
      "👋",
      `${username} left editing`,
      this.getSmartTimestamp()
    );

    console.log(`✅ User ${username} left editing session`);
  }

  // ===== TYPING INDICATORS =====
  setTypingStatus(isTyping) {
    // ✅ ENHANCED: Better state management
    if (this.isTyping === isTyping) return;

    const previousState = this.isTyping;
    this.isTyping = isTyping;

    if (!this.socket || !this.socket.connected) return;

    // ✅ ENHANCED: Only send if state actually changed
    if (previousState !== isTyping) {
      const typingData = {
        snippet_id: this.snippetId,
        user_id: this.userId,
        is_typing: isTyping,
        line: this.getCurrentLine(),
      };

      this.socket.emit("typing_indicator_change", typingData);
      console.log(
        `⌨️ Typing status changed: ${isTyping ? "started" : "stopped"} typing`
      );
    }
  }

  handleTypingStatus(data) {
    if (data.user_id === this.userId) return;

    const user = this.activeUsers.get(data.user_id);
    if (user) {
      const wasTyping = user.isTyping;
      user.isTyping = data.is_typing;

      if (data.is_typing && !wasTyping) {
        // ✅ FIXED: Only add activity when user STARTS typing (prevent spam)
        this.updateUserActivity(data.user_id, `⌨️ Typing on line ${data.line}`);
        this.showTypingAnimation(data.user_id);

        // ✅ FIXED: Add to activity feed only once with auto-remove
        const activityId = `typing-${data.user_id}`;
        this.updateActivityFeedWithId(
          activityId,
          "⌨️",
          `${data.username || "Someone"} is typing on line ${data.line}`,
          "now",
          5000
        );
      } else if (!data.is_typing && wasTyping) {
        // ✅ FIXED: When user stops typing, show "editing"
        this.updateUserActivity(data.user_id, "🔴 Currently editing");
        this.hideTypingAnimation(data.user_id);

        // ✅ FIXED: Remove typing activity
        this.removeActivityById(`typing-${data.user_id}`);
      }
    }
  }

  showTypingIndicator(data) {
    const indicator = document.createElement("div");
    indicator.className = "typing-indicator";
    indicator.id = `typing-${data.user_id}`;
    indicator.style.color = data.user_color;
    indicator.innerHTML = `
            <span class="typing-dots">
                <span></span><span></span><span></span>
            </span>
            ${data.username} is typing...
        `;

    // Position near cursor
    const position = this.getPixelPositionFromTextPosition(
      data.cursor_position
    );
    indicator.style.left = position.x + "px";
    indicator.style.top = position.y + 20 + "px";

    const editorContainer = this.editor.parentElement;
    editorContainer.appendChild(indicator);

    // Remove after 3 seconds
    setTimeout(() => {
      if (indicator.parentElement) {
        indicator.remove();
      }
    }, 3000);
  }

  // ===== COMMENT SYSTEM INTEGRATION =====
  // ✅ FIXED:
  // ===== FIXED: COMMENT HANDLER WITH TIMESTAMPS =====
  handleCommentAdded(data) {
    // ✅ ALWAYS add comment/chat to UI (including your own)
    if (data.type === "comment") {
      this.addCommentToUI(data);
    } else if (data.type === "chat") {
      this.addChatMessageToUI(data);
    }

    // ✅ ONLY add activity feed for OTHER users (prevent duplicate activity)
    if (data.user_id !== this.userId) {
      const activityText =
        data.type === "comment"
          ? `${data.username} commented`
          : `${data.username} sent message`;

      // ✅ FIXED: Use updateSingleUserActivity for timestamp tracking
      const activityId = `comment-${data.user_id}-${Date.now()}`;
      this.updateSingleUserActivity(data.user_id, "💬", activityText, false);

      console.log(
        `✅ Added comment activity with timestamp tracking: ${activityText}`
      );
    }
  }

  addCommentToUI(commentData) {
    const commentsContainer = document.getElementById("comments-container");
    if (!commentsContainer) return;

    // ✅ ENHANCED: Remove "no comments" message if it exists
    const noComments = commentsContainer.querySelector(".no-comments");
    if (noComments) {
      noComments.remove();
    }

    const commentElement = document.createElement("div");
    commentElement.className = "message";

    // ✅ ENHANCED: Better timestamp handling
    const timestamp = commentData.time || this.getSmartTimestamp();

    commentElement.innerHTML = `
        <div class="message-header">
            <span class="message-author">${commentData.username}</span>
            <span class="message-time">${timestamp}</span>
        </div>
        <div class="message-content">${commentData.comment}</div>
    `;

    commentsContainer.appendChild(commentElement);
    commentsContainer.scrollTop = commentsContainer.scrollHeight;
  }

  addChatMessageToUI(messageData) {
    console.log("💭 Adding chat message to UI:", messageData);

    const chatContainer = document.getElementById("chat-container");
    if (!chatContainer) {
      console.error("❌ Chat container not found");
      return;
    }

    // Remove "no chat" message if it exists
    const noChat = chatContainer.querySelector(".no-chat");
    if (noChat) {
      noChat.remove();
    }

    // Get message data with better fallbacks
    const username =
      messageData.username || messageData.userName || "Unknown User";
    const content =
      messageData.comment || messageData.content || messageData.message || "";
    const time = messageData.time || "now";
    const userId = messageData.user_id || messageData.userId;

    // Get current user ID properly
    const currentUserId = window.TEMPLATE_DATA?.user?.id;

    console.log("🔍 CHAT LAYOUT DEBUG:");
    console.log("  - Message userId:", userId);
    console.log("  - Current userId:", currentUserId);
    console.log("  - Are same user:", String(userId) === String(currentUserId));

    // Determine message layout (left/right)
    let messageClass = "message";
    let displayName = username;

    if (currentUserId && userId && String(userId) === String(currentUserId)) {
      // RIGHT: Current user's messages
      messageClass = "message message-right";
      displayName = "You";
      console.log("  - Layout: RIGHT (your message)");
    } else if (userId && String(userId) !== String(currentUserId)) {
      // LEFT: Other users' messages
      messageClass = "message message-left";
      displayName = username;
      console.log("  - Layout: LEFT (other's message)");
    } else {
      // DEFAULT: When user ID is unclear
      messageClass = "message";
      displayName = username;
      console.log("  - Layout: DEFAULT (unclear user)");
    }

    // Create message element with proper class
    const messageElement = document.createElement("div");
    messageElement.className = messageClass;
    messageElement.innerHTML = `
        <div class="message-header">
            <span class="message-author">${displayName}</span>
            <span class="message-time">${time}</span>
        </div>
        <div class="message-content">${content}</div>
    `;

    chatContainer.appendChild(messageElement);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    console.log("✅ Chat message added with class: " + messageClass);
  }
  addUserToSidebar(userData) {
    const usersSection = document.querySelector(".users-section");
    if (!usersSection) {
      console.log(`❌ Users section not found!`);
      return;
    }

    const userId = userData.user_id;
    const username = userData.username;

    console.log(`👥 Adding user to sidebar: ${username} (ID: ${userId})`);

    // ✅ CRITICAL FIX: Force remove any existing corrupted element
    // ✅ FIXED (SAFER):
    const existingUser = document.getElementById(`user-${userId}`);
    if (existingUser) {
      console.log(
        `✅ User ${username} already exists, updating display name only`
      );

      // ✅ FIXED: Just update the name, don't remove and recreate
      const nameElement = existingUser.querySelector(".user-name");
      if (nameElement) {
        const displayName =
          userId === this.userId ? `${username} (You)` : username;
        nameElement.textContent = displayName;
      }
      return;
    }

    // ✅ CREATE: Fresh user element
    this.createAndAttachUser(userData, usersSection);
  }

  // ✅ NEW: Separate function for creating and attaching users
  createAndAttachUser(userData, usersSection) {
    const userId = userData.user_id;
    const username = userData.username;
    const displayName = userId === this.userId ? `${username} (You)` : username;

    const userElement = document.createElement("div");
    userElement.className = "user-item";
    userElement.id = `user-${userId}`;

    // ✅ PROTECTION: Add data attributes for debugging
    userElement.setAttribute("data-user-id", userId);
    userElement.setAttribute("data-username", username);
    userElement.setAttribute("data-created", Date.now());

    userElement.innerHTML = `
        <div class="user-status editing" style="background: ${
          userData.color || "#FF6B6B"
        }; box-shadow: 0 0 10px ${userData.color || "#FF6B6B"};"></div>
        <div class="user-info">
            <div class="user-name">${displayName}</div>
            <div class="user-activity">🔴 Currently editing</div>
        </div>
    `;

    // ✅ CRITICAL: Force proper attachment
    usersSection.appendChild(userElement);

    // ✅ VERIFICATION: Check attachment immediately
    const verification = document.getElementById(`user-${userId}`);
    if (!verification || !document.contains(verification)) {
      console.log(
        `🚨 CRITICAL: User ${username} failed to attach! Retrying...`
      );

      // ✅ RETRY: Try different attachment method
      setTimeout(() => {
        if (!document.getElementById(`user-${userId}`)) {
          usersSection.insertAdjacentHTML(
            "beforeend",
            `
                    <div class="user-item" id="user-${userId}" data-user-id="${userId}" data-username="${username}">
                        <div class="user-status editing" style="background: ${
                          userData.color || "#FF6B6B"
                        }; box-shadow: 0 0 10px ${
              userData.color || "#FF6B6B"
            };"></div>
                        <div class="user-info">
                            <div class="user-name">${displayName}</div>
                            <div class="user-activity">🔴 Currently editing</div>
                        </div>
                    </div>
                `
          );
          console.log(`🔄 Retried adding ${username} with insertAdjacentHTML`);
        }
      }, 50);
    } else {
      console.log(`✅ User ${username} verified in DOM`);
    }

    console.log(`✅ Added ${displayName} to sidebar`);
  }

  removeUserFromSidebar(userId) {
    console.log(`🗑️ Attempting to remove user: ${userId}`);

    const userElement = document.getElementById(`user-${userId}`);
    if (userElement) {
      const username = userElement.querySelector(".user-name")?.textContent;
      console.log(`✅ Removing user: ${username}`);
      userElement.remove();

      // ✅ VERIFICATION: Ensure removal
      setTimeout(() => {
        const stillExists = document.getElementById(`user-${userId}`);
        if (stillExists) {
          console.log(
            `🚨 User ${username} still exists after removal attempt!`
          );
          stillExists.remove();
        }
      }, 10);
    } else {
      console.log(`⚠️ User ${userId} not found for removal`);
    }
  }

  updateUserActivity(userId, activity) {
    const userElement = document.getElementById(`user-${userId}`);
    if (userElement) {
      const activityElement = userElement.querySelector(".user-activity");
      if (activityElement) {
        activityElement.textContent = activity;
      }
    }
  }

  updateActivityFeed(icon, text, time) {
    const activitySection = document.querySelector(".activity-section");
    if (!activitySection) return;

    // ✅ ENHANCED: Generate unique ID for better management
    const activityId = `activity-${Date.now()}-${Math.random()
      .toString(36)
      .substr(2, 9)}`;

    const activityItem = document.createElement("div");
    activityItem.className = "activity-item";
    activityItem.id = activityId; // ✅ NEW: Add unique ID

    // ✅ ENHANCED: Smart timestamp handling
    let displayTime = time;
    let timeClass = "recent";

    if (time === "now") {
      displayTime = "now";
      timeClass = "live";
    } else if (typeof time === "string" && time.includes(":")) {
      displayTime = time;
      timeClass = "recent";
    } else {
      displayTime = this.getSmartTimestamp();
      timeClass = "recent";
    }

    activityItem.innerHTML = `
        <div class="activity-icon">${icon}</div>
        <div class="activity-content">
            <div class="activity-text">${text}</div>
            <div class="activity-time ${timeClass}">${displayTime}</div>
        </div>
    `;

    const header = activitySection.querySelector(".activity-header");
    if (header && header.nextSibling) {
      activitySection.insertBefore(activityItem, header.nextSibling);
    } else {
      activitySection.appendChild(activityItem);
    }

    // ✅ ENHANCED: Keep only last 15 activities (increased from 10)
    const activities = activitySection.querySelectorAll(".activity-item");
    if (activities.length > 15) {
      for (let i = 15; i < activities.length; i++) {
        activities[i].remove();
      }
    }
  }

  // ✅ FIXED (SAFER):
  setupDOMProtection() {
    // ✅ PROTECTION: Monitor DOM changes but be smarter about it
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === "childList") {
          mutation.removedNodes.forEach((node) => {
            if (node.classList && node.classList.contains("user-item")) {
              const username = node.querySelector(".user-name")?.textContent;
              const userId = node.getAttribute("data-user-id");

              // ✅ FIXED: Only log, don't auto-restore (causes infinite loops)
              console.log(`🚨 USER REMOVED FROM DOM: ${username} (${userId})`);
              console.trace("Removal stack trace");

              // ✅ REMOVED: Don't auto-restore - it causes conflicts
              // The user removal might be intentional (like during updates)
            }
          });
        }
      });
    });

    const usersSection = document.querySelector(".users-section");
    if (usersSection) {
      observer.observe(usersSection, {
        childList: true,
        subtree: true,
      });
      console.log(`🛡️ DOM protection activated (monitoring only)`);
    }
  }

  showTypingAnimation(userId) {
    const userElement = document.getElementById(`user-${userId}`);
    if (userElement) {
      const statusElement = userElement.querySelector(".user-status");
      if (statusElement) {
        statusElement.classList.add("typing-animation");
      }
    }
  }

  hideTypingAnimation(userId) {
    const userElement = document.getElementById(`user-${userId}`);
    if (userElement) {
      const statusElement = userElement.querySelector(".user-status");
      if (statusElement) {
        statusElement.classList.remove("typing-animation");
      }
    }
  }

  // ===== UTILITY METHODS =====
  getCurrentLine() {
    if (!this.editor) return 1;
    const text = this.editor.value.substring(0, this.editor.selectionStart);
    return text.split("\n").length;
  }

  // ✅ FIXED (CORRECT):
  getLineFromPosition(position) {
    if (!this.editor) return 1;

    const text = this.editor.value.substring(0, position);
    const lines = text.split("\n");
    const lineNumber = lines.length;

    // ✅ SAFETY CHECK: Don't exceed actual line count
    const totalLines = this.editor.value.split("\n").length;
    const actualLine = Math.min(lineNumber, totalLines);

    console.log(
      `🔍 Line calc: pos=${position}, calculated=${lineNumber}, actual=${actualLine}, total=${totalLines}`
    );
    return actualLine;
  }

  getPixelPositionFromTextPosition(textPosition) {
    // Create a temporary element to measure text position
    const tempElement = document.createElement("div");
    tempElement.style.cssText = `
            position: absolute;
            visibility: hidden;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            padding: 1rem;
            width: ${this.editor.offsetWidth}px;
        `;

    const textBeforeCursor = this.editor.value.substring(0, textPosition);
    tempElement.textContent = textBeforeCursor;

    document.body.appendChild(tempElement);

    const rect = this.editor.getBoundingClientRect();
    const tempRect = tempElement.getBoundingClientRect();

    const position = {
      x: tempRect.width + rect.left,
      y: tempRect.height + rect.top,
    };

    document.body.removeChild(tempElement);

    return position;
  }

  handleContentSync(data) {
    // Update editor content if different
    if (this.editor.value !== data.content) {
      const cursorPosition = this.editor.selectionStart;
      this.editor.value = data.content;
      this.lastContent = data.content;

      // Restore cursor position
      this.editor.setSelectionRange(cursorPosition, cursorPosition);
    }
  }

  // ===== PUBLIC METHODS =====
  sendComment(content, type = "comment") {
    if (!this.socket || !this.socket.connected) return false;

    const commentData = {
      snippet_id: this.snippetId,
      user_id: this.userId,
      comment: content,
      comment_type: type,
    };

    this.socket.emit("collaborative_comment", commentData);
    return true;
  }

  leaveEditingSession() {
    if (!this.socket || !this.socket.connected) return;

    const leaveData = {
      snippet_id: this.snippetId,
      user_id: this.userId,
    };

    this.socket.emit("leave_editing_session", leaveData);

    // Clean up UI
    this.cleanup();
  }

  // ===== CHAT PERSISTENCE METHODS =====
  loadSnippetHistory() {
    if (!this.socket || !this.socket.connected) return;

    console.log("📚 Loading snippet history...");

    this.socket.emit("load_snippet_history", {
      snippet_id: this.snippetId,
      user_id: this.userId,
    });
  }

  saveComment(content) {
    if (!this.socket || !this.socket.connected) return false;

    console.log("💬 Saving comment:", content);

    this.socket.emit("save_snippet_comment", {
      snippet_id: this.snippetId,
      user_id: this.userId,
      team_id: this.teamId,
      content: content,
    });

    return true;
  }

  saveChatMessage(message) {
    if (!this.socket || !this.socket.connected) return false;

    console.log("💭 Saving chat message:", message);

    this.socket.emit("save_snippet_chat", {
      snippet_id: this.snippetId,
      user_id: this.userId,
      team_id: this.teamId,
      message: message,
    });

    return true;
  }

  clearComments() {
    if (!this.socket || !this.socket.connected) return false;

    console.log("🧹 Clearing comments...");

    this.socket.emit("clear_snippet_comments", {
      snippet_id: this.snippetId,
      user_id: this.userId,
      team_id: this.teamId,
    });

    return true;
  }

  clearChats() {
    if (!this.socket || !this.socket.connected) return false;

    console.log("🧹 Clearing chats...");

    this.socket.emit("clear_snippet_chats", {
      snippet_id: this.snippetId,
      user_id: this.userId,
      team_id: this.teamId,
    });

    return true;
  }

  cleanup() {
    console.log("🧹 Starting collaborative editor cleanup");

    // Remove all user cursors
    document.querySelectorAll(".collaborative-cursor").forEach((cursor) => {
      cursor.remove();
    });

    // Remove typing indicators
    document.querySelectorAll(".typing-indicator").forEach((indicator) => {
      indicator.remove();
    });

    // ✅ ENHANCED: Remove activity items created by this editor
    document
      .querySelectorAll(".activity-item[id^='typing-']")
      .forEach((item) => {
        item.remove();
      });

    // Clear all timers
    clearTimeout(this.changeTimeout);
    clearTimeout(this.cursorTimeout);
    clearTimeout(this.typingTimeout);

    // ✅ ENHANCED: Clear active users
    this.activeUsers.clear();
    this.userCursors.clear();

    // ✅ ENHANCED: Reset state
    this.isTyping = false;
    this.lastContent = "";

    console.log("✅ Collaborative editor cleanup completed");
  }

  // ===== GETTERS =====
  getActiveUsers() {
    return Array.from(this.activeUsers.values());
  }

  isUserTyping(userId) {
    const user = this.activeUsers.get(userId);
    return user ? user.isTyping : false;
  }

  getUserColor(userId) {
    const user = this.activeUsers.get(userId);
    return user ? user.color : "#FF6B6B";
  }

  // ===== ADD THESE MISSING METHODS =====

  getSmartTimestamp() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  updateActivityFeedWithId(id, icon, text, time, autoRemove = false) {
    const activitySection = document.querySelector(".activity-section");
    if (!activitySection) return;

    // Remove existing activity with same ID
    this.removeActivityById(id);

    const activityItem = document.createElement("div");
    activityItem.className = "activity-item";
    activityItem.id = id;
    activityItem.innerHTML = `
        <div class="activity-icon">${icon}</div>
        <div class="activity-content">
            <div class="activity-text">${text}</div>
            <div class="activity-time">${time}</div>
        </div>
    `;

    const header = activitySection.querySelector(".activity-header");
    if (header && header.nextSibling) {
      activitySection.insertBefore(activityItem, header.nextSibling);
    } else {
      activitySection.appendChild(activityItem);
    }

    // Auto-remove if specified
    if (autoRemove) {
      setTimeout(() => {
        this.removeActivityById(id);
      }, autoRemove);
    }
  }

  removeActivityById(id) {
    const element = document.getElementById(id);
    if (element) {
      element.remove();
    }
  }

  getSmartActivityTime() {
    return "now"; // For live activities, always show "now"
  }

  // ===== PERFORMANCE OPTIMIZATION =====
  optimizePerformance() {
    // Throttle cursor updates to prevent spam
    const originalHandleCursorChange = this.handleCursorChange.bind(this);
    let cursorUpdateCount = 0;

    this.handleCursorChange = () => {
      cursorUpdateCount++;
      if (cursorUpdateCount % 3 === 0) {
        // Only send every 3rd cursor update
        originalHandleCursorChange();
      }
    };

    // Debounce typing status changes
    let typingDebounceTimeout;
    const originalSetTypingStatus = this.setTypingStatus.bind(this);

    this.setTypingStatus = (isTyping) => {
      clearTimeout(typingDebounceTimeout);
      typingDebounceTimeout = setTimeout(() => {
        originalSetTypingStatus(isTyping);
      }, 100);
    };

    console.log("✅ Performance optimizations applied");
  }

  cleanup() {
    console.log("🧹 Starting collaborative editor cleanup");

    // Clear timestamp updater
    if (this.timestampInterval) {
      clearInterval(this.timestampInterval);
      this.timestampInterval = null;
    }

    // Clear state timeout
    if (this.stateTimeout) {
      clearTimeout(this.stateTimeout);
      this.stateTimeout = null;
    }

    // Clear user activities
    if (this.userActivities) {
      this.userActivities.clear();
    }

    // Remove all user cursors
    document.querySelectorAll(".collaborative-cursor").forEach((cursor) => {
      cursor.remove();
    });

    // Remove typing indicators
    document.querySelectorAll(".typing-indicator").forEach((indicator) => {
      indicator.remove();
    });

    // Clear all timers
    clearTimeout(this.changeTimeout);
    clearTimeout(this.cursorTimeout);
    clearTimeout(this.typingTimeout);

    // Reset state
    this.currentState = "viewing";
    this.activeUsers.clear();
    this.userCursors.clear();
    this.isTyping = false;
    this.lastContent = "";

    console.log("✅ Collaborative editor cleanup completed");
  }
}

// ===== GLOBAL INITIALIZATION =====
window.CollaborativeEditor = CollaborativeEditor;

// Auto-initialize if elements are available
document.addEventListener("DOMContentLoaded", function () {
  // Wait for Socket.IO to be ready
  setTimeout(() => {
    if (window.socket && window.TEMPLATE_DATA) {
      const codeEditor = document.getElementById("code-editor");
      if (codeEditor) {
        console.log("🚀 Auto-initializing Collaborative Editor");

        window.collaborativeEditor = new CollaborativeEditor(codeEditor, {
          socket: window.socket,
          snippetId: window.TEMPLATE_DATA.snippet.id,
          teamId: window.TEMPLATE_DATA.team.id,
          userId: window.TEMPLATE_DATA.user.id,
          username: window.TEMPLATE_DATA.user.name,
          userColor: "#FF6B6B", // Will be assigned by server
        });
      }
    }
  }, 2000);
});

// Clean up on page unload
window.addEventListener("beforeunload", function () {
  if (window.collaborativeEditor) {
    window.collaborativeEditor.leaveEditingSession();
  }
});

console.log("🔮 Collaborative Editor loaded successfully!");

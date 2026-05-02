/**

 * Handles the popup UI interaction and communicates with the background script
 */

document.addEventListener("DOMContentLoaded", function () {
  // New DOM elements for advanced features
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  const syncNowBtn = document.getElementById("sync-now-btn");
  const clearChangesBtn = document.getElementById("clear-changes-btn");
  const captureSnippetBtn = document.getElementById("capture-snippet-btn");
  const viewAllSnippets = document.getElementById("view-all-snippets");
  const createCollectionBtn = document.getElementById("create-collection-btn");
  const searchSnippets = document.getElementById("search-snippets");
  const autoSyncToggle = document.getElementById("auto-sync-toggle");
  const loginBtn = document.getElementById("login-btn");
  const registerBtn = document.getElementById("register-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const settingsBtn = document.getElementById("settings-btn");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const totalSnippetsCount = document.getElementById("total-snippets");
  const collectionsCount = document.getElementById("collections-count");
  const recentSnippetsList = document.getElementById("recent-snippets-list");
  const collectionsList = document.getElementById("collections-list");
  const loginSection = document.getElementById("login-section");
  const userSection = document.getElementById("user-section");
  // DOM elements
  const serverUrlInput = document.getElementById("server-url");
  const connectBtn = document.getElementById("connect-btn");
  const disconnectBtn = document.getElementById("disconnect-btn");
  const testBtn = document.getElementById("test-btn");
  const statusIcon = document.getElementById("status-icon");
  const statusText = document.getElementById("status-text");

  const openDashboardLink = document.getElementById("open-dashboard");
  const viewDocsLink = document.getElementById("view-docs");

  // Load saved settings
  init();
  function checkBackgroundScriptStatus() {
    console.log("🔵 Checking background script status...");

    // Test if background script is responsive
    chrome.runtime.sendMessage(
      { action: "healthCheck", timestamp: Date.now() },
      function (response) {
        if (chrome.runtime.lastError) {
          console.error(
            "🔴 Background script not responding:",
            chrome.runtime.lastError
          );
          showError(
            "Background script connection failed. Try reloading the extension."
          );
        } else {
          console.log("🔵 Background script is healthy:", response);
        }
      }
    );
  }
  function init() {
    initBackgroundParticles();
    loadSettings();
    checkConnectionStatus();
    updateChangeStats();
    loadRecentSnippets();
    checkAuthStatus();
    loadCollections();
    recoverSession();
    maintainAuthState();
    checkBackgroundScriptStatus(); // Add this line

    setupMessageListeners();
  }
  // Add this new function after the init() function:
  function setupMessageListeners() {
    // Listen for messages from background script
    chrome.runtime.onMessage.addListener(
      async (message, sender, sendResponse) => {
        console.log("Popup received message:", message);

        switch (message.type) {
          // Replace your existing login success handler with this:
          case "LOGIN_SUCCESS":
            console.log(
              "🔵 Login successful - Full response data:",
              message.data
            );

            // Reset login button state
            loginBtn.disabled = false;
            loginBtn.textContent = "Login";

            // CRITICAL: Only proceed if we have a token
            const token = message.data.token || message.data.authToken;
            const user = message.data.user || message.data.userData;

            if (token && user) {
              console.log("🔵 Token found, proceeding with login");

              const authData = {
                userEmail: user.email,
                authToken: token,
                isAuthenticated: true,
                loginTimestamp: Date.now(),
                tokenExpiry: Date.now() + 7 * 24 * 60 * 60 * 1000,
              };

              chrome.storage.local.set(authData, function () {
                console.log("🔵 Auth data stored successfully");
                emailInput.value = user.email;
                showNotification("Logged in successfully!");
                showUserSection();
                syncAuthWithContentScript();
                updateChangeStats();
                loadRecentSnippets();
                loadCollections();
              });
            } else {
              // No token = treat as failed login
              console.error("🔴 LOGIN_SUCCESS received but no token found");
              showError("Authentication failed - no access token received");
              showLoginSection();
            }
            break;

          case "LOGIN_FAILED":
            loginBtn.disabled = false;
            loginBtn.textContent = "Login";

            // Show more specific error messages
            let errorMsg = message.data.error || "Login failed";
            if (errorMsg.toLowerCase().includes("invalid credentials")) {
              errorMsg = "Invalid email or password";
            } else if (
              errorMsg.toLowerCase().includes("token generation failed")
            ) {
              errorMsg = "Server authentication error";
            }

            showError(errorMsg);
            showLoginSection(); // Ensure we stay on login screen
            break;
          case "REGISTER_SUCCESS":
            registerBtn.disabled = false;
            registerBtn.textContent = "Register";
            showNotification("Account created successfully!");
            showUserSection();
            updateChangeStats();
            loadRecentSnippets();
            loadCollections();
            break;

          case "REGISTER_FAILED":
            registerBtn.disabled = false;
            registerBtn.textContent = "Register";
            showError(message.data.error);
            break;
          case "AUTH_VERIFICATION":
            console.log("🔵 Auth verification result:", message.data);
            if (message.data.valid) {
              showUserSection();
              updateChangeStats();
            } else {
              showLoginSection();
              showError("Session expired. Please login again.");
            }
            break;

          case "COLLECTION_CREATED":
            console.log("🔵 Collection created successfully in popup");
            showNotification("Collection created successfully!");
            loadCollections();
            updateChangeStats();
            break;

          case "COLLECTION_CREATION_FAILED":
            console.error("🔴 Collection creation failed:", message.data);
            showError(message.data.error, "collection_creation");
            break;

          case "SNIPPET_SAVED":
          case "SNIPPET_UPDATED":
          case "SNIPPET_DELETED":
          case "SNIPPETS_SYNCED":
          case "COLLECTIONS_UPDATED":
            updateChangeStats();
            loadRecentSnippets();
            loadCollections();
            break;
        }
      }
    );
  }
  function testAuth() {
    chrome.runtime.sendMessage({ action: "testAuthEndpoint" }, (response) => {
      console.log("🧪 Auth test result:", response);
    });
  }

  // Event listeners
  connectBtn.addEventListener("click", connectToServer);
  disconnectBtn.addEventListener("click", disconnectFromServer);
  testBtn.addEventListener("click", testAuth);
  openDashboardLink.addEventListener("click", openDashboard);
  viewDocsLink.addEventListener("click", openDocumentation);
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
  document.addEventListener("keydown", function (e) {
    // Ctrl+Shift+T for testing background connection
    if (e.ctrlKey && e.shiftKey && e.key === "T") {
      e.preventDefault();
      debugBackgroundConnection();
    }
  });

  syncNowBtn.addEventListener("click", syncNow);
  clearChangesBtn.addEventListener("click", clearChanges);
  captureSnippetBtn.addEventListener("click", captureCodeSnippet);
  viewAllSnippets.addEventListener("click", viewAllSnippetsAction);
  createCollectionBtn.addEventListener("click", createCollection);
  searchSnippets.addEventListener("input", searchSnippetsAction);
  autoSyncToggle.addEventListener("click", toggleAutoSync);
  loginBtn.addEventListener("click", loginUser);
  registerBtn.addEventListener("click", registerUser);
  logoutBtn.addEventListener("click", logoutUser);
  settingsBtn.addEventListener("click", openSettings);

  // Keyboard shortcuts
  document.addEventListener("keydown", handleKeyboardShortcuts);

  // Check connection status on popup open
  checkConnectionStatus();

  // Update stats on popup open
  updateChangeStats();

  function switchTab(tabName) {
    tabBtns.forEach((btn) => btn.classList.remove("active"));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add("active");

    tabContents.forEach((content) => content.classList.remove("active"));
    document.getElementById(`${tabName}-tab`).classList.add("active");
  }

  function syncNow() {
    if (!isConnected()) {
      showError("Not connected to server");
      return;
    }

    syncNowBtn.style.animation = "spin 1s linear infinite";

    chrome.runtime.sendMessage({ action: "syncSnippets" }, function (response) {
      syncNowBtn.style.animation = "";

      if (response && response.success) {
        showNotification("Sync completed successfully!");
        updateChangeStats();
        loadRecentSnippets();
      } else {
        showError("Sync failed: " + (response?.error || "Unknown error"));
      }
    });
  }

  function setupEventListeners() {
    // Existing event listeners
    connectBtn.addEventListener("click", connectToServer);
    disconnectBtn.addEventListener("click", disconnectFromServer);
    openDashboardLink.addEventListener("click", openDashboard);
    viewDocsLink.addEventListener("click", openDocumentation);

    // New event listeners
    tabBtns.forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    syncNowBtn.addEventListener("click", syncNow);
    clearChangesBtn.addEventListener("click", clearChanges);
    captureSnippetBtn.addEventListener("click", captureCodeSnippet);
    viewAllSnippets.addEventListener("click", viewAllSnippetsAction);
    createCollectionBtn.addEventListener("click", createCollection);
    searchSnippets.addEventListener("input", searchSnippetsAction);
    autoSyncToggle.addEventListener("click", toggleAutoSync);
    loginBtn.addEventListener("click", loginUser);
    registerBtn.addEventListener("click", registerUser);
    logoutBtn.addEventListener("click", logoutUser);
    settingsBtn.addEventListener("click", openSettings);

    // Keyboard shortcuts
    document.addEventListener("keydown", handleKeyboardShortcuts);
  }

  function clearChanges() {
    if (confirm("Are you sure you want to clear all cached data?")) {
      chrome.storage.local.clear(function () {
        showNotification("Cache cleared successfully!");
        loadSettings();
        updateChangeStats();
        loadRecentSnippets();
        loadCollections();
      });
    }
  }

  function captureCodeSnippet() {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      chrome.tabs.sendMessage(
        tabs[0].id,
        { action: "captureCode" },
        function (response) {
          if (response && response.success) {
            showNotification("Code snippet captured!");
            updateChangeStats();
            loadRecentSnippets();
          } else {
            showError("Failed to capture code snippet");
          }
        }
      );
    });
  }

  function viewAllSnippetsAction() {
    openDashboard();
  }

  function createCollection() {
    console.log("🔵 Creating collection - start");
    const collectionName = prompt("Enter collection name:");
    if (collectionName && collectionName.trim()) {
      console.log("🔵 Collection name entered:", collectionName.trim());
      console.log("🔵 Checking connection status before creating collection");

      // Check if connected first
      if (!isConnected()) {
        showError("Not connected to server. Please connect first.");
        return;
      }

      // Check authentication
      chrome.storage.local.get(
        ["authToken", "userEmail"],
        function (authResult) {
          console.log("🔵 Auth check for collection creation:", {
            hasToken: !!authResult.authToken,
            hasEmail: !!authResult.userEmail,
          });

          if (!authResult.authToken || !authResult.userEmail) {
            showError("Please login first to create collections");
            showLoginSection();
            return;
          }

          createCollectionBtn.disabled = true;
          createCollectionBtn.textContent = "Creating...";

          console.log(
            "🔵 Sending createCollection message to background script"
          );

          // Add timeout handling
          const messageTimeout = setTimeout(() => {
            console.error(
              "🔴 Collection creation timeout - no response in 10 seconds"
            );
            createCollectionBtn.disabled = false;
            createCollectionBtn.textContent = "Create Collection";
            showError("Request timeout - please try again");
          }, 10000);

          chrome.runtime.sendMessage(
            {
              action: "createCollection",
              name: collectionName.trim(),
              timestamp: Date.now(),
            },
            function (response) {
              clearTimeout(messageTimeout);
              console.log("🔵 Create collection response received:", response);

              createCollectionBtn.disabled = false;
              createCollectionBtn.textContent = "Create Collection";

              if (chrome.runtime.lastError) {
                console.error(
                  "🔴 Chrome runtime error:",
                  chrome.runtime.lastError
                );
                showError(
                  "Extension communication error: " +
                    chrome.runtime.lastError.message
                );
                return;
              }

              if (!response) {
                console.error("🔴 No response received from background script");
                showError(
                  "No response from background script - check background script logs"
                );
                return;
              }

              if (response.success) {
                console.log("🔵 Collection created successfully");
                showNotification("Collection created successfully!");

                // ✅ IMMEDIATELY REFRESH COLLECTIONS LIST
                loadCollections();
                updateChangeStats();

                // ✅ ALSO UPDATE THE COLLECTIONS COUNT
                setTimeout(() => {
                  loadCollections();
                }, 500);
              } else {
                const errorMsg =
                  response.error || "Failed to create collection";
                console.error("🔴 Collection creation failed:", {
                  response: response,
                  error: errorMsg,
                  errorType: response.errorType,
                  serverStatus: response.status,
                  serverResponse: response.data,
                });

                if (response.errorType === "duplicate_name") {
                  showError(
                    "Collection name already exists! Please choose a different name."
                  );
                } else if (
                  errorMsg.includes("authenticated") ||
                  errorMsg.includes("token") ||
                  errorMsg.includes("unauthorized")
                ) {
                  console.error("🔴 Authentication error detected");
                  logoutUser();
                  showError("Authentication expired. Please login again.");
                } else {
                  showError(errorMsg);
                }
              }
            }
          );
        }
      );
    } else {
      console.log("🔵 Collection creation cancelled - no name provided");
    }
  }
  function debugBackgroundConnection() {
    console.log("🔵 Testing background script connection...");

    chrome.runtime.sendMessage(
      { action: "ping", timestamp: Date.now() },
      function (response) {
        if (chrome.runtime.lastError) {
          console.error(
            "🔴 Background script connection failed:",
            chrome.runtime.lastError
          );
        } else {
          console.log("🔵 Background script responded:", response);
        }
      }
    );
  }

  function searchSnippetsAction() {
    const query = searchSnippets.value.trim();
    if (query.length > 2) {
      chrome.runtime.sendMessage(
        {
          action: "searchSnippets",
          query: query,
        },
        function (response) {
          if (response && response.snippets) {
            displaySnippets(response.snippets);
          }
        }
      );
    } else if (query.length === 0) {
      loadRecentSnippets();
    }
  }

  function toggleAutoSync() {
    const currentState = autoSyncToggle.classList.contains("active");
    const newState = !currentState;

    updateToggleState(autoSyncToggle, newState);
    chrome.storage.local.set({ autoSync: newState });

    showNotification(
      `Auto-sync ${newState ? "enabled" : "disabled"}`,
      newState ? "success" : "error"
    );
  }

  function loginUser() {
    const email = emailInput.value.trim();
    const password = passwordInput.value.trim();

    if (!email || !password) {
      showError("Please enter both email and password");
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = "Logging in...";

    chrome.runtime.sendMessage(
      {
        action: "login",
        email: email,
        password: password,
      },
      function (response) {
        // Don't reset button state here - let the message listeners handle it
        console.log("🔵 Login request sent, response:", response);

        // The actual login response will come via WebSocket message listeners
        // Don't process login success/failure here since it's async via WebSocket
        if (chrome.runtime.lastError) {
          loginBtn.disabled = false;
          loginBtn.textContent = "Login";
          showError(
            "Extension communication error: " + chrome.runtime.lastError.message
          );
        }
      }
    );
  }

  function syncAuthWithContentScript() {
    chrome.storage.local.get(["authToken", "userEmail"], function (result) {
      if (result.authToken && result.userEmail) {
        // Notify all tabs about authentication
        chrome.tabs.query({}, function (tabs) {
          tabs.forEach((tab) => {
            chrome.tabs
              .sendMessage(tab.id, {
                type: "AUTH_SYNC",
                token: result.authToken,
                email: result.userEmail,
              })
              .catch(() => {}); // Ignore errors for tabs without content script
          });
        });
      } else {
        console.log("🔵 Skipping auth sync - missing token or email");
      }
    });
  }

  function registerUser() {
    const email = emailInput.value.trim();
    const password = passwordInput.value.trim();

    if (!email || !password) {
      showError("Please enter both email and password");
      return;
    }

    if (password.length < 6) {
      showError("Password must be at least 6 characters");
      return;
    }

    registerBtn.disabled = true;
    registerBtn.textContent = "Registering...";

    chrome.runtime.sendMessage(
      {
        action: "register",
        email: email,
        password: password,
      },
      function (response) {
        registerBtn.disabled = false;
        registerBtn.textContent = "Register";

        if (response && response.success) {
          console.log("🔵 Registration successful, storing auth data:", {
            email: email,
            token: response.token ? "present" : "missing",
          });

          chrome.storage.local.set(
            {
              userEmail: email,
              authToken: response.token,
              isAuthenticated: true,
              loginTimestamp: Date.now(),
            },
            function () {
              console.log("🔵 Registration auth data stored successfully");
              syncAuthWithContentScript();
              showUserSection();
              updateChangeStats();
              loadRecentSnippets();
              loadCollections();
              showNotification("Account created successfully!");
            }
          );
        } else {
          console.error("🔴 Registration failed:", response);
          showError(response?.error || "Registration failed");
        }
      }
    );
  }

  function logoutUser() {
    console.log("🔵 Logging out user");
    chrome.storage.local.remove(
      ["userEmail", "authToken", "isAuthenticated", "loginTimestamp"],
      function () {
        console.log("🔵 Auth data cleared");
        showNotification("Logged out successfully!");
        showLoginSection();
        updateChangeStats();

        // Clear UI state
        emailInput.value = "";
        passwordInput.value = "";
      }
    );
  }

  function openSettings() {
    openDashboard();
  }

  function checkAuthStatus() {
    chrome.storage.local.get(["userEmail", "authToken"], function (result) {
      if (result.userEmail && result.authToken) {
        showUserSection();
      } else {
        showLoginSection();
      }
    });
  }

  function maintainAuthState() {
    console.log("🔵 Checking authentication state...");

    chrome.storage.local.get(
      [
        "userEmail",
        "authToken",
        "isAuthenticated",
        "loginTimestamp",
        "tokenExpiry",
        "lastVerified",
      ],
      function (result) {
        console.log("🔵 Auth state check:", {
          hasEmail: !!result.userEmail,
          hasToken: !!result.authToken,
          isAuthenticated: !!result.isAuthenticated,
          loginAge: result.loginTimestamp
            ? (Date.now() - result.loginTimestamp) / 1000 / 60
            : "no timestamp",
          tokenExpired: result.tokenExpiry
            ? Date.now() > result.tokenExpiry
            : "no expiry set",
          lastVerified: result.lastVerified
            ? (Date.now() - result.lastVerified) / 1000 / 60 + " minutes ago"
            : "never",
        });

        // Check if token has expired
        if (result.tokenExpiry && Date.now() > result.tokenExpiry) {
          console.log("🔴 Token has expired, clearing auth");
          logoutUser();
          return;
        }

        if (result.userEmail && result.authToken && result.isAuthenticated) {
          console.log("🔵 Valid auth found");
          emailInput.value = result.userEmail;

          // Show user section immediately, verify in background
          showUserSection();
          syncAuthWithContentScript();
          updateChangeStats();
          loadRecentSnippets();
          loadCollections();

          // Only verify if not verified recently
          const lastVerified = result.lastVerified || 0;
          const tenMinutesAgo = Date.now() - 10 * 60 * 1000;

          if (lastVerified < tenMinutesAgo && !window.verificationInProgress) {
            console.log("🔵 Performing background verification");
            verifyAuthToken(result.authToken, result.userEmail);
          }
        } else {
          console.log("🔵 No valid auth found, showing login");
          showLoginSection();
        }
      }
    );
  }
  function verifyAuthToken(token, email) {
    console.log("🔵 Verifying auth token...");

    if (!token || !email) {
      console.log("🔴 Missing token or email for verification");
      showLoginSection();
      return;
    }

    // Check if verification was done recently (within last 5 minutes)
    chrome.storage.local.get(["lastVerified"], function (result) {
      const lastVerified = result.lastVerified || 0;
      const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;

      if (lastVerified > fiveMinutesAgo) {
        console.log("🔵 Token verified recently, skipping verification");
        showUserSection();
        syncAuthWithContentScript();
        updateChangeStats();
        loadRecentSnippets();
        loadCollections();
        return;
      }

      // Prevent multiple simultaneous verification requests
      if (window.verificationInProgress) {
        console.log("🔵 Verification already in progress, skipping...");
        return;
      }
      window.verificationInProgress = true;

      // Send verification request to background script
      chrome.runtime.sendMessage(
        {
          action: "verifyAuth",
          token: token,
          email: email,
        },
        function (response) {
          window.verificationInProgress = false;

          console.log("🔵 Token verification response:", response);

          if (chrome.runtime.lastError) {
            console.error(
              "🔴 Chrome runtime error during verification:",
              chrome.runtime.lastError
            );
            // On communication error, keep user logged in
            showUserSection();
            showNotification("Connection issue - staying logged in", "warning");
            return;
          }

          if (!response) {
            console.error("🔴 No response received from verification");
            // Keep user logged in on no response
            showUserSection();
            showNotification(
              "Verification unavailable - staying logged in",
              "warning"
            );
            return;
          }

          if (response.success === true && response.valid === true) {
            console.log("🔵 Token is valid, maintaining login state");

            // Update last verified timestamp
            chrome.storage.local.set({ lastVerified: Date.now() });

            showUserSection();
            syncAuthWithContentScript();
            updateChangeStats();
            loadRecentSnippets();
            loadCollections();
          } else {
            console.log("🔴 Token validation failed:", response);
            handleVerificationError("Session invalid");
          }
        }
      );
    });
  }
  function handleVerificationError(errorMessage, isServerIssue = false) {
    console.log(
      "🔴 Handling verification error:",
      errorMessage,
      "Server issue:",
      isServerIssue
    );

    if (isServerIssue) {
      // For server issues, keep user logged in but show warning
      console.log(
        "🔵 Server issue detected, keeping user logged in with warning"
      );
      showUserSection();
      showNotification("Connection issue - " + errorMessage, "warning");

      // Retry verification after 30 seconds
      setTimeout(() => {
        chrome.storage.local.get(["authToken", "userEmail"], function (result) {
          if (
            result.authToken &&
            result.userEmail &&
            !window.verificationInProgress
          ) {
            console.log("🔵 Retrying token verification after server issue");
            verifyAuthToken(result.authToken, result.userEmail);
          }
        });
      }, 30000);
    } else {
      // For actual auth failures, clear session
      console.log("🔴 Authentication failed, clearing session");
      chrome.storage.local.remove(
        [
          "userEmail",
          "authToken",
          "isAuthenticated",
          "loginTimestamp",
          "tokenExpiry",
        ],
        function () {
          showLoginSection();
          showError("Session expired. Please login again.");
          emailInput.value = "";
          passwordInput.value = "";
        }
      );
    }
  }
  function handleVerificationFailure(response) {
    // This function is now deprecated - use handleVerificationError instead
    console.log(
      "🔵 Using deprecated handleVerificationFailure - redirecting to new handler"
    );

    if (
      response &&
      (response.status_code === 404 || response.status_code >= 500)
    ) {
      handleVerificationError("Server connection issue", true);
    } else {
      handleVerificationError("Authentication failed");
    }
  }
  function recoverSession() {
    console.log("🔵 Attempting session recovery...");

    chrome.storage.local.get(
      ["userEmail", "authToken", "loginTimestamp"],
      function (result) {
        if (result.userEmail && result.authToken) {
          const sessionAge = Date.now() - (result.loginTimestamp || 0);
          const maxSessionAge = 7 * 24 * 60 * 60 * 1000; // 7 days

          if (sessionAge < maxSessionAge) {
            console.log("🔵 Session recovery possible, verifying token...");
            emailInput.value = result.userEmail;
            verifyAuthToken(result.authToken, result.userEmail);
          } else {
            console.log("🔴 Session too old, requiring fresh login");
            logoutUser();
          }
        } else {
          console.log("🔵 No session to recover");
          showLoginSection();
        }
      }
    );
  }

  function showUserSection() {
    loginSection.classList.add("hidden");
    userSection.classList.remove("hidden");
  }

  function showLoginSection() {
    userSection.classList.add("hidden");
    loginSection.classList.remove("hidden");
  }

  function updateChangeStats() {
    chrome.runtime.sendMessage({ action: "getStats" }, function (response) {
      if (response && response.stats) {
        totalSnippetsCount.textContent = response.stats.totalSnippets || 0;
        collectionsCount.textContent = response.stats.collections || 0;

        animateNumber(totalSnippetsCount, response.stats.totalSnippets || 0);
        animateNumber(collectionsCount, response.stats.collections || 0);
      }
    });
  }

  function loadRecentSnippets() {
    chrome.runtime.sendMessage(
      { action: "getRecentSnippets" },
      function (response) {
        if (response && response.snippets) {
          displaySnippets(response.snippets);
        }
      }
    );
  }

  function displaySnippets(snippets) {
    recentSnippetsList.innerHTML = "";

    if (snippets.length === 0) {
      recentSnippetsList.innerHTML = `
            <div style="text-align: center; color: #666; padding: 20px;">
                No snippets found
            </div>
        `;
      return;
    }

    snippets.forEach((snippet) => {
      const snippetElement = document.createElement("div");
      snippetElement.className = "snippet-item";
      snippetElement.innerHTML = `
            <div class="snippet-title">${snippet.title || "Untitled"}</div>
            <div class="snippet-meta">${
              snippet.language || "Unknown"
            } • ${formatDate(snippet.created_at)}</div>
        `;

      snippetElement.addEventListener("click", () => {
        chrome.tabs.create({
          url: `${serverUrlInput.value}/snippet/${snippet.id}`,
        });
      });

      recentSnippetsList.appendChild(snippetElement);
    });
  }

  function loadCollections() {
    chrome.runtime.sendMessage(
      { action: "getCollections" },
      function (response) {
        if (response && response.collections) {
          displayCollections(response.collections);
        }
      }
    );
  }

  function displayCollections(collections) {
    collectionsList.innerHTML = "";

    if (collections.length === 0) {
      collectionsList.innerHTML = `
            <div style="text-align: center; color: #666; padding: 15px; font-size: 12px;">
                No collections yet
            </div>
        `;
      return;
    }

    collections.forEach((collection) => {
      const collectionElement = document.createElement("div");
      collectionElement.className = "snippet-item";
      collectionElement.innerHTML = `
            <div class="snippet-title">📁 ${collection.name}</div>
            <div class="snippet-meta">${
              collection.snippets_count || 0
            } snippets</div>
        `;

      collectionElement.addEventListener("click", () => {
        chrome.tabs.create({
          url: `${serverUrlInput.value}/collection/${collection.id}`,
        });
      });

      collectionsList.appendChild(collectionElement);
    });
  }

  function updateToggleState(toggle, active) {
    if (active) {
      toggle.classList.add("active");
    } else {
      toggle.classList.remove("active");
    }
  }

  function isConnected() {
    return statusIcon.classList.contains("connected");
  }

  function animateNumber(element, targetNumber) {
    const startNumber = parseInt(element.textContent) || 0;
    const duration = 1000;
    const startTime = Date.now();

    function update() {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const currentNumber = Math.floor(
        startNumber + (targetNumber - startNumber) * progress
      );

      element.textContent = currentNumber;

      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }

    update();
  }

  function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
  }

  function handleKeyboardShortcuts(e) {
    if (e.ctrlKey && e.shiftKey && e.key === "S") {
      e.preventDefault();
      captureCodeSnippet();
    }

    if (e.ctrlKey && e.shiftKey && e.key === "D") {
      e.preventDefault();
      openDashboard();
    }

    if (e.ctrlKey && e.shiftKey && e.key === "F") {
      e.preventDefault();
      searchSnippets.focus();
    }
  }

  /**
   * Load saved settings from storage
   */
  function loadSettings() {
    chrome.storage.local.get(
      ["serverUrl", "autoSync", "userEmail"],
      function (result) {
        if (result.serverUrl) {
          serverUrlInput.value = result.serverUrl;
        } else {
          serverUrlInput.value = "http://localhost:5000";
        }

        if (result.autoSync !== undefined) {
          updateToggleState(autoSyncToggle, result.autoSync);
        } else {
          updateToggleState(autoSyncToggle, true);
        }

        if (result.userEmail) {
          emailInput.value = result.userEmail;
        }
      }
    );
  }

  /**
   * Connect to the Flask server
   */
  function connectToServer() {
    const serverUrl = serverUrlInput.value.trim();

    if (!serverUrl) {
      showError("Server URL cannot be empty");
      return;
    }

    updateStatus("connecting", "Connecting...");
    connectBtn.disabled = true;

    // Save the server URL to storage
    chrome.storage.local.set({ serverUrl: serverUrl });

    // Send connection request to background script
    chrome.runtime.sendMessage(
      {
        action: "connect",
        serverUrl: serverUrl,
      },
      function (response) {
        connectBtn.disabled = false;

        if (chrome.runtime.lastError) {
          updateStatus("error", "Connection failed");
          showError("Extension error: " + chrome.runtime.lastError.message);
          return;
        }

        if (response && response.success) {
          updateStatus("connected", "Connected");
          toggleButtons(true);
          showNotification("Connected successfully!");
        } else {
          updateStatus("error", "Connection failed");
          showError(response?.error || "Could not connect to server");
        }
      }
    );
  }

  /**
   * Disconnect from the Flask server
   */
  function disconnectFromServer() {
    chrome.runtime.sendMessage(
      {
        action: "disconnect",
      },
      function (response) {
        updateStatus("disconnected", "Disconnected");
        toggleButtons(false);
        showNotification("Disconnected from server", "error");
      }
    );
  }

  /**
   * Update auto-sync setting
   */

  /**
   * Open the server dashboard in a new tab
   */
  function openDashboard() {
    chrome.storage.local.get(["serverUrl"], function (result) {
      if (result.serverUrl) {
        chrome.tabs.create({ url: result.serverUrl });
      } else {
        showError("No server URL configured");
      }
    });
  }

  /**
   * Open documentation
   */
  function openDocumentation() {
    // Replace with your actual documentation URL when available
    chrome.tabs.create({
      url: "https://github.com/yourusername/documentation",
    });
  }

  /**
   * Check the current connection status
   */
  function checkConnectionStatus() {
    chrome.runtime.sendMessage(
      {
        action: "getStatus",
      },
      function (response) {
        if (response && response.connected) {
          updateStatus("connected", "Connected");
          toggleButtons(true);
        } else {
          updateStatus("disconnected", "Disconnected");
          toggleButtons(false);
        }
      }
    );
  }

  /**
   * Update the connection status UI
   */
  function updateStatus(state, message) {
    statusIcon.className = "status-icon " + state;
    statusText.textContent = message;
  }

  // Auto-refresh stats every 30 seconds
  setInterval(updateChangeStats, 30000);

  // Auto-sync if enabled
  setInterval(() => {
    chrome.storage.local.get(["autoSync"], function (result) {
      if (result.autoSync && isConnected()) {
        syncNow();
      }
    });
  }, 60000); // Every minute

  /**
   * Enable/disable buttons based on connection state
   */
  function toggleButtons(connected) {
    connectBtn.disabled = connected;
    disconnectBtn.disabled = !connected;
    syncNowBtn.style.opacity = connected ? "1" : "0.5";
    clearChangesBtn.style.opacity = connected ? "1" : "0.5";
    captureSnippetBtn.style.opacity = connected ? "1" : "0.5";
    createCollectionBtn.style.opacity = connected ? "1" : "0.5";
  }

  /**
   * Show an error message
   */
  function showError(message, context = "general") {
    const errorDetails = {
      message: message,
      context: context,
      timestamp: new Date().toISOString(),
      url: window.location.href,
      connectionStatus: isConnected() ? "connected" : "disconnected",
      authStatus: "checking...",
      stack: new Error().stack,
    };

    // Check auth status for error context
    chrome.storage.local.get(["authToken", "userEmail"], function (result) {
      errorDetails.authStatus = {
        hasToken: !!result.authToken,
        hasEmail: !!result.userEmail,
        email: result.userEmail || "none",
      };

      console.error("🔴 POPUP ERROR DETAILS:", errorDetails);
    });

    console.error("🔴 POPUP ERROR:", errorDetails);

    // Create a more sophisticated error display
    showNotification(message, "error");

    // Log to background for centralized logging
    chrome.runtime
      .sendMessage({
        action: "logError",
        error: errorDetails,
        source: "popup",
      })
      .catch((err) => {
        console.error("🔴 Failed to send error to background:", err);
      });
  }

  function initBackgroundParticles() {
    const particlesContainer = document.querySelector(".bg-particles");
    const particleCount = 15;

    for (let i = 0; i < particleCount; i++) {
      const particle = document.createElement("div");
      particle.className = "particle";
      particle.style.left = Math.random() * 100 + "%";
      particle.style.top = Math.random() * 100 + "%";
      particle.style.animationDelay = Math.random() * 6 + "s";
      particlesContainer.appendChild(particle);
    }
  }

  /**
   * Show a notification
   */
  function showNotification(message, type = "success") {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll(".notification");
    existingNotifications.forEach((n) => n.remove());

    // Create notification element
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.textContent = message;

    // Add warning styles if needed (add this CSS to your popup styles)
    if (type === "warning") {
      notification.style.backgroundColor = "#ff9800";
      notification.style.color = "white";
    }

    // Add to body
    document.body.appendChild(notification);

    // Remove after appropriate time (longer for warnings)
    const displayTime = type === "warning" ? 8000 : 5000;
    setTimeout(() => {
      notification.style.animation = "slideOut 0.3s ease-in forwards";
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, displayTime);

    console.log(`${type.toUpperCase()}: ${message}`);
  }
});

// Integration Management System
// Modern, Dynamic UI with Advanced Integration Features

class IntegrationManager {
  constructor() {
    this.integrations = new Map();
    this.webhooks = new Map();
    this.apiConnections = new Map();
    this.syncStatus = new Map();

    this.init();
  }

  init() {
    this.loadIntegrations();
    this.initializeUI();
    this.setupEventListeners();
    this.startSyncMonitor();
    this.loadWebhooks();
  }

  initializeUI() {
    this.createIntegrationDashboard();
    this.setupIntegrationCards();
    this.initializeConnectionMonitor();
    this.createWebhookManager();
    this.setupApiKeyManager();
  }

  createIntegrationDashboard() {
    const dashboard = document.createElement("div");
    dashboard.className = "integrations-dashboard";
    dashboard.innerHTML = `
            <div class="dashboard-header">
                <div class="header-content">
                    <h1 class="dashboard-title">
                        <span class="title-icon">🔗</span>
                        Integrations
                    </h1>
                    <p class="dashboard-subtitle">Connect your favorite tools and automate your workflow</p>
                </div>
                <div class="dashboard-actions">
                    <button class="btn-outline" id="webhook-manager-btn">
                        <i class="icon-webhook"></i>
                        Webhooks
                    </button>
                    <button class="btn-outline" id="api-keys-btn">
                        <i class="icon-key"></i>
                        API Keys
                    </button>
                    <button class="btn-primary" id="add-integration-btn">
                        <i class="icon-plus"></i>
                        Add Integration
                    </button>
                </div>
            </div>

            <div class="connection-status-bar">
                <div class="status-indicators">
                    <div class="status-item">
                        <div class="status-dot connected"></div>
                        <span>All Systems Operational</span>
                    </div>
                    <div class="sync-indicator">
                        <div class="sync-spinner"></div>
                        <span>Last sync: <span id="last-sync-time">2 minutes ago</span></span>
                    </div>
                </div>
                <div class="quick-actions">
                    <button class="btn-ghost" id="refresh-all-btn" title="Refresh All Integrations">
                        <i class="icon-refresh"></i>
                    </button>
                    <button class="btn-ghost" id="test-connections-btn" title="Test All Connections">
                        <i class="icon-activity"></i>
                    </button>
                </div>
            </div>

            <div class="integrations-grid" id="integrations-grid">
                <!-- Integration cards will be dynamically inserted here -->
            </div>

            <div class="integration-categories">
                <div class="category-filter">
                    <button class="filter-btn active" data-category="all">All</button>
                    <button class="filter-btn" data-category="development">Development</button>
                    <button class="filter-btn" data-category="communication">Communication</button>
                    <button class="filter-btn" data-category="storage">Storage</button>
                    <button class="filter-btn" data-category="automation">Automation</button>
                </div>
            </div>
        `;

    const container = document.querySelector(".dashboard-main");
    container.innerHTML = "";
    container.appendChild(dashboard);
    this.animateElementIn(dashboard);
  }

  setupIntegrationCards() {
    const integrations = [
      {
        id: "github",
        name: "GitHub",
        description: "Save snippets directly to your repositories",
        category: "development",
        icon: "🐙",
        color: "#24292e",
        status: "connected",
        features: ["Repository sync", "Gist creation", "Branch management"],
        lastSync: Date.now() - 120000,
        config: {
          repos: 12,
          gists: 45,
          branches: 8,
        },
      },
      {
        id: "vscode",
        name: "VS Code",
        description: "Insert snippets directly into your editor",
        category: "development",
        icon: "🔷",
        color: "#007acc",
        status: "connected",
        features: ["Direct insertion", "Snippet preview", "Workspace sync"],
        lastSync: Date.now() - 60000,
        config: {
          workspaces: 3,
          extensions: 1,
          shortcuts: 15,
        },
      },
      {
        id: "slack",
        name: "Slack",
        description: "Share code snippets with your team instantly",
        category: "communication",
        icon: "💬",
        color: "#4a154b",
        status: "connected",
        features: ["Channel sharing", "Direct messages", "Bot commands"],
        lastSync: Date.now() - 300000,
        config: {
          channels: 8,
          messages: 124,
          commands: 6,
        },
      },
      {
        id: "notion",
        name: "Notion",
        description: "Embed snippets in your documentation",
        category: "storage",
        icon: "📝",
        color: "#000000",
        status: "available",
        features: ["Page embedding", "Database sync", "Block creation"],
        config: null,
      },
      {
        id: "discord",
        name: "Discord",
        description: "Share snippets in your developer communities",
        category: "communication",
        icon: "🎮",
        color: "#5865f2",
        status: "available",
        features: ["Server sharing", "Bot integration", "Slash commands"],
        config: null,
      },
      {
        id: "zapier",
        name: "Zapier",
        description: "Automate snippet workflows with 3000+ apps",
        category: "automation",
        icon: "⚡",
        color: "#ff4a00",
        status: "available",
        features: ["Workflow automation", "Trigger setup", "Multi-app sync"],
        config: null,
      },
    ];

    const grid = document.getElementById("integrations-grid");
    integrations.forEach((integration) => {
      const card = this.createIntegrationCard(integration);
      grid.appendChild(card);
      this.integrations.set(integration.id, integration);
    });
  }

  createIntegrationCard(integration) {
    const card = document.createElement("div");
    card.className = `integration-card ${integration.status}`;
    card.dataset.category = integration.category;
    card.style.setProperty("--integration-color", integration.color);

    const statusClass =
      integration.status === "connected"
        ? "connected"
        : integration.status === "error"
        ? "error"
        : "available";

    card.innerHTML = `
            <div class="card-header">
                <div class="integration-icon">
                    <span class="icon-emoji">${integration.icon}</span>
                </div>
                <div class="integration-info">
                    <h3 class="integration-name">${integration.name}</h3>
                    <p class="integration-description">${
                      integration.description
                    }</p>
                </div>
                <div class="integration-status ${statusClass}">
                    <div class="status-indicator"></div>
                    <span class="status-text">${this.getStatusText(
                      integration.status
                    )}</span>
                </div>
            </div>

            <div class="card-content">
                <div class="integration-features">
                    ${integration.features
                      .map(
                        (feature) =>
                          `<span class="feature-tag">${feature}</span>`
                      )
                      .join("")}
                </div>
                
                ${
                  integration.config
                    ? this.renderIntegrationStats(integration.config)
                    : ""
                }
                
                ${
                  integration.status === "connected"
                    ? `<div class="last-sync">
                        <i class="icon-clock"></i>
                        Last sync: ${this.formatRelativeTime(
                          integration.lastSync
                        )}
                    </div>`
                    : ""
                }
            </div>

            <div class="card-actions">
                ${
                  integration.status === "connected"
                    ? `
                    <button class="btn-ghost" onclick="integrationManager.configureIntegration('${integration.id}')">
                        <i class="icon-settings"></i>
                        Configure
                    </button>
                    <button class="btn-ghost" onclick="integrationManager.testConnection('${integration.id}')">
                        <i class="icon-activity"></i>
                        Test
                    </button>
                    <button class="btn-danger-outline" onclick="integrationManager.disconnectIntegration('${integration.id}')">
                        <i class="icon-unlink"></i>
                        Disconnect
                    </button>
                `
                    : `
                    <button class="btn-primary" onclick="integrationManager.connectIntegration('${integration.id}')">
                        <i class="icon-link"></i>
                        Connect
                    </button>
                    <button class="btn-ghost" onclick="integrationManager.learnMore('${integration.id}')">
                        <i class="icon-info"></i>
                        Learn More
                    </button>
                `
                }
            </div>
        `;

    return card;
  }

  renderIntegrationStats(config) {
    const stats = Object.entries(config)
      .map(
        ([key, value]) =>
          `<div class="stat-item">
                <span class="stat-value">${value}</span>
                <span class="stat-label">${key}</span>
            </div>`
      )
      .join("");

    return `<div class="integration-stats">${stats}</div>`;
  }

  connectIntegration(integrationId) {
    const integration = this.integrations.get(integrationId);
    if (!integration) return;

    this.showConnectModal(integration);
  }

  showConnectModal(integration) {
    const modal = document.createElement("div");
    modal.className = "modal-overlay active";
    modal.innerHTML = `
            <div class="modal-content integration-modal">
                <div class="modal-header">
                    <div class="integration-header">
                        <span class="integration-icon">${
                          integration.icon
                        }</span>
                        <div>
                            <h2>Connect ${integration.name}</h2>
                            <p>Authorize access to enable seamless integration</p>
                        </div>
                    </div>
                    <button class="btn-close" onclick="this.closest('.modal-overlay').remove()">
                        <i class="icon-x"></i>
                    </button>
                </div>
                
                <div class="modal-body">
                    <div class="integration-benefits">
                        <h3>What you'll get:</h3>
                        <ul class="benefits-list">
                            ${integration.features
                              .map(
                                (feature) =>
                                  `<li><i class="icon-check"></i>${feature}</li>`
                              )
                              .join("")}
                        </ul>
                    </div>
                    
                    <div class="connection-form">
                        ${this.getConnectionForm(integration.id)}
                    </div>
                    
                    <div class="privacy-notice">
                        <i class="icon-shield"></i>
                        <div>
                            <strong>Your privacy is protected</strong>
                            <p>We only access the data necessary for integration functionality. You can revoke access anytime.</p>
                        </div>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn-primary" onclick="integrationManager.authorizeIntegration('${
                      integration.id
                    }')">
                        <i class="icon-link"></i>
                        Authorize & Connect
                    </button>
                </div>
            </div>
        `;

    document.body.appendChild(modal);
    this.animateElementIn(modal.querySelector(".modal-content"));
  }

  getConnectionForm(integrationId) {
    const forms = {
      github: `
                <div class="form-group">
                    <label>GitHub Token</label>
                    <input type="password" placeholder="ghp_xxxxxxxxxxxx" class="form-input" id="github-token">
                    <small class="form-hint">
                        <a href="https://github.com/settings/tokens" target="_blank">Generate a personal access token</a>
                        with 'repo' and 'gist' permissions
                    </small>
                </div>
                <div class="form-group">
                    <label>Default Repository (Optional)</label>
                    <input type="text" placeholder="username/repository" class="form-input" id="github-repo">
                </div>
            `,
      slack: `
                <div class="oauth-section">
                    <p>Click below to authorize Slack access through OAuth:</p>
                    <button class="btn-oauth slack" onclick="integrationManager.initiateOAuth('slack')">
                        <i class="icon-slack"></i>
                        Connect with Slack
                    </button>
                </div>
            `,
      vscode: `
                <div class="extension-install">
                    <p>Install the VS Code extension to enable integration:</p>
                    <div class="install-steps">
                        <div class="step">
                            <span class="step-number">1</span>
                            <span>Search for "Snippet Manager" in VS Code Extensions</span>
                        </div>
                        <div class="step">
                            <span class="step-number">2</span>
                            <span>Install and reload VS Code</span>
                        </div>
                        <div class="step">
                            <span class="step-number">3</span>
                            <span>Enter your API key when prompted</span>
                        </div>
                    </div>
                    <div class="api-key-display">
                        <label>Your API Key:</label>
                        <div class="key-container">
                            <input type="text" readonly value="sm_${this.generateApiKey()}" class="api-key-input">
                            <button class="btn-copy" onclick="this.previousElementSibling.select(); document.execCommand('copy')">
                                <i class="icon-copy"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `,
      default: `
                <div class="oauth-section">
                    <p>This integration uses OAuth for secure authentication:</p>
                    <button class="btn-oauth" onclick="integrationManager.initiateOAuth('${integrationId}')">
                        <i class="icon-link"></i>
                        Connect with ${integrationId}
                    </button>
                </div>
            `,
    };

    return forms[integrationId] || forms.default;
  }

  createWebhookManager() {
    const webhookSection = document.createElement("div");
    webhookSection.className = "webhook-manager hidden";
    webhookSection.id = "webhook-manager";
    webhookSection.innerHTML = `
            <div class="section-header">
                <h2>Webhook Management</h2>
                <button class="btn-primary" id="create-webhook-btn">
                    <i class="icon-plus"></i>
                    Create Webhook
                </button>
            </div>
            
            <div class="webhooks-list" id="webhooks-list">
                <!-- Webhook items will be dynamically added -->
            </div>
            
            <div class="webhook-templates">
                <h3>Quick Templates</h3>
                <div class="template-grid">
                    <div class="template-card" onclick="integrationManager.useWebhookTemplate('snippet-created')">
                        <i class="icon-plus-circle"></i>
                        <h4>Snippet Created</h4>
                        <p>Trigger when new snippets are added</p>
                    </div>
                    <div class="template-card" onclick="integrationManager.useWebhookTemplate('collection-shared')">
                        <i class="icon-share"></i>
                        <h4>Collection Shared</h4>
                        <p>Notify when collections are shared</p>
                    </div>
                    <div class="template-card" onclick="integrationManager.useWebhookTemplate('team-activity')">
                        <i class="icon-users"></i>
                        <h4>Team Activity</h4>
                        <p>Track team collaboration events</p>
                    </div>
                </div>
            </div>
        `;

    document.querySelector(".dashboard-main").appendChild(webhookSection);
  }

  setupEventListeners() {
    // Category filters
    document.querySelectorAll(".filter-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        this.filterIntegrations(e.target.dataset.category);
        document
          .querySelectorAll(".filter-btn")
          .forEach((b) => b.classList.remove("active"));
        e.target.classList.add("active");
      });
    });

    // Webhook manager toggle
    document
      .getElementById("webhook-manager-btn")
      ?.addEventListener("click", () => {
        this.toggleWebhookManager();
      });

    // API keys manager
    document.getElementById("api-keys-btn")?.addEventListener("click", () => {
      this.showApiKeysManager();
    });

    // Refresh all integrations
    document
      .getElementById("refresh-all-btn")
      ?.addEventListener("click", () => {
        this.refreshAllIntegrations();
      });

    // Test all connections
    document
      .getElementById("test-connections-btn")
      ?.addEventListener("click", () => {
        this.testAllConnections();
      });

    // Create webhook
    document
      .getElementById("create-webhook-btn")
      ?.addEventListener("click", () => {
        this.showCreateWebhookModal();
      });
  }

  filterIntegrations(category) {
    const cards = document.querySelectorAll(".integration-card");
    cards.forEach((card) => {
      if (category === "all" || card.dataset.category === category) {
        card.style.display = "block";
        this.animateElementIn(card);
      } else {
        card.style.display = "none";
      }
    });
  }

  async authorizeIntegration(integrationId) {
    this.showLoadingState(integrationId);

    try {
      const response = await fetch(
        `/api/integrations/${integrationId}/authorize`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${this.getAuthToken()}`,
          },
          body: JSON.stringify(this.getAuthData(integrationId)),
        }
      );

      if (response.ok) {
        const result = await response.json();
        this.handleSuccessfulConnection(integrationId, result);
        this.showNotification({
          type: "success",
          title: "Connected Successfully",
          message: `${integrationId} integration is now active`,
          icon: "check-circle",
        });
      } else {
        throw new Error("Authorization failed");
      }
    } catch (error) {
      this.handleConnectionError(integrationId, error);
      this.showNotification({
        type: "error",
        title: "Connection Failed",
        message: `Could not connect to ${integrationId}. Please try again.`,
        icon: "alert-circle",
      });
    } finally {
      this.hideLoadingState(integrationId);
      document.querySelector(".modal-overlay")?.remove();
    }
  }

  showCreateWebhookModal() {
    const modal = document.createElement("div");
    modal.className = "modal-overlay active";
    modal.innerHTML = `
            <div class="modal-content webhook-modal">
                <div class="modal-header">
                    <h2>Create Webhook</h2>
                    <button class="btn-close" onclick="this.closest('.modal-overlay').remove()">
                        <i class="icon-x"></i>
                    </button>
                </div>
                
                <div class="modal-body">
                    <div class="webhook-form">
                        <div class="form-group">
                            <label>Webhook Name</label>
                            <input type="text" placeholder="My Webhook" class="form-input" id="webhook-name">
                        </div>
                        
                        <div class="form-group">
                            <label>Target URL</label>
                            <input type="url" placeholder="https://api.example.com/webhook" class="form-input" id="webhook-url">
                        </div>
                        
                        <div class="form-group">
                            <label>Events to Listen</label>
                            <div class="checkbox-group">
                                <label class="checkbox-label">
                                    <input type="checkbox" value="snippet.created">
                                    <span class="checkbox-custom"></span>
                                    Snippet Created
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" value="snippet.updated">
                                    <span class="checkbox-custom"></span>
                                    Snippet Updated
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" value="collection.shared">
                                    <span class="checkbox-custom"></span>
                                    Collection Shared
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" value="team.member_added">
                                    <span class="checkbox-custom"></span>
                                    Team Member Added
                                </label>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label>HTTP Method</label>
                            <select class="form-select" id="webhook-method">
                                <option value="POST">POST</option>
                                <option value="PUT">PUT</option>
                                <option value="PATCH">PATCH</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label>Custom Headers (Optional)</label>
                            <textarea placeholder='{"Authorization": "Bearer token", "Content-Type": "application/json"}' 
                                      class="form-textarea" id="webhook-headers"></textarea>
                        </div>
                        
                        <div class="form-group">
                            <label class="checkbox-label">
                                <input type="checkbox" id="webhook-active" checked>
                                <span class="checkbox-custom"></span>
                                Active (receive events immediately)
                            </label>
                        </div>
                    </div>
                    
                    <div class="webhook-preview">
                        <h3>Payload Preview</h3>
                        <pre class="code-preview"><code>{
  "event": "snippet.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "id": "snippet_123",
    "title": "Sample Snippet",
    "language": "javascript",
    "user": {
      "id": "user_456",
      "name": "John Doe"
    }
  }
}</code></pre>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                    <button class="btn-outline" onclick="integrationManager.testWebhook()">
                        <i class="icon-activity"></i>
                        Test Webhook
                    </button>
                    <button class="btn-primary" onclick="integrationManager.createWebhook()">
                        <i class="icon-plus"></i>
                        Create Webhook
                    </button>
                </div>
            </div>
        `;

    document.body.appendChild(modal);
    this.animateElementIn(modal.querySelector(".modal-content"));
  }

  async createWebhook() {
    const webhookData = {
      name: document.getElementById("webhook-name").value,
      url: document.getElementById("webhook-url").value,
      events: Array.from(
        document.querySelectorAll('input[type="checkbox"]:checked')
      )
        .map((cb) => cb.value)
        .filter((v) => v !== "webhook-active"),
      method: document.getElementById("webhook-method").value,
      headers: this.parseJSON(document.getElementById("webhook-headers").value),
      active: document.getElementById("webhook-active").checked,
    };

    try {
      const response = await fetch("/api/webhooks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.getAuthToken()}`,
        },
        body: JSON.stringify(webhookData),
      });

      if (response.ok) {
        const webhook = await response.json();
        this.addWebhookToList(webhook);
        document.querySelector(".modal-overlay")?.remove();
        this.showNotification({
          type: "success",
          title: "Webhook Created",
          message: "Your webhook is now active and ready to receive events",
          icon: "check-circle",
        });
      }
    } catch (error) {
      this.showNotification({
        type: "error",
        title: "Error",
        message: "Could not create webhook. Please check your configuration.",
        icon: "alert-circle",
      });
    }
  }

  addWebhookToList(webhook) {
    const webhooksList = document.getElementById("webhooks-list");
    const webhookElement = document.createElement("div");
    webhookElement.className = "webhook-item";
    webhookElement.innerHTML = `
            <div class="webhook-header">
                <div class="webhook-info">
                    <h4>${webhook.name}</h4>
                    <p class="webhook-url">${webhook.url}</p>
                </div>
                <div class="webhook-status ${
                  webhook.active ? "active" : "inactive"
                }">
                    <div class="status-dot"></div>
                    <span>${webhook.active ? "Active" : "Inactive"}</span>
                </div>
            </div>
            
            <div class="webhook-details">
                <div class="webhook-events">
                    ${webhook.events
                      .map((event) => `<span class="event-tag">${event}</span>`)
                      .join("")}
                </div>
                <div class="webhook-stats">
                    <span class="stat">Last triggered: ${
                      webhook.lastTriggered || "Never"
                    }</span>
                    <span class="stat">Success rate: ${
                      webhook.successRate || "100"
                    }%</span>
                </div>
            </div>
            
            <div class="webhook-actions">
                <button class="btn-ghost" onclick="integrationManager.testWebhookConnection('${
                  webhook.id
                }')">
                    <i class="icon-activity"></i>
                    Test
                </button>
                <button class="btn-ghost" onclick="integrationManager.editWebhook('${
                  webhook.id
                }')">
                    <i class="icon-edit"></i>
                    Edit
                </button>
                <button class="btn-ghost" onclick="integrationManager.toggleWebhook('${
                  webhook.id
                }')">
                    <i class="icon-${webhook.active ? "pause" : "play"}"></i>
                    ${webhook.active ? "Pause" : "Activate"}
                </button>
                <button class="btn-danger-ghost" onclick="integrationManager.deleteWebhook('${
                  webhook.id
                }')">
                    <i class="icon-trash"></i>
                    Delete
                </button>
            </div>
        `;

    webhooksList.appendChild(webhookElement);
    this.animateElementIn(webhookElement);
    this.webhooks.set(webhook.id, webhook);
  }

  // Utility functions
  formatRelativeTime(timestamp) {
    const now = Date.now();
    const diff = now - timestamp;

    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return `${Math.floor(diff / 86400000)}d ago`;
  }

  getStatusText(status) {
    const statusTexts = {
      connected: "Connected",
      available: "Available",
      error: "Error",
      syncing: "Syncing...",
    };
    return statusTexts[status] || status;
  }

  generateApiKey() {
    return (
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15)
    );
  }

  parseJSON(str) {
    try {
      return JSON.parse(str || "{}");
    } catch {
      return {};
    }
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

  showNotification(notification) {
    // Implementation similar to showNotification in team-collaboration.js
    const notificationCenter =
      document.getElementById("notification-center") ||
      document.createElement("div");
    if (!notificationCenter.id) {
      notificationCenter.id = "notification-center";
      notificationCenter.className = "notification-center";
      document.body.appendChild(notificationCenter);
    }

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

    notificationCenter.appendChild(notif);

    setTimeout(() => {
      if (notif.parentElement) {
        notif.classList.add("slide-out");
        setTimeout(() => notif.remove(), 300);
      }
    }, 5000);
  }

  // Placeholder methods for integration functionality
  // At the beginning of your IntegrationManager class
  async loadIntegrations() {
    try {
      const response = await fetch("/api/v1/integrations/", {
        headers: {
          Authorization: `Bearer ${this.getAuthToken()}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          this.updateIntegrationUI(data.data.integrations);
        }
      }
    } catch (error) {
      console.error("Error loading integrations:", error);
    }
  }

  // Update the getAuthToken method
  getAuthToken() {
    return (
      localStorage.getItem("authToken") || sessionStorage.getItem("authToken")
    );
  }

  startSyncMonitor() {
    setInterval(() => {
      this.updateSyncStatus();
    }, 30000);
  }

  updateSyncStatus() {
    document.getElementById("last-sync-time").textContent =
      this.formatRelativeTime(Date.now() - 120000);
  }

  configureIntegration(id) {
    /* Implementation */
  }
  testConnection(id) {
    /* Implementation */
  }
  disconnectIntegration(id) {
    /* Implementation */
  }
  learnMore(id) {
    /* Implementation */
  }
  toggleWebhookManager() {
    /* Implementation */
  }
  showApiKeysManager() {
    /* Implementation */
  }
  refreshAllIntegrations() {
    /* Implementation */
  }
  testAllConnections() {
    /* Implementation */
  }
  getAuthToken() {
    return localStorage.getItem("auth_token");
  }
  getAuthData(id) {
    /* Implementation */
  }
  handleSuccessfulConnection(id, result) {
    /* Implementation */
  }
  handleConnectionError(id, error) {
    /* Implementation */
  }
  showLoadingState(id) {
    /* Implementation */
  }
  hideLoadingState(id) {
    /* Implementation */
  }
}

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  window.integrationManager = new IntegrationManager();
});

// CSS Variables for dynamic theming
document.documentElement.style.setProperty("--integration-primary", "#3b82f6");
document.documentElement.style.setProperty("--integration-success", "#10b981");
document.documentElement.style.setProperty("--integration-warning", "#f59e0b");
document.documentElement.style.setProperty("--integration-error", "#ef4444");

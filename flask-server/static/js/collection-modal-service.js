/**
 * Universal Collection Modal Service
 * Can be used anywhere in the application
 */
class CollectionModalService {
  constructor() {
    this.modal = null;
    this.form = null;
    this.isInitialized = false;
    this.editingCollectionId = null;
    this.onSuccessCallback = null;
    this.onCloseCallback = null;
  }

  // Initialize the modal (creates HTML dynamically)
  init() {
    if (this.isInitialized) return;

    console.log(
      "🎯 CollectionModal: Initializing universal collection modal..."
    );

    this.createModalHTML();
    this.setupEventListeners();
    this.isInitialized = true;

    console.log("✅ CollectionModal: Universal modal initialized successfully");
  }

  // Create modal HTML dynamically
  createModalHTML() {
    const modalHTML = `
      <div id="universalCollectionModal" class="universal-modal" style="display: none;">
        <div class="universal-modal-overlay"></div>
        <div class="universal-modal-content">
          <div class="universal-modal-header">
            <h2 id="universalCollectionTitle">Create New Collection</h2>
            <button class="universal-close-btn" id="universalCloseBtn">&times;</button>
          </div>
          <form id="universalCollectionForm">
            <div class="universal-form-group">
              <label class="universal-form-label" for="universalCollectionName">Collection Title *</label>
              <input
                type="text"
                class="universal-form-input"
                id="universalCollectionName"
                name="name"
                required
                placeholder="Enter collection title..."
                maxlength="100"
              />
              <small class="universal-form-hint">Maximum 100 characters</small>
            </div>

            <div class="universal-form-group">
              <label class="universal-form-label" for="universalCollectionDescription">Description</label>
              <textarea
                class="universal-form-textarea"
                id="universalCollectionDescription"
                name="description"
                placeholder="Describe your collection..."
                maxlength="500"
                rows="4"
              ></textarea>
              <small class="universal-form-hint">Maximum 500 characters (optional)</small>
            </div>

            <div class="universal-form-group">
              <label class="universal-form-label" for="universalCollectionTags">Tags</label>
              <input
                type="text"
                class="universal-form-input"
                id="universalCollectionTags"
                name="tags"
                placeholder="Enter tags separated by commas (e.g., React, JavaScript, UI)"
                maxlength="200"
              />
              <small class="universal-form-hint">Separate multiple tags with commas</small>
            </div>

            <div class="universal-form-group">
  <label class="universal-checkbox-label">
    <input
      type="checkbox"
      id="universalIsPublic"
      name="is_public"
      class="universal-checkbox"
    />
    <span>Make this collection public</span>
  </label>
  <small class="universal-form-hint">Public collections can be viewed by other users</small>
</div>

<div class="universal-form-group" id="universalTeamSection">
  <label class="universal-form-label">Share with Teams</label>
  <div id="universalTeamsList" class="universal-teams-container">
    <div class="universal-loading">Loading teams...</div>
  </div>
  <small class="universal-form-hint">Select teams to share this collection with</small>
</div>

            <div class="universal-modal-actions">
              <button type="button" class="universal-btn universal-btn-secondary" id="universalCancelBtn">
                Cancel
              </button>
              <button type="submit" class="universal-btn universal-btn-primary" id="universalSubmitBtn">
                <i class="fas fa-plus"></i>
                <span id="universalSubmitText">Create Collection</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    `;

    // Add modal to body
    document.body.insertAdjacentHTML("beforeend", modalHTML);

    // Get references
    this.modal = document.getElementById("universalCollectionModal");
    this.form = document.getElementById("universalCollectionForm");
  }

  // Setup event listeners
  setupEventListeners() {
    const closeBtn = document.getElementById("universalCloseBtn");
    const cancelBtn = document.getElementById("universalCancelBtn");
    const overlay = this.modal.querySelector(".universal-modal-overlay");

    // Close modal events
    closeBtn.addEventListener("click", () => this.close());
    cancelBtn.addEventListener("click", () => this.close());
    overlay.addEventListener("click", () => this.close());

    // Form submission
    this.form.addEventListener("submit", (e) => this.handleSubmit(e));

    // ESC key to close
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.modal.style.display === "flex") {
        this.close();
      }
    });
  }

  // Load user teams for collection sharing
  async loadUserTeams() {
    try {
      console.log("🏢 COLLECTION_MODAL: Loading user teams...");

      const response = await fetch("/api/collections/user-teams", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "include",
      });

      console.log(
        `📡 COLLECTION_MODAL: Teams API response status: ${response.status}`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      console.log("📡 COLLECTION_MODAL: Teams API response:", result);

      if (result.success && result.teams) {
        console.log(`✅ COLLECTION_MODAL: Loaded ${result.teams.length} teams`);
        return result.teams;
      } else {
        console.warn("⚠️ COLLECTION_MODAL: No teams found or API error");
        return [];
      }
    } catch (error) {
      console.error("❌ COLLECTION_MODAL: Failed to load teams:", error);
      return [];
    }
  }

  // Load and display teams in the modal
  async loadAndDisplayTeams() {
    try {
      console.log("🎯 COLLECTION_MODAL: Loading and displaying teams...");

      const teamsContainer = document.getElementById("universalTeamsList");
      if (!teamsContainer) {
        console.error("❌ COLLECTION_MODAL: Teams container not found");
        return;
      }

      // Show loading state
      teamsContainer.innerHTML =
        '<div class="universal-loading">Loading teams...</div>';

      // Load teams from API
      const teams = await this.loadUserTeams();

      if (teams.length === 0) {
        teamsContainer.innerHTML = `
        <div class="universal-no-teams">
          <i class="fas fa-users" style="color: #a0a0a0; margin-bottom: 0.5rem;"></i>
          <p>No teams available</p>
          <small>Create a team first to share collections</small>
        </div>
      `;
        return;
      }

      // Display teams as checkboxes
      teamsContainer.innerHTML = teams
        .map(
          (team) => `
      <label class="universal-team-checkbox">
        <input 
          type="checkbox" 
          name="team_ids" 
          value="${team.id}"
          class="universal-checkbox"
        />
        <div class="universal-team-info">
          <div class="universal-team-name">${team.name}</div>
          <div class="universal-team-role">${team.role} • ${
            team.member_count || 0
          } members</div>
        </div>
      </label>
    `
        )
        .join("");

      console.log(`✅ COLLECTION_MODAL: Displayed ${teams.length} teams`);
    } catch (error) {
      console.error("❌ COLLECTION_MODAL: Error displaying teams:", error);
      const teamsContainer = document.getElementById("universalTeamsList");
      if (teamsContainer) {
        teamsContainer.innerHTML = `
        <div class="universal-error">
          <i class="fas fa-exclamation-triangle" style="color: #ef4444;"></i>
          <p>Failed to load teams</p>
        </div>
      `;
      }
    }
  }

  // Get selected team IDs from checkboxes
  getSelectedTeams() {
    try {
      const checkboxes = document.querySelectorAll(
        'input[name="team_ids"]:checked'
      );
      const teamIds = Array.from(checkboxes).map((cb) => cb.value);
      console.log(`🎯 COLLECTION_MODAL: Selected teams:`, teamIds);
      return teamIds;
    } catch (error) {
      console.error(
        "❌ COLLECTION_MODAL: Error getting selected teams:",
        error
      );
      return [];
    }
  }

  // Open modal for creating new collection
  async openForCreate(options = {}) {
    console.log("🎯 CollectionModal: Opening for CREATE mode");

    if (!this.isInitialized) this.init();

    this.editingCollectionId = null;
    this.onSuccessCallback = options.onSuccess || null;
    this.onCloseCallback = options.onClose || null;

    // Reset form and set create mode
    this.form.reset();
    document.getElementById("universalCollectionTitle").textContent =
      "Create New Collection";
    document.getElementById("universalSubmitText").textContent =
      "Create Collection";

    // Load teams for sharing
    await this.loadAndDisplayTeams();

    // Show modal
    this.modal.style.display = "flex";
    this.modal.classList.add("active");

    // Focus on name input
    setTimeout(() => {
      document.getElementById("universalCollectionName").focus();
    }, 100);
  }
  // Open modal for editing existing collection
  openForEdit(collection, options = {}) {
    console.log("🎯 CollectionModal: Opening for EDIT mode", collection);

    if (!this.isInitialized) this.init();

    this.editingCollectionId = collection.id;
    this.onSuccessCallback = options.onSuccess || null;
    this.onCloseCallback = options.onClose || null;

    // Populate form with existing data
    document.getElementById("universalCollectionName").value =
      collection.name || "";
    document.getElementById("universalCollectionDescription").value =
      collection.description || "";
    document.getElementById("universalCollectionTags").value =
      collection.tags || "";
    document.getElementById("universalIsPublic").checked =
      collection.is_public || false;

    // Set edit mode
    document.getElementById("universalCollectionTitle").textContent =
      "Edit Collection";
    document.getElementById("universalSubmitText").textContent =
      "Update Collection";

    // Show modal
    this.modal.style.display = "flex";
    this.modal.classList.add("active");

    // Focus on name input
    setTimeout(() => {
      document.getElementById("universalCollectionName").focus();
    }, 100);
  }

  // Open modal for sharing collection with teams
  async openShareModal(collectionId, collectionName) {
    console.log(
      "🔗 CollectionModal: Opening SHARE modal for collection:",
      collectionId
    );

    if (!this.isInitialized) this.init();

    // Create share modal HTML
    this.createShareModalHTML(collectionId, collectionName);

    // Load teams and show which ones already have access
    await this.loadTeamsForSharing(collectionId);

    // Show modal
    const shareModal = document.getElementById("universalShareModal");
    shareModal.style.display = "flex";
    shareModal.classList.add("active");
  }

  // Create share modal HTML
  createShareModalHTML(collectionId, collectionName) {
    // Remove existing share modal if any
    const existingModal = document.getElementById("universalShareModal");
    if (existingModal) {
      existingModal.remove();
    }

    const shareModalHTML = `
    <div id="universalShareModal" class="universal-modal" style="display: none;">
      <div class="universal-modal-overlay" onclick="this.parentElement.style.display='none'"></div>
      <div class="universal-modal-content">
        <div class="universal-modal-header">
          <h2>🔗 Share "${collectionName}"</h2>
          <button class="universal-close-btn" onclick="document.getElementById('universalShareModal').style.display='none'">&times;</button>
        </div>
        
        <div class="universal-share-tabs">
          <button class="universal-tab-btn active" onclick="switchShareTab('created')">Created Teams</button>
          <button class="universal-tab-btn" onclick="switchShareTab('joined')">Joined Teams</button>
        </div>
        
        <div id="shareTeamsContainer" class="universal-teams-container" style="min-height: 200px;">
          <div class="universal-loading">Loading teams...</div>
        </div>
        
        <div class="universal-modal-actions">
          <button type="button" class="universal-btn universal-btn-secondary" onclick="document.getElementById('universalShareModal').style.display='none'">
            Cancel
          </button>
          <button type="button" class="universal-btn universal-btn-primary" onclick="shareWithSelectedTeams('${collectionId}')">
            <i class="fas fa-share"></i>
            Share with Selected Teams
          </button>
        </div>
      </div>
    </div>
  `;

    document.body.insertAdjacentHTML("beforeend", shareModalHTML);
  }

  // Load teams for sharing with current share status
  async loadTeamsForSharing(collectionId) {
    try {
      console.log("🏢 Loading teams for sharing collection:", collectionId);

      const container = document.getElementById("shareTeamsContainer");
      container.innerHTML =
        '<div class="universal-loading">Loading teams...</div>';

      // Load user teams
      const teams = await this.loadUserTeams();

      // Load already shared teams
      const sharedTeams = await this.getSharedTeams(collectionId);
      const sharedTeamIds = new Set(sharedTeams.map((t) => t.id));

      if (teams.length === 0) {
        container.innerHTML = `
        <div class="universal-no-teams">
          <i class="fas fa-users"></i>
          <p>No teams available</p>
          <small>Create a team first to share collections</small>
        </div>
      `;
        return;
      }

      // Separate created vs joined teams
      // 🔥 FIXED: Proper team separation logic
      const createdTeams = teams.filter((t) => {
        const role = String(t.role || "").toUpperCase();
        return (
          role === "OWNER" ||
          t.is_team_creator === true ||
          t.team_type === "created" ||
          t.is_owner === true
        );
      });

      const joinedTeams = teams.filter((t) => {
        const role = String(t.role || "").toUpperCase();
        return !(
          role === "OWNER" ||
          t.is_team_creator === true ||
          t.team_type === "created" ||
          t.is_owner === true
        );
      });

      // Store teams data globally for tab switching
      window.shareTeamsData = {
        created: createdTeams,
        joined: joinedTeams,
        shared: sharedTeamIds,
      };

      // Display created teams by default
      this.displayShareTeams("created");
    } catch (error) {
      console.error("❌ Error loading teams for sharing:", error);
      document.getElementById("shareTeamsContainer").innerHTML = `
      <div class="universal-error">
        <i class="fas fa-exclamation-triangle"></i>
        <p>Failed to load teams</p>
      </div>
    `;
    }
  }

  // Get teams collection is already shared with
  async getSharedTeams(collectionId) {
    try {
      const response = await fetch(
        `/api/collections/${collectionId}/shared-teams`,
        {
          credentials: "include",
        }
      );

      if (response.ok) {
        const result = await response.json();
        return result.shared_teams || [];
      }
      return [];
    } catch (error) {
      console.error("❌ Error getting shared teams:", error);
      return [];
    }
  }

  // Display teams for sharing
  displayShareTeams(tabType) {
    const container = document.getElementById("shareTeamsContainer");
    const teams = window.shareTeamsData[tabType] || [];
    const sharedTeamIds = window.shareTeamsData.shared || new Set();

    if (teams.length === 0) {
      container.innerHTML = `
      <div class="universal-no-teams">
        <i class="fas fa-users"></i>
        <p>No ${tabType} teams</p>
      </div>
    `;
      return;
    }

    container.innerHTML = teams
      .map(
        (team) => `
    <label class="universal-team-checkbox">
      <input 
        type="checkbox" 
        name="share_team_ids" 
        value="${team.id}"
        class="universal-checkbox"
        ${sharedTeamIds.has(team.id) ? "checked" : ""}
      />
      <div class="universal-team-info">
        <div class="universal-team-name">
          ${team.name} 
          ${
            sharedTeamIds.has(team.id)
              ? '<span style="color: #10b981;">✓ Shared</span>'
              : ""
          }
        </div>
        <div class="universal-team-role">${team.role} • ${
          team.member_count || 0
        } members</div>
      </div>
    </label>
  `
      )
      .join("");
  }

  // Close modal
  close() {
    console.log("🎯 CollectionModal: Closing modal");

    this.modal.style.display = "none";
    this.modal.classList.remove("active");
    this.form.reset();
    this.editingCollectionId = null;

    // Call close callback if provided
    if (this.onCloseCallback) {
      this.onCloseCallback();
    }
  }

  // Handle form submission
  async handleSubmit(e) {
    e.preventDefault();
    console.log("🎯 CollectionModal: Form submitted");

    const formData = {
      name: document.getElementById("universalCollectionName").value.trim(),
      description: document
        .getElementById("universalCollectionDescription")
        .value.trim(),
      tags: document.getElementById("universalCollectionTags").value.trim(),
      is_public: document.getElementById("universalIsPublic").checked,
      team_ids: this.getSelectedTeams(),
    };

    // Validation
    if (!formData.name) {
      this.showToast("Collection name is required", "error");
      return;
    }

    if (formData.name.length > 100) {
      this.showToast("Collection name must be 100 characters or less", "error");
      return;
    }

    // Show loading state
    const submitBtn = document.getElementById("universalSubmitBtn");
    const originalHTML = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    submitBtn.disabled = true;

    try {
      const url = this.editingCollectionId
        ? `/api/collections/${this.editingCollectionId}`
        : "/api/collections";
      const method = this.editingCollectionId ? "PUT" : "POST";

      console.log(`🎯 CollectionModal: Making ${method} request to ${url}`);

      const response = await fetch(url, {
        method: method,
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify(formData),
      });

      const result = await response.json();
      console.log("🎯 CollectionModal: Response:", result);

      if (response.ok && result.success) {
        const action = this.editingCollectionId ? "updated" : "created";
        this.showToast(`Collection ${action} successfully! 🎉`, "success");

        this.close();

        // Call success callback if provided
        if (this.onSuccessCallback) {
          this.onSuccessCallback(result.collection);
        }
      } else {
        this.showToast(result.message || "Failed to save collection", "error");
      }
    } catch (error) {
      console.error("❌ CollectionModal: Error:", error);
      this.showToast("Failed to save collection. Please try again.", "error");
    } finally {
      // Reset button state
      submitBtn.innerHTML = originalHTML;
      submitBtn.disabled = false;
    }
  }

  // Show toast notification
  showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `universal-toast universal-toast-${type}`;

    const colors = {
      success: "#10b981",
      error: "#ef4444",
      info: "#3b82f6",
    };

    toast.style.cssText = `
      position: fixed;
      top: 2rem;
      right: 2rem;
      background: ${colors[type]};
      color: white;
      padding: 1rem 1.5rem;
      border-radius: 12px;
      z-index: 10000;
      font-weight: 500;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
      animation: slideInRight 0.3s ease;
    `;

    toast.innerHTML = `
      <i class="fas fa-${
        type === "success"
          ? "check-circle"
          : type === "error"
          ? "exclamation-circle"
          : "info-circle"
      }" style="margin-right: 8px;"></i>
      <span>${message}</span>
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = "slideOutRight 0.3s ease forwards";
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, 3000);
  }
}

// Create global instance
window.CollectionModal = new CollectionModalService();
// Global functions for share modal
window.switchShareTab = function (tabType) {
  // Update tab buttons
  document.querySelectorAll(".universal-tab-btn").forEach((btn) => {
    btn.classList.remove("active");
  });
  event.target.classList.add("active");

  // Display teams for selected tab
  if (window.CollectionModal) {
    window.CollectionModal.displayShareTeams(tabType);
  }
};

window.shareWithSelectedTeams = async function (collectionId) {
  try {
    const checkboxes = document.querySelectorAll(
      'input[name="share_team_ids"]:checked'
    );
    const teamIds = Array.from(checkboxes).map((cb) => cb.value);

    if (teamIds.length === 0) {
      window.CollectionModal.showToast(
        "Please select at least one team",
        "error"
      );
      return;
    }

    console.log("🔗 Sharing collection with teams:", teamIds);

    const response = await fetch(`/api/collections/${collectionId}/share`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify({
        team_ids: teamIds,
        sharing_type: "copy",
      }),
    });

    const result = await response.json();

    // ✅ FIXED: Proper success/error handling
    if (result.success) {
      // ✅ SUCCESS: Show green notification
      window.CollectionModal.showToast(
        `Collection shared with ${result.shared_count} team(s)! 🎉`,
        "success"
      );
      document.getElementById("universalShareModal").style.display = "none";

      // ✅ FIXED: Refresh logic moved inside success block
      if (
        window.location.pathname.includes("/teams/detail/") ||
        window.location.pathname.includes("/api/teams/detail/")
      ) {
        console.log("🔄 REFRESHING: Team collections after sharing");

        // Method 1: Reload collections via neuralUI
        if (
          window.neuralUI &&
          typeof window.neuralUI.loadCollections === "function"
        ) {
          setTimeout(() => {
            window.neuralUI.loadCollections();
          }, 1000);
        }

        // Method 2: Force page refresh as fallback
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      }
    } else {
      // ❌ ERROR: Show red notification only on actual failure
      window.CollectionModal.showToast(
        result.message || "Failed to share collection",
        "error"
      );
    }
  } catch (error) {
    console.error("❌ Error sharing collection:", error);
    window.CollectionModal.showToast("Failed to share collection", "error");
  }
};

// CSS Styles
const styles = `
<style>
.universal-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.3s ease;
}

.universal-modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(10px);
}

.universal-modal-content {
  position: relative;
  background: #1a1a1a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 2rem;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  animation: slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.universal-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.universal-modal-header h2 {
  font-size: 1.3rem;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.universal-close-btn {
  background: none;
  border: none;
  color: #a0a0a0;
  font-size: 1.5rem;
  cursor: pointer;
  transition: color 0.2s ease;
}

.universal-close-btn:hover {
  color: #ffffff;
}

.universal-form-group {
  margin-bottom: 1.5rem;
}

.universal-form-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #ffffff;
}

.universal-form-input,
.universal-form-textarea {
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.75rem;
  color: #ffffff;
  font-size: 0.9rem;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.universal-form-input:focus,
.universal-form-textarea:focus {
  outline: none;
  border-color: #00d4ff;
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
}

.universal-form-textarea {
  min-height: 100px;
  resize: vertical;
}

.universal-form-hint {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.8rem;
  color: #a0a0a0;
}

.universal-checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: #ffffff;
}

.universal-checkbox {
  width: 18px;
  height: 18px;
  accent-color: #00d4ff;
  cursor: pointer;
}

.universal-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}

.universal-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
}

.universal-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.universal-btn-primary {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
}

.universal-btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(0, 212, 255, 0.3);
}

.universal-btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.universal-btn-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from {
    transform: translateY(50px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes slideInRight {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

@keyframes slideOutRight {
  from { transform: translateX(0); opacity: 1; }
  to { transform: translateX(100%); opacity: 0; }
}

@media (max-width: 768px) {
  .universal-modal-content {
    width: 95%;
    padding: 1.5rem;
  }
  
  .universal-modal-actions {
    flex-direction: column;
  }
  
  .universal-btn {
    width: 100%;
    justify-content: center;
  }
}

.universal-teams-container {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.02);
}

.universal-team-checkbox {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s ease;
  margin-bottom: 0.5rem;
}

.universal-team-checkbox:hover {
  background: rgba(255, 255, 255, 0.05);
}

.universal-team-checkbox:last-child {
  margin-bottom: 0;
}

.universal-team-info {
  flex: 1;
}

.universal-team-name {
  font-weight: 500;
  color: #ffffff;
  margin-bottom: 0.25rem;
}

.universal-team-role {
  font-size: 0.8rem;
  color: #a0a0a0;
}

.universal-loading,
.universal-no-teams,
.universal-error {
  text-align: center;
  padding: 2rem;
  color: #a0a0a0;
}

.universal-no-teams i,
.universal-error i {
  font-size: 2rem;
  display: block;
  margin-bottom: 0.5rem;
}

.universal-share-tabs {
  display: flex;
  margin-bottom: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.universal-tab-btn {
  flex: 1;
  padding: 0.75rem;
  background: none;
  border: none;
  color: #a0a0a0;
  cursor: pointer;
  transition: all 0.2s ease;
  border-bottom: 2px solid transparent;
}

.universal-tab-btn.active {
  color: #00d4ff;
  border-bottom-color: #00d4ff;
}

.universal-tab-btn:hover {
  color: #ffffff;
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML("beforeend", styles);

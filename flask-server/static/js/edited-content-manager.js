// ===== EDITED CONTENT MANAGER - REAL-TIME SYSTEM =====

class EditedContentManager {
  constructor() {
    this.teamId = null;
    this.currentUserId = null;
    this.groupedEdits = [];
    this.socket = null;
    this.isInitialized = false;
    this.animationQueue = [];
    this.init();
  }

  init() {
    console.log("✏️ EDITED_CONTENT: Initializing manager");

    this.teamId = this.extractTeamId();
    this.currentUserId = this.getCurrentUserId();

    this.setupWebSocketListeners();
    this.setupEventListeners();
    this.setupAnimationSystem();

    this.isInitialized = true;
    console.log("✅ EDITED_CONTENT: Manager initialized");
  }

  // ===== WEBSOCKET REAL-TIME SYSTEM =====

  setupWebSocketListeners() {
    console.log("🔧 EDITED_CONTENT: Setting up WebSocket listeners");

    // Wait for Socket.IO connection
    const checkSocket = () => {
      if (window.teamChatSocket && window.teamChatSocket.connected) {
        this.socket = window.teamChatSocket;
        this.registerSocketEvents();
        console.log("✅ EDITED_CONTENT: WebSocket connected");
      } else {
        setTimeout(checkSocket, 1000);
      }
    };

    checkSocket();
  }

  registerSocketEvents() {
    // Listen for new edits created
    this.socket.on("edit_created", (data) => {
      console.log("🆕 EDITED_CONTENT: New edit created:", data);
      this.handleNewEdit(data);
    });

    // Listen for edits deleted
    this.socket.on("edit_deleted", (data) => {
      console.log("🗑️ EDITED_CONTENT: Edit deleted:", data);
      this.handleEditDeleted(data);
    });

    // Listen for edit updates
    this.socket.on("edit_updated", (data) => {
      console.log("✏️ EDITED_CONTENT: Edit updated:", data);
      this.handleEditUpdated(data);
    });

    console.log("✅ EDITED_CONTENT: Socket events registered");
  }

  // ===== REAL-TIME EVENT HANDLERS =====

  handleNewEdit(data) {
    if (data.team_id !== this.teamId) return;

    console.log("🆕 PROCESSING NEW EDIT:", data.edit);

    // Check if we're on the edited content tab
    if (!this.isEditedContentTabActive()) {
      this.showNotification(
        `New edit created by ${data.edit.editor_name}`,
        "info"
      );
      return;
    }

    // Add edit to existing group or create new group
    this.addEditToDisplay(data.edit);

    // Show notification
    this.showNotification(
      `New edit added by ${data.edit.editor_name}`,
      "success"
    );
  }

  handleEditDeleted(data) {
    if (data.team_id !== this.teamId) return;

    console.log("🗑️ PROCESSING EDIT DELETION:", data);

    // Remove edit card with animation
    this.removeEditFromDisplay(data.edit_id, data.original_snippet_id);

    // Show notification
    this.showNotification("Edit deleted", "info");
  }

  handleEditUpdated(data) {
    if (data.team_id !== this.teamId) return;

    console.log("✏️ PROCESSING EDIT UPDATE:", data);

    // Update existing edit card
    this.updateEditInDisplay(data.edit);
  }

  // ===== DISPLAY MANAGEMENT =====

  addEditToDisplay(edit) {
    const grid = document.getElementById("editedSnippetsGrid");
    if (!grid) return;

    // Check if row for this original snippet exists
    let existingRow = grid.querySelector(
      `[data-original-snippet-id="${edit.original_snippet_id}"]`
    );

    if (existingRow) {
      // Add card to existing row
      this.addCardToExistingRow(existingRow, edit);
    } else {
      // Create new row
      this.createNewRowWithEdit(edit);
    }
  }

  addCardToExistingRow(row, edit) {
    const cardsContainer = row.querySelector(".edited-snippet-cards");
    if (!cardsContainer) return;

    // Create new card
    const cardHTML = this.createEditedSnippetCardHTML(edit);
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = cardHTML;
    const newCard = tempDiv.firstElementChild;

    // Add card with animation
    cardsContainer.appendChild(newCard);
    this.animateCardIn(newCard);

    // Update edit count
    this.updateEditCount(row);

    console.log("✅ EDITED_CONTENT: Card added to existing row");
  }

  createNewRowWithEdit(edit) {
    const grid = document.getElementById("editedSnippetsGrid");
    if (!grid) return;

    // Remove empty state if exists
    const emptyState = grid.querySelector(".empty-matrix");
    if (emptyState) {
      emptyState.remove();
    }

    // Create new group structure
    const newGroup = {
      original_snippet_id: edit.original_snippet_id,
      original_title: edit.original_title || "Unknown Snippet",
      edits: [edit],
    };

    // Create row element
    const row = this.createEditedSnippetRow(newGroup);

    // Add row with animation
    grid.appendChild(row);
    this.animateRowIn(row);

    console.log("✅ EDITED_CONTENT: New row created with edit");
  }

  removeEditFromDisplay(editId, originalSnippetId) {
    const card = document.querySelector(`[data-edit-id="${editId}"]`);
    if (!card) return;

    // Animate card out
    this.animateCardOut(card, () => {
      card.remove();

      // Check if row is now empty
      const row = document.querySelector(
        `[data-original-snippet-id="${originalSnippetId}"]`
      );
      if (row) {
        const remainingCards = row.querySelectorAll(".edited-snippet-card");

        if (remainingCards.length === 0) {
          // Remove entire row
          this.animateRowOut(row, () => {
            row.remove();
            this.checkForEmptyState();
          });
        } else {
          // Update edit count
          this.updateEditCount(row);
        }
      }
    });

    console.log("✅ EDITED_CONTENT: Edit removed from display");
  }

  updateEditInDisplay(edit) {
    const card = document.querySelector(`[data-edit-id="${edit.id}"]`);
    if (!card) return;

    // Update card content
    const descriptionElement = card.querySelector(".edit-description");
    if (descriptionElement) {
      descriptionElement.textContent = `"${edit.edit_description}"`;
    }

    // Add update animation
    this.animateCardUpdate(card);

    console.log("✅ EDITED_CONTENT: Edit updated in display");
  }

  updateEditCount(row) {
    const countElement = row.querySelector(".edit-count");
    const cardCount = row.querySelectorAll(".edited-snippet-card").length;

    if (countElement) {
      countElement.textContent = `${cardCount} edit${
        cardCount !== 1 ? "s" : ""
      }`;
    }
  }

  checkForEmptyState() {
    const grid = document.getElementById("editedSnippetsGrid");
    if (!grid) return;

    const rows = grid.querySelectorAll(".edited-snippet-row");
    if (rows.length === 0) {
      // Show empty state
      grid.innerHTML = this.createEmptyState();
    }
  }

  // ===== ANIMATION SYSTEM =====

  setupAnimationSystem() {
    console.log("🎬 EDITED_CONTENT: Setting up animation system");

    // Initialize GSAP if available
    if (typeof gsap !== "undefined") {
      this.useGSAP = true;
      console.log("✅ EDITED_CONTENT: GSAP animations enabled");
    } else {
      this.useGSAP = false;
      console.log("⚠️ EDITED_CONTENT: Using CSS animations fallback");
    }
  }

  animateCardIn(card) {
    if (this.useGSAP) {
      gsap.set(card, { opacity: 0, y: 30, scale: 0.9 });
      gsap.to(card, {
        opacity: 1,
        y: 0,
        scale: 1,
        duration: 0.6,
        ease: "back.out(1.7)",
        onComplete: () => {
          this.animateCardPulse(card);
        },
      });
    } else {
      card.style.opacity = "0";
      card.style.transform = "translateY(30px) scale(0.9)";
      card.style.transition = "all 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55)";

      setTimeout(() => {
        card.style.opacity = "1";
        card.style.transform = "translateY(0) scale(1)";
      }, 50);
    }
  }

  animateCardOut(card, callback) {
    if (this.useGSAP) {
      gsap.to(card, {
        opacity: 0,
        y: -20,
        scale: 0.8,
        duration: 0.4,
        ease: "power2.in",
        onComplete: callback,
      });
    } else {
      card.style.transition = "all 0.4s ease-in";
      card.style.opacity = "0";
      card.style.transform = "translateY(-20px) scale(0.8)";

      setTimeout(callback, 400);
    }
  }

  animateRowIn(row) {
    if (this.useGSAP) {
      gsap.set(row, { opacity: 0, y: 50 });
      gsap.to(row, {
        opacity: 1,
        y: 0,
        duration: 0.8,
        ease: "power3.out",
      });
    } else {
      row.style.opacity = "0";
      row.style.transform = "translateY(50px)";
      row.style.transition = "all 0.8s ease-out";

      setTimeout(() => {
        row.style.opacity = "1";
        row.style.transform = "translateY(0)";
      }, 50);
    }
  }

  animateRowOut(row, callback) {
    if (this.useGSAP) {
      gsap.to(row, {
        opacity: 0,
        y: -30,
        height: 0,
        marginBottom: 0,
        paddingTop: 0,
        paddingBottom: 0,
        duration: 0.6,
        ease: "power2.in",
        onComplete: callback,
      });
    } else {
      row.style.transition = "all 0.6s ease-in";
      row.style.opacity = "0";
      row.style.transform = "translateY(-30px)";
      row.style.height = "0";
      row.style.marginBottom = "0";
      row.style.paddingTop = "0";
      row.style.paddingBottom = "0";
      row.style.overflow = "hidden";

      setTimeout(callback, 600);
    }
  }

  animateCardUpdate(card) {
    if (this.useGSAP) {
      gsap.to(card, {
        scale: 1.05,
        duration: 0.2,
        yoyo: true,
        repeat: 1,
        ease: "power2.inOut",
      });
    } else {
      card.style.transition = "transform 0.2s ease";
      card.style.transform = "scale(1.05)";

      setTimeout(() => {
        card.style.transform = "scale(1)";
      }, 200);
    }
  }

  animateCardPulse(card) {
    if (this.useGSAP) {
      gsap.to(card, {
        boxShadow: "0 0 20px rgba(0, 180, 216, 0.5)",
        duration: 0.3,
        yoyo: true,
        repeat: 1,
        ease: "power2.inOut",
      });
    }
  }

  // ===== DELETE FUNCTIONALITY =====

  async deleteEdit(editId) {
    console.log("🗑️ EDITED_CONTENT: Deleting edit:", editId);

    if (
      !confirm(
        "Are you sure you want to delete this edit? This action cannot be undone."
      )
    ) {
      return;
    }

    try {
      const response = await fetch(`/api/snippet-edits/${editId}`, {
        method: "DELETE",
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
      console.log("✅ EDITED_CONTENT: Delete response:", data);

      // Real-time update will handle UI removal via WebSocket
      this.showNotification("Edit deleted successfully", "success");
    } catch (error) {
      console.error("❌ EDITED_CONTENT: Delete error:", error);
      this.showNotification("Failed to delete edit", "error");
    }
  }

  // ===== COPY FUNCTIONALITY =====

  copyEditCode(editId) {
    console.log("📋 COPY_EDIT: Copying code for edit:", editId);

    try {
      // Find the edit in our data
      let editData = null;

      // Search through grouped edits to find the specific edit
      if (window.neuralState && window.neuralState.state.editedContent) {
        for (const group of window.neuralState.state.editedContent) {
          const foundEdit = group.edits.find((edit) => edit.id === editId);
          if (foundEdit) {
            editData = foundEdit;
            break;
          }
        }
      }

      if (!editData || !editData.code) {
        console.error("❌ COPY_EDIT: Edit data or code not found");
        this.showNotification("No code to copy", "error");
        return;
      }

      // Copy to clipboard
      navigator.clipboard
        .writeText(editData.code)
        .then(() => {
          console.log("✅ COPY_EDIT: Code copied successfully");
          this.showNotification("Code copied to clipboard! 📋", "success");
        })
        .catch((error) => {
          console.error("❌ COPY_EDIT: Clipboard error:", error);

          // Fallback: Create temporary textarea
          this.fallbackCopyToClipboard(editData.code);
        });
    } catch (error) {
      console.error("❌ COPY_EDIT: General error:", error);
      this.showNotification("Failed to copy code", "error");
    }
  }

  // Fallback copy method for older browsers
  fallbackCopyToClipboard(text) {
    try {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      const successful = document.execCommand("copy");
      document.body.removeChild(textArea);

      if (successful) {
        console.log("✅ COPY_EDIT: Fallback copy successful");
        this.showNotification("Code copied to clipboard! 📋", "success");
      } else {
        throw new Error("Fallback copy failed");
      }
    } catch (error) {
      console.error("❌ COPY_EDIT: Fallback copy failed:", error);
      this.showNotification(
        "Copy failed - please select and copy manually",
        "error"
      );
    }
  }

  // ===== VIEW FUNCTIONALITY =====

  viewEdit(editId) {
    console.log("👁️ EDITED_CONTENT: Viewing edit:", editId);

    // Find the edit data
    const edit = this.findEditById(editId);
    if (!edit) {
      this.showNotification("Edit not found", "error");
      return;
    }

    // Open edit viewer modal
    this.openEditViewer(edit);
  }

  openEditViewer(edit) {
    // Create modal overlay
    const modal = document.createElement("div");
    modal.className = "edit-viewer-modal";
    modal.innerHTML = `
      <div class="edit-viewer-overlay" onclick="this.parentElement.remove()"></div>
      <div class="edit-viewer-content">
        <div class="edit-viewer-header">
          <h3>Edit by ${this.escapeHtml(edit.editor_name)}</h3>
          <button class="edit-viewer-close" onclick="this.closest('.edit-viewer-modal').remove()">×</button>
        </div>
        <div class="edit-viewer-body">
          <div class="edit-description-section">
            <h4>Description:</h4>
            <p>"${this.escapeHtml(edit.edit_description)}"</p>
          </div>
          <div class="edit-code-section">
            <h4>Edited Code:</h4>
            <pre><code class="language-${
              edit.language || "text"
            }">${this.escapeHtml(edit.code)}</code></pre>
          </div>
        </div>
        <div class="edit-viewer-footer">
                    <button class="neural-btn" onclick="this.closest('.edit-viewer-modal').remove()">
            <span class="btn-icon">✖️</span>
            <span class="btn-text">CLOSE</span>
          </button>
          <button class="neural-btn neural-btn-primary" onclick="navigator.clipboard.writeText(\`${this.escapeHtml(
            edit.code
          )}\`).then(() => neuralUI.showNotification('Code copied!', 'success'))">
            <span class="btn-icon">📋</span>
            <span class="btn-text">COPY CODE</span>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // Animate modal in
    if (this.useGSAP) {
      gsap.set(modal.querySelector(".edit-viewer-content"), {
        opacity: 0,
        scale: 0.8,
      });
      gsap.to(modal.querySelector(".edit-viewer-content"), {
        opacity: 1,
        scale: 1,
        duration: 0.3,
        ease: "back.out(1.7)",
      });
    }
  }

  // ===== UTILITY METHODS =====

  findEditById(editId) {
    for (const group of this.groupedEdits) {
      const edit = group.edits.find((e) => e.id === editId);
      if (edit) return edit;
    }
    return null;
  }

  isEditedContentTabActive() {
    const tab = document.querySelector('[data-tab="edited-content"]');
    return tab && tab.classList.contains("active");
  }

  extractTeamId() {
    const pathParts = window.location.pathname.split("/");
    return pathParts[pathParts.length - 1];
  }

  getCurrentUserId() {
    const metaUserId = document.querySelector('meta[name="user-id"]')?.content;
    return metaUserId && metaUserId !== "null" ? metaUserId : null;
  }

  createEditedSnippetRow(group) {
    const row = document.createElement("div");
    row.className = "edited-snippet-row";
    row.dataset.originalSnippetId = group.original_snippet_id;

    const editCardsHTML = group.edits
      .map((edit, index) => {
        return this.createEditedSnippetCardHTML(edit, index);
      })
      .join("");

    row.innerHTML = `
      <div class="edited-snippet-row-header">
        <span class="original-snippet-icon">📝</span>
        <h3 class="original-snippet-title">${this.escapeHtml(
          group.original_title
        )}</h3>
        <span class="edit-count">${group.edits.length} edit${
      group.edits.length !== 1 ? "s" : ""
    }</span>
      </div>
      <div class="edited-snippet-cards">
        ${editCardsHTML}
      </div>
    `;

    return row;
  }

  createEditedSnippetCardHTML(edit, index) {
    const editDate = this.formatEditDate(edit.created_at);

    // Create tags for the edit (same as snippet cards)
    const tagsHtml =
      edit.tags && edit.tags.length > 0
        ? edit.tags
            .map(
              (tag) => `<span class="meta-chip">${this.escapeHtml(tag)}</span>`
            )
            .join("")
        : "";

    // Add EDITED chip
    const editedChip = `<span class="meta-chip" style="background: rgba(255, 0, 110, 0.2); border-color: rgba(255, 0, 110, 0.3); color: #ff006e;">✏️ EDITED</span>`;

    // Get code content
    const editCode = edit.code || "No code available";

    // Generate line numbers (same as snippet cards)
    const codeLines = editCode.split("\n");
    const lineCount = codeLines.length;
    const lineNumbers = Array.from({ length: lineCount }, (_, i) => i + 1).join(
      "\n"
    );

    return `
    <div class="snippet-card" data-edit-id="${edit.id}" data-language="${
      edit.language || "text"
    }" data-created="${edit.created_at}" data-id="${edit.id}">
      <div class="snippet-header">
        <div>
          <h3 class="snippet-title">${this.escapeHtml(
            edit.title || "Edited Snippet"
          )}</h3>
          <div class="snippet-meta">
            <span class="meta-chip">${this.escapeHtml(
              edit.language || "Text"
            )}</span>
            ${tagsHtml}
            ${editedChip}
          </div>
          <div class="edit-info" style="
            margin-top: 0.75rem;
            padding: 0.5rem 0.75rem;
            background: rgba(255, 0, 110, 0.1);
            border-left: 3px solid var(--cyber-accent);
            border-radius: 6px;
            font-size: 0.85rem;
          ">
            <div style="color: var(--cyber-neon); font-weight: 500; margin-bottom: 0.25rem;">
              📝 Edited by ${this.escapeHtml(edit.editor_name)} • ${editDate}
            </div>
            <div style="color: var(--cyber-text); font-style: italic;">
              "${this.escapeHtml(edit.edit_description)}"
            </div>
          </div>
        </div>
      </div>
      
      <div class="snippet-code">
        <div class="line-numbers" id="editLineNumbers-${
          edit.id
        }">${lineNumbers}</div>
        <pre class="code-content"><code class="language-${
          edit.language || "text"
        }">${this.escapeHtml(editCode)}</code></pre>
      </div>
      
      <div class="snippet-actions">
        <button class="action-btn" title="Copy Code" onclick="window.editedContentManager.copyEditCode('${
          edit.id
        }')">📋</button>
        <button class="action-btn" title="View Edit" onclick="window.editedContentManager.viewEdit('${
          edit.id
        }')">👁️</button>
        <button class="action-btn" title="Delete Edit" onclick="window.editedContentManager.deleteEdit('${
          edit.id
        }')">🗑️</button>
      </div>
    </div>
  `;
  }

  formatEditDate(dateString) {
    if (!dateString) return "Unknown date";

    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffTime = Math.abs(now - date);
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

      if (diffDays === 1) return "Yesterday";
      if (diffDays < 7) return `${diffDays} days ago`;
      if (diffDays < 30) return `${Math.ceil(diffDays / 7)} weeks ago`;

      return date.toLocaleDateString();
    } catch (error) {
      return "Invalid date";
    }
  }

  createEmptyState() {
    return `
      <div class="empty-matrix">
        <div class="empty-icon">✏️</div>
        <h3 class="empty-title">No Edited Snippets Yet</h3>
        <p class="empty-description">Team members haven't created any snippet edits yet!</p>
        <button class="neural-btn neural-btn-primary" onclick="document.querySelector('[data-tab=\"snippets\"]').click()">
          <span class="btn-icon">✨</span>
          <span class="btn-text">Edit First Snippet</span>
        </button>
      </div>
    `;
  }

  escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  showNotification(message, type = "info") {
    if (
      window.neuralUI &&
      typeof window.neuralUI.showNotification === "function"
    ) {
      window.neuralUI.showNotification(message, type);
    } else {
      console.log(`🔔 EDITED_CONTENT [${type.toUpperCase()}]: ${message}`);
    }
  }

  // ===== EVENT LISTENERS =====

  setupEventListeners() {
    // Refresh button
    document.addEventListener("click", (e) => {
      if (e.target.closest("#refreshEditedContentBtn")) {
        this.refreshEditedContent();
      }
    });

    // Tab change detection
    document.addEventListener("click", (e) => {
      if (e.target.closest('[data-tab="edited-content"]')) {
        setTimeout(() => {
          this.onTabActivated();
        }, 100);
      }
    });
  }

  async refreshEditedContent() {
    console.log("🔄 EDITED_CONTENT: Refreshing content");

    if (
      window.neuralUI &&
      typeof window.neuralUI.loadEditedContent === "function"
    ) {
      await window.neuralUI.loadEditedContent();
    }

    this.showNotification("Content refreshed", "success");
  }

  onTabActivated() {
    console.log("🔄 EDITED_CONTENT: Tab activated");

    // Load content if not already loaded
    if (
      window.neuralUI &&
      typeof window.neuralUI.loadEditedContent === "function"
    ) {
      window.neuralUI.loadEditedContent();
    }
  }

  // Add this method to the EditedContentManager class
  debugButtonClick(editId, action) {
    console.log(`🔧 DEBUG: ${action} button clicked for edit:`, editId);
    console.log(
      "🔧 DEBUG: editedContentManager exists:",
      !!window.editedContentManager
    );
    console.log("🔧 DEBUG: this context:", this);

    if (action === "view") {
      this.viewEdit(editId);
    } else if (action === "delete") {
      this.deleteEdit(editId);
    }
  }
}

// ===== INITIALIZATION =====

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  // Wait for neuralUI to be ready
  const initEditedContentManager = () => {
    if (window.neuralUI) {
      window.editedContentManager = new EditedContentManager();
      console.log("✅ EDITED_CONTENT: Manager globally available");
    } else {
      setTimeout(initEditedContentManager, 500);
    }
  };

  initEditedContentManager();
});

// Export for module systems
if (typeof module !== "undefined" && module.exports) {
  module.exports = EditedContentManager;
}

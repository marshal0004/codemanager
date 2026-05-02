/**
 * Modern Dashboard Functionality
 * Futuristic UI/UX with smooth animations and interactions
 */

class DashboardManager {
  constructor() {
    this.isLoading = false;
    this.theme = this.getStoredTheme() || "dark";
    this.currentView = "grid";
    this.allCollections = [];
    this.searchQuery = "";
    this.selectedTags = new Set();
    this.sortBy = "updated";
    this.sortOrder = "desc";

    // ADD THESE MODAL PROPERTIES:
    this.snippetModal = null;
    this.snippetForm = null;
    this.newSnippetBtn = null;
    this.closeModalBtn = null;
    this.editingSnippetId = null;

    this.init();
  }

  init() {
    this.setupFabMenu();
    this.setupEventListeners();
    this.initializeTheme();
    this.loadDashboardData();
    this.setupKeyboardShortcuts();
    this.initializeAnimations();
    this.setupWebSocket();
    this.setupCollectionLinks(); // Add this line
    this.setupActionButtons();
    this.makeFabDraggable(); // Add this line
    this.initTeamCollaboration(); // Add this line
    this.initializeSidebar(); // Add this line

    // ADD THIS LINE:
    this.initializeSnippetModal();
    this.checkCollectionModalService();
    // 🎯 ADD THIS LINE TO LOAD COLLECTIONS ON INIT
    this.loadCollections();
  }
  // Replace your setupEventListeners method with this one
  setupEventListeners() {
    // Theme toggle - Fix the selector
    const themeToggle = document.querySelector(".theme-toggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", () => this.toggleTheme());
    }

    // Sidebar toggle
    const sidebarToggle = document.querySelector(".sidebar-toggle");
    if (sidebarToggle) {
      sidebarToggle.addEventListener("click", () => this.toggleSidebar());
    }

    // View toggles
    const gridViewBtn = document.getElementById("gridView");
    const listViewBtn = document.getElementById("listView");

    if (gridViewBtn)
      gridViewBtn.addEventListener("click", () => this.setView("grid"));
    if (listViewBtn)
      listViewBtn.addEventListener("click", () => this.setView("list"));

    // Search functionality
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
      searchInput.addEventListener(
        "input",
        this.debounce((e) => {
          this.searchQuery = e.target.value;
          this.filterContent();
        }, 300)
      );
    }

    // Sort options
    const sortSelect = document.getElementById("sortSelect");
    if (sortSelect) {
      sortSelect.addEventListener("change", (e) => {
        const [sortBy, sortOrder] = e.target.value.split("-");
        this.sortBy = sortBy;
        this.sortOrder = sortOrder;
        this.sortContent();
      });
    }

    // Bulk actions
    const selectAllBtn = document.getElementById("selectAll");
    const bulkDeleteBtn = document.getElementById("bulkDelete");
    const bulkExportBtn = document.getElementById("bulkExport");

    if (selectAllBtn)
      selectAllBtn.addEventListener("click", () => this.toggleSelectAll());
    if (bulkDeleteBtn)
      bulkDeleteBtn.addEventListener("click", () => this.bulkDelete());
    if (bulkExportBtn)
      bulkExportBtn.addEventListener("click", () => this.bulkExport());

    // Modal handlers
    this.setupModalHandlers();

    // Drag and drop
    this.setupDragAndDrop();

    // Infinite scroll
    this.setupInfiniteScroll();
  }

  setupFabMenu() {
    const fab = document.querySelector(".fab");
    const fabMenu = document.querySelector(".fab-menu");

    if (fab && fabMenu) {
      // Toggle menu on click
      fab.addEventListener("click", (e) => {
        e.preventDefault();
        fabMenu.classList.toggle("active");
      });

      // Close menu when clicking outside
      document.addEventListener("click", (e) => {
        if (!e.target.closest(".fab-container")) {
          fabMenu.classList.remove("active");
        }
      });

      // Prevent menu from closing when clicking on menu items
      fabMenu.addEventListener("click", (e) => {
        e.stopPropagation();
      });

      // Handle FAB menu item clicks
      document.querySelectorAll(".fab-item").forEach((item) => {
        const action = item.dataset.action;
        console.log(`🚀 Dashboard: Found FAB item - Action: ${action}`);

        item.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          console.log(`🚀 Dashboard: FAB item clicked - Action: ${action}`);

          // Close the FAB menu
          fabMenu.classList.remove("active");

          // Handle the action
          switch (action) {
            case "snippet":
              console.log("🚀 Dashboard: FAB - Creating new snippet");
              this.createNewSnippet();
              break;
            case "collection":
              console.log("🚀 Dashboard: FAB - Creating new collection");
              if (typeof CollectionModal !== "undefined") {
                CollectionModal.openForCreate({
                  onSuccess: (collection) => {
                    this.showToast(
                      `Collection "${collection.name}" created! 🎉`,
                      "success"
                    );
                    setTimeout(() => {
                      window.location.href = `/dashboard/collections/${collection.id}`;
                    }, 1500);
                  },
                });
              } else {
                this.createNewCollection();
              }
              break;
            case "import":
              console.log("🚀 Dashboard: FAB - Import action");
              this.showToast("Import functionality coming soon", "info");
              break;
            default:
              console.warn(
                `🚀 Dashboard: No handler for FAB action: ${action}`
              );
          }
        });
      });
    }
  }

  setupModalHandlers() {
    // Close modals on overlay click
    document.querySelectorAll(".modal-overlay").forEach((overlay) => {
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) {
          this.closeModal(overlay.closest(".modal"));
        }
      });
    });

    // Close modals on ESC key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const openModal = document.querySelector(".modal.show");
        if (openModal) {
          this.closeModal(openModal);
        }
      }
    });

    // Modal close buttons
    document.querySelectorAll(".modal-close").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        this.closeModal(e.target.closest(".modal"));
      });
    });
  }
  // Add this to the init() method in your DashboardManager class
  makeFabDraggable() {
    const fab = document.querySelector(".fab");
    if (!fab) return;

    let isDragging = false;
    let dragTimeout = null;
    let offsetX, offsetY;

    // Long press to activate dragging
    fab.addEventListener("mousedown", (e) => {
      // Clear any existing timeout
      if (dragTimeout) clearTimeout(dragTimeout);

      // Set a timeout to activate dragging after 500ms
      dragTimeout = setTimeout(() => {
        isDragging = true;
        fab.classList.add("dragging");

        // Calculate the offset from the pointer to the FAB center
        const rect = fab.getBoundingClientRect();
        offsetX = e.clientX - rect.left - rect.width / 2;
        offsetY = e.clientY - rect.top - rect.height / 2;

        // Store original position for transform
        fab.dataset.originalLeft = getComputedStyle(fab).left;
        fab.dataset.originalTop = getComputedStyle(fab).top || "32px";

        // Remove the transform that centers it
        fab.style.transform = "none";
        fab.style.left = rect.left + "px";
        fab.style.top = rect.top + "px";
      }, 500); // 500ms delay for long press
    });

    // Handle click events (prevent normal click during drag)
    fab.addEventListener("click", (e) => {
      if (isDragging) {
        e.preventDefault();
        e.stopPropagation();
      }
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;

      // Update position
      fab.style.left = e.clientX - offsetX + "px";
      fab.style.top = e.clientY - offsetY + "px";
    });

    document.addEventListener("mouseup", () => {
      // Clear the timeout to prevent drag activation
      if (dragTimeout) {
        clearTimeout(dragTimeout);
        dragTimeout = null;
      }

      if (!isDragging) return;

      isDragging = false;
      fab.classList.remove("dragging");

      // Save position to localStorage
      const rect = fab.getBoundingClientRect();
      localStorage.setItem(
        "fab-position",
        JSON.stringify({
          left: rect.left,
          top: rect.top,
        })
      );
    });

    // Load saved position
    const savedPosition = localStorage.getItem("fab-position");
    if (savedPosition) {
      const { left, top } = JSON.parse(savedPosition);
      fab.style.transform = "none"; // Remove the centering transform
      fab.style.left = left + "px";
      fab.style.top = top + "px";
    }
  }

  setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      // Ctrl/Cmd + K for search
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        const searchInput = document.getElementById("searchInput");
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }

      // Ctrl/Cmd + N for new snippet
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        this.createNewSnippet();
      }

      // Ctrl/Cmd + Shift + N for new collection
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "N") {
        e.preventDefault();
        this.createNewCollection();
      }

      // Toggle theme with Ctrl/Cmd + T
      if ((e.ctrlKey || e.metaKey) && e.key === "t") {
        e.preventDefault();
        this.toggleTheme();
      }

      // Delete selected items with Delete key
      if (e.key === "Delete" && this.getSelectedItems().length > 0) {
        e.preventDefault();
        this.bulkDelete();
      }
    });
  }

  setupDragAndDrop() {
    const snippetCards = document.querySelectorAll(".snippet-card");
    const collectionDropZones = document.querySelectorAll(
      ".collection-drop-zone"
    );

    snippetCards.forEach((card) => {
      card.draggable = true;
      card.addEventListener("dragstart", this.handleDragStart.bind(this));
      card.addEventListener("dragend", this.handleDragEnd.bind(this));
    });

    collectionDropZones.forEach((zone) => {
      zone.addEventListener("dragover", this.handleDragOver.bind(this));
      zone.addEventListener("drop", this.handleDrop.bind(this));
      zone.addEventListener("dragenter", this.handleDragEnter.bind(this));
      zone.addEventListener("dragleave", this.handleDragLeave.bind(this));
    });
  }

  setupInfiniteScroll() {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !this.isLoading) {
            this.loadMoreContent();
          }
        });
      },
      {
        rootMargin: "100px",
      }
    );

    const sentinel = document.getElementById("scrollSentinel");
    if (sentinel) {
      observer.observe(sentinel);
    }
  }

  setupWebSocket() {
    if (typeof io !== "undefined") {
      this.socket = io();

      this.socket.on("snippet_updated", (data) => {
        this.handleSnippetUpdate(data);
      });

      this.socket.on("snippet_deleted", (data) => {
        this.handleSnippetDelete(data);
      });

      this.socket.on("collection_updated", (data) => {
        this.handleCollectionUpdate(data);
      });

      this.socket.on("sync_status", (data) => {
        this.updateSyncStatus(data);
      });
    }
  }

  initializeAnimations() {
    // Animate cards on page load
    this.animateCardsIn();

    // Setup intersection observer for scroll animations
    const animateOnScroll = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("animate-in");
          }
        });
      },
      {
        threshold: 0.1,
      }
    );

    document.querySelectorAll(".animate-on-scroll").forEach((el) => {
      animateOnScroll.observe(el);
    });
  }

  animateCardsIn() {
    const cards = document.querySelectorAll(".snippet-card, .collection-card");
    cards.forEach((card, index) => {
      card.style.opacity = "0";
      card.style.transform = "translateY(20px)";

      setTimeout(() => {
        card.style.transition = "all 0.5s cubic-bezier(0.4, 0, 0.2, 1)";
        card.style.opacity = "1";
        card.style.transform = "translateY(0)";
      }, index * 100);
    });
  }

  // Theme Management
  toggleTheme() {
    this.theme = this.theme === "dark" ? "light" : "dark";
    this.applyTheme();
    this.storeTheme();
  }

  applyTheme() {
    document.documentElement.setAttribute("data-theme", this.theme);

    // Update theme toggle icon - Fix the selector
    const themeIcon = document.querySelector(".theme-toggle i");
    if (themeIcon) {
      themeIcon.className =
        this.theme === "dark" ? "fas fa-sun" : "fas fa-moon";
    }

    // Smooth theme transition
    document.body.style.transition =
      "background-color 0.3s ease, color 0.3s ease";
    setTimeout(() => {
      document.body.style.transition = "";
    }, 300);
  }

  initializeTheme() {
    this.applyTheme();
  }

  getStoredTheme() {
    return localStorage.getItem("dashboard-theme");
  }
  // Add these methods to your DashboardManager class

  // Handle creating a new snippet

  // Handle creating a new collection
  createNewCollection() {
    window.location.href = "/dashboard/collections?new=true";
  }

  // Handle sharing a snippet
  shareSnippet(snippetId) {
    // Show a sharing dialog
    this.showToast("Sharing functionality coming soon", "info");
  }

  // Handle clicking on a snippet
  viewSnippet(snippetId) {
    window.location.href = `/dashboard/snippets/${snippetId}`;
  }

  // Handle clicking on a collection
  viewCollection(collectionId) {
    window.location.href = `/dashboard/collections/${collectionId}`;
  }

  storeTheme() {
    localStorage.setItem("dashboard-theme", this.theme);
  }

  // View Management
  setView(view) {
    this.currentView = view;
    const container = document.getElementById("contentContainer");

    if (container) {
      container.className = `content-container view-${view}`;
    }

    // Update view buttons
    document.querySelectorAll(".view-btn").forEach((btn) => {
      btn.classList.remove("active");
    });
    document.getElementById(`${view}View`)?.classList.add("active");

    // Animate view change
    this.animateViewChange();
  }

  animateViewChange() {
    const cards = document.querySelectorAll(".snippet-card, .collection-card");
    cards.forEach((card, index) => {
      card.style.animation = `fadeInUp 0.4s ease ${index * 0.05}s both`;
    });
  }

  // Search and Filter
  filterContent() {
    this.showLoadingState();

    // Simulate API call delay
    setTimeout(() => {
      const items = document.querySelectorAll(
        ".snippet-card, .collection-card"
      );
      items.forEach((item) => {
        const title =
          item.querySelector(".title")?.textContent.toLowerCase() || "";
        const description =
          item.querySelector(".description")?.textContent.toLowerCase() || "";
        const tags = Array.from(item.querySelectorAll(".tag")).map((tag) =>
          tag.textContent.toLowerCase()
        );

        const matchesSearch =
          !this.searchQuery ||
          title.includes(this.searchQuery.toLowerCase()) ||
          description.includes(this.searchQuery.toLowerCase()) ||
          tags.some((tag) => tag.includes(this.searchQuery.toLowerCase()));

        const matchesTags =
          this.selectedTags.size === 0 ||
          tags.some((tag) => this.selectedTags.has(tag));

        if (matchesSearch && matchesTags) {
          item.style.display = "block";
          item.classList.add("filter-match");
        } else {
          item.style.display = "none";
          item.classList.remove("filter-match");
        }
      });

      this.hideLoadingState();
      this.updateResultsCount();
    }, 300);
  }

  // Add this new method to your DashboardManager class
  toggleSidebar() {
    const sidebar = document.querySelector(".sidebar");

    if (sidebar) {
      sidebar.classList.toggle("collapsed");

      // Save state to localStorage
      const isCollapsed = sidebar.classList.contains("collapsed");
      localStorage.setItem("sidebar-collapsed", isCollapsed);
    }
  }

  // Add this to your init() method to restore sidebar state
  initializeSidebar() {
    const sidebar = document.querySelector(".sidebar");
    if (sidebar) {
      const isCollapsed = localStorage.getItem("sidebar-collapsed") === "true";
      if (isCollapsed) {
        sidebar.classList.add("collapsed");
      }
    }
  }

  // Add this to your init() method
  setupActionButtons() {
    console.log("🚀 Dashboard: ===== SETUP ACTION BUTTONS START =====");

    const actionCards = document.querySelectorAll(".action-card");
    console.log(`🚀 Dashboard: Found ${actionCards.length} action cards`);

    actionCards.forEach((button, index) => {
      const action = button.dataset.action;
      const url = button.dataset.url;
      const id = button.id;

      console.log(`🚀 Dashboard: Action Card ${index + 1}:`, {
        action: action,
        url: url,
        id: id,
        element: button,
      });

      button.addEventListener("click", (e) => {
        e.preventDefault();
        console.log(`🚀 Dashboard: ===== ACTION BUTTON CLICKED =====`);
        console.log(`🚀 Dashboard: Action: ${action}`);
        console.log(`🚀 Dashboard: Button ID: ${id}`);
        console.log(`🚀 Dashboard: Event:`, e);

        // Handle specific actions
        switch (action) {
          case "new-snippet":
            console.log("🚀 Dashboard: Handling new-snippet action");
            try {
              this.createNewSnippet();
              console.log("✅ Dashboard: createNewSnippet called successfully");
            } catch (error) {
              console.error("❌ Dashboard: Error in createNewSnippet:", error);
              this.showToast(
                "Error opening snippet modal. Check console for details.",
                "error"
              );
            }
            break;
          case "new-collection":
            console.log("🚀 Dashboard: Handling new-collection action");
            if (typeof CollectionModal !== "undefined") {
              CollectionModal.openForCreate({
                onSuccess: (collection) => {
                  this.showToast(
                    `Collection "${collection.name}" created! 🎉`,
                    "success"
                  );
                  setTimeout(() => {
                    window.location.href = `/dashboard/collections/${collection.id}`;
                  }, 1500);
                },
              });
            } else {
              this.createNewCollection();
            }
            break;
          case "import":
            console.log("🚀 Dashboard: Handling import action");
            this.showToast("Import functionality coming soon", "info");
            break;
          case "extension":
            console.log("🚀 Dashboard: Handling extension action");
            this.showToast(
              "Browser extension functionality coming soon",
              "info"
            );
            break;
          default:
            // Fallback to URL navigation
            if (url) {
              console.log(`🚀 Dashboard: Navigating to URL: ${url}`);
              window.location.href = url;
            } else {
              console.warn(`🚀 Dashboard: No handler for action: ${action}`);
              this.showToast(`No handler for action: ${action}`, "error");
            }
        }
        console.log(`🚀 Dashboard: ===== ACTION BUTTON END =====`);
      });
    });

    console.log("✅ Dashboard: Action buttons setup complete");
    console.log("🚀 Dashboard: ===== SETUP ACTION BUTTONS END =====");
  }

  sortContent() {
    const container = document.getElementById("contentContainer");
    const items = Array.from(
      container.querySelectorAll(".snippet-card, .collection-card")
    );

    items.sort((a, b) => {
      let aValue, bValue;

      switch (this.sortBy) {
        case "name":
          aValue = a.querySelector(".title")?.textContent || "";
          bValue = b.querySelector(".title")?.textContent || "";
          break;
        case "updated":
          aValue = new Date(a.dataset.updated || 0);
          bValue = new Date(b.dataset.updated || 0);
          break;
        case "created":
          aValue = new Date(a.dataset.created || 0);
          bValue = new Date(b.dataset.created || 0);
          break;
        default:
          return 0;
      }

      if (this.sortOrder === "asc") {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    // Animate sort
    items.forEach((item, index) => {
      item.style.transform = "scale(0.8)";
      item.style.opacity = "0.5";

      setTimeout(() => {
        container.appendChild(item);
        item.style.transform = "scale(1)";
        item.style.opacity = "1";
      }, index * 50);
    });
  }

  // Bulk Operations
  toggleSelectAll() {
    const checkboxes = document.querySelectorAll(".item-checkbox");
    const selectAllBtn = document.getElementById("selectAll");
    const allChecked = Array.from(checkboxes).every((cb) => cb.checked);

    checkboxes.forEach((cb) => {
      cb.checked = !allChecked;
    });

    selectAllBtn.textContent = allChecked ? "Select All" : "Deselect All";
    this.updateBulkActions();
  }

  getSelectedItems() {
    return Array.from(document.querySelectorAll(".item-checkbox:checked")).map(
      (cb) => cb.closest(".snippet-card, .collection-card")
    );
  }

  updateBulkActions() {
    const selectedCount = this.getSelectedItems().length;
    const bulkActions = document.getElementById("bulkActions");

    if (bulkActions) {
      bulkActions.style.display = selectedCount > 0 ? "flex" : "none";

      const countElement = document.getElementById("selectedCount");
      if (countElement) {
        countElement.textContent = selectedCount;
      }
    }
  }

  async bulkDelete() {
    const selectedItems = this.getSelectedItems();
    if (selectedItems.length === 0) return;

    const confirmed = await this.showConfirmDialog(
      "Delete Selected Items",
      `Are you sure you want to delete ${selectedItems.length} item(s)? This action cannot be undone.`
    );

    if (confirmed) {
      this.showLoadingState();

      // Animate items out
      selectedItems.forEach((item, index) => {
        setTimeout(() => {
          item.style.animation = "fadeOutUp 0.4s ease both";
          setTimeout(() => {
            item.remove();
          }, 400);
        }, index * 100);
      });

      // API call would go here
      setTimeout(() => {
        this.hideLoadingState();
        this.showToast("Items deleted successfully", "success");
        this.updateBulkActions();
      }, 1000);
    }
  }

  async bulkExport() {
    const selectedItems = this.getSelectedItems();
    if (selectedItems.length === 0) return;

    this.showLoadingState();

    // Simulate export process
    setTimeout(() => {
      this.hideLoadingState();
      this.showToast(`Exported ${selectedItems.length} items`, "success");

      // Trigger download
      const blob = new Blob(
        [
          JSON.stringify(
            {
              exported_at: new Date().toISOString(),
              items: selectedItems.map((item) => ({
                title: item.querySelector(".title")?.textContent,
                type: item.classList.contains("snippet-card")
                  ? "snippet"
                  : "collection",
              })),
            },
            null,
            2
          ),
        ],
        { type: "application/json" }
      );

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `export-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }, 1500);
  }

  // Drag and Drop Handlers
  handleDragStart(e) {
    e.dataTransfer.setData("text/plain", e.target.dataset.id);
    e.target.classList.add("dragging");

    // Create drag ghost
    const ghost = e.target.cloneNode(true);
    ghost.style.opacity = "0.5";
    ghost.style.transform = "rotate(5deg)";
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 0, 0);

    setTimeout(() => document.body.removeChild(ghost), 0);
  }

  handleDragEnd(e) {
    e.target.classList.remove("dragging");
  }

  handleDragOver(e) {
    e.preventDefault();
  }

  handleDragEnter(e) {
    e.target.classList.add("drag-over");
  }

  handleDragLeave(e) {
    e.target.classList.remove("drag-over");
  }

  handleDrop(e) {
    e.preventDefault();
    const itemId = e.dataTransfer.getData("text/plain");
    const targetCollection = e.target.closest(".collection-card")?.dataset.id;

    e.target.classList.remove("drag-over");

    if (itemId && targetCollection) {
      this.moveItemToCollection(itemId, targetCollection);
    }
  }

  // WebSocket Handlers
  handleSnippetUpdate(data) {
    const card = document.querySelector(`[data-id="${data.id}"]`);
    if (card) {
      this.updateSnippetCard(card, data);
      this.showToast("Snippet updated", "info");
    }
  }

  setupCollectionLinks() {
    // Add click handlers for collection links
    document
      .querySelectorAll('.collection-link, [data-page="collections"]')
      .forEach((link) => {
        link.addEventListener("click", (e) => {
          e.preventDefault();
          window.location.href = "/dashboard/collections";
        });
      });
  }

  handleSnippetDelete(data) {
    const card = document.querySelector(`[data-id="${data.id}"]`);
    if (card) {
      card.style.animation = "fadeOutUp 0.4s ease both";
      setTimeout(() => card.remove(), 400);
      this.showToast("Snippet deleted", "info");
    }
  }

  handleCollectionUpdate(data) {
    const card = document.querySelector(`[data-id="${data.id}"]`);
    if (card) {
      this.updateCollectionCard(card, data);
      this.showToast("Collection updated", "info");
    }
  }

  updateSyncStatus(data) {
    const syncIndicator = document.getElementById("syncStatus");
    if (syncIndicator) {
      syncIndicator.className = `sync-status ${data.status}`;
      syncIndicator.title = data.message;
    }
  }

  // Modal Management
  openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.style.display = "flex";
      modal.classList.add("show");

      // Animate in
      setTimeout(() => {
        modal.querySelector(".modal-content").style.transform =
          "translate(-50%, -50%) scale(1)";
        modal.querySelector(".modal-content").style.opacity = "1";
      }, 10);
    }
  }

  closeModal(modal) {
    if (modal) {
      const content = modal.querySelector(".modal-content");
      content.style.transform = "translate(-50%, -50%) scale(0.9)";
      content.style.opacity = "0";

      setTimeout(() => {
        modal.style.display = "none";
        modal.classList.remove("show");
      }, 200);
    }
  }

  // API Calls
  async loadDashboardData() {
    this.showLoadingState();

    try {
      // Try to load data, but don't fail if one request fails
      const results = await Promise.allSettled([
        this.loadSnippets(),
        this.loadCollections(),
        this.loadStats(),
      ]);

      // Check for any rejected promises
      const errors = results.filter((r) => r.status === "rejected");
      if (errors.length > 0) {
        console.error("Some data failed to load:", errors);
        this.showToast("Some dashboard data could not be loaded", "warning");
      }

      this.hideLoadingState();
    } catch (error) {
      console.error("Error loading dashboard data:", error);
      this.hideLoadingState();
      this.showToast("Failed to load dashboard data", "error");
    }
  }

  async loadSnippets() {
    console.log("🔍 loadSnippets called");

    try {
      const response = await fetch("/dashboard/api/snippets");
      console.log("🔍 API response status:", response.status);

      if (!response.ok) throw new Error("Failed to load snippets");

      const data = await response.json();
      console.log("🔍 API response data:", data);

      // Update the snippets grid with real data
      this.updateSnippetsGrid(data.snippets);

      return data;
    } catch (error) {
      console.error("Error loading snippets:", error);

      // Show error message in the grid
      const snippetsGrid = document.getElementById("snippetsGrid");
      if (snippetsGrid) {
        snippetsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-secondary);">
          <i class="fas fa-exclamation-triangle" style="font-size: 3rem; margin-bottom: 1rem; color: #ff6b6b;"></i>
          <h3>Failed to load snippets</h3>
          <p>Please check your connection and try again.</p>
          <button class="btn-primary" onclick="dashboardManager.loadSnippets()" style="margin-top: 1rem;">Retry</button>
        </div>
      `;
      }

      throw error;
    }
  }

  // Load Collections Function
  async loadCollections() {
    console.log("🔍 Dashboard: ===== LOADING COLLECTIONS START =====");

    try {
      const response = await fetch("/api/collections");
      console.log(
        "🔍 Dashboard: Collections API response status:",
        response.status
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log("🔍 Dashboard: Collections API response data:", data);

      if (data.success && data.collections) {
        this.allCollections = data.collections;
        console.log(
          `✅ Dashboard: Loaded ${this.allCollections.length} collections`
        );

        // Update dropdown
        this.updateCollectionDropdown();

        return this.allCollections;
      } else {
        console.error(
          "❌ Dashboard: Collections API returned unsuccessful response:",
          data
        );
        this.allCollections = [];
        return [];
      }
    } catch (error) {
      console.error("❌ Dashboard: Error loading collections:", error);
      console.error("❌ Dashboard: Error stack:", error.stack);
      this.allCollections = [];
      return [];
    } finally {
      console.log("🔍 Dashboard: ===== LOADING COLLECTIONS END =====");
    }
  }

  // Update Collection Dropdown
  updateCollectionDropdown() {
    console.log("🔄 Dashboard: Updating collection dropdown...");

    const collectionSelect = document.getElementById("snippetCollection");

    if (collectionSelect) {
      collectionSelect.innerHTML =
        '<option value="" style="background: var(--bg-secondary); color: var(--text-primary);">-- No Collection --</option>';

      this.allCollections.forEach((collection) => {
        const option = document.createElement("option");
        option.value = collection.id;
        option.textContent = collection.name;
        option.style.cssText =
          "background: var(--bg-secondary); color: var(--text-primary);";
        collectionSelect.appendChild(option);
      });

      // Apply dark theme styling
      collectionSelect.style.cssText =
        "background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--glass-border);";
      console.log(
        `✅ Dashboard: Updated dropdown with ${this.allCollections.length} collections`
      );
    } else {
      console.warn("⚠️ Dashboard: Collection dropdown not found");
    }
  }

  // Enhanced snippet creation with collection support
  async createSnippetWithCollection(snippetData, collectionId = null) {
    console.log("🎯 Dashboard: ===== CREATE SNIPPET WITH COLLECTION =====");
    console.log("🎯 Dashboard: Snippet data:", snippetData);
    console.log("🎯 Dashboard: Collection ID:", collectionId);

    try {
      // Add collection_id to snippet data if provided
      if (collectionId) {
        snippetData.collection_id = collectionId;
        console.log("✅ Dashboard: Added collection_id to snippet data");
      }

      const response = await fetch("/api/snippets/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(snippetData),
      });

      console.log(
        "🎯 Dashboard: Create snippet response status:",
        response.status
      );
      const result = await response.json();
      console.log("🎯 Dashboard: Create snippet response:", result);

      if (result.success) {
        const collectionName = collectionId
          ? this.allCollections.find((c) => c.id === collectionId)?.name ||
            "Unknown"
          : null;

        const message = collectionName
          ? `Snippet created and added to "${collectionName}" ✅`
          : "Snippet created successfully ✅";

        this.showToast(message, "success");
        console.log("✅ Dashboard: Snippet created successfully");

        return result;
      } else {
        this.showToast(result.message || "Failed to create snippet", "error");
        console.error("❌ Dashboard: Failed to create snippet:", result);
        return null;
      }
    } catch (error) {
      console.error("❌ Dashboard: Error creating snippet:", error);
      this.showToast("Failed to create snippet", "error");
      return null;
    }
  }

  async loadStats() {
    try {
      const response = await fetch("/dashboard/api/stats");
      if (!response.ok) throw new Error("Failed to load stats");

      const data = await response.json();
      // Update UI with the stats data
      this.updateStatsUI(data);
      return data;
    } catch (error) {
      console.error("Error loading stats:", error);
      throw error;
    }
  }

  async loadMoreContent() {
    if (this.isLoading) return;

    this.isLoading = true;
    const loadingIndicator = document.getElementById("loadingMore");
    if (loadingIndicator) {
      loadingIndicator.style.display = "block";
    }

    try {
      // Simulate loading more content
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Add new content here
    } catch (error) {
      this.showToast("Failed to load more content", "error");
    } finally {
      this.isLoading = false;
      if (loadingIndicator) {
        loadingIndicator.style.display = "none";
      }
    }
  }

  // Add these methods to update the UI with the data from the backend
  updateSnippetsUI(snippets) {
    // Update the recent activity section with snippet data
    const activityGrid = document.querySelector(".activity-grid");
    if (!activityGrid || !snippets || snippets.length === 0) return;

    // Clear existing content
    activityGrid.innerHTML = "";

    // Add snippets to the activity grid
    snippets.slice(0, 3).forEach((snippet) => {
      const timeAgo = this.getTimeAgo(new Date(snippet.updated_at));

      const card = document.createElement("div");
      card.className = "activity-card";
      card.dataset.id = snippet.id;

      card.innerHTML = `
            <div class="activity-icon ${snippet.language.toLowerCase()}">
                <i class="fab fa-${this.getLanguageIcon(snippet.language)}"></i>
            </div>
            <div class="activity-content">
                <h3>${snippet.title}</h3>
                <p>Updated ${timeAgo}</p>
                <div class="activity-tags">
                    ${this.renderTags(snippet.tags)}
                </div>
            </div>
            <div class="activity-actions">
                <button class="btn-icon" data-tooltip="View" onclick="window.location.href='/dashboard/snippets/${
                  snippet.id
                }'">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="btn-icon" data-tooltip="Edit" onclick="window.location.href='/dashboard/snippets/${
                  snippet.id
                }/edit'">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn-icon" data-tooltip="Share" onclick="dashboardManager.shareSnippet('${
                  snippet.id
                }')">
                    <i class="fas fa-share"></i>
                </button>
            </div>
        `;

      activityGrid.appendChild(card);
    });
  }
  updateSnippetsGrid(snippets) {
    console.log("🔍 updateSnippetsGrid called with:", snippets);
    console.log(
      "🔍 Number of snippets:",
      snippets ? snippets.length : "snippets is null/undefined"
    );
    const snippetsGrid = document.getElementById("snippetsGrid");
    console.log("🔍 snippetsGrid element:", snippetsGrid);

    if (!snippetsGrid) {
      console.log(
        "ℹ️ Dashboard: snippetsGrid not found on this page, skipping update"
      );
      return;
    }

    // Clear existing content
    snippetsGrid.innerHTML = "";

    if (!snippets || snippets.length === 0) {
      snippetsGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-secondary);">
        <i class="fas fa-code" style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.5;"></i>
        <h3>No snippets found</h3>
        <p>Create your first snippet to get started!</p>
      </div>
    `;
      return;
    }

    // Create snippet cards from real data
    snippets.forEach((snippet) => {
      const card = document.createElement("div");
      card.className = "snippet-card";
      card.dataset.language = snippet.language || "text";
      card.dataset.created = snippet.created_at;
      card.dataset.id = snippet.id;

      // Process tags
      const tags = snippet.tags
        ? typeof snippet.tags === "string"
          ? snippet.tags.split(",")
          : snippet.tags
        : [];

      card.innerHTML = `
      <div class="snippet-header">
        <div>
          <h3 class="snippet-title">${snippet.title || "Untitled"}</h3>
          <div class="snippet-meta">
            <span class="meta-chip">${snippet.language || "Text"}</span>
            ${tags
              .map((tag) => `<span class="meta-chip">${tag.trim()}</span>`)
              .join("")}
          </div>
        </div>
      </div>
      <div class="snippet-code">
        <pre><code class="language-${
          snippet.language || "text"
        }">${this.escapeHtml(snippet.code || "")}</code></pre>
      </div>
      <div class="snippet-actions">
        <button class="action-btn" title="Copy" onclick="dashboardManager.copySnippet('${
          snippet.id
        }')">📋</button>
        <button class="action-btn" title="Edit" onclick="dashboardManager.editSnippet('${
          snippet.id
        }')">✏️</button>
        <button class="action-btn" title="Share" onclick="dashboardManager.shareSnippet('${
          snippet.id
        }')">🔗</button>
        <button class="action-btn" title="Favorite" onclick="dashboardManager.toggleFavorite('${
          snippet.id
        }')">⭐</button>
        <button class="action-btn" title="Delete" onclick="dashboardManager.deleteSnippet('${
          snippet.id
        }')">🗑️</button>
      </div>
    `;

      snippetsGrid.appendChild(card);
    });

    // Re-initialize syntax highlighting
    if (typeof hljs !== "undefined") {
      hljs.highlightAll();
    }

    // Update snippet count
    const snippetCount = document.getElementById("snippetCount");
    if (snippetCount) {
      snippetCount.textContent = `${snippets.length} snippet${
        snippets.length !== 1 ? "s" : ""
      }`;
    }
  }

  // Helper function to escape HTML
  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Add these action methods
  copySnippet(snippetId) {
    const card = document.querySelector(`[data-id="${snippetId}"]`);
    if (card) {
      const code = card.querySelector("code").textContent;
      navigator.clipboard.writeText(code).then(() => {
        this.showToast("Code copied to clipboard! 📋", "success");
      });
    }
  }

  editSnippet(snippetId) {
    window.location.href = `/dashboard/snippets/${snippetId}/edit`;
  }

  deleteSnippet(snippetId) {
    if (confirm("Are you sure you want to delete this snippet?")) {
      // API call to delete snippet
      this.showToast("Snippet deleted 🗑️", "success");
      // Remove from UI
      const card = document.querySelector(`[data-id="${snippetId}"]`);
      if (card) {
        card.style.animation = "fadeOut 0.3s ease";
        setTimeout(() => card.remove(), 300);
      }
    }
  }

  toggleFavorite(snippetId) {
    const card = document.querySelector(`[data-id="${snippetId}"]`);
    if (card) {
      card.classList.toggle("favorite");
      const btn = card.querySelector('[title="Favorite"]');
      btn.style.color = card.classList.contains("favorite") ? "#fbbf24" : "";
      this.showToast("Favorite toggled", "info");
    }
  }

  updateCollectionsUI(collections) {
    // Update collections in the sidebar
    const collectionCount = document.querySelector(
      '.sidebar-link[data-page="collections"] .count'
    );
    if (collectionCount) {
      collectionCount.textContent = collections.length;
    }

    // If we're on the collections page, update the grid
    const collectionsGrid = document.querySelector(".collections-grid");
    if (collectionsGrid && collections.length > 0) {
      // Update existing collections or add new ones
      collections.forEach((collection) => {
        const existingCard = document.querySelector(
          `[data-id="${collection.id}"]`
        );
        if (existingCard) {
          // Update existing card
          const title = existingCard.querySelector(".collection-title");
          const description = existingCard.querySelector(
            ".collection-description"
          );
          const snippetCount = existingCard.querySelector(".stat span");

          if (title) title.textContent = collection.name;
          if (description)
            description.textContent =
              collection.description || "No description";
          if (snippetCount)
            snippetCount.textContent = `${collection.snippet_count} snippets`;
        }
      });
    }
  }

  //team functions

  // ADD THIS FUNCTION TO HANDLE TEAM NAVIGATION:
  navigateToTeams() {
    console.log("🏢 DASHBOARD: Navigating to teams page...");
    window.location.href = "/dashboard/teams";
  }

  // ADD TEAM-RELATED ACTION HANDLERS:
  joinTeamRoom(teamId) {
    console.log(`🏢 DASHBOARD: Joining team room: ${teamId}`);

    if (this.socket) {
      this.socket.emit("join_team_room", {
        team_id: teamId,
        user_id: this.getCurrentUserId(),
      });
    }
  }

  getCurrentUserId() {
    // Get current user ID from page data or localStorage
    const userElement = document.querySelector("[data-user-id]");
    return userElement ? userElement.dataset.userId : null;
  }

  setupWebSocket() {
    console.log("🚀 Dashboard: Setting up WebSocket...");

    // Check if Socket.IO is available
    if (typeof io !== "undefined") {
      console.log("✅ Dashboard: Socket.IO found, initializing...");
      try {
        this.socket = io();

        this.socket.on("snippet_updated", (data) => {
          this.handleSnippetUpdate(data);
        });

        this.socket.on("snippet_deleted", (data) => {
          this.handleSnippetDelete(data);
        });

        this.socket.on("collection_updated", (data) => {
          this.handleCollectionUpdate(data);
        });

        this.socket.on("sync_status", (data) => {
          this.updateSyncStatus(data);
        });

        console.log("✅ Dashboard: WebSocket setup complete");
      } catch (error) {
        console.warn("⚠️ Dashboard: WebSocket setup failed:", error);
      }
    } else {
      console.warn(
        "⚠️ Dashboard: Socket.IO not available, skipping WebSocket setup"
      );
    }
  }

  updateStatsUI(stats) {
    console.log("🔍 updateStatsUI called with:", stats);

    // Update the stats cards with REAL data from API
    const totalSnippetsElement = document.querySelector(
      ".stat-card:nth-child(1) .stat-number"
    );
    const totalCollectionsElement = document.querySelector(
      ".stat-card:nth-child(2) .stat-number"
    );
    const viewsTodayElement = document.querySelector(
      ".stat-card:nth-child(3) .stat-number"
    );
    const sharedElement = document.querySelector(
      ".stat-card:nth-child(4) .stat-number"
    );

    // FIXED: Use the correct stats from API (which now excludes deleted snippets)
    if (totalSnippetsElement)
      totalSnippetsElement.textContent = stats.total_snippets;
    if (totalCollectionsElement)
      totalCollectionsElement.textContent = stats.total_collections;
    if (viewsTodayElement)
      viewsTodayElement.textContent = stats.views_today || "0";
    if (sharedElement) sharedElement.textContent = stats.shared_count || "0";

    // Update the sidebar counts
    const snippetsCount = document.querySelector(
      '.sidebar-link[data-page="snippets"] .count'
    );
    if (snippetsCount) {
      snippetsCount.textContent = stats.total_snippets;
    }

    // FIXED: Update weekly snippets change
    const weeklyChangeElement = document.querySelector(
      ".stat-card:nth-child(1) .stat-change"
    );
    if (weeklyChangeElement) {
      weeklyChangeElement.textContent = `+${
        stats.snippets_this_week || 0
      } this week`;
    }

    console.log("✅ Stats UI updated with real data:", {
      total_snippets: stats.total_snippets,
      total_collections: stats.total_collections,
      snippets_this_week: stats.snippets_this_week,
    });
  }

  initializeSnippetModal() {
    console.log("🚀 Dashboard: Initializing snippet modal functionality...");

    // Check if we're on a page that has the snippet modal
    if (!document.getElementById("snippetModal")) {
      console.log(
        "ℹ️ Dashboard: Snippet modal not found on this page, skipping initialization"
      );
      return;
    }

    console.log("🚀 Dashboard: Getting modal elements...");

    // Get modal elements
    this.snippetModal = document.getElementById("snippetModal");
    this.snippetForm = document.getElementById("snippetForm");
    this.newSnippetBtn = document.getElementById("newSnippetBtn");
    this.closeModalBtn = document.getElementById("closeModal");

    // Check if elements exist
    if (
      !this.snippetModal ||
      !this.snippetForm ||
      !this.newSnippetBtn ||
      !this.closeModalBtn
    ) {
      console.error("❌ Dashboard: Some modal elements not found!");
      return;
    }

    console.log("✅ Dashboard: All modal elements found successfully");

    // Load collections when modal is initialized
    this.loadCollections();

    // Setup event listeners
    this.setupSnippetModalEvents();
  }

  setupSnippetModalEvents() {
    console.log("🚀 Dashboard: Setting up modal event listeners...");

    // New snippet button click
    this.newSnippetBtn.addEventListener("click", (e) => {
      e.preventDefault();
      console.log("🚀 Dashboard: New snippet button clicked");
      this.openSnippetModal();
    });

    // Close modal button click
    this.closeModalBtn.addEventListener("click", (e) => {
      e.preventDefault();
      console.log("🚀 Dashboard: Close modal button clicked");
      this.closeSnippetModal();
    });

    // Click outside modal to close
    this.snippetModal.addEventListener("click", (e) => {
      if (e.target === this.snippetModal) {
        console.log("🚀 Dashboard: Clicked outside modal, closing...");
        this.closeSnippetModal();
      }
    });

    // Form submission
    this.snippetForm.addEventListener("submit", (e) => {
      e.preventDefault();
      console.log("🚀 Dashboard: Snippet form submitted");
      this.handleSnippetSubmit();
    });

    // ESC key to close modal (add to existing keydown handler)
    document.addEventListener("keydown", (e) => {
      if (
        e.key === "Escape" &&
        this.snippetModal &&
        this.snippetModal.classList.contains("active")
      ) {
        console.log("🚀 Dashboard: ESC key pressed, closing modal...");
        this.closeSnippetModal();
      }
    });

    console.log("✅ Dashboard: Modal event listeners setup complete");
  }
  checkCollectionModalService() {
    // Skip collection modal check on profile page and other non-dashboard pages
    const currentPath = window.location.pathname;
    const skipPages = ["/profile", "/settings", "/integrations", "/teams"];

    console.log(`🔍 Dashboard: Current path: ${currentPath}`);

    if (skipPages.some((page) => currentPath.includes(page))) {
      console.log(
        `ℹ️ Dashboard: On ${currentPath} page, skipping CollectionModal check`
      );
      return;
    }

    setTimeout(() => {
      if (typeof CollectionModal !== "undefined") {
        console.log("✅ Dashboard: CollectionModal service is available");
      } else {
        console.warn(
          "⚠️ Dashboard: CollectionModal service not found on this page"
        );
        console.log(
          "ℹ️ Dashboard: This is normal for pages that don't need collection functionality"
        );
      }
    }, 100);
  }
  openSnippetModal(snippet = null) {
    console.log(
      "🚀 Dashboard: Opening snippet modal...",
      snippet ? `Editing snippet ID: ${snippet.id}` : "Creating new snippet"
    );

    this.editingSnippetId = snippet ? snippet.id : null;

    if (snippet) {
      // Edit mode
      console.log("🚀 Dashboard: Setting up modal for editing");
      document.getElementById("modalTitle").textContent = "Edit Snippet";
      document.getElementById("snippetTitle").value = snippet.title || "";
      document.getElementById("snippetLanguage").value = snippet.language || "";
      document.getElementById("snippetTags").value = Array.isArray(snippet.tags)
        ? snippet.tags.join(", ")
        : snippet.tags || "";
      document.getElementById("snippetCode").value = snippet.code || "";
      document.getElementById("snippetDescription").value =
        snippet.description || "";
    } else {
      // Create mode
      console.log("🚀 Dashboard: Setting up modal for new snippet");
      document.getElementById("modalTitle").textContent = "Add New Snippet";
      this.snippetForm.reset();
    }

    this.snippetModal.classList.add("active");
    console.log("✅ Dashboard: Modal opened successfully");

    // Focus on title input
    setTimeout(() => {
      document.getElementById("snippetTitle").focus();
    }, 100);
  }

  closeSnippetModal() {
    console.log("🚀 Dashboard: Closing snippet modal...");

    this.snippetModal.classList.remove("active");
    this.editingSnippetId = null;
    this.snippetForm.reset();

    console.log("✅ Dashboard: Modal closed successfully");
  }

  async handleSnippetSubmit() {
    console.log("🚀 Dashboard: ===== ENHANCED SNIPPET SUBMIT START =====");

    // Get form data
    const formData = {
      title: document.getElementById("snippetTitle").value.trim(),
      language: document.getElementById("snippetLanguage").value.trim(),
      tags: document.getElementById("snippetTags").value.trim(),
      code: document.getElementById("snippetCode").value.trim(),
      description: document.getElementById("snippetDescription").value.trim(),
    };

    // Get selected collection
    const collectionSelect = document.getElementById("snippetCollection");
    const selectedCollectionId = collectionSelect
      ? collectionSelect.value
      : null;

    console.log("🚀 Dashboard: Form data:", formData);
    console.log("🚀 Dashboard: Selected collection ID:", selectedCollectionId);

    // Validation
    if (!formData.title || !formData.code || !formData.language) {
      console.error(
        "❌ Dashboard: Validation failed - missing required fields"
      );
      this.showToast(
        "Please fill in all required fields (Title, Language, Code)",
        "error"
      );
      return;
    }

    console.log("✅ Dashboard: Form validation passed");

    try {
      const result = await this.createSnippetWithCollection(
        formData,
        selectedCollectionId
      );

      if (result) {
        this.closeSnippetModal();
        this.loadSnippets(); // Reload snippets to show the new one
      }
    } catch (error) {
      console.error("❌ Dashboard: Error in enhanced snippet submit:", error);
      this.showToast("Failed to save snippet. Please try again.", "error");
    }

    console.log("🚀 Dashboard: ===== ENHANCED SNIPPET SUBMIT END =====");
  }

  // Helper methods
  getLanguageIcon(language) {
    const iconMap = {
      javascript: "js-square",
      python: "python",
      css: "css3-alt",
      html: "html5",
      java: "java",
      php: "php",
      ruby: "gem",
      sql: "database",
      c: "code",
      cpp: "code",
      csharp: "microsoft",
    };

    return iconMap[language.toLowerCase()] || "code";
  }

  renderTags(tags) {
    if (!tags) return "";

    const tagArray = typeof tags === "string" ? tags.split(",") : tags;
    return tagArray
      .map((tag) => `<span class="tag">${tag.trim()}</span>`)
      .join("");
  }

  getTimeAgo(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffDay > 0) {
      return diffDay === 1 ? "yesterday" : `${diffDay} days ago`;
    } else if (diffHour > 0) {
      return `${diffHour} ${diffHour === 1 ? "hour" : "hours"} ago`;
    } else if (diffMin > 0) {
      return `${diffMin} ${diffMin === 1 ? "minute" : "minutes"} ago`;
    } else {
      return "just now";
    }
  }

  // Utility Functions
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

  showLoadingState() {
    const loader = document.getElementById("globalLoader");
    if (loader) {
      loader.style.display = "flex";
    }
  }

  hideLoadingState() {
    const loader = document.getElementById("globalLoader");
    if (loader) {
      loader.style.display = "none";
    }
  }

  showToast(message, type = "info") {
    console.log(
      `🚀 Dashboard: Showing toast - Type: ${type}, Message: ${message}`
    );

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    // Enhanced styling for better visibility
    const colors = {
      success: "linear-gradient(135deg, #00d4ff 0%, #7c3aed 100%)",
      error: "linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%)",
      info: "linear-gradient(135deg, #74b9ff 0%, #0984e3 100%)",
    };

    toast.style.cssText = `
        position: fixed;
        top: 2rem;
        right: 2rem;
        background: ${colors[type] || colors.info};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        z-index: 3000;
        animation: slideIn 0.3s ease;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        font-weight: 500;
        max-width: 400px;
        word-wrap: break-word;
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
      toast.classList.add("show");
    }, 100);

    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
          console.log(`✅ Dashboard: Toast removed - ${message}`);
        }
      }, 300);
    }, 3000);

    console.log(`✅ Dashboard: Toast displayed successfully - ${message}`);
  }

  async showConfirmDialog(title, message) {
    return new Promise((resolve) => {
      const dialog = document.createElement("div");
      dialog.className = "modal confirm-dialog";
      dialog.innerHTML = `
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>${title}</h3>
                    </div>
                    <div class="modal-body">
                        <p>${message}</p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary cancel-btn">Cancel</button>
                        <button class="btn btn-danger confirm-btn">Confirm</button>
                    </div>
                </div>
            `;

      document.body.appendChild(dialog);
      dialog.style.display = "flex";

      dialog.querySelector(".cancel-btn").onclick = () => {
        document.body.removeChild(dialog);
        resolve(false);
      };

      dialog.querySelector(".confirm-btn").onclick = () => {
        document.body.removeChild(dialog);
        resolve(true);
      };

      dialog.querySelector(".modal-overlay").onclick = () => {
        document.body.removeChild(dialog);
        resolve(false);
      };
    });
  }

  updateResultsCount() {
    const visibleItems = document.querySelectorAll(
      '.snippet-card:not([style*="display: none"]), .collection-card:not([style*="display: none"])'
    ).length;
    const counter = document.getElementById("resultsCount");
    if (counter) {
      counter.textContent = `${visibleItems} items found`;
    }
  }

  // New item creation
  // Handle creating a new snippet
  // Handle creating a new snippet
  createNewSnippet() {
    console.log("🚀 Dashboard: ===== CREATE NEW SNIPPET START =====");
    console.log("🚀 Dashboard: Modal elements check:", {
      snippetModal: !!this.snippetModal,
      snippetForm: !!this.snippetForm,
      newSnippetBtn: !!this.newSnippetBtn,
      closeModalBtn: !!this.closeModalBtn,
    });

    if (!this.snippetModal) {
      console.error(
        "❌ Dashboard: snippetModal not initialized, trying to reinitialize..."
      );
      this.initializeSnippetModal();

      // Try again after initialization
      if (!this.snippetModal) {
        console.error(
          "❌ Dashboard: Failed to initialize modal, showing error toast"
        );
        this.showToast(
          "Modal initialization failed. Please refresh the page.",
          "error"
        );
        return;
      }
    }

    console.log("✅ Dashboard: Opening snippet modal...");
    this.openSnippetModal();
    console.log("🚀 Dashboard: ===== CREATE NEW SNIPPET END =====");
  }

  createNewCollection() {
    console.log("🚀 Dashboard: Creating new collection using universal modal");

    // Check if CollectionModal is available
    if (typeof CollectionModal === "undefined") {
      console.error("❌ Dashboard: CollectionModal service not available");
      this.showToast(
        "Collection modal service not loaded. Please refresh the page.",
        "error"
      );
      return;
    }

    CollectionModal.openForCreate({
      onSuccess: (collection) => {
        console.log(
          "✅ Dashboard: Collection created successfully:",
          collection
        );

        this.showToast(
          `Collection "${collection.name}" created successfully! 🎉`,
          "success"
        );

        // Refresh collections data
        if (typeof this.loadCollections === "function") {
          this.loadCollections();
        }

        // Optional: Redirect to new collection
        setTimeout(() => {
          window.location.href = `/dashboard/collections/${collection.id}`;
        }, 1500);
      },
      onClose: () => {
        console.log("🚀 Dashboard: Collection modal closed");
      },
    });
  }

  // ADD THIS METHOD TO DashboardManager CLASS:
  initTeamCollaboration() {
    console.log("🏢 DASHBOARD: Initializing team collaboration...");

    // Only initialize if we're on a team-related page or dashboard
    const currentPath = window.location.pathname;
    if (currentPath.includes("/teams") || currentPath.includes("/dashboard")) {
      // Initialize team WebSocket connection
      if (this.socket) {
        console.log("🏢 DASHBOARD: Setting up team WebSocket events...");

        // Listen for team events
        this.socket.on("team_joined", (data) => {
          console.log("🏢 DASHBOARD: Team joined:", data);
          this.showToast(`Joined team: ${data.team_name}`, "success");
        });

        this.socket.on("team_activity_update", (data) => {
          console.log("🏢 DASHBOARD: Team activity:", data);
          this.updateTeamActivity(data);
        });

        this.socket.on("team_member_online", (data) => {
          console.log("🏢 DASHBOARD: Team member online:", data);
          this.updateMemberStatus(data.user_id, "online");
        });

        this.socket.on("team_member_offline", (data) => {
          console.log("🏢 DASHBOARD: Team member offline:", data);
          this.updateMemberStatus(data.user_id, "offline");
        });

        // ADD THESE NEW TEAM COLLABORATION EVENTS
        this.socket.on("collaboration_started", (data) => {
          console.log("🤝 COLLABORATION: Session started:", data);
          this.showToast(`Collaboration started on ${data.snippet_id}`, "info");
        });

        this.socket.on("collaboration_joined", (data) => {
          console.log("🤝 COLLABORATION: User joined session:", data);
          this.showToast("Joined collaboration session", "success");
        });

        this.socket.on("operation_applied", (data) => {
          console.log("✏️ COLLABORATION: Operation applied:", data);
          // Handle real-time collaborative edits
          this.handleCollaborativeEdit(data);
        });
      }

      // Load team collaboration UI if on teams page
      if (currentPath.includes("/teams")) {
        this.loadTeamCollaborationUI();
      }
    }

    console.log("✅ DASHBOARD: Team collaboration initialized");
  }

  // ADD THESE NEW METHODS TO HANDLE COLLABORATIVE EDITING
  handleCollaborativeEdit(data) {
    console.log("✏️ COLLABORATION: Handling collaborative edit:", data);

    // Find the editor element if it exists
    const editor = document.getElementById("collaborative-editor");
    if (editor && data.operation) {
      // Apply the operation to the editor
      this.applyCollaborativeOperation(editor, data.operation);
    }
  }

  applyCollaborativeOperation(editor, operation) {
    console.log("✏️ COLLABORATION: Applying operation:", operation);

    try {
      const currentContent = editor.value;
      let newContent = currentContent;

      switch (operation.type) {
        case "insert":
          newContent =
            currentContent.slice(0, operation.position) +
            operation.content +
            currentContent.slice(operation.position);
          break;
        case "delete":
          const endPos = operation.position + operation.content.length;
          newContent =
            currentContent.slice(0, operation.position) +
            currentContent.slice(endPos);
          break;
        case "replace":
          const replaceEndPos = operation.position + operation.content.length;
          newContent =
            currentContent.slice(0, operation.position) +
            operation.content +
            currentContent.slice(replaceEndPos);
          break;
      }

      editor.value = newContent;
      console.log("✅ COLLABORATION: Operation applied successfully");
    } catch (error) {
      console.error("❌ COLLABORATION: Error applying operation:", error);
    }
  }

  // ADD THESE HELPER METHODS:
  loadTeamCollaborationUI() {
    console.log("🏢 DASHBOARD: Loading team collaboration UI...");

    // Initialize team collaboration class if available
    if (typeof TeamCollaboration !== "undefined") {
      this.teamCollaboration = new TeamCollaboration();
      console.log("✅ DASHBOARD: TeamCollaboration class initialized");
    } else {
      console.warn("⚠️ DASHBOARD: TeamCollaboration class not found");
    }
  }

  updateTeamActivity(data) {
    // Update team activity in UI
    const activityFeed = document.querySelector(".team-activity-feed");
    if (activityFeed) {
      const activityItem = document.createElement("div");
      activityItem.className = "activity-item";
      activityItem.innerHTML = `
      <div class="activity-icon">
        <i class="fas fa-${this.getActivityIcon(data.type)}"></i>
      </div>
      <div class="activity-content">
        <span>${data.message || "Team activity update"}</span>
        <small>${new Date().toLocaleTimeString()}</small>
      </div>
    `;
      activityFeed.insertBefore(activityItem, activityFeed.firstChild);
    }
  }

  updateMemberStatus(userId, status) {
    // Update member online/offline status
    const memberElement = document.querySelector(`[data-user-id="${userId}"]`);
    if (memberElement) {
      const statusIndicator = memberElement.querySelector(".status-indicator");
      if (statusIndicator) {
        statusIndicator.className = `status-indicator ${status}`;
      }
    }
  }

  getActivityIcon(type) {
    const icons = {
      snippet_created: "code",
      collection_created: "folder",
      member_joined: "user-plus",
      member_left: "user-minus",
    };
    return icons[type] || "activity";
  }

  moveItemToCollection(itemId, collectionId) {
    // API call to move item
    this.showToast("Item moved to collection", "success");
  }

  updateSnippetCard(card, data) {
    // Update card with new data
    const title = card.querySelector(".title");
    const description = card.querySelector(".description");

    if (title) title.textContent = data.title;
    if (description) description.textContent = data.description;

    card.classList.add("updated");
    setTimeout(() => card.classList.remove("updated"), 2000);
  }

  updateCollectionCard(card, data) {
    // Update collection card with new data
    const title = card.querySelector(".title");
    const description = card.querySelector(".description");

    if (title) title.textContent = data.title;
    if (description) description.textContent = data.description;

    card.classList.add("updated");
    setTimeout(() => card.classList.remove("updated"), 2000);
  }
}

// Initialize dashboard when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  window.dashboardManager = new DashboardManager();
});

// Export for use in other modules
if (typeof module !== "undefined" && module.exports) {
  module.exports = DashboardManager;
}

// ===== FIXED LOGOUT FUNCTIONALITY =====
document.addEventListener("DOMContentLoaded", function () {
  console.log("🔍 Setting up logout functionality...");

  // Prevent console from clearing by adding persistent logging
  const originalLog = console.log;
  const logHistory = [];
  console.log = function (...args) {
    logHistory.push(args.join(" "));
    originalLog.apply(console, args);
  };

  setTimeout(() => {
    setupLogoutFunctionality();
  }, 500);
});

function setupLogoutFunctionality() {
  console.log("🔍 Looking for logout button...");

  const logoutBtn = document.querySelector(".dropdown-item.logout");
  console.log("🔍 Logout button found:", !!logoutBtn);

  if (logoutBtn) {
    console.log("✅ Setting up logout click handler...");

    logoutBtn.addEventListener("click", function (e) {
      console.log("🚀 LOGOUT CLICKED - Starting process...");
      e.preventDefault();
      e.stopPropagation();

      // Show loading state
      const originalHTML = this.innerHTML;
      this.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i><span>Signing out...</span>';
      this.style.pointerEvents = "none";

      console.log("🚀 Making logout request...");

      fetch("/auth/logout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
        body: JSON.stringify({
          action: "logout",
          timestamp: new Date().toISOString(),
        }),
      })
        .then((response) => {
          console.log(
            "🚀 Response received:",
            response.status,
            response.statusText
          );
          return response.json();
        })
        .then((data) => {
          console.log("🚀 Response data:", data);

          if (data.success) {
            console.log("✅ Logout successful!");
            this.innerHTML =
              '<i class="fas fa-check"></i><span>Signed out!</span>';

            // FORCE page reload to clear all client-side state
            console.log("🚀 Force reloading page...");
            setTimeout(() => {
              // Clear all local storage and session storage
              localStorage.clear();
              sessionStorage.clear();

              // Force reload the page completely
              window.location.replace("/");
            }, 1000);
          } else {
            throw new Error(data.error || "Logout failed");
          }
        })
        .catch((error) => {
          console.error("❌ Logout error:", error);

          // Show error but still try to redirect
          this.innerHTML =
            '<i class="fas fa-exclamation-triangle"></i><span>Error - Redirecting...</span>';

          setTimeout(() => {
            // Force redirect even on error
            window.location.replace("/auth/logout");
          }, 2000);
        });
    });

    console.log("✅ Logout functionality setup complete");
  } else {
    console.error("❌ Logout button not found!");

    // Debug: show all dropdown items
    const dropdownItems = document.querySelectorAll(".dropdown-item");
    console.log("🔍 All dropdown items:", dropdownItems);
    dropdownItems.forEach((item, i) => {
      console.log(
        `  ${i}: "${item.textContent.trim()}" - classes: ${item.className}`
      );
    });
  }
}

// ===== PROFILE AND SETTINGS FUNCTIONALITY =====
document.addEventListener("DOMContentLoaded", function () {
  console.log("🔍 Setting up Profile and Settings functionality...");
  setupProfileAndSettings();
});

function setupProfileAndSettings() {
  console.log("🔍 PROFILE & SETTINGS - Starting setup...");

  // Get dropdown items with better selectors
  const dropdownItems = document.querySelectorAll(".dropdown-item");
  console.log(`🔍 Found ${dropdownItems.length} dropdown items`);

  dropdownItems.forEach((item, index) => {
    const icon = item.querySelector("i");
    const text = item.querySelector("span");
    const iconClass = icon ? icon.className : "";
    const textContent = text ? text.textContent.trim() : "";

    console.log(
      `🔍 Dropdown item ${index}: "${textContent}" - Icon: ${iconClass}`
    );

    // Profile button (has fa-user icon)
    if (iconClass.includes("fa-user")) {
      console.log("✅ Setting up Profile button click handler");
      item.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        console.log("🚀 PROFILE CLICKED - Navigating to profile page");

        // Log the action
        logUserAction("profile_accessed", {
          source: "dropdown_menu",
          timestamp: new Date().toISOString(),
        });

        // Show loading state
        const originalHTML = this.innerHTML;
        this.innerHTML =
          '<i class="fas fa-spinner fa-spin"></i><span>Loading...</span>';

        // Navigate to profile
        setTimeout(() => {
          window.location.href = "/dashboard/profile";
        }, 300);
      });
    }

    // Settings button (has fa-cog icon)
    if (iconClass.includes("fa-cog")) {
      console.log("✅ Setting up Settings button click handler");
      item.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        console.log("🚀 SETTINGS CLICKED - Navigating to settings page");

        // Log the action
        logUserAction("settings_accessed", {
          source: "dropdown_menu",
          timestamp: new Date().toISOString(),
        });

        // Show loading state
        const originalHTML = this.innerHTML;
        this.innerHTML =
          '<i class="fas fa-spinner fa-spin"></i><span>Loading...</span>';

        // Navigate to settings
        setTimeout(() => {
          window.location.href = "/dashboard/settings";
        }, 300);
      });
    }
  });

  console.log("✅ Profile and Settings functionality setup complete");
}

// Profile update function
function updateProfile(formData) {
  console.log("🔍 UPDATE PROFILE - Starting with data:", formData);

  return fetch("/dashboard/api/update-profile", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify(formData),
  })
    .then((response) => {
      console.log(`🔍 UPDATE PROFILE - Response status: ${response.status}`);
      return response.json();
    })
    .then((data) => {
      console.log("🔍 UPDATE PROFILE - Response data:", data);

      if (data.success) {
        console.log("✅ UPDATE PROFILE - Success!");
        if (window.dashboardManager && window.dashboardManager.showToast) {
          window.dashboardManager.showToast(
            "Profile updated successfully! 👤",
            "success"
          );
        }

        // Log the successful update
        logUserAction("profile_updated", {
          updated_fields: data.updated_fields,
          timestamp: new Date().toISOString(),
        });
      } else {
        console.error("❌ UPDATE PROFILE - Server error:", data.message);
        if (window.dashboardManager && window.dashboardManager.showToast) {
          window.dashboardManager.showToast(
            data.message || "Failed to update profile",
            "error"
          );
        }
      }
      return data;
    })
    .catch((error) => {
      console.error("❌ UPDATE PROFILE - Network error:", error);
      if (window.dashboardManager && window.dashboardManager.showToast) {
        window.dashboardManager.showToast(
          "Network error occurred while updating profile",
          "error"
        );
      }
      throw error;
    });
}

// Settings update function
function updateSettings(settingsData) {
  console.log("🔍 UPDATE SETTINGS - Starting with data:", settingsData);

  return fetch("/dashboard/api/update-settings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify(settingsData),
  })
    .then((response) => {
      console.log(`🔍 UPDATE SETTINGS - Response status: ${response.status}`);
      return response.json();
    })
    .then((data) => {
      console.log("🔍 UPDATE SETTINGS - Response data:", data);

      if (data.success) {
        console.log("✅ UPDATE SETTINGS - Success!");
        if (window.dashboardManager && window.dashboardManager.showToast) {
          window.dashboardManager.showToast(
            "Settings updated successfully! ⚙️",
            "success"
          );
        }

        // Apply theme change immediately if theme was updated
        if (data.updated && data.updated.includes("theme")) {
          applyThemeChange(settingsData.theme);
        }

        // Apply other settings changes
        if (data.updated && data.updated.includes("dashboard")) {
          applyDashboardSettings(settingsData.dashboard);
        }

        // Log the successful update
        logUserAction("settings_updated", {
          updated_settings: data.updated,
          timestamp: new Date().toISOString(),
        });
      } else {
        console.error("❌ UPDATE SETTINGS - Server error:", data.message);
        if (window.dashboardManager && window.dashboardManager.showToast) {
          window.dashboardManager.showToast(
            data.message || "Failed to update settings",
            "error"
          );
        }
      }
      return data;
    })
    .catch((error) => {
      console.error("❌ UPDATE SETTINGS - Network error:", error);
      if (window.dashboardManager && window.dashboardManager.showToast) {
        window.dashboardManager.showToast(
          "Network error occurred while updating settings",
          "error"
        );
      }
      throw error;
    });
}

// Theme application function
function applyThemeChange(theme) {
  console.log(`🔍 APPLY THEME - Applying theme: ${theme}`);

  // Update document theme
  document.documentElement.setAttribute("data-theme", theme);
  document.body.setAttribute("data-theme", theme);

  // Update theme toggle icon
  const themeToggle = document.querySelector(".theme-toggle i");
  if (themeToggle) {
    themeToggle.className = theme === "dark" ? "fas fa-sun" : "fas fa-moon";
    console.log(`✅ APPLY THEME - Icon updated to: ${themeToggle.className}`);
  }

  // Store in localStorage for persistence
  localStorage.setItem("dashboard-theme", theme);

  // Update dashboard manager theme if available
  if (window.dashboardManager) {
    window.dashboardManager.theme = theme;
  }

  console.log(`✅ APPLY THEME - Theme applied successfully: ${theme}`);
}

// Dashboard settings application function
function applyDashboardSettings(dashboardSettings) {
  console.log("🔍 APPLY DASHBOARD SETTINGS - Applying:", dashboardSettings);

  if (dashboardSettings.sidebar_collapsed !== undefined) {
    const sidebar = document.querySelector(".sidebar");
    if (sidebar) {
      if (dashboardSettings.sidebar_collapsed) {
        sidebar.classList.add("collapsed");
      } else {
        sidebar.classList.remove("collapsed");
      }
      localStorage.setItem(
        "sidebar-collapsed",
        dashboardSettings.sidebar_collapsed
      );
      console.log(
        `✅ APPLY DASHBOARD SETTINGS - Sidebar collapsed: ${dashboardSettings.sidebar_collapsed}`
      );
    }
  }

  if (dashboardSettings.snippets_per_page !== undefined) {
    // Update pagination if on snippets page
    console.log(
      `✅ APPLY DASHBOARD SETTINGS - Snippets per page: ${dashboardSettings.snippets_per_page}`
    );
  }

  console.log("✅ APPLY DASHBOARD SETTINGS - Settings applied successfully");
}

// User action logging function
function logUserAction(action, details = {}) {
  console.log(`📊 LOG USER ACTION - Action: ${action}, Details:`, details);

  fetch("/dashboard/api/log-user-action", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({
      action: action,
      details: details,
      timestamp: new Date().toISOString(),
      user_agent: navigator.userAgent,
      page_url: window.location.href,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        console.log(`✅ LOG USER ACTION - Logged successfully: ${action}`);
      } else {
        console.warn(`⚠️ LOG USER ACTION - Failed to log: ${action}`);
      }
    })
    .catch((error) => {
      console.warn(`⚠️ LOG USER ACTION - Network error for: ${action}`, error);
    });
}

// Enhanced dropdown interaction tracking
document.addEventListener("DOMContentLoaded", function () {
  const userDropdown = document.querySelector(".user-dropdown");
  if (userDropdown) {
    userDropdown.addEventListener("click", function (e) {
      const clickedItem = e.target.closest(".dropdown-item");
      if (clickedItem) {
        const itemText =
          clickedItem.querySelector("span")?.textContent || "Unknown";
        console.log(`🔍 DROPDOWN INTERACTION - Item clicked: ${itemText}`);

        // Log to server for analytics
        logUserAction("dropdown_click", {
          item: itemText,
          timestamp: new Date().toISOString(),
        });
      }
    });
  }
});

// Profile form handling (if on profile page)
document.addEventListener("DOMContentLoaded", function () {
  const profileForm = document.getElementById("profileForm");
  if (profileForm) {
    console.log("🔍 PROFILE FORM - Setting up form handler");

    profileForm.addEventListener("submit", function (e) {
      e.preventDefault();
      console.log("🔍 PROFILE FORM - Form submitted");

      const formData = new FormData(this);
      const profileData = {
        profile_settings: {},
        email: formData.get("email"),
        theme_preference: formData.get("theme_preference"),
      };

      // Collect profile settings
      [
        "bio",
        "location",
        "website",
        "twitter",
        "github",
        "linkedin",
        "timezone",
        "language",
      ].forEach((field) => {
        const value = formData.get(field);
        if (value !== null) {
          profileData.profile_settings[field] = value;
        }
      });

      console.log("🔍 PROFILE FORM - Collected data:", profileData);

      // Show loading state
      const submitBtn = this.querySelector('button[type="submit"]');
      const originalText = submitBtn.textContent;
      submitBtn.textContent = "Updating...";
      submitBtn.disabled = true;

      updateProfile(profileData)
        .then((result) => {
          if (result.success) {
            console.log("✅ PROFILE FORM - Update successful");
          }
        })
        .catch((error) => {
          console.error("❌ PROFILE FORM - Update failed:", error);
        })
        .finally(() => {
          submitBtn.textContent = originalText;
          submitBtn.disabled = false;
        });
    });
  }
});

// Settings form handling (if on settings page)
document.addEventListener("DOMContentLoaded", function () {
  const settingsForm = document.getElementById("settingsForm");
  if (settingsForm) {
    console.log("🔍 SETTINGS FORM - Setting up form handler");

    settingsForm.addEventListener("submit", function (e) {
      e.preventDefault();
      console.log("🔍 SETTINGS FORM - Form submitted");

      const formData = new FormData(this);
      const settingsData = {
        theme: formData.get("theme"),
        notifications: {
          email: formData.get("email_notifications") === "on",
          browser: formData.get("browser_notifications") === "on",
          collaboration: formData.get("collaboration_notifications") === "on",
        },
        editor: {
          font_family: formData.get("font_family"),
          font_size: parseInt(formData.get("font_size")) || 14,
          theme: formData.get("editor_theme"),
          word_wrap: formData.get("word_wrap") === "on",
          show_line_numbers: formData.get("show_line_numbers") === "on",
          vim_mode: formData.get("vim_mode") === "on",
        },
        dashboard: {
          sidebar_collapsed: formData.get("sidebar_collapsed") === "on",
          show_analytics: formData.get("show_analytics") === "on",
          snippets_per_page: parseInt(formData.get("snippets_per_page")) || 20,
          auto_save_enabled: formData.get("auto_save_enabled") === "on",
        },
      };

      console.log("🔍 SETTINGS FORM - Collected data:", settingsData);

      // Show loading state
      const submitBtn = this.querySelector('button[type="submit"]');
      const originalText = submitBtn.textContent;
      submitBtn.textContent = "Updating...";
      submitBtn.disabled = true;

      updateSettings(settingsData)
        .then((result) => {
          if (result.success) {
            console.log("✅ SETTINGS FORM - Update successful");
          }
        })
        .catch((error) => {
          console.error("❌ SETTINGS FORM - Update failed:", error);
        })
        .finally(() => {
          submitBtn.textContent = originalText;
          submitBtn.disabled = false;
        });
    });
  }
});

// Real-time settings updates (for toggles and sliders)
document.addEventListener("DOMContentLoaded", function () {
  // Theme toggle in settings
  const themeSelect = document.getElementById("themeSelect");
  if (themeSelect) {
    themeSelect.addEventListener("change", function () {
      const theme = this.value;
      console.log(`🔍 THEME TOGGLE - Changed to: ${theme}`);

      updateSettings({ theme: theme }).then((result) => {
        if (result.success) {
          console.log("✅ THEME TOGGLE - Updated successfully");
        }
      });
    });
  }

  // Notification toggles
  document.querySelectorAll(".notification-toggle").forEach((toggle) => {
    toggle.addEventListener("change", function () {
      const notificationType = this.dataset.type;
      const enabled = this.checked;

      console.log(`🔍 NOTIFICATION TOGGLE - ${notificationType}: ${enabled}`);

      const notifications = {};
      notifications[notificationType] = enabled;

      updateSettings({ notifications: notifications }).then((result) => {
        if (result.success) {
          console.log(
            `✅ NOTIFICATION TOGGLE - ${notificationType} updated successfully`
          );
        }
      });
    });
  });

  // Editor settings
  document.querySelectorAll(".editor-setting").forEach((setting) => {
    setting.addEventListener("change", function () {
      const settingName = this.dataset.setting;
      let value = this.value;

      // Handle different input types
      if (this.type === "checkbox") {
        value = this.checked;
      } else if (this.type === "number") {
        value = parseInt(value);
      }

      console.log(`🔍 EDITOR SETTING - ${settingName}: ${value}`);

      const editor = {};
      editor[settingName] = value;

      updateSettings({ editor: editor }).then((result) => {
        if (result.success) {
          console.log(
            `✅ EDITOR SETTING - ${settingName} updated successfully`
          );
        }
      });
    });
  });
});

// Export functions for global access
window.updateProfile = updateProfile;
window.updateSettings = updateSettings;
window.applyThemeChange = applyThemeChange;
window.logUserAction = logUserAction;

console.log("✅ Profile and Settings functionality loaded successfully");

/**
 * Advanced Snippet Editor - Modern Futuristic UI
 * Features: Syntax highlighting, Auto-completion, Real-time preview, AI suggestions
 */

class AdvancedSnippetEditor {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.options = {
      theme: "cyber-dark",
      autoSave: true,
      aiSuggestions: true,
      livePreview: true,
      fontSize: 14,
      tabSize: 2,
      wordWrap: true,
      ...options,
    };

    this.currentSnippet = null;
    this.editor = null;
    this.isModified = false;
    this.autoSaveTimer = null;
    this.suggestions = [];

    this.init();
  }

  init() {
    this.createEditorStructure();
    this.initializeEditor();
    this.setupEventListeners();
    this.initializeTheme();
    this.setupKeyboardShortcuts();
  }

  createEditorStructure() {
    this.container.innerHTML = `
            <div class="snippet-editor-wrapper">
                <!-- Editor Header -->
                <div class="editor-header">
                    <div class="editor-tabs">
                        <div class="tab active" data-tab="editor">
                            <i class="icon-code"></i>
                            <span>Editor</span>
                        </div>
                        <div class="tab" data-tab="preview">
                            <i class="icon-eye"></i>
                            <span>Preview</span>
                        </div>
                        <div class="tab" data-tab="settings">
                            <i class="icon-settings"></i>
                            <span>Settings</span>
                        </div>
                    </div>
                    
                    <div class="editor-controls">
                        <div class="control-group">
                            <select class="language-selector modern-select">
                                <option value="javascript">JavaScript</option>
                                <option value="python">Python</option>
                                <option value="java">Java</option>
                                <option value="cpp">C++</option>
                                <option value="html">HTML</option>
                                <option value="css">CSS</option>
                                <option value="sql">SQL</option>
                                <option value="json">JSON</option>
                                <option value="markdown">Markdown</option>
                                <option value="bash">Bash</option>
                            </select>
                            
                            <button class="btn-icon ai-assist" title="AI Assistance">
                                <i class="icon-sparkles"></i>
                            </button>
                            
                            <button class="btn-icon format-code" title="Format Code">
                                <i class="icon-align-left"></i>
                            </button>
                            
                            <button class="btn-icon fullscreen-toggle" title="Toggle Fullscreen">
                                <i class="icon-maximize"></i>
                            </button>
                        </div>
                        
                        <div class="save-status">
                            <span class="status-indicator"></span>
                            <span class="status-text">Saved</span>
                        </div>
                    </div>
                </div>

                <!-- Editor Content Area -->
                <div class="editor-content">
                    <!-- Code Editor Panel -->
                    <div class="editor-panel active" data-panel="editor">
                        <div class="editor-sidebar">
                            <div class="sidebar-section">
                                <h4>Quick Actions</h4>
                                <div class="quick-actions">
                                    <button class="action-btn" data-action="duplicate">
                                        <i class="icon-copy"></i>
                                        Duplicate
                                    </button>
                                    <button class="action-btn" data-action="share">
                                        <i class="icon-share"></i>
                                        Share
                                    </button>
                                    <button class="action-btn" data-action="export">
                                        <i class="icon-download"></i>
                                        Export
                                    </button>
                                </div>
                            </div>
                            
                            <div class="sidebar-section">
                                <h4>Collections</h4>
                                <div class="collections-list">
                                    <!-- Dynamic collections will be loaded here -->
                                </div>
                            </div>

<div class="sidebar-section">
  <h4>Team Sharing</h4>
  <div class="team-sharing-list">
    <div class="loading-teams">Loading teams...</div>
    <div class="teams-container" style="display: none;">
      <!-- Dynamic teams will be loaded here -->
    </div>
    <button class="share-with-teams-btn"  style="
      width: 100%;
      padding: 0.5rem;
      background: var(--accent-gradient);
      border: none;
      border-radius: 6px;
      color: white;
      font-weight: 600;
      cursor: pointer;
      margin-top: 0.5rem;
    ">
      🔗 Share with Teams
    </button>
  </div>
</div>

                            
                            <div class="sidebar-section">
                                <h4>Suggestions</h4>
                                <div class="ai-suggestions">
                                    <!-- AI suggestions will appear here -->
                                </div>
                            </div>
                        </div>
                        
                        <div class="editor-main">
                            <div class="editor-toolbar">
                                <div class="snippet-info">
                                    <input type="text" class="snippet-title" placeholder="Untitled Snippet" />
                                    <div class="snippet-meta">
                                        <span class="language-badge">JavaScript</span>
                                        <span class="chars-count">0 chars</span>
                                        <span class="lines-count">1 line</span>
                                    </div>
                                </div>
                                
                                <div class="editor-actions">
                                    <button class="btn-ghost run-code" title="Run Code">
                                        <i class="icon-play"></i>
                                        Run
                                    </button>
                                    <button class="btn-ghost save-snippet" title="Save Snippet">
                                        <i class="icon-save"></i>
                                        Save
                                    </button>
                                </div>
                            </div>
                            
                            <div class="code-editor-container">
                                <div class="line-numbers"></div>
                                <textarea class="code-editor" placeholder="Start typing your code..."></textarea>
                                <div class="editor-overlay">
                                    <div class="autocomplete-popup hidden">
                                        <div class="autocomplete-list"></div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="editor-footer">
                                <div class="cursor-info">
                                    <span>Line 1, Column 1</span>
                                </div>
                                <div class="editor-settings-quick">
                                    <span class="setting-item">Spaces: 2</span>
                                    <span class="setting-item">UTF-8</span>
                                    <span class="setting-item">LF</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Preview Panel -->
                    <div class="editor-panel" data-panel="preview">
                        <div class="preview-container">
                            <div class="preview-header">
                                <h3>Live Preview</h3>
                                <div class="preview-controls">
                                    <button class="btn-icon" data-preview="rendered">
                                        <i class="icon-eye"></i>
                                    </button>
                                    <button class="btn-icon" data-preview="highlighted">
                                        <i class="icon-code"></i>
                                    </button>
                                </div>
                            </div>
                            <div class="preview-content">
                                <pre class="highlighted-code"></pre>
                                <div class="rendered-output hidden"></div>
                            </div>
                        </div>
                    </div>

                    <!-- Settings Panel -->
                    <div class="editor-panel" data-panel="settings">
                        <div class="settings-container">
                            <div class="settings-section">
                                <h3>Editor Settings</h3>
                                <div class="setting-group">
                                    <label>Theme</label>
                                    <select class="theme-selector">
                                        <option value="cyber-dark">Cyber Dark</option>
                                        <option value="neon-blue">Neon Blue</option>
                                        <option value="matrix">Matrix Green</option>
                                        <option value="synthwave">Synthwave</option>
                                        <option value="minimal-light">Minimal Light</option>
                                    </select>
                                </div>
                                <div class="setting-group">
                                    <label>Font Size</label>
                                    <input type="range" class="font-size-slider" min="10" max="24" value="14" />
                                    <span class="font-size-value">14px</span>
                                </div>
                                <div class="setting-group">
                                    <label>Tab Size</label>
                                    <select class="tab-size-selector">
                                        <option value="2">2 spaces</option>
                                        <option value="4">4 spaces</option>
                                        <option value="8">8 spaces</option>
                                    </select>
                                </div>
                                <div class="setting-group">
                                    <label class="checkbox-label">
                                        <input type="checkbox" class="word-wrap-toggle" checked />
                                        <span class="checkmark"></span>
                                        Word Wrap
                                    </label>
                                </div>
                                <div class="setting-group">
                                    <label class="checkbox-label">
                                        <input type="checkbox" class="auto-save-toggle" checked />
                                        <span class="checkmark"></span>
                                        Auto Save
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Floating AI Assistant -->
            <div class="ai-assistant-float hidden">
                <div class="ai-header">
                    <i class="icon-sparkles"></i>
                    <span>AI Assistant</span>
                    <button class="close-ai">×</button>
                </div>
                <div class="ai-content">
                    <div class="ai-suggestions-list"></div>
                    <div class="ai-input">
                        <input type="text" placeholder="Ask AI anything..." />
                        <button class="send-ai">
                            <i class="icon-send"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
  }

  initializeEditor() {
    this.codeEditor = this.container.querySelector(".code-editor");
    this.lineNumbers = this.container.querySelector(".line-numbers");
    this.updateLineNumbers();

    // Initialize syntax highlighting
    this.initSyntaxHighlighting();

    // Load existing snippet if provided
    if (this.options.snippetId) {
      this.loadSnippet(this.options.snippetId);
    }
    this.loadTeamsForSharing();
  }

  loadSnippet(snippetId) {
    console.log("📄 Loading snippet:", snippetId);

    // Store current snippet ID
    this.currentSnippet = { id: snippetId };

    // Try to get snippet data from template data first
    if (window.TEMPLATE_DATA && window.TEMPLATE_DATA.snippet) {
      const snippetData = window.TEMPLATE_DATA.snippet;

      if (snippetData.id === snippetId) {
        console.log("✅ Loading snippet from template data");
        this.loadSnippetData(snippetData);
        return;
      }
    }

    // Fallback: Load via API
    this.loadSnippetFromAPI(snippetId);
  }

  loadSnippetData(snippetData) {
    console.log("📄 Loading snippet data:", snippetData);

    // Update editor with snippet data
    if (this.codeEditor) {
      this.codeEditor.value = snippetData.code || "";
    }

    // Update title
    const titleInput = this.container.querySelector(".snippet-title");
    if (titleInput) {
      titleInput.value = snippetData.title || "Untitled Snippet";
    }

    // Update language
    const languageSelector = this.container.querySelector(".language-selector");
    if (languageSelector && snippetData.language) {
      languageSelector.value = snippetData.language;
      this.changeLanguage(snippetData.language);
    }

    // Update metrics
    this.updateMetrics();
    this.updateLineNumbers();
    this.highlightSyntax();

    // Store current snippet
    this.currentSnippet = snippetData;

    console.log("✅ Snippet data loaded successfully");
  }

  async loadSnippetFromAPI(snippetId) {
    try {
      console.log("🌐 Loading snippet from API:", snippetId);

      const response = await fetch(`/api/snippets/${snippetId}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success && data.snippet) {
        this.loadSnippetData(data.snippet);
      } else {
        console.error("❌ Failed to load snippet:", data.message);
      }
    } catch (error) {
      console.error("❌ Error loading snippet from API:", error);

      // Show error in editor
      if (this.codeEditor) {
        this.codeEditor.value = `// Error loading snippet: ${error.message}`;
      }
    }
  }

  setupEventListeners() {
    // Tab switching
    this.container.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", (e) => {
        this.switchTab(e.target.closest(".tab").dataset.tab);
      });
    });
    const shareTeamsBtn = this.container.querySelector(".share-with-teams-btn");
    if (shareTeamsBtn) {
      shareTeamsBtn.addEventListener("click", () => {
        this.shareSnippet();
      });
    }

    // Code editor events
    this.codeEditor.addEventListener("input", (e) => {
      this.handleCodeInput(e);
    });

    this.codeEditor.addEventListener("keydown", (e) => {
      this.handleKeyDown(e);
    });

    this.codeEditor.addEventListener("scroll", () => {
      this.syncLineNumbers();
    });

    // Language selector
    this.container
      .querySelector(".language-selector")
      .addEventListener("change", (e) => {
        this.changeLanguage(e.target.value);
      });

    // Control buttons
    this.container.querySelector(".ai-assist").addEventListener("click", () => {
      this.toggleAIAssistant();
    });

    this.container
      .querySelector(".format-code")
      .addEventListener("click", () => {
        this.formatCode();
      });

    this.container
      .querySelector(".fullscreen-toggle")
      .addEventListener("click", () => {
        this.toggleFullscreen();
      });

    this.container.querySelector(".run-code").addEventListener("click", () => {
      this.runCode();
    });

    this.container
      .querySelector(".save-snippet")
      .addEventListener("click", () => {
        this.saveSnippet();
      });

    // Settings
    this.container
      .querySelector(".theme-selector")
      .addEventListener("change", (e) => {
        this.changeTheme(e.target.value);
      });

    this.container
      .querySelector(".font-size-slider")
      .addEventListener("input", (e) => {
        this.changeFontSize(e.target.value);
      });

    // Quick actions
    this.container.querySelectorAll(".action-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        this.handleQuickAction(e.target.closest(".action-btn").dataset.action);
      });
    });
  }

  handleCodeInput(e) {
    this.isModified = true;
    this.updateStatus("modified");
    this.updateLineNumbers();
    this.updateMetrics();
    this.highlightSyntax();

    if (this.options.livePreview) {
      this.updatePreview();
    }

    if (this.options.autoSave) {
      this.scheduleAutoSave();
    }

    // Show autocomplete
    this.showAutocomplete(e);
  }

  handleKeyDown(e) {
    // Handle special key combinations
    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case "s":
          e.preventDefault();
          this.saveSnippet();
          break;
        case "d":
          e.preventDefault();
          this.duplicateSnippet();
          break;
        case "/":
          e.preventDefault();
          this.toggleComment();
          break;
        case "f":
          e.preventDefault();
          this.formatCode();
          break;
      }
    }

    // Handle Tab key for indentation
    if (e.key === "Tab") {
      e.preventDefault();
      this.insertTab();
    }

    // Handle auto-closing brackets
    if (["(", "[", "{", '"', "'"].includes(e.key)) {
      this.handleAutoClose(e);
    }
  }

  initSyntaxHighlighting() {
    // ✅ FIXED: Use existing syntax highlighting method
    console.log("🎨 Initializing syntax highlighting");
    this.highlighter = {
      theme: this.options.theme,
      language: "javascript",
      highlight: (code, language) =>
        this.applySyntaxHighlighting(code, language),
    };

    // Apply initial highlighting
    this.highlightSyntax();
  }

  highlightSyntax() {
    const code = this.codeEditor.value;
    const language = this.container.querySelector(".language-selector").value;

    // Apply syntax highlighting (simplified - in real implementation, use Prism.js or Monaco)
    const highlighted = this.applySyntaxHighlighting(code, language);

    // Update preview
    if (this.options.livePreview) {
      this.container.querySelector(".highlighted-code").innerHTML = highlighted;
    }
  }

  applySyntaxHighlighting(code, language) {
    // Simplified syntax highlighting - replace with proper library
    const keywords = {
      javascript: [
        "function",
        "const",
        "let",
        "var",
        "if",
        "else",
        "for",
        "while",
        "return",
        "class",
        "import",
        "export",
      ],
      python: [
        "def",
        "class",
        "if",
        "else",
        "elif",
        "for",
        "while",
        "return",
        "import",
        "from",
        "try",
        "except",
      ],
      java: [
        "public",
        "private",
        "class",
        "interface",
        "extends",
        "implements",
        "if",
        "else",
        "for",
        "while",
        "return",
      ],
    };

    let highlighted = code;

    if (keywords[language]) {
      keywords[language].forEach((keyword) => {
        const regex = new RegExp(`\\b${keyword}\\b`, "g");
        highlighted = highlighted.replace(
          regex,
          `<span class="keyword">${keyword}</span>`
        );
      });
    }

    // Highlight strings
    highlighted = highlighted.replace(
      /(["'])((?:(?!\1)[^\\]|\\.)*)(\1)/g,
      '<span class="string">$1$2$3</span>'
    );

    // Highlight comments
    highlighted = highlighted.replace(
      /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm,
      '<span class="comment">$1</span>'
    );

    return highlighted;
  }

  updateLineNumbers() {
    const lines = this.codeEditor.value.split("\n").length;
    const lineNumbersHtml = Array.from(
      { length: lines },
      (_, i) => `<div class="line-number">${i + 1}</div>`
    ).join("");

    this.lineNumbers.innerHTML = lineNumbersHtml;
  }

  syncLineNumbers() {
    this.lineNumbers.scrollTop = this.codeEditor.scrollTop;
  }

  updateMetrics() {
    const code = this.codeEditor.value;
    const chars = code.length;
    const lines = code.split("\n").length;

    this.container.querySelector(".chars-count").textContent = `${chars} chars`;
    this.container.querySelector(".lines-count").textContent = `${lines} line${
      lines !== 1 ? "s" : ""
    }`;
  }

  switchTab(tabName) {
    // Update tab active states
    this.container.querySelectorAll(".tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.tab === tabName);
    });

    // Update panel visibility
    this.container.querySelectorAll(".editor-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.panel === tabName);
    });
  }

  changeLanguage(language) {
    this.container.querySelector(".language-badge").textContent =
      language.charAt(0).toUpperCase() + language.slice(1);
    this.highlightSyntax();
    this.updatePreview();
  }

  toggleAIAssistant() {
    const aiFloat = this.container.querySelector(".ai-assistant-float");
    aiFloat.classList.toggle("hidden");

    if (!aiFloat.classList.contains("hidden")) {
      this.loadAISuggestions();
    }
  }

  formatCode() {
    const code = this.codeEditor.value;
    const language = this.container.querySelector(".language-selector").value;

    // Format code based on language (simplified)
    const formatted = this.formatCodeForLanguage(code, language);
    this.codeEditor.value = formatted;
    this.highlightSyntax();
    this.updateMetrics();
  }

  formatCodeForLanguage(code, language) {
    // Simplified formatting - replace with proper formatter
    let formatted = code;

    // Basic indentation fix
    const lines = code.split("\n");
    let indentLevel = 0;
    const tabSize =
      parseInt(this.container.querySelector(".tab-size-selector").value) || 2;

    formatted = lines
      .map((line) => {
        const trimmed = line.trim();

        if (trimmed.includes("}") && !trimmed.includes("{")) {
          indentLevel = Math.max(0, indentLevel - 1);
        }

        const indented = " ".repeat(indentLevel * tabSize) + trimmed;

        if (trimmed.includes("{") && !trimmed.includes("}")) {
          indentLevel++;
        }

        return indented;
      })
      .join("\n");

    return formatted;
  }

  scheduleAutoSave() {
    clearTimeout(this.autoSaveTimer);
    this.autoSaveTimer = setTimeout(() => {
      this.saveSnippet(true);
    }, 2000);
  }

  saveSnippet(isAutoSave = false) {
    const snippetData = {
      title:
        this.container.querySelector(".snippet-title").value ||
        "Untitled Snippet",
      code: this.codeEditor.value,
      language: this.container.querySelector(".language-selector").value,
      id: this.currentSnippet?.id,
    };

    // Send to server via WebSocket or API
    if (window.wsClient) {
      window.wsClient.saveSnippet(snippetData);
    } else {
      this.saveViaAPI(snippetData);
    }

    this.isModified = false;
    this.updateStatus(isAutoSave ? "auto-saved" : "saved");
  }

  updateStatus(status) {
    const indicator = this.container.querySelector(".status-indicator");
    const text = this.container.querySelector(".status-text");

    indicator.className = `status-indicator ${status}`;

    switch (status) {
      case "saved":
        text.textContent = "Saved";
        break;
      case "auto-saved":
        text.textContent = "Auto-saved";
        break;
      case "modified":
        text.textContent = "Modified";
        break;
      case "saving":
        text.textContent = "Saving...";
        break;
    }
  }

  initializeTheme() {
    this.changeTheme(this.options.theme);
  }

  changeTheme(themeName) {
    this.container.className = `snippet-editor-wrapper theme-${themeName}`;
    this.options.theme = themeName;
  }

  setupKeyboardShortcuts() {
    const shortcuts = {
      "Ctrl+S": () => this.saveSnippet(),
      "Ctrl+D": () => this.duplicateSnippet(),
      "Ctrl+/": () => this.toggleComment(),
      "Ctrl+F": () => this.formatCode(),
      F11: () => this.toggleFullscreen(),
      "Ctrl+Space": () => this.showAutocomplete(),
    };

    document.addEventListener("keydown", (e) => {
      const key = `${e.ctrlKey ? "Ctrl+" : ""}${e.altKey ? "Alt+" : ""}${
        e.shiftKey ? "Shift+" : ""
      }${e.key}`;
      if (shortcuts[key] && this.container.contains(document.activeElement)) {
        e.preventDefault();
        shortcuts[key]();
      }
    });
  }

  // Placeholder methods for advanced features
  runCode() {
    // Implementation for code execution
    console.log("Running code...");
  }

  loadAISuggestions() {
    // Implementation for AI suggestions
    console.log("Loading AI suggestions...");
  }

  async loadTeamsForSharing() {
    console.log("🏢 ADVANCED EDITOR: Loading teams for sharing");

    try {
      const response = await fetch("/api/snippets/user-teams");

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success) {
        const allTeams = [
          ...data.created_teams.map((team) => ({ ...team, role: "Owner" })),
          ...data.joined_teams.map((team) => ({
            ...team,
            role: team.user_role || "Member",
          })),
        ];

        this.renderTeamsInSidebar(allTeams);
        console.log(`✅ ADVANCED EDITOR: Loaded ${allTeams.length} teams`);
      }
    } catch (error) {
      console.error("❌ ADVANCED EDITOR: Error loading teams:", error);
      this.showTeamsError();
    }
  }

  renderTeamsInSidebar(teams) {
    const loadingElement = this.container.querySelector(".loading-teams");
    const teamsContainer = this.container.querySelector(".teams-container");

    if (!teamsContainer || !loadingElement) return;

    if (teams.length === 0) {
      loadingElement.textContent = "No teams available";
      return;
    }

    loadingElement.style.display = "none";
    teamsContainer.style.display = "block";

    teamsContainer.innerHTML = teams
      .map(
        (team) => `
    <div class="team-item" style="
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem;
      border-radius: 4px;
      cursor: pointer;
      transition: background 0.2s ease;
      font-size: 0.9rem;
    " onmouseover="this.style.background='rgba(255,255,255,0.1)'" 
       onmouseout="this.style.background='transparent'">
      <span style="font-size: 1.2rem;">🏢</span>
      <div style="flex: 1;">
        <div style="font-weight: 500;">${this.escapeHtml(team.name)}</div>
        <div style="font-size: 0.8rem; opacity: 0.7;">${team.role}</div>
      </div>
    </div>
  `
      )
      .join("");
  }

  showTeamsError() {
    const loadingElement = this.container.querySelector(".loading-teams");
    if (loadingElement) {
      loadingElement.textContent = "Failed to load teams";
      loadingElement.style.color = "#ff6b6b";
    }
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  showAutocomplete() {
    // Implementation for autocomplete
    console.log("Showing autocomplete...");
  }

  async shareSnippet() {
    console.log("🔗 ===== ADVANCED EDITOR SHARE SNIPPET =====");

    // Get current snippet data
    const snippetData = {
      id: this.currentSnippet?.id,
      title:
        this.container.querySelector(".snippet-title").value ||
        "Untitled Snippet",
      code: this.codeEditor.value,
      language: this.container.querySelector(".language-selector").value,
    };

    console.log("🔗 Sharing snippet from advanced editor:", snippetData);

    // If snippet doesn't exist, save it first
    if (!snippetData.id) {
      console.log("🔗 Snippet not saved yet, saving first...");
      await this.saveSnippet(false);

      // Get the ID after saving
      if (this.currentSnippet?.id) {
        snippetData.id = this.currentSnippet.id;
      } else {
        this.showNotification(
          "Please save the snippet first before sharing",
          "warning"
        );
        return;
      }
    }

    // 🔥 FIX: Use direct sharing instead of modal
    await this.shareSnippetDirect();

    console.log("✅ Share action completed for snippet:", snippetData.id);
  }
  // 🔥 NATURAL LANGUAGE: Advanced editor sharing
  async shareSnippetDirect() {
    console.log("🔗 ===== ADVANCED EDITOR SHARING START =====");

    const snippetData = {
      id: this.currentSnippet?.id,
      title:
        this.container.querySelector(".snippet-title").value ||
        "Untitled Snippet",
      code: this.codeEditor.value,
      language: this.container.querySelector(".language-selector").value,
    };

    if (!snippetData.id) {
      this.showNotification(
        "Please save the snippet first before sharing",
        "warning"
      );
      return;
    }

    try {
      const response = await fetch("/api/snippets/user-teams");
      const data = await response.json();

      if (!data.success) {
        this.showNotification("Failed to load teams", "error");
        return;
      }

      const allTeams = [
        ...data.created_teams.map((team) => ({ ...team, role: "Owner" })),
        ...data.joined_teams.map((team) => ({
          ...team,
          role: team.user_role || "Member",
        })),
      ];

      if (allTeams.length === 0) {
        this.showNotification("No teams available for sharing", "info");
        return;
      }

      const teamOptions = allTeams
        .map(
          (team) =>
            `<label style="display: block; margin: 0.5rem 0;">
        <input type="checkbox" value="${team.id}" style="margin-right: 0.5rem;">
        ${this.escapeHtml(team.name)} (${team.role})
      </label>`
        )
        .join("");

      // 🔥 NATURAL LANGUAGE: "Share" not "Create copies"
      const confirmed = confirm(`Share "${snippetData.title}" with teams?`);

      if (confirmed) {
        const dialog = document.createElement("div");
        dialog.style.cssText = `
        position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 10000; max-width: 400px; max-height: 500px; overflow-y: auto;
        color: black;
      `;

        dialog.innerHTML = `
        <h3>🔗 Share with Teams:</h3>
        <div style="margin: 1rem 0;">${teamOptions}</div>
        <div style="text-align: right; margin-top: 1rem;">
          <button id="cancelShare" style="margin-right: 1rem; padding: 0.5rem 1rem; background: #ccc; border: none; border-radius: 4px;">Cancel</button>
          <button id="confirmShare" style="padding: 0.5rem 1rem; background: #007bff; color: white; border: none; border-radius: 4px;">🔗 Share</button>
        </div>
      `;

        document.body.appendChild(dialog);

        document.getElementById("cancelShare").onclick = () => {
          document.body.removeChild(dialog);
        };

        document.getElementById("confirmShare").onclick = async () => {
          const selectedTeams = Array.from(
            dialog.querySelectorAll('input[type="checkbox"]:checked')
          ).map((cb) => cb.value);

          if (selectedTeams.length === 0) {
            alert("Please select at least one team");
            return;
          }

          try {
            let successCount = 0;

            for (const teamId of selectedTeams) {
              try {
                const shareResponse = await fetch(
                  `/api/snippets/${snippetData.id}/share`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      team_ids: [teamId],
                      sharing_type: "copy", // Technical implementation (hidden)
                    }),
                  }
                );

                const result = await shareResponse.json();

                if (result.success) {
                  successCount++;
                }
              } catch (teamError) {
                console.error(`❌ Share error for team ${teamId}:`, teamError);
              }
            }

            if (successCount > 0) {
              // 🔥 NATURAL MESSAGE: "Shared" not "Copied"
              this.showNotification(
                `✅ Snippet shared with ${successCount} team(s) successfully!`,
                "success"
              );
            } else {
              this.showNotification("Failed to share with any teams", "error");
            }
          } catch (error) {
            console.error("❌ Advanced editor share error:", error);
            this.showNotification("Failed to share snippet", "error");
          }

          document.body.removeChild(dialog);
        };
      }
    } catch (error) {
      console.error("❌ Advanced editor share error:", error);
      this.showNotification("Failed to load teams for sharing", "error");
    }

    console.log("🔗 ===== ADVANCED EDITOR SHARING END =====");
  }

  showNotification(message, type = "info") {
    // Simple notification - you can enhance this
    console.log(`${type.toUpperCase()}: ${message}`);

    // If there's a global notification system, use it
    if (window.showToast) {
      window.showToast(message, type);
    } else {
      alert(message);
    }
  }

  duplicateSnippet() {
    console.log("Duplicating snippet...");
    // Implementation for duplicating snippet
  }

  exportSnippet() {
    console.log("Exporting snippet...");
    // Implementation for exporting snippet
  }

  saveViaAPI(snippetData) {
    console.log("Saving via API:", snippetData);
    // Implementation for API saving
  }

  insertTab() {
    // Implementation for tab insertion
    const start = this.codeEditor.selectionStart;
    const end = this.codeEditor.selectionEnd;
    const spaces = " ".repeat(this.options.tabSize);

    this.codeEditor.value =
      this.codeEditor.value.substring(0, start) +
      spaces +
      this.codeEditor.value.substring(end);

    this.codeEditor.selectionStart = this.codeEditor.selectionEnd =
      start + spaces.length;
  }

  handleAutoClose(e) {
    // Implementation for auto-closing brackets
    console.log("Auto-closing:", e.key);
  }

  toggleComment() {
    // Implementation for toggling comments
    console.log("Toggling comment...");
  }

  updatePreview() {
    // Implementation for updating preview
    this.highlightSyntax();
  }

  changeFontSize(size) {
    this.codeEditor.style.fontSize = `${size}px`;
    this.container.querySelector(".font-size-value").textContent = `${size}px`;
  }

  toggleFullscreen() {
    this.container.classList.toggle("fullscreen");
  }

  handleQuickAction(action) {
    switch (action) {
      case "duplicate":
        this.duplicateSnippet();
        break;
      case "share":
        this.shareSnippet();
        break;
      case "export":
        this.exportSnippet();
        break;
    }
  }
}

// Export for use
window.AdvancedSnippetEditor = AdvancedSnippetEditor;

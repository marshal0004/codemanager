// Code Snippet Manager - Content Script
// Detects code blocks and handles selection UI

window.snippetManagerInjected = true;

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("Content script received message:", message);
  return true; // Keep channel open for async response
});

class CodeSnippetDetector {
  constructor() {
    this.isActive = false;
    this.selectedText = "";
    this.detectedLanguage = "";
    this.sourceUrl = window.location.href;
    this.init();
  }

  init() {
    this.createSaveButton();
    this.attachEventListeners();
    this.highlightCodeBlocks();
    this.initializeDebugFunction(); // Add this line
    this.trackSyntaxErrors(); // Add this line for error tracking
  }

  // Detect and highlight existing code blocks
  highlightCodeBlocks() {
    console.log("Starting code block detection...");
    console.log("Current URL:", window.location.href);
    console.log("Document ready state:", document.readyState);
    console.log("Body children count:", document.body.children.length);

    const codeSelectors = [
      "pre code",
      "pre",
      ".highlight",
      ".codehilite",
      ".language-",
      '[class*="language-"]',
      ".hljs",
      "code",
      ".code",
      "[class*='lang-']",
    ];

    let totalFound = 0;
    let totalEnhanced = 0;

    // First, let's see what's actually in the DOM
    console.log("DOM inspection:");
    console.log("- All PRE elements:", document.querySelectorAll("pre").length);
    console.log(
      "- All CODE elements:",
      document.querySelectorAll("code").length
    );
    console.log(
      "- Elements with 'language' in class:",
      document.querySelectorAll('[class*="language"]').length
    );
    console.log(
      "- Elements with 'hljs' class:",
      document.querySelectorAll(".hljs").length
    );

    codeSelectors.forEach((selector) => {
      const blocks = document.querySelectorAll(selector);
      console.log(`Selector "${selector}" found ${blocks.length} elements`);
      totalFound += blocks.length;

      blocks.forEach((block, index) => {
        console.log(`Processing block ${index + 1}:`, {
          tagName: block.tagName,
          className: block.className,
          textContent: (block.textContent || "").substring(0, 50) + "...",
          textLength: (block.textContent || "").length,
        });

        if (this.isValidCodeBlock(block)) {
          this.enhanceCodeBlock(block);
          block.dataset.snippetEnabled = "true";
          totalEnhanced++;
          console.log(`✅ Enhanced code block ${index + 1}:`, block);
        } else {
          console.log(`❌ Skipped code block ${index + 1} (invalid):`, {
            hasDataset: !!block.dataset.snippetEnabled,
            textLength: (block.textContent || "").length,
            tagName: block.tagName,
            className: block.className,
          });
        }
      });
    });

    console.log(
      `Code block detection complete. Found: ${totalFound}, Enhanced: ${totalEnhanced}`
    );
  }
  // Check if element is a valid code block worth enhancing
  isValidCodeBlock(element) {
    // Skip if it's our own modal preview
    if (
      element.classList.contains("code-preview") ||
      element.closest(".code-preview") ||
      element.closest(".cyberpunk-preview")
    ) {
      return false;
    }
    // Skip if already enhanced
    if (element.dataset.snippetEnabled) {
      return false;
    }

    // Skip very small code snippets (likely inline code)
    const text = element.textContent || element.innerText || "";
    if (text.trim().length < 20) {
      return false;
    }

    // Skip if it's just a single word or very short
    if (text.trim().split(/\s+/).length < 3) {
      return false;
    }

    // Skip if it's inside our own UI elements
    if (
      element.closest(".snippet-collection-modal") ||
      element.closest(".snippet-quick-save") ||
      element.closest(".snippet-selection-save") ||
      element.closest(".cyberpunk-modal") ||
      element.closest(".cyberpunk-preview") ||
      element.closest(".code-preview") ||
      element.classList.contains("code-preview")
    ) {
      return false;
    }

    // Prefer pre tags and code blocks with specific classes
    if (
      element.tagName === "PRE" ||
      element.classList.contains("highlight") ||
      element.classList.contains("hljs") ||
      element.className.includes("language-")
    ) {
      return true;
    }

    // For regular code tags, be more selective
    if (element.tagName === "CODE") {
      // Only enhance if it's inside a pre tag or has multiple lines
      return element.closest("pre") || text.includes("\n");
    }

    return true;
  }

  // Add hover effect and save button to code blocks
  // Add hover effect and save button to code blocks
  // Add hover effect and save button to code blocks - ENHANCED LOGGING
  enhanceCodeBlock(codeBlock) {
    console.log("🔧 ENHANCE CODE BLOCK - Starting enhancement:", {
      tagName: codeBlock.tagName,
      className: codeBlock.className,
      textLength: codeBlock.textContent?.length || 0,
      hasPosition: !!codeBlock.style.position,
      currentPosition: codeBlock.style.position || "static",
    });

    // Ensure relative positioning for absolute button placement
    if (!codeBlock.style.position || codeBlock.style.position === "static") {
      codeBlock.style.position = "relative";
      console.log("🔧 ENHANCE CODE BLOCK - Set position to relative");
    }

    codeBlock.addEventListener("mouseenter", () => {
      console.log("🎯 CODE BLOCK - Mouse entered, showing save button");
      this.showQuickSave(codeBlock);
    });

    codeBlock.addEventListener("mouseleave", () => {
      console.log("🎯 CODE BLOCK - Mouse left, scheduling hide save button");
      this.hideQuickSave();
    });

    console.log("✅ ENHANCE CODE BLOCK - Enhancement completed successfully");
  }

  // Show quick save button on code block hover - FIXED POSITIONING
  showQuickSave(codeBlock) {
    const existingBtn = document.querySelector(".snippet-quick-save");
    if (existingBtn) existingBtn.remove();

    const quickSaveBtn = document.createElement("button");
    quickSaveBtn.className = "snippet-quick-save";
    quickSaveBtn.innerHTML = `
    <div class="cyberpunk-save-icon">
      <div class="save-core"></div>
      <div class="save-ring"></div>
      <div class="save-pulse"></div>
    </div>
  `;
    quickSaveBtn.title = "Save this code snippet";

    // FIXED: Position on LEFT side, always visible
    quickSaveBtn.style.cssText = `
    position: absolute;
    top: 8px;
    left: 8px;
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, #00ffff, #ff00ff);
    border: 2px solid #ffff00;
    border-radius: 50%;
    cursor: pointer;
    z-index: 1001;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
    box-shadow: 
      0 0 15px rgba(0, 255, 255, 0.5),
      inset 0 0 10px rgba(255, 255, 255, 0.2);
    animation: cyberpunkPulse 2s infinite;
  `;

    // Enhanced hover effects
    quickSaveBtn.addEventListener("mouseenter", () => {
      quickSaveBtn.style.transform = "scale(1.1) rotate(10deg)";
      quickSaveBtn.style.boxShadow = `
      0 0 25px rgba(0, 255, 255, 0.8),
      0 0 35px rgba(255, 0, 255, 0.6),
      inset 0 0 15px rgba(255, 255, 255, 0.3)
    `;
      console.log("🎯 SAVE BUTTON - Hover effect activated");
    });

    quickSaveBtn.addEventListener("mouseleave", () => {
      quickSaveBtn.style.transform = "scale(1) rotate(0deg)";
      quickSaveBtn.style.boxShadow = `
      0 0 15px rgba(0, 255, 255, 0.5),
      inset 0 0 10px rgba(255, 255, 255, 0.2)
    `;
    });

    quickSaveBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      console.log("🎯 SAVE BUTTON - Clicked, saving code block");

      // Add click animation
      quickSaveBtn.style.transform = "scale(0.9)";
      setTimeout(() => {
        quickSaveBtn.style.transform = "scale(1)";
      }, 150);

      this.saveCodeBlock(codeBlock);
    });

    // Add cyberpunk styles if not already present
    this.addCyberpunkSaveStyles();

    codeBlock.appendChild(quickSaveBtn);
    console.log("🎯 SAVE BUTTON - Positioned on LEFT side of code block");
  }

  // Add cyberpunk save button styles
  addCyberpunkSaveStyles() {
    if (document.querySelector("#cyberpunk-save-styles")) {
      return; // Already added
    }

    const style = document.createElement("style");
    style.id = "cyberpunk-save-styles";
    style.textContent = `
    @keyframes cyberpunkPulse {
      0%, 100% { 
        box-shadow: 
          0 0 15px rgba(0, 255, 255, 0.5),
          inset 0 0 10px rgba(255, 255, 255, 0.2);
      }
      50% { 
        box-shadow: 
          0 0 25px rgba(0, 255, 255, 0.8),
          0 0 35px rgba(255, 0, 255, 0.4),
          inset 0 0 15px rgba(255, 255, 255, 0.3);
      }
    }
    
    @keyframes saveRingRotate {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    
    @keyframes savePulseGlow {
      0%, 100% { opacity: 0.3; transform: scale(1); }
      50% { opacity: 0.8; transform: scale(1.2); }
    }

      @keyframes fadeOut {
        from { opacity: 1; transform: scale(1); }
        to { opacity: 0; transform: scale(0.8); }
    }
    
    .cyberpunk-save-icon {
      position: relative;
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .save-core {
      width: 12px;
      height: 12px;
      background: linear-gradient(45deg, #ffff00, #ffffff);
      border-radius: 50%;
      position: relative;
      z-index: 3;
      box-shadow: 0 0 8px rgba(255, 255, 0, 0.8);
    }
    
    .save-core::before {
      content: "💾";
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 8px;
      color: #000;
    }
    
    .save-ring {
      position: absolute;
      width: 20px;
      height: 20px;
      border: 2px solid transparent;
      border-top: 2px solid #00ffff;
      border-right: 2px solid #ff00ff;
      border-radius: 50%;
      animation: saveRingRotate 2s linear infinite;
      z-index: 2;
    }
    
    
    .save-pulse {
      position: absolute;
      width: 24px;
      height: 24px;
      border: 1px solid #ffff00;
      border-radius: 50%;
      animation: savePulseGlow 1.5s ease-in-out infinite;
      z-index: 1;
    }
    
    /* Ensure code blocks have relative positioning for absolute button */
    pre, code, .highlight, .hljs {
      position: relative !important;
    }
    
    /* Prevent button from being affected by code block scrolling */
    .snippet-quick-save {
      position: absolute !important;
      left: 8px !important;
      top: 8px !important;
      z-index: 1001 !important;
    }
  `;

    document.head.appendChild(style);
    console.log("🎨 CYBERPUNK SAVE STYLES - Added to page");
  }
  // Debug function to check button positioning
  debugButtonPosition() {
    console.log("🔍 BUTTON POSITION DEBUG - Checking all save buttons");

    const buttons = document.querySelectorAll(".snippet-quick-save");
    const codeBlocks = document.querySelectorAll(
      "pre, code, .highlight, .hljs"
    );

    console.log(
      `📊 Found ${buttons.length} save buttons and ${codeBlocks.length} code blocks`
    );

    buttons.forEach((button, index) => {
      const rect = button.getBoundingClientRect();
      const parent = button.parentElement;
      const parentRect = parent ? parent.getBoundingClientRect() : null;

      console.log(`🎯 Button ${index + 1}:`, {
        position: button.style.position,
        left: button.style.left,
        top: button.style.top,
        zIndex: button.style.zIndex,
        visible: rect.width > 0 && rect.height > 0,
        parentTag: parent?.tagName,
        parentPosition: parent?.style.position,
      });
    });

    codeBlocks.forEach((block, index) => {
      console.log(`📝 Code Block ${index + 1}:`, {
        tagName: block.tagName,
        position: block.style.position || "static",
        hasButton: !!block.querySelector(".snippet-quick-save"),
        scrollWidth: block.scrollWidth,
        clientWidth: block.clientWidth,
        needsHorizontalScroll: block.scrollWidth > block.clientWidth,
      });
    });
  }

  // Initialize debug function after class instantiation
  initializeDebugFunction() {
    const self = this;
    window.debugSaveButtons = function () {
      self.debugButtonPosition();
    };
    console.log("🔧 Debug function initialized globally");
  }
  // Enhanced error tracking for syntax issues
  trackSyntaxErrors() {
    console.log("🔍 SYNTAX CHECK - Verifying class structure");

    try {
      // Check if all methods are properly defined
      const methods = [
        "init",
        "highlightCodeBlocks",
        "isValidCodeBlock",
        "enhanceCodeBlock",
        "showQuickSave",
        "addCyberpunkSaveStyles",
        "debugButtonPosition",
        "hideQuickSave",
        "saveCodeBlock",
        "attachEventListeners",
      ];

      methods.forEach((method) => {
        if (typeof this[method] === "function") {
          console.log(`✅ Method ${method}: OK`);
        } else {
          console.error(`❌ Method ${method}: MISSING or INVALID`);
        }
      });

      console.log("✅ SYNTAX CHECK - All methods verified");
    } catch (error) {
      console.error("❌ SYNTAX CHECK - Error during verification:", error);
    }
  }

  // Enhanced save flow tracking
  trackSaveFlow(step, data = {}) {
    const timestamp = new Date().toISOString();
    console.log(`🔍 SAVE FLOW TRACKER [${timestamp}] - ${step}:`, data);

    // Store in session for debugging
    if (!window.saveFlowLog) {
      window.saveFlowLog = [];
    }

    window.saveFlowLog.push({
      timestamp,
      step,
      data,
    });

    // Keep only last 20 entries
    if (window.saveFlowLog.length > 20) {
      window.saveFlowLog.shift();
    }
  }
  hideQuickSave() {
    setTimeout(() => {
      const btn = document.querySelector(".snippet-quick-save");
      if (btn) {
        console.log("🎯 SAVE BUTTON - Hiding save button");
        btn.style.animation = "fadeOut 0.3s ease-out";
        setTimeout(() => {
          if (btn.parentNode) {
            btn.remove();
            console.log("🎯 SAVE BUTTON - Save button removed from DOM");
          }
        }, 300);
      }
    }, 100);
  }

  // Save code block content
  // Save code block content - FIXED: Variable declaration order
  saveCodeBlock(codeBlock) {
    console.log("🎯 SAVE CODE BLOCK - Starting save process");

    // Remove the save button temporarily to get clean code
    const saveBtn = codeBlock.querySelector(".snippet-quick-save");
    if (saveBtn) {
      saveBtn.remove();
      console.log(
        "🎯 SAVE CODE BLOCK - Removed save button for clean code extraction"
      );
    }

    // Get the clean code content FIRST
    const code = codeBlock.textContent || codeBlock.innerText;
    const language = this.detectLanguage(codeBlock);
    const title = this.generateTitle(code, language);

    // NOW we can use the variables in trackSaveFlow
    // this.trackSaveFlow("ICON_CLICKED", {
    //   codeLength: code.trim().length,
    //   language: language,
    //   title: title,
    // });

    console.log("🎯 SAVE CODE BLOCK - Extracted data:", {
      codeLength: code.trim().length,
      language: language,
      title: title,
    });

    // Send to background - SUCCESS MESSAGE WILL BE SHOWN ONLY AFTER MODAL SAVE
    this.sendSnippetToBackground({
      code: code.trim(),
      language: language,
      title: title,
      source_url: this.sourceUrl,
      tags: [language, "auto-saved"],
      timestamp: Date.now(),
    });

    console.log(
      "🎯 SAVE CODE BLOCK - Sent to background, waiting for modal completion"
    );
  }

  // Handle text selection
  attachEventListeners() {
    // Listen for text selection
    document.addEventListener("mouseup", () => {
      const selection = window.getSelection();
      if (selection.toString().trim().length > 10) {
        this.selectedText = selection.toString().trim();
        this.showSelectionSaveButton(selection);
      } else {
        this.hideSelectionButton();
      }
    });

    // Keyboard shortcut (Ctrl+S)
    document.addEventListener("keydown", (e) => {
      if (e.ctrlKey && e.key === "s" && this.selectedText) {
        e.preventDefault();
        this.saveSelectedText();
      }
    });

    // Hide button when clicking elsewhere
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".snippet-selection-save")) {
        this.hideSelectionButton();
      }
    });
  }

  // Show save button for selected text
  showSelectionSaveButton(selection) {
    this.hideSelectionButton();

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();

    const saveBtn = document.createElement("div");
    saveBtn.className = "snippet-selection-save";
    saveBtn.innerHTML = `
            <button class="save-snippet-btn">💾 Save Code</button>
        `;

    saveBtn.style.cssText = `
            position: fixed;
            top: ${rect.bottom + window.scrollY + 5}px;
            left: ${rect.left + window.scrollX}px;
            background: #333;
            border-radius: 6px;
            padding: 4px;
            z-index: 10000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        `;

    const button = saveBtn.querySelector(".save-snippet-btn");
    button.style.cssText = `
            background: #007acc;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 12px;
            cursor: pointer;
            white-space: nowrap;
        `;

    button.addEventListener("click", () => {
      this.saveSelectedText();
    });

    document.body.appendChild(saveBtn);
  }

  hideSelectionButton() {
    const btn = document.querySelector(".snippet-selection-save");
    if (btn) btn.remove();
  }

  // Save selected text as snippet - FIXED: No premature success message
  saveSelectedText() {
    if (!this.selectedText) return;

    console.log("🎯 SAVE SELECTED TEXT - Starting save process");
    console.log(
      "🎯 SAVE SELECTED TEXT - Selected text length:",
      this.selectedText.length
    );

    const language = this.detectLanguage();
    const title = this.generateTitle(this.selectedText, language);

    console.log("🎯 SAVE SELECTED TEXT - Generated data:", {
      language: language,
      title: title,
    });

    this.sendSnippetToBackground({
      code: this.selectedText,
      language: language,
      title: title,
      source_url: this.sourceUrl,
      tags: [language, "manual-selection"],
      timestamp: Date.now(),
    });

    console.log(
      "🎯 SAVE SELECTED TEXT - Sent to background, waiting for modal completion"
    );
    // ← REMOVED this.showSuccessMessage() - Success will be shown only after modal save

    this.hideSelectionButton();
    window.getSelection().removeAllRanges();
    this.selectedText = "";
  }

  // Detect programming language
  detectLanguage(element = null) {
    // Check element classes first
    if (element) {
      const className = element.className;
      const langMatch = className.match(/language-(\w+)|lang-(\w+)|\b(\w+)\b/);
      if (langMatch) {
        return langMatch[1] || langMatch[2] || langMatch[3];
      }
    }

    // Basic content-based detection
    const code = this.selectedText || (element ? element.textContent : "");

    if (code.includes("function") && code.includes("{")) return "javascript";
    if (code.includes("def ") && code.includes(":")) return "python";
    if (code.includes("public class") || code.includes("System.out"))
      return "java";
    if (code.includes("#include") || code.includes("int main")) return "cpp";
    if (code.includes("<?php")) return "php";
    if (code.includes("<html>") || code.includes("<div>")) return "html";
    if (code.includes("{") && code.includes("color:")) return "css";
    if (code.includes("SELECT") || code.includes("FROM")) return "sql";

    return "text";
  }

  // Generate title from code content
  generateTitle(code, language) {
    const lines = code.split("\n");
    const firstLine = lines[0].trim();

    // Try to extract function name or meaningful identifier
    if (firstLine.includes("function")) {
      const match = firstLine.match(/function\s+(\w+)/);
      if (match) return `${match[1]}() - ${language}`;
    }

    if (firstLine.includes("def ")) {
      const match = firstLine.match(/def\s+(\w+)/);
      if (match) return `${match[1]}() - ${language}`;
    }

    if (firstLine.includes("class ")) {
      const match = firstLine.match(/class\s+(\w+)/);
      if (match) return `${match[1]} Class - ${language}`;
    }

    // Fallback to truncated first line
    const title =
      firstLine.length > 30 ? firstLine.substring(0, 30) + "..." : firstLine;
    return title || `${language} Snippet`;
  }

  // Send snippet to background script
  // Send snippet to background script with collection selection
  sendSnippetToBackground(snippetData) {
    // First, get available collections
    chrome.runtime.sendMessage(
      { action: "getCollections" },
      (collectionsResponse) => {
        if (chrome.runtime.lastError) {
          console.error("Error getting collections:", chrome.runtime.lastError);
          this.showErrorMessage();
          return;
        }

        const collections = collectionsResponse?.collections || [];

        // Show collection selection modal
        this.showCollectionSelectionModal(snippetData, collections);
      }
    );
  }

  showCollectionSelectionModal(snippetData, collections) {
    console.log("Showing cyberpunk collection modal with data:", snippetData);

    // Remove existing modal if any
    const existingModal = document.querySelector(".snippet-collection-modal");
    if (existingModal) {
      console.log("Removing existing modal");
      existingModal.remove();
    }

    // Add cyberpunk CSS if not already added
    this.addCyberpunkStyles();

    // Create modal
    const modal = document.createElement("div");
    modal.className = "snippet-collection-modal cyberpunk-modal";
    modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.9);
    backdrop-filter: blur(5px);
    z-index: 10002;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: modalFadeIn 0.3s ease-out;
  `;

    const modalContent = document.createElement("div");
    modalContent.className = "cyberpunk-modal-content";
    modalContent.style.cssText = `
    background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
    border: 2px solid #00ffff;
    border-radius: 12px;
    padding: 30px;
    max-width: 500px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 
      0 0 30px rgba(0, 255, 255, 0.3),
      inset 0 0 20px rgba(0, 255, 255, 0.1);
    position: relative;
    animation: modalSlideIn 0.4s ease-out;
  `;

    modalContent.innerHTML = `
    <div class="cyberpunk-header">
      <h3 class="cyberpunk-title">
        <span class="glitch-text">SAVE CODE SNIPPET</span>
        <div class="title-underline"></div>
      </h3>
    </div>
    
    <div class="cyberpunk-form">
      <div class="input-group">
        <label class="cyberpunk-label">
          <span class="label-icon">📝</span>
          TITLE
        </label>
        <input type="text" id="snippet-title" value="${this.escapeHtml(
          snippetData.title
        )}" 
               class="cyberpunk-input" placeholder="Enter snippet title...">
        <div class="input-glow"></div>
      </div>
      
      <div class="input-group">
        <label class="cyberpunk-label">
          <span class="label-icon">📁</span>
          COLLECTION
        </label>
        <select id="snippet-collection" class="cyberpunk-select">
          <option value="">No Collection (Save to Library)</option>
          ${collections
            .map(
              (col) =>
                `<option value="${col.id}">${this.escapeHtml(
                  col.name
                )}</option>`
            )
            .join("")}
        </select>
        <div class="input-glow"></div>
      </div>
      
      <div class="input-group">
        <label class="cyberpunk-label">
          <span class="label-icon">⚡</span>
          LANGUAGE
        </label>
        <input type="text" id="snippet-language" value="${this.escapeHtml(
          snippetData.language
        )}" 
               class="cyberpunk-input" placeholder="e.g., javascript, python...">
        <div class="input-glow"></div>
      </div>
      
      <div class="input-group">
        <label class="cyberpunk-label">
          <span class="label-icon">👁️</span>
          PREVIEW
        </label>
        <div class="cyberpunk-preview">
  <pre class="code-preview">${this.escapeHtml(
    this.cleanCodeForPreview(snippetData.code)
  )}</pre>
</div>
      </div>
    </div>
    
    <div class="cyberpunk-actions">
      <button id="cancel-snippet" class="cyberpunk-btn cyberpunk-btn-secondary">
        <span class="btn-text">CANCEL</span>
        <div class="btn-glow"></div>
      </button>
      <button id="save-snippet" class="cyberpunk-btn cyberpunk-btn-primary">
        <span class="btn-text">💾 SAVE SNIPPET</span>
        <div class="btn-glow"></div>
      </button>
    </div>
    
    <div class="modal-corners">
      <div class="corner corner-tl"></div>
      <div class="corner corner-tr"></div>
      <div class="corner corner-bl"></div>
      <div class="corner corner-br"></div>
    </div>
  `;

    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    console.log("Cyberpunk modal created and added to DOM");

    // Event listeners with enhanced logging
    document.getElementById("cancel-snippet").addEventListener("click", () => {
      console.log("Cancel button clicked");
      modal.remove();
    });

    document.getElementById("save-snippet").addEventListener("click", () => {
      console.log("Save button clicked");

      const title = document.getElementById("snippet-title").value.trim();
      const collectionId = document.getElementById("snippet-collection").value;
      console.log(
        "🔍 FORM COLLECTION ID:",
        collectionId,
        "Type:",
        typeof collectionId
      );

      // Ensure it's not empty string
      const finalCollectionId =
        collectionId && collectionId.trim() !== "" ? collectionId : null;
      console.log("🔍 FINAL COLLECTION ID:", finalCollectionId);
      const language = document.getElementById("snippet-language").value.trim();

      console.log("Form values:", { title, collectionId, language });

      if (!title) {
        this.showCyberpunkAlert("Please enter a title for the snippet");
        return;
      }

      // Update snippet data
      const finalSnippetData = {
        ...snippetData,
        title: title,
        language: language || snippetData.language,
        collection_id: finalCollectionId, // ← USE finalCollectionId
      };

      // ADD DEBUG LOGGING
      console.log("🔍 COLLECTION DEBUG IN CONTENT SCRIPT:");
      console.log("   - collectionId from form:", collectionId);
      console.log("   - snippetData.collection_id:", snippetData.collection_id);
      console.log(
        "   - finalSnippetData.collection_id:",
        finalSnippetData.collection_id
      );

      console.log("Final snippet data:", finalSnippetData);

      const self = this; // ← ADD THIS LINE

      // Send to background
      // Send to background
      try {
        chrome.runtime.sendMessage(
          {
            action: "SAVE_SNIPPET",
            snippet: finalSnippetData,
          },
          function (response) {
            console.log("🔵 Snippet save response received:", response);

            if (chrome.runtime.lastError) {
              console.error(
                "❌ Extension context error:",
                chrome.runtime.lastError.message
              );

              if (
                chrome.runtime.lastError.message.includes(
                  "Extension context invalidated"
                )
              ) {
                alert(
                  "Extension was updated. Please refresh the page and try again."
                );
                return;
              }
            }

            if (!response) {
              console.error("🔴 No response received from background script");
              self.showErrorMessage(); // ← USE self INSTEAD OF this
              return;
            }

            if (response.success) {
              console.log("🔵 Snippet saved successfully");
              self.trackSaveFlow("MODAL_SAVE_SUCCESS", {
                response: response,
              });
              console.log(
                "🔵 SUCCESS MESSAGE - Now showing success notification after modal save"
              );
              self.showSuccessMessage(); // ← USE self INSTEAD OF this

              // Find and remove the modal
              const modalToClose = document.querySelector(
                ".snippet-collection-modal"
              );
              if (modalToClose) {
                console.log("🔵 Closing modal after successful save");
                modalToClose.remove();
              } else {
                console.log("⚠️ Modal not found to close");
              }
            } else {
              console.error("🔴 Snippet save failed:", response);
              self.showErrorMessage(); // ← USE self INSTEAD OF this
            }
          }
        );
      } catch (error) {
        console.error("❌ Failed to send message to background:", error);
        alert("Extension error. Please refresh the page and try again.");
      }
    });

    // Close modal when clicking outside
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        console.log("Modal backdrop clicked, closing modal");
        modal.remove();
      }
    });

    // Focus on title input with delay
    setTimeout(() => {
      const titleInput = document.getElementById("snippet-title");
      if (titleInput) {
        titleInput.focus();
        titleInput.select();
        console.log("Title input focused");
      }
    }, 100);
  }
  // Add cyberpunk styles to the page
  addCyberpunkStyles() {
    if (document.querySelector("#cyberpunk-modal-styles")) {
      return; // Already added
    }

    const style = document.createElement("style");
    style.id = "cyberpunk-modal-styles";
    style.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
    
    @keyframes modalFadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    
    @keyframes modalSlideIn {
      from { transform: translateY(-50px) scale(0.9); opacity: 0; }
      to { transform: translateY(0) scale(1); opacity: 1; }
    }
    
    @keyframes glitch {
      0% { text-shadow: 0.05em 0 0 #00ffff, -0.05em -0.025em 0 #ff00ff, 0.025em 0.05em 0 #ffff00; }
      15% { text-shadow: 0.05em 0 0 #00ffff, -0.05em -0.025em 0 #ff00ff, 0.025em 0.05em 0 #ffff00; }
      16% { text-shadow: -0.05em -0.025em 0 #00ffff, 0.025em 0.025em 0 #ff00ff, -0.05em -0.05em 0 #ffff00; }
      49% { text-shadow: -0.05em -0.025em 0 #00ffff, 0.025em 0.025em 0 #ff00ff, -0.05em -0.05em 0 #ffff00; }
      50% { text-shadow: 0.025em 0.05em 0 #00ffff, 0.05em 0 0 #ff00ff, 0 -0.05em 0 #ffff00; }
      99% { text-shadow: 0.025em 0.05em 0 #00ffff, 0.05em 0 0 #ff00ff, 0 -0.05em 0 #ffff00; }
      100% { text-shadow: -0.025em 0 0 #00ffff, -0.025em -0.025em 0 #ff00ff, -0.025em -0.05em 0 #ffff00; }
    }
    
    @keyframes neonGlow {
      0%, 100% { box-shadow: 0 0 5px #00ffff, 0 0 10px #00ffff, 0 0 15px #00ffff; }
      50% { box-shadow: 0 0 10px #00ffff, 0 0 20px #00ffff, 0 0 30px #00ffff; }
    }
    
    .cyberpunk-modal-content {
      font-family: 'Orbitron', monospace;
      color: #00ffff;
    }
    
    .cyberpunk-header {
      text-align: center;
      margin-bottom: 25px;
    }
    
    .cyberpunk-title {
      margin: 0;
      font-size: 24px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 2px;
    }
    
    .glitch-text {
      animation: glitch 2s infinite;
    }
    
    .title-underline {
      height: 2px;
      background: linear-gradient(90deg, transparent, #00ffff, transparent);
      margin: 10px auto;
      width: 80%;
      animation: neonGlow 2s infinite alternate;
    }
    
    .cyberpunk-form {
      margin-bottom: 25px;
    }
    
    .input-group {
      margin-bottom: 20px;
      position: relative;
    }
    
    .cyberpunk-label {
      display: flex;
      align-items: center;
      margin-bottom: 8px;
      font-weight: 700;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #00ffff;
    }
    
    .label-icon {
      margin-right: 8px;
      font-size: 14px;
    }
    
    .cyberpunk-input, .cyberpunk-select {
      width: 100%;
      padding: 12px 15px;
      background: rgba(0, 0, 0, 0.7);
      border: 1px solid #00ffff;
      border-radius: 6px;
      color: #00ffff;
      font-family: 'Orbitron', monospace;
      font-size: 14px;
      transition: all 0.3s ease;
      position: relative;
      z-index: 2;
    }
    
    .cyberpunk-input:focus, .cyberpunk-select:focus {
      outline: none;
      border-color: #ff00ff;
      box-shadow: 0 0 15px rgba(255, 0, 255, 0.5);
      background: rgba(0, 0, 0, 0.9);
    }
    
    .cyberpunk-input::placeholder {
      color: rgba(0, 255, 255, 0.5);
    }
    
    .input-glow {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(45deg, transparent, rgba(0, 255, 255, 0.1), transparent);
      border-radius: 6px;
      opacity: 0;
      transition: opacity 0.3s ease;
      pointer-events: none;
    }
    
    .cyberpunk-input:focus + .input-glow,
    .cyberpunk-select:focus + .input-glow {
      opacity: 1;
    }
    
    .cyberpunk-preview {
      background: rgba(0, 0, 0, 0.8);
      border: 1px solid #00ffff;
      border-radius: 6px;
      padding: 15px;
      position: relative;
      overflow: hidden;
    }
    
   .code-preview {
  margin: 0;
  color: #00ff00;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.3;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre;
  word-break: normal;
  overflow-x: auto;
  tab-size: 2;
}
    
    .cyberpunk-actions {
      display: flex;
      gap: 15px;
      justify-content: flex-end;
    }
    
    .cyberpunk-btn {
      position: relative;
      padding: 12px 24px;
      border: none;
      border-radius: 6px;
      font-family: 'Orbitron', monospace;
      font-weight: 700;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1px;
      cursor: pointer;
      transition: all 0.3s ease;
      overflow: hidden;
      min-width: 120px;
    }
    
    .cyberpunk-btn-primary {
      background: linear-gradient(45deg, #ff00ff, #00ffff);
      color: #000;
    }
    
    .cyberpunk-btn-secondary {
      background: rgba(0, 0, 0, 0.7);
      border: 1px solid #00ffff;
      color: #00ffff;
    }
    
    .cyberpunk-btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(0, 255, 255, 0.4);
    }
    
        .cyberpunk-btn-primary:hover {
      box-shadow: 0 5px 15px rgba(255, 0, 255, 0.6);
    }
    
    .btn-text {
      position: relative;
      z-index: 2;
    }
    
    .btn-glow {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(45deg, transparent, rgba(255, 255, 255, 0.2), transparent);
      opacity: 0;
      transition: opacity 0.3s ease;
    }
    
    .cyberpunk-btn:hover .btn-glow {
      opacity: 1;
    }
    
    .modal-corners {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      pointer-events: none;
    }
    
    .corner {
      position: absolute;
      width: 20px;
      height: 20px;
      border: 2px solid #ff00ff;
    }
    
    .corner-tl {
      top: -2px;
      left: -2px;
      border-right: none;
      border-bottom: none;
    }
    
    .corner-tr {
      top: -2px;
      right: -2px;
      border-left: none;
      border-bottom: none;
    }
    
    .corner-bl {
      bottom: -2px;
      left: -2px;
      border-right: none;
      border-top: none;
    }
    
    .corner-br {
      bottom: -2px;
      right: -2px;
      border-left: none;
      border-top: none;
    }
    
    /* Scrollbar styling */
    .cyberpunk-modal-content::-webkit-scrollbar,
    .code-preview::-webkit-scrollbar {
      width: 8px;
    }
    
    .cyberpunk-modal-content::-webkit-scrollbar-track,
    .code-preview::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.3);
      border-radius: 4px;
    }
    
    .cyberpunk-modal-content::-webkit-scrollbar-thumb,
    .code-preview::-webkit-scrollbar-thumb {
      background: linear-gradient(45deg, #00ffff, #ff00ff);
      border-radius: 4px;
    }
    
    .cyberpunk-modal-content::-webkit-scrollbar-thumb:hover,
    .code-preview::-webkit-scrollbar-thumb:hover {
      background: linear-gradient(45deg, #ff00ff, #00ffff);
    }
    
    /* Mobile responsiveness */
    @media (max-width: 600px) {
      .cyberpunk-modal-content {
        padding: 20px;
        margin: 10px;
      }
      
      .cyberpunk-title {
        font-size: 18px;
      }
      
      .cyberpunk-actions {
        flex-direction: column;
      }
      
      .cyberpunk-btn {
        width: 100%;
      }
    }
  `;

    document.head.appendChild(style);
    console.log("Cyberpunk styles added to page");
  }

  // Add cyberpunk alert method
  showCyberpunkAlert(message) {
    console.log("Showing cyberpunk alert:", message);

    const alert = document.createElement("div");
    alert.className = "cyberpunk-alert";
    alert.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: linear-gradient(135deg, #ff0000, #ff6600);
    border: 2px solid #ffff00;
    border-radius: 8px;
    padding: 20px 30px;
    color: #fff;
    font-family: 'Orbitron', monospace;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    z-index: 10003;
    box-shadow: 0 0 30px rgba(255, 255, 0, 0.5);
    animation: alertPulse 0.5s ease-out;
  `;

    alert.textContent = message;

    // Add alert animation
    if (!document.querySelector("#cyberpunk-alert-styles")) {
      const alertStyle = document.createElement("style");
      alertStyle.id = "cyberpunk-alert-styles";
      alertStyle.textContent = `
      @keyframes alertPulse {
        0% { transform: translate(-50%, -50%) scale(0.8); opacity: 0; }
        50% { transform: translate(-50%, -50%) scale(1.1); }
        100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
      }
    `;
      document.head.appendChild(alertStyle);
    }

    document.body.appendChild(alert);

    setTimeout(() => {
      if (alert.parentNode) {
        alert.remove();
      }
    }, 3000);
  }

  // Add HTML escaping method for security
  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
  // Clean code by removing save buttons and other UI elements
  // Clean code by removing save buttons and other UI elements
  // Clean code by removing save buttons and other UI elements
  cleanCodeForPreview(code) {
    // Remove save button text that might be included
    let cleanCode = code.replace(/💾\s*Save/g, "");

    // Remove any button-like patterns
    cleanCode = cleanCode.replace(/💾/g, "");

    // Remove "Save" only if it appears at the end of a line or end of string
    cleanCode = cleanCode.replace(/\s*Save\s*$/gm, "");
    cleanCode = cleanCode.replace(/\s*Save\s*\n/g, "\n");

    // Remove any HTML button elements if they got included
    cleanCode = cleanCode.replace(/<button[^>]*>.*?<\/button>/gi, "");

    // DON'T replace multiple spaces - preserve formatting
    // Just trim the beginning and end
    cleanCode = cleanCode.trim();

    return cleanCode;
  }

  // Show success message
  showSuccessMessage() {
    this.showMessage("✅ Code snippet saved!", "#4CAF50");
  }

  // Show error message
  showErrorMessage() {
    this.showMessage("❌ Failed to save snippet", "#f44336");
  }

  // Show temporary message
  showMessage(text, color) {
    const existing = document.querySelector(".snippet-message");
    if (existing) existing.remove();

    const message = document.createElement("div");
    message.className = "snippet-message";
    message.textContent = text;
    message.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${color};
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            z-index: 10001;
            font-size: 14px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            animation: slideIn 0.3s ease-out;
        `;

    // Add CSS animation
    if (!document.querySelector("#snippet-animations")) {
      const style = document.createElement("style");
      style.id = "snippet-animations";
      style.textContent = `
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
            `;
      document.head.appendChild(style);
    }

    document.body.appendChild(message);

    setTimeout(() => {
      if (message.parentNode) {
        message.remove();
      }
    }, 3000);
  }

  // Create floating save button (always visible)
  createSaveButton() {
    const floatingBtn = document.createElement("div");
    floatingBtn.id = "snippet-floating-btn";
    floatingBtn.innerHTML = "💾";
    floatingBtn.title = "Open Code Snippet Manager";

    floatingBtn.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 50px;
            height: 50px;
            background: #007acc;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            z-index: 10000;
            font-size: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            transition: transform 0.2s;
        `;

    floatingBtn.addEventListener("click", () => {
      chrome.runtime.sendMessage({ type: "OPEN_POPUP" });
    });

    floatingBtn.addEventListener("mouseenter", () => {
      floatingBtn.style.transform = "scale(1.1)";
    });

    floatingBtn.addEventListener("mouseleave", () => {
      floatingBtn.style.transform = "scale(1)";
    });

    document.body.appendChild(floatingBtn);
  }
}

// Handle dynamic content (for SPAs) - Less aggressive
let detectorInstance = null;
let observerTimeout = null;
let initializationAttempts = 0;
const MAX_INIT_ATTEMPTS = 10;

// Enhanced initialization function
function initializeDetector() {
  initializationAttempts++;
  console.log(
    `Initialization attempt ${initializationAttempts}/${MAX_INIT_ATTEMPTS}`
  );

  detectorInstance = new CodeSnippetDetector();

  // Check if we found any code blocks
  setTimeout(() => {
    const codeElements = document.querySelectorAll(
      'pre, code, [class*="language-"], .hljs'
    );
    console.log(
      `Post-initialization check: found ${codeElements.length} potential code elements`
    );

    if (
      codeElements.length === 0 &&
      initializationAttempts < MAX_INIT_ATTEMPTS
    ) {
      console.log(`No code blocks found, retrying in 2 seconds...`);
      setTimeout(initializeDetector, 2000);
    } else if (codeElements.length > 0) {
      console.log(`Code blocks detected, re-running detection...`);
      detectorInstance.highlightCodeBlocks();
    }
  }, 1000);
}

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM loaded, initializing detector...");
    initializeDetector();
  });
} else {
  console.log("DOM already ready, initializing detector immediately...");
  initializeDetector();
}

const observer = new MutationObserver((mutations) => {
  // Clear existing timeout to debounce
  if (observerTimeout) {
    clearTimeout(observerTimeout);
  }

  // Only process if significant changes occurred
  let significantChange = false;
  mutations.forEach((mutation) => {
    if (mutation.addedNodes.length > 0) {
      // Check if any added nodes contain code elements
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === 1) {
          // Element node
          if (
            node.tagName === "PRE" ||
            node.tagName === "CODE" ||
            (node.querySelector &&
              (node.querySelector("pre") || node.querySelector("code")))
          ) {
            significantChange = true;
            console.log(
              "New code element detected via mutation observer:",
              node
            );
          }
        }
      });
    }
  });

  if (significantChange) {
    // Debounced re-scan
    observerTimeout = setTimeout(() => {
      if (detectorInstance) {
        console.log("Rescanning for new code blocks due to DOM changes...");
        detectorInstance.highlightCodeBlocks();
      }
    }, 1000);
  }
});

observer.observe(document.body, {
  childList: true,
  subtree: true,
});

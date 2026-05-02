const vscode = require("vscode");
const axios = require("axios");
const WebSocket = require("ws");

class CodeSnippetManager {
  constructor() {
    this.apiBaseUrl = "http://localhost:5000";
    this.ws = null;
    this.statusBar = null;
    this.isAuthenticated = false;
    this.user = null;
    this.snippets = [];
    this.collections = [];
    this.initializeWebSocket();
    this.setupStatusBar();
  }

  async activate(context) {
    console.log("Code Snippet Manager extension activated!");

    // Register commands
    const commands = [
      vscode.commands.registerCommand("codeSnippetManager.saveSnippet", () =>
        this.saveSelectedSnippet()
      ),
      vscode.commands.registerCommand("codeSnippetManager.insertSnippet", () =>
        this.showSnippetPicker()
      ),
      vscode.commands.registerCommand("codeSnippetManager.searchSnippets", () =>
        this.searchSnippets()
      ),
      vscode.commands.registerCommand(
        "codeSnippetManager.manageCollections",
        () => this.manageCollections()
      ),
      vscode.commands.registerCommand("codeSnippetManager.syncSnippets", () =>
        this.syncWithServer()
      ),
      vscode.commands.registerCommand("codeSnippetManager.login", () =>
        this.showLoginPanel()
      ),
      vscode.commands.registerCommand(
        "codeSnippetManager.createFromSelection",
        () => this.createSnippetFromSelection()
      ),
      vscode.commands.registerCommand("codeSnippetManager.shareSnippet", () =>
        this.shareSnippet()
      ),
      vscode.commands.registerCommand("codeSnippetManager.viewAnalytics", () =>
        this.showAnalytics()
      ),
    ];

    // Register tree data provider for snippets explorer
    const snippetProvider = new SnippetTreeProvider(this);
    vscode.window.createTreeView("codeSnippetManager.snippetExplorer", {
      treeDataProvider: snippetProvider,
      showCollapseAll: true,
    });

    // Register hover provider for snippet preview
    const hoverProvider = new SnippetHoverProvider(this);
    vscode.languages.registerHoverProvider("*", hoverProvider);

    // Register completion provider for quick snippet insertion
    const completionProvider = new SnippetCompletionProvider(this);
    vscode.languages.registerCompletionItemProvider(
      "*",
      completionProvider,
      "!",
      "@"
    );

    context.subscriptions.push(
      ...commands,
      snippetProvider,
      hoverProvider,
      completionProvider
    );

    // Auto-login if credentials exist
    await this.attemptAutoLogin();
  }

  setupStatusBar() {
    this.statusBar = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100
    );
    this.statusBar.command = "codeSnippetManager.syncSnippets";
    this.updateStatusBar("disconnected");
    this.statusBar.show();
  }

  updateStatusBar(status) {
    const statusIcons = {
      connected: "$(cloud) Snippets: Connected",
      syncing: "$(sync~spin) Snippets: Syncing...",
      disconnected: "$(cloud-offline) Snippets: Offline",
      error: "$(error) Snippets: Error",
    };
    this.statusBar.text = statusIcons[status] || statusIcons.disconnected;
  }

  initializeWebSocket() {
    try {
      this.ws = new WebSocket("ws://localhost:5000/ws");

      this.ws.on("open", () => {
        console.log("WebSocket connected");
        this.updateStatusBar("connected");
      });

      this.ws.on("message", (data) => {
        const message = JSON.parse(data.toString());
        this.handleWebSocketMessage(message);
      });

      this.ws.on("close", () => {
        console.log("WebSocket disconnected");
        this.updateStatusBar("disconnected");
        // Reconnect after 5 seconds
        setTimeout(() => this.initializeWebSocket(), 5000);
      });

      this.ws.on("error", (error) => {
        console.error("WebSocket error:", error);
        this.updateStatusBar("error");
      });
    } catch (error) {
      console.error("Failed to initialize WebSocket:", error);
      this.updateStatusBar("error");
    }
  }

  handleWebSocketMessage(message) {
    switch (message.type) {
      case "snippet_updated":
        this.updateSnippetInCache(message.data);
        break;
      case "snippet_deleted":
        this.removeSnippetFromCache(message.data.id);
        break;
      case "collection_updated":
        this.updateCollectionInCache(message.data);
        break;
      case "sync_complete":
        this.updateStatusBar("connected");
        vscode.window.showInformationMessage(
          "Snippets synchronized successfully!"
        );
        break;
    }
  }

  async attemptAutoLogin() {
    const config = vscode.workspace.getConfiguration("codeSnippetManager");
    const savedToken = await this.getSecretToken();

    if (savedToken) {
      try {
        const response = await axios.get(`${this.apiBaseUrl}/api/auth/verify`, {
          headers: { Authorization: `Bearer ${savedToken}` },
        });

        if (response.data.success) {
          this.isAuthenticated = true;
          this.user = response.data.user;
          await this.loadUserSnippets();
          vscode.window.showInformationMessage(
            `Welcome back, ${this.user.name}!`
          );
        }
      } catch (error) {
        console.error("Auto-login failed:", error);
        await this.clearSecretToken();
      }
    }
  }

  async showLoginPanel() {
    const panel = vscode.window.createWebviewPanel(
      "snippetLogin",
      "Code Snippet Manager - Login",
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    );

    panel.webview.html = this.getLoginHtml();

    panel.webview.onDidReceiveMessage(async (message) => {
      switch (message.command) {
        case "login":
          await this.handleLogin(message.data, panel);
          break;
        case "register":
          await this.handleRegister(message.data, panel);
          break;
      }
    });
  }

  async handleLogin(credentials, panel) {
    try {
      const response = await axios.post(
        `${this.apiBaseUrl}/api/auth/login`,
        credentials
      );

      if (response.data.success) {
        this.isAuthenticated = true;
        this.user = response.data.user;
        await this.saveSecretToken(response.data.token);
        await this.loadUserSnippets();

        panel.dispose();
        vscode.window.showInformationMessage(
          `Login successful! Welcome, ${this.user.name}!`
        );
      } else {
        panel.webview.postMessage({
          command: "loginError",
          message: response.data.message,
        });
      }
    } catch (error) {
      panel.webview.postMessage({
        command: "loginError",
        message: "Login failed. Please check your credentials.",
      });
    }
  }

  async saveSelectedSnippet() {
    if (!this.isAuthenticated) {
      vscode.window.showWarningMessage("Please login first to save snippets.");
      return;
    }

    const editor = vscode.window.activeTextEditor;
    if (!editor || !editor.selection || editor.selection.isEmpty) {
      vscode.window.showWarningMessage(
        "Please select some code to save as a snippet."
      );
      return;
    }

    const selectedText = editor.document.getText(editor.selection);
    const language = editor.document.languageId;
    const fileName = editor.document.fileName;

    const title = await vscode.window.showInputBox({
      prompt: "Enter a title for your snippet",
      placeHolder: "My awesome snippet...",
    });

    if (!title) return;

    const description = await vscode.window.showInputBox({
      prompt: "Enter a description (optional)",
      placeHolder: "What does this code do?",
    });

    const tags = await vscode.window.showInputBox({
      prompt: "Enter tags (comma-separated, optional)",
      placeHolder: "react, hooks, api...",
    });

    const collection = await this.selectCollection();

    try {
      this.updateStatusBar("syncing");

      const snippetData = {
        title,
        description: description || "",
        code: selectedText,
        language,
        tags: tags ? tags.split(",").map((t) => t.trim()) : [],
        source: fileName,
        collection_id: collection?.id,
      };

      const response = await axios.post(
        `${this.apiBaseUrl}/api/snippets`,
        snippetData,
        {
          headers: { Authorization: `Bearer ${await this.getSecretToken()}` },
        }
      );

      if (response.data.success) {
        this.snippets.push(response.data.snippet);
        vscode.window.showInformationMessage("Snippet saved successfully!");
        this.updateStatusBar("connected");
      }
    } catch (error) {
      vscode.window.showErrorMessage(
        "Failed to save snippet. Please try again."
      );
      this.updateStatusBar("error");
    }
  }

  async showSnippetPicker() {
    if (!this.isAuthenticated) {
      vscode.window.showWarningMessage(
        "Please login first to access your snippets."
      );
      return;
    }

    const items = this.snippets.map((snippet) => ({
      label: snippet.title,
      description: snippet.language,
      detail: snippet.description,
      snippet,
    }));

    const selected = await vscode.window.showQuickPick(items, {
      placeHolder: "Search and select a snippet to insert...",
      matchOnDescription: true,
      matchOnDetail: true,
    });

    if (selected) {
      await this.insertSnippet(selected.snippet);
    }
  }

  async insertSnippet(snippet) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage("No active editor found.");
      return;
    }

    const position = editor.selection.active;
    await editor.edit((editBuilder) => {
      editBuilder.insert(position, snippet.code);
    });

    // Track snippet usage
    this.trackSnippetUsage(snippet.id);

    vscode.window.showInformationMessage(`Inserted snippet: ${snippet.title}`);
  }

  async searchSnippets() {
    if (!this.isAuthenticated) {
      vscode.window.showWarningMessage(
        "Please login first to search snippets."
      );
      return;
    }

    const query = await vscode.window.showInputBox({
      prompt: "Search your snippets...",
      placeHolder: "Enter keywords, tags, or language...",
    });

    if (!query) return;

    try {
      const response = await axios.get(
        `${this.apiBaseUrl}/api/snippets/search`,
        {
          params: { q: query },
          headers: { Authorization: `Bearer ${await this.getSecretToken()}` },
        }
      );

      const results = response.data.snippets;

      if (results.length === 0) {
        vscode.window.showInformationMessage(
          "No snippets found for your search."
        );
        return;
      }

      const items = results.map((snippet) => ({
        label: snippet.title,
        description: `${snippet.language} • ${snippet.tags.join(", ")}`,
        detail: snippet.description,
        snippet,
      }));

      const selected = await vscode.window.showQuickPick(items, {
        placeHolder: `Found ${results.length} snippets. Select one to insert...`,
      });

      if (selected) {
        await this.insertSnippet(selected.snippet);
      }
    } catch (error) {
      vscode.window.showErrorMessage("Search failed. Please try again.");
    }
  }

  async selectCollection() {
    if (this.collections.length === 0) {
      return null;
    }

    const items = [
      {
        label: "$(file) No Collection",
        description: "Save without collection",
        collection: null,
      },
      ...this.collections.map((collection) => ({
        label: `$(folder) ${collection.name}`,
        description: collection.description,
        collection,
      })),
    ];

    const selected = await vscode.window.showQuickPick(items, {
      placeHolder: "Select a collection (optional)...",
    });

    return selected?.collection;
  }

  async loadUserSnippets() {
    try {
      const [snippetsResponse, collectionsResponse] = await Promise.all([
        axios.get(`${this.apiBaseUrl}/api/snippets`, {
          headers: { Authorization: `Bearer ${await this.getSecretToken()}` },
        }),
        axios.get(`${this.apiBaseUrl}/api/collections`, {
          headers: { Authorization: `Bearer ${await this.getSecretToken()}` },
        }),
      ]);

      this.snippets = snippetsResponse.data.snippets;
      this.collections = collectionsResponse.data.collections;
    } catch (error) {
      console.error("Failed to load user data:", error);
    }
  }

  async trackSnippetUsage(snippetId) {
    try {
      await axios.post(
        `${this.apiBaseUrl}/api/snippets/${snippetId}/usage`,
        {},
        {
          headers: { Authorization: `Bearer ${await this.getSecretToken()}` },
        }
      );
    } catch (error) {
      console.error("Failed to track snippet usage:", error);
    }
  }

  getLoginHtml() {
    return `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Login - Code Snippet Manager</title>
            <style>
                body {
                    font-family: var(--vscode-font-family);
                    background: var(--vscode-editor-background);
                    color: var(--vscode-editor-foreground);
                    padding: 20px;
                    margin: 0;
                }
                .container {
                    max-width: 400px;
                    margin: 50px auto;
                    padding: 30px;
                    border: 1px solid var(--vscode-widget-border);
                    border-radius: 8px;
                    background: var(--vscode-editor-widget-background);
                }
                .form-group {
                    margin-bottom: 20px;
                }
                label {
                    display: block;
                    margin-bottom: 8px;
                    font-weight: 600;
                }
                input {
                    width: 100%;
                    padding: 10px;
                    border: 1px solid var(--vscode-input-border);
                    background: var(--vscode-input-background);
                    color: var(--vscode-input-foreground);
                    border-radius: 4px;
                    font-size: 14px;
                }
                button {
                    width: 100%;
                    padding: 12px;
                    margin: 10px 0;
                    border: none;
                    border-radius: 4px;
                    font-size: 14px;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .btn-primary {
                    background: var(--vscode-button-background);
                    color: var(--vscode-button-foreground);
                }
                .btn-secondary {
                    background: var(--vscode-button-secondaryBackground);
                    color: var(--vscode-button-secondaryForeground);
                }
                button:hover {
                    opacity: 0.9;
                }
                .error {
                    color: var(--vscode-errorForeground);
                    margin-top: 10px;
                    padding: 10px;
                    border-radius: 4px;
                    background: var(--vscode-inputValidation-errorBackground);
                    border: 1px solid var(--vscode-inputValidation-errorBorder);
                }
                .title {
                    text-align: center;
                    margin-bottom: 30px;
                    font-size: 24px;
                    font-weight: 600;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="title">Code Snippet Manager</h1>
                <form id="loginForm">
                    <div class="form-group">
                        <label for="email">Email:</label>
                        <input type="email" id="email" required>
                    </div>
                    <div class="form-group">
                        <label for="password">Password:</label>
                        <input type="password" id="password" required>
                    </div>
                    <button type="submit" class="btn-primary">Login</button>
                    <button type="button" id="registerBtn" class="btn-secondary">Create Account</button>
                </form>
                <div id="error" class="error" style="display: none;"></div>
            </div>

            <script>
                const vscode = acquireVsCodeApi();
                
                document.getElementById('loginForm').addEventListener('submit', (e) => {
                    e.preventDefault();
                    const email = document.getElementById('email').value;
                    const password = document.getElementById('password').value;
                    
                    vscode.postMessage({
                        command: 'login',
                        data: { email, password }
                    });
                });

                document.getElementById('registerBtn').addEventListener('click', () => {
                    const email = document.getElementById('email').value;
                    const password = document.getElementById('password').value;
                    
                    vscode.postMessage({
                        command: 'register',
                        data: { email, password }
                    });
                });

                window.addEventListener('message', event => {
                    const message = event.data;
                    if (message.command === 'loginError') {
                        const errorDiv = document.getElementById('error');
                        errorDiv.textContent = message.message;
                        errorDiv.style.display = 'block';
                    }
                });
            </script>
        </body>
        </html>
        `;
  }

  async saveSecretToken(token) {
    // Use VS Code's secret storage for secure token storage
    const context = vscode.extensions.getExtension(
      "your-publisher.code-snippet-manager"
    );
    if (context) {
      await context.exports.globalState.update("authToken", token);
    }
  }

  async getSecretToken() {
    const context = vscode.extensions.getExtension(
      "your-publisher.code-snippet-manager"
    );
    return context ? context.exports.globalState.get("authToken") : null;
  }

  async clearSecretToken() {
    const context = vscode.extensions.getExtension(
      "your-publisher.code-snippet-manager"
    );
    if (context) {
      await context.exports.globalState.update("authToken", undefined);
    }
  }
}

// Tree Data Provider for Snippets Explorer
class SnippetTreeProvider {
  constructor(manager) {
    this.manager = manager;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
  }

  refresh() {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element) {
    return element;
  }

  async getChildren(element) {
    if (!this.manager.isAuthenticated) {
      return [new vscode.TreeItem("Please login to view snippets")];
    }

    if (!element) {
      // Root level - show collections and uncategorized snippets
      const items = [];

      // Add collections
      this.manager.collections.forEach((collection) => {
        const item = new vscode.TreeItem(
          collection.name,
          vscode.TreeItemCollapsibleState.Collapsed
        );
        item.iconPath = new vscode.ThemeIcon("folder");
        item.contextValue = "collection";
        item.collection = collection;
        items.push(item);
      });

      // Add uncategorized snippets
      const uncategorized = this.manager.snippets.filter(
        (s) => !s.collection_id
      );
      uncategorized.forEach((snippet) => {
        const item = new vscode.TreeItem(
          snippet.title,
          vscode.TreeItemCollapsibleState.None
        );
        item.iconPath = new vscode.ThemeIcon("code");
        item.contextValue = "snippet";
        item.snippet = snippet;
        item.command = {
          command: "codeSnippetManager.insertSnippet",
          title: "Insert Snippet",
          arguments: [snippet],
        };
        items.push(item);
      });

      return items;
    } else if (element.collection) {
      // Show snippets in collection
      const collectionSnippets = this.manager.snippets.filter(
        (s) => s.collection_id === element.collection.id
      );
      return collectionSnippets.map((snippet) => {
        const item = new vscode.TreeItem(
          snippet.title,
          vscode.TreeItemCollapsibleState.None
        );
        item.iconPath = new vscode.ThemeIcon("code");
        item.contextValue = "snippet";
        item.snippet = snippet;
        item.command = {
          command: "codeSnippetManager.insertSnippet",
          title: "Insert Snippet",
          arguments: [snippet],
        };
        return item;
      });
    }

    return [];
  }
}

// Hover Provider for Snippet Preview
class SnippetHoverProvider {
  constructor(manager) {
    this.manager = manager;
  }

  provideHover(document, position, token) {
    // Provide hover information for snippet-related content
    const range = document.getWordRangeAtPosition(position);
    if (!range) return;

    const word = document.getText(range);
    const snippet = this.manager.snippets.find((s) =>
      s.title.toLowerCase().includes(word.toLowerCase())
    );

    if (snippet) {
      const markdown = new vscode.MarkdownString();
      markdown.appendCodeblock(snippet.code, snippet.language);
      markdown.appendText(`\n**${snippet.title}**\n${snippet.description}`);
      return new vscode.Hover(markdown);
    }
  }
}

// Completion Provider for Quick Snippet Insertion
class SnippetCompletionProvider {
  constructor(manager) {
    this.manager = manager;
  }

  provideCompletionItems(document, position, token, context) {
    const line = document.lineAt(position);
    const lineText = line.text.substring(0, position.character);

    // Trigger on !snippet or @snippet
    if (lineText.endsWith("!snippet") || lineText.endsWith("@snippet")) {
      return this.manager.snippets.map((snippet) => {
        const item = new vscode.CompletionItem(
          snippet.title,
          vscode.CompletionItemKind.Snippet
        );
        item.insertText = snippet.code;
        item.documentation = snippet.description;
        item.detail = `${snippet.language} • ${snippet.tags.join(", ")}`;
        return item;
      });
    }

    return [];
  }
}

// Extension activation
function activate(context) {
  const manager = new CodeSnippetManager();
  manager.activate(context);
}

function deactivate() {
  // Cleanup when extension is deactivated
}

module.exports = {
  activate,
  deactivate,
};

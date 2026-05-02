// Syntax highlighting and utility functions for Chrome Extension

/**
 * Language detection based on code patterns and context
 */
class LanguageDetector {
  static patterns = {
    javascript: [
      /\b(function|const|let|var|=&gt;|async|await)\b/,
      /console\.(log|error|warn)/,
      /document\.(getElementById|querySelector)/,
      /\$\(/,
      /\.addEventListener/
    ],
    python: [
      /\b(def|import|from|class|if __name__|print)\b/,
      /:\s*$\n\s+/m,
      /#.*$/m,
      /\bself\b/,
      /\.py$/
    ],
    css: [
      /\{[^}]*\}/,
      /\.[a-zA-Z-]+\s*\{/,
      /#[a-zA-Z-]+\s*\{/,
      /@media|@import|@keyframes/,
      /:\s*[^;]+;/
    ],
    html: [
      /&lt;\/?\w+[^&gt;]*&gt;/,
      /&lt;!DOCTYPE/i,
      /&lt;html|&lt;head|&lt;body/i,
      /class=|id=/
    ],
    java: [
      /\b(public|private|protected|class|interface)\b/,
      /System\.out\.print/,
      /\.java$/,
      /\bString\[\]/,
      /import java\./
    ],
    cpp: [
      /#include|#define/,
      /std::|cout|cin/,
      /\.(cpp|hpp|cc)$/,
      /\bnamespace\b/,
      /::/
    ],
    sql: [
      /\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b/i,
      /\bJOIN\b/i,
      /\bGROUP BY|ORDER BY\b/i
    ],
    json: [
      /^\s*[\{\[]/,
      /:\s*[\{\[\"]|,\s*$/m,
      /^\s*[\}\]]/m
    ],
    bash: [
      /^#!\/bin\/(bash|sh)/,
      /\$\w+|\$\{/,
      /\|\s*\w+/,
      /&&|\|\|/,
      /\.(sh|bash)$/
    ],
    php: [
      /&lt;\?php/,
      /\$\w+/,
      /echo|print/,
      /-&gt;|\:\:/,
      /\.php$/
    ]
  };

  static detectLanguage(code, context = {}) {
    const { url = '', filename = '', element = null } = context;
    
    // Check file extension first
    const extMatch = filename.match(/\.([^.]+)$/);
    if (extMatch) {
      const ext = extMatch[1].toLowerCase();
      const extMap = {
        js: 'javascript', py: 'python', css: 'css', html: 'html',
        java: 'java', cpp: 'cpp', c: 'cpp', sql: 'sql',
        json: 'json', sh: 'bash', php: 'php', ts: 'typescript'
      };
      if (extMap[ext]) return extMap[ext];
    }

    // Check URL context
    if (url.includes('github.com')) {
      const pathMatch = url.match(/\.([^./]+)(?:#|$)/);
      if (pathMatch) {
        const ext = pathMatch[1].toLowerCase();
        if (ext === 'js') return 'javascript';
        if (ext === 'py') return 'python';
        if (ext === 'css') return 'css';
      }
    }

    // Stack Overflow context
    if (url.includes('stackoverflow.com')) {
      const tags = document.querySelectorAll('.post-tag');
      for (let tag of tags) {
        if (tag.textContent.includes('javascript')) return 'javascript';
        if (tag.textContent.includes('python')) return 'python';
        if (tag.textContent.includes('java')) return 'java';
      }
    }

    // Pattern-based detection
    const scores = {};
    for (const [lang, patterns] of Object.entries(this.patterns)) {
      scores[lang] = 0;
      for (const pattern of patterns) {
        if (pattern.test(code)) {
          scores[lang]++;
        }
      }
    }

    // Find language with highest score
    const detected = Object.entries(scores)
      .filter(([_, score]) => score > 0)
      .sort(([, a], [, b]) => b - a)[0];

    return detected ? detected[0] : 'text';
  }
}

/**
 * Syntax highlighter for code snippets
 */
class SyntaxHighlighter {
  static keywords = {
    javascript: ['function', 'const', 'let', 'var', 'if', 'else', 'for', 'while', 'return', 'class', 'async', 'await'],
    python: ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'import', 'from', 'return', 'try', 'except'],
    css: ['color', 'background', 'margin', 'padding', 'border', 'width', 'height', 'font-size', 'display'],
    html: ['div', 'span', 'p', 'h1', 'h2', 'h3', 'body', 'head', 'title', 'script', 'style'],
    java: ['public', 'private', 'protected', 'class', 'interface', 'extends', 'implements', 'static', 'final'],
    sql: ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'JOIN']
  };

  static highlight(code, language) {
    if (!code || language === 'text') return this.escapeHtml(code);

    let highlighted = this.escapeHtml(code);
    const keywords = this.keywords[language] || [];

    // Highlight keywords
    for (const keyword of keywords) {
      const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
      highlighted = highlighted.replace(regex, `<span class="keyword">${keyword}</span>`);
    }

    // Highlight strings
    highlighted = highlighted.replace(/(["'])((?:\\.|(?!\1)[^\\])*?)\1/g, 
      '<span class="string">$1$2$1</span>');

    // Highlight comments
    if (language === 'javascript' || language === 'java' || language === 'css') {
      highlighted = highlighted.replace(/\/\*[\s\S]*?\*\//g, '<span class="comment">$&</span>');
      highlighted = highlighted.replace(/\/\/.*$/gm, '<span class="comment">$&</span>');
    } else if (language === 'python' || language === 'bash') {
      highlighted = highlighted.replace(/#.*$/gm, '<span class="comment">$&</span>');
    } else if (language === 'html') {
      highlighted = highlighted.replace(/&lt;!--[\s\S]*?--&gt;/g, '<span class="comment">$&</span>');
    }

    // Highlight numbers
    highlighted = highlighted.replace(/\b\d+\.?\d*\b/g, '<span class="number">$&</span>');

    return highlighted;
  }

  static escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

/**
 * Code formatter utilities
 */
class CodeFormatter {
  static format(code, language) {
    if (!code) return code;

    switch (language) {
      case 'json':
        try {
          return JSON.stringify(JSON.parse(code), null, 2);
        } catch (e) {
          return code;
        }
      case 'css':
        return this.formatCSS(code);
      case 'html':
        return this.formatHTML(code);
      default:
        return this.basicFormat(code);
    }
  }

  static formatCSS(css) {
    return css
      .replace(/\s*{\s*/g, ' {\n  ')
      .replace(/;\s*/g, ';\n  ')
      .replace(/\s*}\s*/g, '\n}\n')
      .replace(/,\s*/g, ',\n');
  }

  static formatHTML(html) {
    let formatted = html;
    let indent = 0;
    const tab = '  ';

    formatted = formatted.replace(/></g, '>\n<');
    
    const lines = formatted.split('\n');
    const result = [];

    for (let line of lines) {
      line = line.trim();
      if (!line) continue;

      if (line.startsWith('</')) {
        indent--;
      }

      result.push(tab.repeat(Math.max(0, indent)) + line);

      if (line.startsWith('<') && !line.startsWith('</') && !line.endsWith('/>')) {
        indent++;
      }
    }

    return result.join('\n');
  }

  static basicFormat(code) {
    return code
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
      .join('\n');
  }
}

/**
 * Snippet validation utilities
 */
class SnippetValidator {
  static validate(snippet) {
    const errors = [];

    if (!snippet.title || snippet.title.trim().length === 0) {
      errors.push('Title is required');
    }

    if (!snippet.code || snippet.code.trim().length === 0) {
      errors.push('Code content is required');
    }

    if (snippet.title && snippet.title.length > 100) {
      errors.push('Title must be less than 100 characters');
    }

    if (snippet.code && snippet.code.length > 50000) {
      errors.push('Code content is too large (max 50KB)');
    }

    if (snippet.tags && snippet.tags.length > 10) {
      errors.push('Maximum 10 tags allowed');
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  static sanitizeTitle(title) {
    return title.trim().substring(0, 100);
  }

  static sanitizeTags(tags) {
    if (!Array.isArray(tags)) return [];
    return tags
      .filter(tag => typeof tag === 'string')
      .map(tag => tag.trim().toLowerCase())
      .filter(tag => tag.length > 0)
      .slice(0, 10);
  }
}

/**
 * Storage utilities for offline functionality
 */
class StorageUtils {
  static async saveOfflineSnippet(snippet) {
    const offlineSnippets = await this.getOfflineSnippets();
    snippet.id = 'offline_' + Date.now();
    snippet.isOffline = true;
    offlineSnippets.push(snippet);
    
    await chrome.storage.local.set({ offlineSnippets });
    return snippet.id;
  }

  static async getOfflineSnippets() {
    const result = await chrome.storage.local.get(['offlineSnippets']);
    return result.offlineSnippets || [];
  }

  static async clearOfflineSnippets() {
    await chrome.storage.local.remove(['offlineSnippets']);
  }

  static async getRecentSnippets(limit = 10) {
    const result = await chrome.storage.local.get(['recentSnippets']);
    const recent = result.recentSnippets || [];
    return recent.slice(-limit).reverse();
  }

  static async addToRecentSnippets(snippet) {
    const recent = await this.getRecentSnippets(50);
    
    // Remove if already exists
    const filtered = recent.filter(s => s.id !== snippet.id);
    
    // Add to beginning
    filtered.unshift({
      id: snippet.id,
      title: snippet.title,
      language: snippet.language,
      code: snippet.code.substring(0, 200) + (snippet.code.length > 200 ? '...' : ''),
      created_at: new Date().toISOString()
    });

    await chrome.storage.local.set({ 
      recentSnippets: filtered.slice(0, 50) 
    });
  }
}

/**
 * URL and context utilities
 */
class ContextUtils {
  static getCurrentPageContext() {
    return {
      url: window.location.href,
      title: document.title,
      domain: window.location.hostname,
      path: window.location.pathname,
      timestamp: new Date().toISOString()
    };
  }

  static extractRepoInfo(url) {
    const githubMatch = url.match(/github\.com\/([^\/]+)\/([^\/]+)/);
    if (githubMatch) {
      return {
        platform: 'github',
        owner: githubMatch[1],
        repo: githubMatch[2],
        url: url
      };
    }

    const gitlabMatch = url.match(/gitlab\.com\/([^\/]+)\/([^\/]+)/);
    if (gitlabMatch) {
      return {
        platform: 'gitlab',
        owner: gitlabMatch[1],
        repo: gitlabMatch[2],
        url: url
      };
    }

    return null;
  }

  static isCodeSite(url) {
    const codeSites = [
      'github.com',
      'gitlab.com',
      'stackoverflow.com',
      'codepen.io',
      'jsfiddle.net',
      'codesandbox.io',
      'repl.it',
      'glitch.com'
    ];

    return codeSites.some(site => url.includes(site));
  }
}

// Export utilities for use in other scripts
window.SnippetUtils = {
  LanguageDetector,
  SyntaxHighlighter,
  CodeFormatter,
  SnippetValidator,
  StorageUtils,
  ContextUtils
};
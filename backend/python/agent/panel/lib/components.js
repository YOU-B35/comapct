/**
 * CrossHub Sync Helper - 前端组件库
 * 现代化的 UI 组件，支持暗黑/亮色主题
 * 使用原生 Web Components 确保兼容性
 */

// ============================================================
// 1. 主题管理
// ============================================================
export const ThemeManager = {
  isDark: true,

  init() {
    const stored = localStorage.getItem('theme-mode');
    if (stored) {
      this.isDark = stored === 'dark';
    } else {
      // 在测试环境中 matchMedia 可能不可用
      if (typeof window !== 'undefined' && window.matchMedia) {
        this.isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      } else {
        this.isDark = true; // 默认暗黑主题
      }
    }
    this.apply();

    // 监听系统主题变化
    if (typeof window !== 'undefined' && window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        this.isDark = e.matches;
        this.apply();
      });
    }
  },

  toggle() {
    this.isDark = !this.isDark;
    this.apply();
  },

  apply() {
    const root = document.documentElement;
    if (this.isDark) {
      root.classList.remove('light');
      root.classList.add('dark');
      localStorage.setItem('theme-mode', 'dark');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
      localStorage.setItem('theme-mode', 'light');
    }
  }
};

// ============================================================
// 2. 通知/Toast 系统
// ============================================================
export class Toast {
  static create(message, type = 'info', duration = 3000) {
    const id = `toast-${Date.now()}`;
    // 直接转义文本内容，防止 HTML 注入
    const escapedMessage = String(message)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');

    const html = `
      <div class="toast toast-${type}" id="${id}">
        <div class="toast-icon">${this._getIcon(type)}</div>
        <div class="toast-content">
          <p class="toast-message">${escapedMessage}</p>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
      </div>
    `;

    const container = document.querySelector('.toast-container') || this._createContainer();
    container.insertAdjacentHTML('beforeend', html);

    const toast = document.getElementById(id);
    if (duration > 0) {
      setTimeout(() => toast.remove(), duration);
    }

    return toast;
  }

  static success(msg, duration = 2500) { return this.create(msg, 'success', duration); }
  static error(msg, duration = 4000) { return this.create(msg, 'error', duration); }
  static warn(msg, duration = 3500) { return this.create(msg, 'warn', duration); }
  static info(msg, duration = 3000) { return this.create(msg, 'info', duration); }

  static _createContainer() {
    const div = document.createElement('div');
    div.className = 'toast-container';
    document.body.appendChild(div);
    return div;
  }

  static _getIcon(type) {
    const icons = {
      success: '✓',
      error: '✕',
      warn: '⚠',
      info: 'ⓘ'
    };
    return icons[type] || icons.info;
  }

  static _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// ============================================================
// 3. 模态对话框
// ============================================================
export class Modal {
  static confirm(title, message, onConfirm, onCancel) {
    const id = `modal-${Date.now()}`;
    const html = `
      <div class="modal-overlay" id="${id}">
        <div class="modal-content">
          <div class="modal-header">
            <h3>${this._escapeHtml(title)}</h3>
            <button class="modal-close" onclick="document.getElementById('${id}').remove()">&times;</button>
          </div>
          <div class="modal-body">
            <p>${this._escapeHtml(message)}</p>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" onclick="document.getElementById('${id}').remove()">取消</button>
            <button class="btn btn-primary" data-action="confirm">确认</button>
          </div>
        </div>
      </div>
    `;

    const modal = document.createElement('div');
    modal.innerHTML = html;
    document.body.appendChild(modal.firstElementChild);

    const modalEl = document.getElementById(id);
    modalEl.querySelector('[data-action="confirm"]').addEventListener('click', () => {
      onConfirm?.();
      modalEl.remove();
    });

    return modalEl;
  }

  static alert(title, message) {
    return this.confirm(title, message, null, null);
  }

  static _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// ============================================================
// 4. 状态徽章
// ============================================================
export class Badge {
  static create(status, label) {
    const statusClass = {
      'online': 'badge-success',
      'offline': 'badge-error',
      'loading': 'badge-info',
      'pending': 'badge-warn'
    }[status] || 'badge-info';

    return `
      <span class="badge ${statusClass}">
        <span class="badge-dot"></span>
        <span class="badge-label">${label}</span>
      </span>
    `;
  }
}

// ============================================================
// 5. 进度指示器
// ============================================================
export class Progress {
  static create(percentage, label = '') {
    // 限制进度在 0-100
    const normalizedPercentage = Math.max(0, Math.min(100, percentage));
    return `
      <div class="progress-wrapper">
        ${label ? `<div class="progress-label">${label}</div>` : ''}
        <div class="progress-bar">
          <div class="progress-fill" style="width: ${normalizedPercentage}%"></div>
        </div>
        <div class="progress-percent">${Math.round(normalizedPercentage)}%</div>
      </div>
    `;
  }
}

// ============================================================
// 6. 加载动画
// ============================================================
export class Spinner {
  static create(size = 'md', label = '') {
    return `
      <div class="spinner-wrapper">
        <div class="spinner spinner-${size}">
          <div class="spinner-ring"></div>
        </div>
        ${label ? `<p class="spinner-label">${label}</p>` : ''}
      </div>
    `;
  }
}

// ============================================================
// 7. 卡片容器
// ============================================================
export class Card {
  static create(content, { title = '', icon = '', clickable = false } = {}) {
    const clickClass = clickable ? 'card-clickable' : '';
    return `
      <div class="card ${clickClass}">
        ${title || icon ? `
          <div class="card-header">
            ${icon ? `<span class="card-icon">${icon}</span>` : ''}
            ${title ? `<h4 class="card-title">${title}</h4>` : ''}
          </div>
        ` : ''}
        <div class="card-body">${content}</div>
      </div>
    `;
  }
}

// ============================================================
// 8. 按钮组件
// ============================================================
export class Button {
  static create(label, { type = 'primary', size = 'md', icon = '', disabled = false } = {}) {
    const disabledAttr = disabled ? 'disabled' : '';
    return `
      <button class="btn btn-${type} btn-${size}" ${disabledAttr}>
        ${icon ? `<span class="btn-icon">${icon}</span>` : ''}
        <span>${label}</span>
      </button>
    `;
  }
}

// ============================================================
// 9. 表单验证
// ============================================================
export class FormValidator {
  static validate(form) {
    const errors = [];
    const inputs = form.querySelectorAll('[required]');

    inputs.forEach(input => {
      const value = input.value?.trim();
      if (!value) {
        errors.push({
          field: input.name,
          message: `${input.placeholder || input.name} 不能为空`
        });
        input.classList.add('input-error');
      } else {
        input.classList.remove('input-error');
      }
    });

    return errors;
  }

  static clearErrors(form) {
    form.querySelectorAll('.input-error').forEach(el => {
      el.classList.remove('input-error');
    });
  }
}

// ============================================================
// 10. API 请求封装
// ============================================================
export class API {
  static async request(endpoint, options = {}) {
    const url = `/api${endpoint}`;
    const defaults = {
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 30000
    };

    const config = { ...defaults, ...options };

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), config.timeout);

      const response = await fetch(url, {
        ...config,
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new Error('请求超时');
      }
      throw error;
    }
  }

  static get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }

  static post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  static put(endpoint, data) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }

  static delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
}

// ============================================================
// 11. 事件总线
// ============================================================
export const EventBus = new (class {
  constructor() {
    this.events = new Map();
  }

  on(event, callback) {
    if (!this.events.has(event)) {
      this.events.set(event, []);
    }
    this.events.get(event).push(callback);
  }

  off(event, callback) {
    if (this.events.has(event)) {
      const listeners = this.events.get(event);
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.events.has(event)) {
      this.events.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`EventBus error for ${event}:`, error);
        }
      });
    }
  }
})();

// ============================================================
// 12. 存储管理
// ============================================================
export const Storage = {
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      console.error('Storage.set failed:', e);
    }
  },

  get(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (e) {
      console.error('Storage.get failed:', e);
      return defaultValue;
    }
  },

  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.error('Storage.remove failed:', e);
    }
  },

  clear() {
    try {
      localStorage.clear();
    } catch (e) {
      console.error('Storage.clear failed:', e);
    }
  }
};

export default {
  ThemeManager,
  Toast,
  Modal,
  Badge,
  Progress,
  Spinner,
  Card,
  Button,
  FormValidator,
  API,
  EventBus,
  Storage
};

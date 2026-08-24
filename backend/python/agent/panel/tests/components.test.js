/**
 * CrossHub Sync Helper - 前端单元测试
 * 使用 Vitest + JSDOM 测试组件库
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
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
} from '../lib/components.js';

// ============================================================
// 主题管理测试
// ============================================================
describe('ThemeManager', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = '';
  });

  it('应该初始化为暗黑主题', () => {
    ThemeManager.isDark = true;
    ThemeManager.apply();
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('应该切换主题', () => {
    ThemeManager.isDark = true;
    ThemeManager.apply();
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    ThemeManager.toggle();
    expect(document.documentElement.classList.contains('light')).toBe(true);
  });

  it('应该保存主题选择到 localStorage', () => {
    ThemeManager.isDark = true;
    ThemeManager.apply();
    expect(localStorage.getItem('theme-mode')).toBe('dark');

    ThemeManager.toggle();
    expect(localStorage.getItem('theme-mode')).toBe('light');
  });

  it('应该从 localStorage 恢复主题', () => {
    localStorage.setItem('theme-mode', 'light');
    ThemeManager.isDark = true; // 重置
    ThemeManager.init();
    expect(ThemeManager.isDark).toBe(false);
  });
});

// ============================================================
// Toast 通知测试
// ============================================================
describe('Toast', () => {
  beforeEach(() => {
    const container = document.querySelector('.toast-container');
    if (container) container.remove();
  });

  it('应该创建成功提示', () => {
    Toast.success('操作成功');
    const toast = document.querySelector('.toast-success');
    expect(toast).toBeTruthy();
    expect(toast.textContent).toContain('操作成功');
  });

  it('应该创建错误提示', () => {
    Toast.error('发生错误');
    const toast = document.querySelector('.toast-error');
    expect(toast).toBeTruthy();
  });

  it('应该在指定时间后自动移除', async () => {
    const toast = Toast.info('信息', 100);
    expect(toast).toBeTruthy();
    await new Promise(resolve => setTimeout(resolve, 150));
    expect(document.querySelector(`#${toast.id}`)).toBeFalsy();
  });

  it('应该转义 HTML 内容', () => {
    Toast.success('<script>alert("xss")</script>');
    const toast = document.querySelector('.toast-success');
    const innerHTML = toast.querySelector('.toast-message').innerHTML;
    // 转义后应该不包含可执行的脚本
    expect(innerHTML).toContain('&lt;script&gt;');
    expect(innerHTML).not.toContain('<script>');
  });
});

// ============================================================
// 模态对话框测试
// ============================================================
describe('Modal', () => {
  afterEach(() => {
    const modals = document.querySelectorAll('.modal-overlay');
    modals.forEach(m => m.remove());
  });

  it('应该创建确认对话框', () => {
    Modal.confirm('确认', '确定要删除吗？', () => {}, () => {});
    const modal = document.querySelector('.modal-overlay');
    expect(modal).toBeTruthy();
    expect(modal.textContent).toContain('确定要删除吗？');
  });

  it('应该执行确认回调', async () => {
    const onConfirm = vi.fn();
    Modal.confirm('确认', '删除吗？', onConfirm);
    const confirmBtn = document.querySelector('[data-action="confirm"]');
    confirmBtn.click();
    expect(onConfirm).toHaveBeenCalled();
  });

  it('应该关闭对话框', () => {
    Modal.confirm('确认', '删除吗？', () => {});
    const modal = document.querySelector('.modal-overlay');
    const closeBtn = modal.querySelector('.modal-close');
    closeBtn.click();
    expect(document.querySelector('.modal-overlay')).toBeFalsy();
  });
});

// ============================================================
// 徽章测试
// ============================================================
describe('Badge', () => {
  it('应该创建成功徽章', () => {
    const html = Badge.create('online', '在线');
    expect(html).toContain('badge-success');
    expect(html).toContain('在线');
  });

  it('应该创建错误徽章', () => {
    const html = Badge.create('offline', '离线');
    expect(html).toContain('badge-error');
  });

  it('应该创建加载徽章', () => {
    const html = Badge.create('loading', '加载中');
    expect(html).toContain('badge-info');
  });
});

// ============================================================
// 进度条测试
// ============================================================
describe('Progress', () => {
  it('应该创建进度条', () => {
    const html = Progress.create(50, '上传中');
    expect(html).toContain('progress');
    expect(html).toContain('50%');
    expect(html).toContain('上传中');
  });

  it('应该限制进度在 0-100', () => {
    const html1 = Progress.create(150);
    expect(html1).toContain('width: 100%');

    const html2 = Progress.create(-10);
    expect(html2).toContain('width: 0%');
  });
});

// ============================================================
// 加载动画测试
// ============================================================
describe('Spinner', () => {
  it('应该创建加载动画', () => {
    const html = Spinner.create('md', '加载中...');
    expect(html).toContain('spinner');
    expect(html).toContain('spinner-md');
    expect(html).toContain('加载中...');
  });

  it('应该支持不同大小', () => {
    const sizes = ['sm', 'md', 'lg'];
    sizes.forEach(size => {
      const html = Spinner.create(size);
      expect(html).toContain(`spinner-${size}`);
    });
  });
});

// ============================================================
// 卡片测试
// ============================================================
describe('Card', () => {
  it('应该创建卡片', () => {
    const html = Card.create('卡片内容', { title: '标题' });
    expect(html).toContain('card');
    expect(html).toContain('标题');
    expect(html).toContain('卡片内容');
  });

  it('应该支持可点击模式', () => {
    const html = Card.create('内容', { clickable: true });
    expect(html).toContain('card-clickable');
  });

  it('应该支持图标', () => {
    const html = Card.create('内容', { icon: '✓' });
    expect(html).toContain('card-icon');
    expect(html).toContain('✓');
  });
});

// ============================================================
// 按钮测试
// ============================================================
describe('Button', () => {
  it('应该创建主要按钮', () => {
    const html = Button.create('点击', { type: 'primary' });
    expect(html).toContain('btn-primary');
    expect(html).toContain('点击');
  });

  it('应该支持不同大小', () => {
    const sizes = ['sm', 'md', 'lg'];
    sizes.forEach(size => {
      const html = Button.create('按钮', { size });
      expect(html).toContain(`btn-${size}`);
    });
  });

  it('应该支持禁用状态', () => {
    const html = Button.create('按钮', { disabled: true });
    expect(html).toContain('disabled');
  });

  it('应该支持图标', () => {
    const html = Button.create('删除', { icon: '🗑️' });
    expect(html).toContain('btn-icon');
  });
});

// ============================================================
// 表单验证测试
// ============================================================
describe('FormValidator', () => {
  let form;

  beforeEach(() => {
    form = document.createElement('form');
    form.innerHTML = `
      <input type="text" name="username" placeholder="用户名" required>
      <input type="email" name="email" placeholder="邮箱" required>
      <textarea name="message" required></textarea>
    `;
    document.body.appendChild(form);
  });

  afterEach(() => {
    form.remove();
  });

  it('应该检测空字段', () => {
    const errors = FormValidator.validate(form);
    expect(errors.length).toBeGreaterThan(0);
  });

  it('应该添加错误样式', () => {
    FormValidator.validate(form);
    const inputs = form.querySelectorAll('.input-error');
    expect(inputs.length).toBeGreaterThan(0);
  });

  it('应该验证已填充的字段', () => {
    form.querySelector('input[name="username"]').value = '用户名';
    form.querySelector('input[name="email"]').value = 'test@example.com';
    form.querySelector('textarea').value = '消息内容';

    const errors = FormValidator.validate(form);
    expect(errors.length).toBe(0);
  });

  it('应该清除错误样式', () => {
    FormValidator.validate(form);
    FormValidator.clearErrors(form);
    const errorInputs = form.querySelectorAll('.input-error');
    expect(errorInputs.length).toBe(0);
  });
});

// ============================================================
// API 请求测试
// ============================================================
describe('API', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('应该发送 GET 请求', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true })
    });

    const result = await API.get('/status');
    expect(result.success).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/status'),
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('应该发送 POST 请求', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1 })
    });

    const result = await API.post('/bind', { code: '123' });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/bind'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('code')
      })
    );
  });

  it('应该处理请求超时', async () => {
    global.fetch.mockImplementationOnce(() =>
      new Promise((_, reject) => {
        const error = new Error();
        error.name = 'AbortError';
        reject(error);
      })
    );

    await expect(API.get('/timeout')).rejects.toThrow('请求超时');
  });

  it('应该处理 HTTP 错误', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found'
    });

    await expect(API.get('/notfound')).rejects.toThrow('HTTP 404');
  });
});

// ============================================================
// 事件总线测试
// ============================================================
describe('EventBus', () => {
  it('应该发送和接收事件', () => {
    const callback = vi.fn();
    EventBus.on('test-event', callback);
    EventBus.emit('test-event', { data: 'test' });

    expect(callback).toHaveBeenCalledWith({ data: 'test' });
  });

  it('应该支持多个监听器', () => {
    const callback1 = vi.fn();
    const callback2 = vi.fn();

    EventBus.on('event', callback1);
    EventBus.on('event', callback2);
    EventBus.emit('event', { value: 1 });

    expect(callback1).toHaveBeenCalled();
    expect(callback2).toHaveBeenCalled();
  });

  it('应该移除监听器', () => {
    const callback = vi.fn();
    EventBus.on('event', callback);
    EventBus.off('event', callback);
    EventBus.emit('event');

    expect(callback).not.toHaveBeenCalled();
  });

  it('应该处理异常', () => {
    const errorCallback = vi.fn(() => {
      throw new Error('Test error');
    });
    const normalCallback = vi.fn();

    EventBus.on('event', errorCallback);
    EventBus.on('event', normalCallback);
    EventBus.emit('event');

    expect(errorCallback).toHaveBeenCalled();
    expect(normalCallback).toHaveBeenCalled(); // 不因为异常中断
  });
});

// ============================================================
// 存储管理测试
// ============================================================
describe('Storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('应该保存和读取数据', () => {
    Storage.set('key1', { name: 'test' });
    const value = Storage.get('key1');

    expect(value.name).toBe('test');
  });

  it('应该返回默认值', () => {
    const value = Storage.get('nonexistent', 'default');
    expect(value).toBe('default');
  });

  it('应该移除键', () => {
    Storage.set('key1', 'value');
    Storage.remove('key1');
    const value = Storage.get('key1', 'default');

    expect(value).toBe('default');
  });

  it('应该清空所有数据', () => {
    Storage.set('key1', 'value1');
    Storage.set('key2', 'value2');
    Storage.clear();

    expect(Storage.get('key1')).toBeNull();
    expect(Storage.get('key2')).toBeNull();
  });

  it('应该处理 JSON 解析错误', () => {
    localStorage.setItem('corrupt', 'not-valid-json{');
    const value = Storage.get('corrupt', 'default');
    expect(value).toBe('default');
  });
});

// ============================================================
// 集成测试
// ============================================================
describe('集成场景', () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = '';
  });

  it('应该完成登录流程', () => {
    // 创建表单
    const form = document.createElement('form');
    form.innerHTML = `
      <input type="text" name="code" placeholder="绑定码" required>
      <button type="button">确认绑定</button>
    `;
    document.body.appendChild(form);

    // 验证表单
    const errors = FormValidator.validate(form);
    expect(errors.length).toBeGreaterThan(0);

    // 填充表单
    form.querySelector('input[name="code"]').value = 'ABC123';
    const errors2 = FormValidator.validate(form);
    expect(errors2.length).toBe(0);

    // 显示成功提示
    Toast.success('绑定成功');
    expect(document.querySelector('.toast-success')).toBeTruthy();
  });

  it('应该完成文件上传流程', () => {
    const modal = Modal.confirm('上传文件', '是否继续？', () => {
      Toast.success('上传成功');
    });

    // 点击确认
    const confirmBtn = modal.querySelector('[data-action="confirm"]');
    confirmBtn.click();

    expect(document.querySelector('.toast-success')).toBeTruthy();
  });
});

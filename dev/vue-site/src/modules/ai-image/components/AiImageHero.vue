<template>
  <header class="ai-hero">
    <div class="ai-hero__brand">
      <div class="ai-hero__logo" aria-hidden="true">
        <svg viewBox="0 0 48 48" width="40" height="40">
          <defs>
            <linearGradient id="aiHeroGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#1f4fd6" />
              <stop offset="100%" stop-color="#4d73e0" />
            </linearGradient>
          </defs>
          <rect width="48" height="48" rx="10" fill="url(#aiHeroGrad)" />
          <path
            d="M14 30c4-10 16-10 20 0M18 22c2-4 10-4 12 0M22 16c1-2 3-2 4 0"
            stroke="#fff"
            stroke-width="2.4"
            stroke-linecap="round"
            fill="none"
          />
          <circle cx="24" cy="34" r="2.2" fill="#fff" />
        </svg>
      </div>
      <div class="ai-hero__text">
        <p class="ai-hero__eyebrow">智能工具</p>
        <h1>AI 生图</h1>
        <p>GPT Image 2.0 · 电商主图 / 场景图一键生成，支持参考图与多比例输出</p>
      </div>
    </div>
  </header>
</template>

<style scoped>
.ai-hero {
  padding: 4px 2px 8px;
  border-bottom: 1px solid var(--ch-border);
  margin-bottom: 4px;
}

.ai-hero__brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ai-hero__logo {
  flex-shrink: 0;
}

.ai-hero__eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--ch-text-muted);
}

.ai-hero__text h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--ch-text);
  letter-spacing: -0.025em;
}

.ai-hero__text > p:last-child {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--ch-text-secondary);
  max-width: 56ch;
}
</style>

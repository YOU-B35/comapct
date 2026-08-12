<template>
  <div class="about">
    <PageHeader
      title="关于"
      eyebrow="自媒体"
      description="social-auto-upload 自媒体运营模块"
    />

    <PageSection title="系统简介">
      <p>
        本系统是一款强大的自动化工具，帮助内容创作者和运营人员一键将视频内容高效发布到多个国内外主流社交媒体平台。
        支持视频上传、定时发布等功能。
      </p>
    </PageSection>

    <PageSection title="支持平台">
      <div class="platform-tags">
        <el-tag type="danger">抖音</el-tag>
        <el-tag type="success">快手</el-tag>
        <el-tag type="warning">视频号</el-tag>
        <el-tag type="info">小红书</el-tag>
        <el-tag type="danger" effect="dark">TikTok</el-tag>
      </div>
    </PageSection>

    <PageSection title="核心功能">
      <ul class="feature-list">
        <li>多平台账号管理与登录状态维护</li>
        <li>视频 / 图片素材上传与管理</li>
        <li>一键多平台发布</li>
        <li>定时发布与批量发布</li>
        <li>Cookie 导入导出</li>
      </ul>
    </PageSection>

    <PageSection title="技术栈">
      <div class="tech-tags">
        <el-tag effect="plain">Vue 3</el-tag>
        <el-tag effect="plain">Element Plus</el-tag>
        <el-tag effect="plain">Pinia</el-tag>
        <el-tag effect="plain">Flask</el-tag>
        <el-tag effect="plain">Playwright</el-tag>
        <el-tag effect="plain">SQLite</el-tag>
      </div>
    </PageSection>
  </div>
</template>

<script setup>
import PageHeader from '@/components/common/PageHeader.vue'
import PageSection from '@/components/common/PageSection.vue'
</script>

<style lang="scss" scoped>
@use '@sau/styles/variables.scss' as *;

.about {
  max-width: 700px;

  p {
    color: $text-secondary;
    line-height: 1.8;
    margin: 0;
  }

  .platform-tags,
  .tech-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .feature-list {
    margin: 0;
    padding-left: 20px;
    color: $text-secondary;
    line-height: 2;
  }
}
</style>

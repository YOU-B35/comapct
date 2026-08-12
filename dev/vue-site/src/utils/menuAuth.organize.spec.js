import { describe, expect, it } from 'vitest'
import {
  buildSidebarTree,
  organizeSidebarGroups,
  sidebarMenuOpenKeys,
} from '@/utils/menuAuth'

describe('organizeSidebarGroups', () => {
  it('collapses platforms and tools into folders', () => {
    const tree = buildSidebarTree([
      {
        code: 'boss.dashboard',
        parent_code: null,
        portal: 'boss',
        platform: null,
        path: '/boss/dashboard',
        label: '运营总览',
        menu_type: 'admin',
        sort_order: 10,
      },
      {
        code: 'boss.platform.temu',
        parent_code: null,
        portal: 'boss',
        platform: 'temu',
        path: '/boss/temu',
        label: 'Temu 运营',
        menu_type: 'module',
        sort_order: 30,
      },
      {
        code: 'boss.platform.amazon',
        parent_code: null,
        portal: 'boss',
        platform: 'amazon',
        path: '/boss/amazon',
        label: 'Amazon 运营',
        menu_type: 'module',
        sort_order: 50,
      },
      {
        code: 'boss.ai_image',
        parent_code: null,
        portal: 'boss',
        platform: null,
        path: '/boss/ai-image',
        label: 'AI 生图',
        menu_type: 'base',
        sort_order: 15,
      },
      {
        code: 'boss.settings',
        parent_code: null,
        portal: 'boss',
        platform: null,
        path: '#',
        label: '设置',
        menu_type: 'group',
        sort_order: 120,
      },
      {
        code: 'boss.employees',
        parent_code: 'boss.settings',
        portal: 'boss',
        platform: null,
        path: '/boss/employees',
        label: '运营绑定',
        menu_type: 'admin',
        sort_order: 122,
      },
    ])

    const organized = organizeSidebarGroups(tree)
    const codes = organized.map((m) => m.code)
    expect(codes).toContain('boss.dashboard')
    expect(codes).toContain('boss.nav.platforms')
    expect(codes).toContain('boss.nav.tools')
    expect(codes).toContain('boss.settings')
    expect(codes).not.toContain('boss.platform.temu')
    expect(codes).not.toContain('boss.ai_image')

    const platforms = organized.find((m) => m.code === 'boss.nav.platforms')
    expect(platforms.children.map((c) => c.label)).toEqual(['Temu', 'Amazon'])

    const tools = organized.find((m) => m.code === 'boss.nav.tools')
    expect(tools.children.map((c) => c.code)).toEqual(['boss.ai_image'])
  })
})

describe('sidebarMenuOpenKeys', () => {
  it('only opens the active group', () => {
    expect(sidebarMenuOpenKeys('/boss/dashboard')).toEqual([])
    expect(sidebarMenuOpenKeys('/boss/amazon')).toEqual(['boss.nav.platforms'])
    expect(sidebarMenuOpenKeys('/boss/ai-image')).toEqual(['boss.nav.tools'])
    expect(sidebarMenuOpenKeys('/boss/ops-teams')).toEqual(['boss.settings'])
    expect(sidebarMenuOpenKeys('/employee/temu')).toEqual(['employee.nav.platforms'])
  })
})

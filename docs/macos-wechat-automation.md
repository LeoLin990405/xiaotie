# macOS 微信小程序自动化技术方案

> 研究日期: 2026-02-25
> 适用项目: xiaotie (小铁) - AI Agent 框架

## 1. 概述

本文档研究在 macOS 上自动化操作微信桌面版，特别是打开和抓取微信小程序数据的技术方案。
目标是为 xiaotie 项目的 `automation` 模块提供 macOS 原生方案，替代现有的 Appium 移动端方案。

### 1.1 核心挑战

| 挑战 | 说明 |
|------|------|
| 微信无公开 API | 桌面版微信没有自动化 API，只能通过 UI 操作 |
| 小程序运行在 WKWebView | macOS 版小程序使用 WKWebView 渲染，JS 运行在 JavaScriptCore |
| HTTPS 证书校验 | 微信可能使用证书固定 (Certificate Pinning)，增加抓包难度 |
| UI 元素不稳定 | 微信版本更新可能改变 UI 层级结构 |

## 2. 自动化方案对比

### 2.1 方案总览

| 方案 | 可行性 | 稳定性 | 开发难度 | 维护成本 | 推荐度 |
|------|--------|--------|----------|----------|--------|
| AppleScript + System Events | ★★★★ | ★★★ | ★★★★★ | ★★★ | **推荐** |
| macOS Accessibility API (Python) | ★★★★★ | ★★★★ | ★★★ | ★★★ | **首选** |
| PyAutoGUI (图像识别) | ★★★ | ★★ | ★★★★ | ★★ | 备选 |
| Appium (现有方案) | ★★ | ★★★ | ★★ | ★★ | 仅移动端 |

---

## 3. 方案一: AppleScript + System Events (推荐)

### 3.1 原理

通过 macOS System Events 的 GUI Scripting 功能，操控微信桌面版的 UI 元素。

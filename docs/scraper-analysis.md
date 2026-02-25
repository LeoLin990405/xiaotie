# 竞品爬虫代码架构分析报告

**分析日期**: 2026-02-25
**代码版本**: v2.2.0 (py_2026-01-20)
**代码位置**: `/Users/leo/Desktop/竞品代码/新竞品代码/`

---

## 1. 项目概述

该竞品代码是一个面向中国台球/娱乐场所的多品牌门店数据抓取系统，覆盖19个品牌。系统从v1.0（每品牌独立脚本，500-1000行）演进到v2.0（基于继承的统一架构，100-200行/品牌），代码复用率从10%提升到90%。

### 核心指标
- 品牌数量: 19个
- 核心库模块: 10个 (`lib/` 目录)
- 认证方式: 6种
- 代码减少率: 平均75%
- 性能提升: 约17-20%（连接池复用）

---

## 2. 整体架构

### 2.1 目录结构

```
新竞品代码/
├── lib/                          # 核心共享库 (10个模块)
│   ├── __init__.py              # 模块导出 (v2.2.0)
│   ├── base_scraper.py          # BaseScraper 抽象基类 (330行)
│   ├── config.py                # ConfigManager 配置管理 (214行)
│   ├── threading_utils.py       # SessionManager + ThreadStats (183行)
│   ├── stability.py             # StabilityAnalyzer 稳定性分析 (279行)
│   ├── output.py                # OutputManager 输出管理 (189行)
│   ├── auth.py                  # AuthHandler 认证处理 (180行)
│   ├── data_processor.py        # DataProcessor 数据处理 (241行)
│   ├── field_aligner.py         # FieldAligner 字段对齐 (325行)
│   ├── geocoder.py              # TencentGeocoder 地理编码 (112行)
│   └── monitoring.py            # 性能监控+日志+链路追踪 (653行)
│
├── config/                       # YAML配置
│   ├── settings.yaml            # 全局设置
│   ├── brands.yaml              # 19品牌配置
│   ├── field_mapping.yaml       # 字段映射规则
│   └── secrets.env.example      # Token模板
│
├── archive/py_2026-01-20/       # 19个品牌脚本
└── output/                       # 统一输出目录
```

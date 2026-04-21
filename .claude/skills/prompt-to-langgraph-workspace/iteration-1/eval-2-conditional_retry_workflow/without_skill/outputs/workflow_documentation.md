# 条件重试工作流文档

## 概述

这个自动化工作流实现了一个智能的数据搜索、分析和报告生成流程，包含了完善的条件逻辑和重试机制。

## 核心功能

### 1. 条件逻辑机制

工作流使用条件节点来实现智能决策：

#### 1.1 搜索成功检查 (`check_search_success`)
- **条件**: `search_success == true`
- **成功分支**: 继续执行分析 (`analyze_results`)
- **失败分支**: 进入重试逻辑 (`retry_search`)

#### 1.2 重试决策 (`retry_search`)
- **条件**: `retry_count < max_retries`
- **真值分支**: 重新执行搜索 (`search_data`)
- **假值分支**: 处理最终失败 (`handle_failure`)

### 2. 重试机制详解

#### 2.1 重试配置参数

```json
{
  "max_retries": 3,              // 最大重试次数
  "initial_delay": 1000,         // 初始延迟（毫秒）
  "max_delay": 10000,           // 最大延迟（毫秒）
  "backoff_multiplier": 2,      // 退避倍数（指数退避）
  "retry_on_errors": [          // 需要重试的错误类型
    "network_error",
    "timeout",
    "rate_limit"
  ],
  "retry_on_conditions": [      // 需要重试的条件
    "result_count == 0",
    "result.quality_score < 0.5"
  ]
}
```

#### 2.2 指数退避策略

重试延迟采用指数退避算法：

```
第1次重试: 1000ms (1秒)
第2次重试: 2000ms (2秒)
第3次重试: 4000ms (4秒)
最大延迟:  10000ms (10秒)
```

**计算公式**: `delay = min(initial_delay * (backoff_multiplier ^ retry_count), max_delay)`

#### 2.3 重试触发条件

重试会在以下情况下触发：

1. **错误类型匹配**:
   - 网络错误 (network_error)
   - 超时错误 (timeout)
   - 速率限制 (rate_limit)

2. **条件不满足**:
   - 搜索结果为空 (result_count == 0)
   - 结果质量分数低于阈值 (result.quality_score < 0.5)

### 3. 状态管理

工作流维护以下状态变量：

| 状态变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `search_success` | boolean | false | 搜索是否成功 |
| `retry_count` | integer | 0 | 当前重试次数 |
| `max_retries` | integer | 3 | 最大重试次数 |
| `search_results` | array | [] | 搜索结果集合 |
| `analysis_results` | object | null | 分析结果 |
| `report` | object | null | 生成的报告 |
| `errors` | array | [] | 错误日志 |
| `execution_log` | array | [] | 执行日志 |

## 工作流程图

```
开始
  ↓
搜索数据 (search_data)
  ↓
检查搜索结果 (check_search_success)
  ├─ 成功 → 分析结果 (analyze_results) → 生成报告 (generate_report) → 结束
  └─ 失败 → 重试决策 (retry_search)
              ├─ retry_count < 3 → 增加重试计数 → 重新搜索
              └─ retry_count >= 3 → 处理失败 (handle_failure) → 结束
```

## 错误处理策略

### 1. 搜索阶段错误
- **可重试错误**: 使用重试机制，最多3次
- **不可重试错误**: 直接进入失败处理流程

### 2. 分析阶段错误
- 记录错误到日志
- 继续生成报告（包含错误信息）
- 不中断工作流执行

### 3. 最终失败处理
- 记录所有尝试的错误信息
- 生成失败报告
- 包含详细的执行日志和重试历史

## 报告生成

报告包含以下信息：

1. **时间戳**: 报告生成时间
2. **执行状态**: 成功/失败
3. **重试统计**: 总重试次数
4. **搜索结果**: 原始搜索数据
5. **分析结果**: 处理后的分析数据
6. **错误日志**: 所遇到的错误
7. **执行日志**: 完整的执行轨迹

## 优化建议

### 1. 性能优化
- 调整重试间隔以减少等待时间
- 实现并行搜索策略
- 添加缓存机制避免重复搜索

### 2. 可靠性增强
- 实现断点续传机制
- 添加持久化状态存储
- 实现工作流恢复功能

### 3. 监控和告警
- 添加性能指标收集
- 实现失败告警机制
- 集成外部监控系统

## 使用示例

```javascript
// 初始化工作流
const workflow = new ConditionalRetryWorkflow({
  maxRetries: 3,
  initialDelay: 1000,
  retryOnError: ['network_error', 'timeout']
});

// 执行工作流
const result = await workflow.execute({
  searchQuery: "example data",
  analysisType: "detailed"
});

// 检查结果
if (result.success) {
  console.log("工作流执行成功");
  console.log("报告:", result.report);
} else {
  console.log("工作流执行失败");
  console.log("错误:", result.errors);
  console.log("重试次数:", result.retryCount);
}
```

## 总结

这个条件重试工作流提供了：
- ✅ 智能的条件决策逻辑
- ✅ 健壮的重试机制
- ✅ 完善的错误处理
- ✅ 详细的状态跟踪
- ✅ 灵活的配置选项
- ✅ 全面的执行日志

通过合理配置重试参数和条件逻辑，可以构建出可靠、高效的数据处理自动化流程。

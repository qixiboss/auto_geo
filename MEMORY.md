# AutoGeo 项目记忆

## 重要修复记录

### 2026-02-06: 账号授权 storage_state 结构错误导致验证失败

**问题描述**：
- 批量检测登录状态时，所有账号都显示"授权已失效"
- 访问平台页面时自动跳转到登录页（如知乎跳转到 /signin）

**根本原因**：
在 `playwright_mgr.py:239-240` 保存 `storage_state` 时，只保存了 `localStorage` 和 `sessionStorage`，**缺少了 `cookies` 字段**。

**错误代码**：
```python
storage_state = await task.page.evaluate(
    "() => ({ localStorage: {...localStorage}, sessionStorage: {...sessionStorage} })")
# 结果只有：{localStorage: {...}, sessionStorage: {...}}
```

**Playwright 要求的 storage_state 结构**：
```python
{
    "cookies": [...],        # ← 必须有！
    "localStorage": {...},  # 可选
    "sessionStorage": {...}  # 可选
}
```

**修复方案**：

1. **修复保存逻辑** (`playwright_mgr.py:237-250`)：
```python
# 提取 Cookies 和 Storage
cookies = await task.context.cookies()

# 获取 localStorage 和 sessionStorage
storage_data = await task.page.evaluate(
    "() => ({ localStorage: {...localStorage}, sessionStorage: {...sessionStorage} })")

# 构建完整的 storage_state（必须包含 cookies 字段！）
storage_state = {
    "cookies": cookies,
    "localStorage": storage_data.get("localStorage", {}),
    "sessionStorage": storage_data.get("sessionStorage", {})
}
```

2. **兼容旧数据** (`account_validator.py` 和 `playwright_mgr.py`)：
```python
# 兼容旧数据格式：如果缺少 cookies 字段，从 account.cookies 补充
if isinstance(state_data, dict) and "cookies" not in state_data and account.cookies:
    logger.warning(f"storage_state缺少cookies字段，使用独立cookies")
    state_data["cookies"] = decrypt_cookies(account.cookies)
```

**注意事项**：
- 旧授权的数据格式不完整，需要**重新授权**才能完全生效
- 兼容逻辑可以让旧数据暂时正常工作，但建议重新授权

### 2026-02-06: Playwright query_selector 不支持 timeout 参数

**问题描述**：
验证时出现错误：`Page.query_selector() got an unexpected keyword argument 'timeout'`

**原因**：
Playwright 的 `query_selector` 方法不支持 `timeout` 参数，应该使用 `wait_for_selector` 或设置页面默认超时。

**修复方案**：
移除所有 `query_selector` 调用中的 `timeout=5000` 参数。

### 2026-02-06: 验证时页面导航导致上下文销毁错误

**问题描述**：
验证网易号等平台时出现错误：`Execution context was destroyed, most likely because of a navigation`

**原因**：
某些平台在页面加载后会进行内部导航（iframe 跳转、重定向等），导致原始页面上下文被销毁。此时调用 `page.url` 或 `page.title()` 会抛出异常。

**修复方案**：
在获取页面信息时添加异常处理：

```python
try:
    actual_url = page.url
    title = await page.title()
except Exception as e:
    logger.warning(f"获取页面信息时发生异常（可能是页面导航）: {e}")
    actual_url = test_url  # 使用导航前的URL
    title = ""
```

### 2026-02-06: 某些平台访问超时

**问题描述**：
验证搜狐号等平台时超时：`Timeout 30000ms exceeded`

**原因**：
- 30秒超时时间对某些加载较慢的网站不够
- 无头模式浏览器加载速度可能较慢

**修复方案**：
1. 增加特定平台的超时时间
2. 优化浏览器启动参数以提高兼容性

```python
timeout = 30000
if account.platform in ["sohu", "wangyi"]:
    timeout = 60000  # 搜狐和网易超时时间增加到60秒
```

浏览器参数优化：
```python
args=BROWSER_ARGS + [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-background-networking",
    "--disable-features=Translate",
    "--disable-infobars",
    "--no-sandbox",
    "--disable-web-security",  # 允许跨域
    "--disable-features=IsolateOrigins,site-per-process"  # 共享进程上下文
]
```

## 开发命令

- `py test_account_data.py` - 检查账号数据是否正常
- `py test_storage_structure.py` - 检查 storage_state 结构
- `py test_account_validation.py` - 测试账号验证逻辑

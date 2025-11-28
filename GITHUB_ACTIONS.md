# GitHub Actions 自动打包使用说明

## 🚀 快速开始

### 手动触发构建

1. **进入 Actions 页面**
   ```
   GitHub 仓库 → Actions → Build Cross-Platform Apps → Run workflow
   ```

2. **输入参数**
   - **版本号** (必填): 如 `1.0.0`
   - **构建 macOS**: ✅ 勾选构建 Mac 版本
   - **构建 Windows**: ✅ 勾选构建 Windows 版本
   - **构建 Linux**: ☐ 可选构建 Linux 版本
   - **创建 Release**: ☐ 测试时不勾选，发布时勾选
   - **Python 版本**: 默认 `3.10`

3. **点击 "Run workflow"**

4. **等待构建完成** (约 15-20 分钟)

5. **下载构建产物**
   - **测试构建**: 在 Artifacts 部分下载
   - **正式发布**: 在 Releases 页面下载

---

## 📦 输出文件

| 平台 | 文件 |
|------|------|
| macOS | DatasetManager-macOS-版本号.zip (包含 .app) |
| Windows | DatasetManager-Windows-版本号.zip (包含 .exe) |
| Linux | DatasetManager-Linux-版本号.tar.gz |

---

## 🎯 使用场景

### 场景 1: 测试构建
```yaml
版本号: 1.0.0-test
macOS: ✅  Windows: ✅  Linux: ☐
创建 Release: ☐
```
→ 从 Artifacts 下载测试（保留 30 天）

### 场景 2: 正式发布
```yaml
版本号: 1.0.0
macOS: ✅  Windows: ✅  Linux: ☐
创建 Release: ✅
```
→ 自动创建 Release v1.0.0（永久保留）

---

## 🔄 自动触发

### 推送代码自动构建
```bash
git push origin main  # 自动构建所有平台
```

### 推送标签自动发布
```bash
git tag v1.0.0
git push origin v1.0.0  # 自动构建并创建 Release
```

---

## ⚙️ 配置文件

- **`.github/workflows/build.yml`** - GitHub Actions 工作流配置
- **`dataset_manager.spec`** - PyInstaller 打包配置

---

## ❓ 常见问题

**Q: 如何只构建 Windows 版本？**  
A: 手动触发时取消勾选 macOS 和 Linux

**Q: Artifacts 在哪里？**  
A: Actions → 点击工作流运行 → 页面底部 Artifacts

**Q: 如何删除错误的 Release？**  
A: Releases → 选择版本 → Delete

**Q: 构建失败怎么办？**  
A: 查看 Actions 日志中的错误信息，修复后重新触发

---

## 📝 版本号建议

- 正式版本: `1.0.0`, `1.1.0`, `2.0.0`
- 测试版本: `1.0.0-alpha`, `1.0.0-beta`, `1.0.0-test`

---

**开始你的自动化打包吧！** 🎉

# 贡献指南

感谢你对 EasyTHS 的关注！

## 如何贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 代码规范

- 使用 Ruff 进行代码检查和格式化（`ruff check` / `ruff format`）
- 使用 mypy 进行类型检查
- 安装 pre-commit 钩子，提交前自动执行检查（`uv run pre-commit install`）
- 单元测试放入 `test/unit/`（默认随 `pytest` 运行）；集成测试放入 `test/integration/`（会触发真实交易，仅显式指定路径时运行）
- 更新相关文档

## 报告问题

请在 [Issues](https://github.com/noimank/easyths/issues) 中报告问题。

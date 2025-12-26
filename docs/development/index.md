# 开发指南

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/noimank/easyths.git
cd easyths

# 安装开发依赖
uv sync --group dev

# 运行测试
pytest

# 代码格式化
black easyths/
ruff check easyths/
```

## 项目结构

```
easyths/
├── easyths/        # 源代码
├── test/           # 测试代码
├── docs/           # 文档
└── pyproject.toml  # 项目配置
```

## 下一步

[贡献指南](contributing.md)

# 安装

## 使用 pip 安装

```bash
pip install easyths
```

## 从源码安装

```bash
git clone https://github.com/noimank/easyths.git
cd easyths
pip install -e .
```

## 安装依赖

系统会自动安装以下依赖：

- FastAPI - Web 框架
- pywinauto - Windows GUI 自动化
- redis - 异步任务队列
- 更多依赖请查看 [pyproject.toml](https://github.com/noimank/easyths/blob/main/pyproject.toml)

## 验证安装

```bash
$ easyths --version
EasyTHS v1.0.1
```

## 下一步

[配置说明](configuration.md)

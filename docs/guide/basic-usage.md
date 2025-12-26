# 基础用法

## 启动服务

```bash
easyths
```

服务默认运行在 `http://127.0.0.1:8000`

## API 文档

启动服务后，访问以下地址查看 API 文档：

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## 命令行选项

```bash
$ easyths --help
Usage: easyths [OPTIONS]

  启动 EasyTHS 服务

Options:
  --config PATH  配置文件路径
  --host TEXT    服务器地址
  --port INTEGER 服务器端口
  --help         显示帮助信息
```

## 更多内容

- [API 服务](api.md)
- [常见问题](faq.md)

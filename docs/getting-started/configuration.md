# 配置

EasyTHS 通过 YAML 配置文件管理系统参数。

## 配置文件位置

配置文件默认位于 `config/config.yaml`。

## 基础配置

```yaml
# 服务器配置
server:
  host: "127.0.0.1"
  port: 7648

# Redis 配置
redis:
  host: "localhost"
  port: 6379
  db: 0

# 日志配置
logging:
  level: "INFO"
  file: "logs/easyths.log"
```

## 环境变量

也可以通过环境变量覆盖配置：

```bash
export EASYTHS_SERVER_HOST=0.0.0.0
export EASYTHS_SERVER_PORT=8080
```

## 下一步

[基础用法](../guide/basic-usage.md)

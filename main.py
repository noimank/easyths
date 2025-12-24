#!/usr/bin/env python3
"""开发环境入口 - 调用 easyths.main

Author: noimank
Email: noimank@163.com
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from easyths.main import main

if __name__ == "__main__":
    main()

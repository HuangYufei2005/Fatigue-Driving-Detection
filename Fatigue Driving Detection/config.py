# config.py - 配置文件
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 疲劳记录文件路径
RECORD_FILE_PATH = os.path.join(BASE_DIR, "records", "fatigue_records.txt")

# 导出文件存储目录
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

# 确保目录存在
os.makedirs(os.path.dirname(RECORD_FILE_PATH), exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# 接口返回状态码
STATUS_SUCCESS = 200
STATUS_ERROR = 500
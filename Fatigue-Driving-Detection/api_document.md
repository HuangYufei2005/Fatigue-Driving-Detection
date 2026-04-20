# 疲劳检测后端API文档

## 基础信息
- 基础URL: http://localhost:5000
- 所有接口返回JSON格式

## 接口列表

### 1. 测试接口
- URL: `/test`
- 方法: GET
- 返回: {"code":200, "msg":"Backend running"}

### 2. 启停控制
- URL: `/start_detection`
- 方法: POST
- 请求体: {"action": "start" 或 "stop"}
- 返回: {"code":200, "msg":"检测已启动", "isDetecting":true}

### 3. 核心检测
- URL: `/process_frame`
- 方法: POST
- 请求体: {
    "image_base64": "base64编码的图片",
    "shoot_timestamp": 1646123456.789  # 拍摄时间戳
  }
- 返回: {
    "code": 200,
    "status": "normal/tired/no_face",
    "warning": {  # 触发预警时才有
      "type": "eye/head/both",
      "time": "14:30:25",
      "message": "检测到闭眼疲劳"
    },
    "fatigueData": {
      "eyelidOpening": 0.15,
      "headAngle": -18.5,
      "isEyeTired": true,
      "isHeadTired": false,
      "closeDuration": 0.35,
      "nodInterval": 0
    }
  }

### 4. 阈值管理
- GET `/get_thresholds`: 获取当前阈值
- POST `/update_thresholds`: 更新阈值

### 5. 健康检查
- GET `/health`: 查看服务状态
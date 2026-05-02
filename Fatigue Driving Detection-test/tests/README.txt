# 全流程测试脚本

- `tests/01_camera_video_input_test.py`
- `tests/02_face_eye_yawn_nod_accuracy_test.py`
- `tests/03_fatigue_rule_alarm_test.py`
- `tests/04_realworld_pipeline_test.py`

公共函数在：

- `tests/fatigue_test_common.py`
- `tests/venv_bootstrap.py`

> 现在 4 个测试脚本会优先自动切到项目根目录下的 `.venv` 运行。  
> 所以你仍然可以直接用：`python tests/xx.py`

## 覆盖范围

1. **摄像头/视频能否正常读入**
2. **人脸、眼睛、点头检测联调**
3. **疲劳判定规则 + 报警冷却逻辑**
4. **真实环境/实车回放跑通**

> 注意：当前项目后端 `app.py` **没有实现打哈欠检测输出**。  
> 所以脚本会把 `yawn_detection` 明确标成 `unsupported`，而不是假装测试通过。

## 当前已下载测试视频

已下载并验证可正常读入的视频：

```text
sample_videos\致命的疲劳驾驶 [BV1vJ411H7pQ].mp4
```

该视频已通过 `01_camera_video_input_test.py` 读入测试。

### 摄像头
```powershell
python tests/01_camera_video_input_test.py --camera 0
```

### 视频文件
```powershell
python tests/01_camera_video_input_test.py --video ".\sample_videos\致命的疲劳驾驶 [BV1vJ411H7pQ].mp4"
```

直接验证：
- `/start_detection`
- `/get_thresholds`
- `/update_thresholds`
- `process_frame` 的 stopped / no_face / normal / eye / head / both
- 报警冷却
- 记录写入

```powershell
python tests/03_fatigue_rule_alarm_test.py
```

## 3) 后端回放联调

### 视频回放
```powershell
python tests/02_face_eye_yawn_nod_accuracy_test.py --video ".\sample_videos\致命的疲劳驾驶 [BV1vJ411H7pQ].mp4" --spawn-backend
```

### 带真值标注评估
```powershell
python tests/02_face_eye_yawn_nod_accuracy_test.py --video ".\sample_videos\致命的疲劳驾驶 [BV1vJ411H7pQ].mp4" --truth .\tests\ground_truth_template.json --spawn-backend
```

## 4) 真实环境 / 实车联调

```powershell
python tests/04_realworld_pipeline_test.py --camera 0 --duration-sec 120 --spawn-backend
```

## 输出结果

测试报告默认保存在：

```text
test_outputs/
```

常见文件：
- `io_check_*.json`
- `rule_suite_*.json`
- `replay_events_*.json`
- `replay_summary_*.json`
- `realworld_summary_*.json`

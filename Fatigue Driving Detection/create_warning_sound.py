import numpy as np
import soundfile as sf

# 生成一个简单的警告音（440Hz，0.5秒）
sample_rate = 22050
duration = 0.5
t = np.linspace(0, duration, int(sample_rate * duration))
warning_sound = 0.3 * np.sin(2 * np.pi * 440 * t)

# 保存为WAV文件
sf.write('warning.wav', warning_sound, sample_rate)
print("✅ 已创建 warning.wav 文件")
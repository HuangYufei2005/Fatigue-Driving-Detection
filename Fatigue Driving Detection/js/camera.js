// camera.js - 完整修复版

class CameraModule {
    constructor() {
        console.log('[CameraModule] 初始化...');
        
        // DOM元素
        this.video = document.getElementById('videoElement');
        this.startBtn = document.getElementById('btnStart');
        this.stopBtn = document.getElementById('btnStop');
        
        // 状态元素
        this.detectionStatus = document.getElementById('detectionStatus');
        this.fpsElement = document.getElementById('fpsDisplay');
        this.faceDetectedElement = document.getElementById('faceDetected');
        this.fatigueStatusElement = document.getElementById('fatigueStatus');
        
        // UI函数
        this.addLog = window.addLog || function(msg, type) { 
            console.log(`[${type}] ${msg}`); 
        };
        this.updateRealTimeStatus = window.updateRealTimeStatus || function(s) {};
        this.showWarning = window.showWarning || function(t) {};
        this.updateStatus = window.updateStatus || function(s) {};
        
        // API地址 - 确保端口是5001
        this.apiUrl = 'http://localhost:5001/process_frame';
        this.startStopUrl = 'http://localhost:5001/start_detection';
        this.healthUrl = 'http://localhost:5001/health';
        
        // 状态变量
        this.stream = null;
        this.isCameraActive = false;
        this.isDetecting = false;
        this.isStarting = false;
        this.animationFrame = null;
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        
        // 平滑滤波
        this.smoothFaceBox = null;
        this.smoothAlpha = 0.7;
        
        // 帧率控制
        this.lastFrameTime = 0;
        this.frameInterval = 100; // 10fps
        
        // 绑定事件
        this.bindEvents();
        
        // 检查后端健康状态
        this.checkHealth();
        
        console.log('[CameraModule] 初始化完成');
    }
    
    async checkHealth() {
        try {
            const response = await fetch(this.healthUrl);
            const data = await response.json();
            console.log('[CameraModule] 后端健康检查:', data);
            if (data.code === 200) {
                this.addLog('后端服务连接成功', 'success');
            }
        } catch (error) {
            console.error('[CameraModule] 后端连接失败:', error);
            this.addLog('后端服务未启动，请运行 python app.py', 'error');
        }
    }

    bindEvents() {
        this.startBtn.addEventListener('click', () => {
            console.log('[CameraModule] Start按钮被点击');
            this.start();
        });
        
        this.stopBtn.addEventListener('click', () => {
            console.log('[CameraModule] Stop按钮被点击');
            this.stop();
        });
    }
    
    async start() {
        // 防止重复启动
        if (this.isStarting || this.isDetecting) {
            console.log('[CameraModule] 已经在启动或运行中，跳过');
            return;
        }
        
        this.isStarting = true;
        console.log('[CameraModule] 启动流程开始...');
        
        try {
            // 1. 先启动后端检测
            this.addLog('正在连接后端服务...', 'info');
            const response = await fetch(this.startStopUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: "start" })
            });
            const result = await response.json();
            console.log('[CameraModule] 后端启动响应:', result);
            
            if (result.code === 200) {
                this.addLog('后端检测已启动', 'success');
            } else {
                this.addLog('后端启动失败: ' + result.msg, 'error');
                this.isStarting = false;
                return;
            }
            
            // 2. 启动摄像头
            await this.startCamera();
            
            // 3. 开始检测循环
            if (this.isCameraActive) {
                this.startDetectionLoop();
                this.addLog('检测循环已启动', 'success');
            }
        } catch (error) {
            console.error('[CameraModule] 启动失败:', error);
            this.addLog('启动失败: ' + error.message, 'error');
        } finally {
            this.isStarting = false;
        }
    }
    
    async stop() {
        console.log('[CameraModule] 停止流程开始...');
        
        // 1. 停止检测循环
        this.stopDetectionLoop();
        
        // 2. 关闭摄像头
        this.stopCamera();
        
        // 3. 停止后端检测
        try {
            const response = await fetch(this.startStopUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: "stop" })
            });
            const result = await response.json();
            console.log('[CameraModule] 后端停止响应:', result);
            if (result.code === 200) {
                this.addLog('后端检测已停止', 'success');
            }
        } catch (error) {
            console.error('[CameraModule] 后端停止失败:', error);
        }
    }

    async startCamera() {
        if (this.isCameraActive) {
            console.log('[CameraModule] 摄像头已开启，跳过');
            return;
        }
        
        console.log('[CameraModule] 开启摄像头...');
        this.addLog('正在开启摄像头...', 'info');

        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { 
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    frameRate: { ideal: 15 }
                }
            });

            this.video.srcObject = this.stream;
            this.isCameraActive = true;
            
            // 显示视频
            this.video.style.display = 'block';
            const placeholder = document.getElementById('cameraPlaceholder');
            if (placeholder) placeholder.style.display = 'none';
            
            // 更新按钮状态
            this.startBtn.disabled = true;
            this.stopBtn.disabled = false;
            
            this.addLog('摄像头开启成功', 'success');
            
            // 等待视频准备就绪
            await new Promise((resolve) => {
                if (this.video.readyState >= 2) {
                    resolve();
                } else {
                    this.video.onloadedmetadata = () => {
                        this.video.play();
                        resolve();
                    };
                }
            });
            
            console.log('[CameraModule] 摄像头已就绪，尺寸:', this.video.videoWidth, 'x', this.video.videoHeight);

        } catch (error) {
            console.error('[CameraModule] 摄像头错误:', error);
            this.addLog('摄像头开启失败: ' + error.message, 'error');
            this.isCameraActive = false;
        }
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
            this.video.srcObject = null;
        }

        this.isCameraActive = false;
        this.video.style.display = 'none';
        
        const placeholder = document.getElementById('cameraPlaceholder');
        if (placeholder) placeholder.style.display = 'block';
        
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        
        if (window.drawModule) {
            window.drawModule.clearCanvas();
        }
        
        this.addLog('摄像头已关闭', 'info');
    }

    startDetectionLoop() {
        if (this.isDetecting) return;
        
        console.log('[CameraModule] 启动检测循环');
        this.isDetecting = true;
        this.canvas.width = 640;
        this.canvas.height = 480;
        this.lastFrameTime = performance.now();
        
        const loop = () => {
            if (!this.isDetecting) return;
            
            const now = performance.now();
            const elapsed = now - this.lastFrameTime;
            
            if (elapsed >= this.frameInterval) {
                this.captureAndSend();
                this.lastFrameTime = now;
            }
            
            this.animationFrame = requestAnimationFrame(loop);
        };
        
        this.animationFrame = requestAnimationFrame(loop);
        console.log('[CameraModule] 检测循环已启动，帧间隔:', this.frameInterval, 'ms');
    }

    stopDetectionLoop() {
        console.log('[CameraModule] 停止检测循环');
        this.isDetecting = false;
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }
    }

    async captureAndSend() {
        if (!this.isDetecting || !this.video || this.video.readyState !== this.video.HAVE_ENOUGH_DATA) {
            return;
        }

        try {
            // 捕获当前帧
            this.ctx.drawImage(this.video, 0, 0, 640, 480);
            const base64Data = this.canvas.toDataURL('image/jpeg', 0.7).split(',')[1];
            
            // 发送到后端
            const response = await fetch(this.apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_base64: base64Data,
                    shoot_timestamp: Date.now() / 1000
                })
            });
            
            const result = await response.json();
            this.handleResult(result);
            
        } catch (error) {
            console.error('[CameraModule] 发送失败:', error);
        }
    }
    
    smoothBox(newBox) {
        if (!this.smoothFaceBox) {
            this.smoothFaceBox = [...newBox];
            return newBox;
        }
        
        const alpha = this.smoothAlpha;
        const smoothed = this.smoothFaceBox.map((val, i) => 
            val * alpha + newBox[i] * (1 - alpha)
        );
        this.smoothFaceBox = smoothed;
        return smoothed;
    }
    
    handleResult(result) {
        if (result.code !== 200) {
            console.log('[CameraModule] 结果错误:', result);
            return;
        }
        
        // 获取绘制数据
        let faceBox = result.face_box;
        const eyePoints = result.eye_points;
        const headPoints = result.head_points;
        const status = result.status;
        const fatigueData = result.fatigueData || {};
        const isFatigue = status === 'tired';
        
        // 平滑人脸框
        if (faceBox && faceBox.length === 4 && faceBox[2] > 0) {
            faceBox = this.smoothBox(faceBox);
        }
        
        // 更新人脸检测状态显示
        const faceDetected = faceBox && faceBox.length === 4 && faceBox[2] > 0;
        if (this.faceDetectedElement) {
            this.faceDetectedElement.textContent = faceDetected ? '是' : '否';
        }
        
        // 更新疲劳状态显示
        if (this.fatigueStatusElement) {
            if (isFatigue) {
                if (fatigueData.isEyeTired && fatigueData.isHeadTired) {
                    this.fatigueStatusElement.textContent = '多重疲劳';
                } else if (fatigueData.isEyeTired) {
                    this.fatigueStatusElement.textContent = '眼睛疲劳';
                } else if (fatigueData.isHeadTired) {
                    this.fatigueStatusElement.textContent = '头部疲劳';
                }
            } else if (status === 'no_face') {
                this.fatigueStatusElement.textContent = '无人脸';
            } else {
                this.fatigueStatusElement.textContent = '正常';
            }
        }
        
        // 更新UI状态
        if (this.updateStatus) {
            if (isFatigue) {
                this.updateStatus('warning');
            } else if (faceDetected) {
                this.updateStatus('active');
            }
        }
        
        if (this.updateRealTimeStatus) {
            if (isFatigue) {
                this.updateRealTimeStatus('fatigue');
            } else if (faceDetected) {
                this.updateRealTimeStatus('normal');
            } else if (status === 'no_face') {
                this.updateRealTimeStatus('exception');
            }
        }
        
        // 显示预警弹窗
        if (isFatigue && this.showWarning) {
            let fatigueType = 'eye';
            if (fatigueData.isEyeTired && fatigueData.isHeadTired) {
                fatigueType = 'both';
            } else if (fatigueData.isHeadTired) {
                fatigueType = 'head';
            }
            this.showWarning(fatigueType);
            this.addLog(`⚠️ 疲劳预警`, 'warning');
        }
        
        // 绘制标注
        this.drawAnnotations(faceBox, eyePoints, headPoints, isFatigue, fatigueData);
    }
    
    drawAnnotations(faceBox, eyePoints, headPoints, isFatigue, fatigueData) {
        const drawModule = window.drawModule;
        if (!drawModule) {
            console.warn('[CameraModule] drawModule 未找到');
            return;
        }
        
        drawModule.clearCanvas();
        
        if (!faceBox || faceBox.length !== 4 || faceBox[2] <= 0) {
            return;
        }
        
        // 获取画布实际尺寸
        const canvas = drawModule.canvas;
        const canvasRect = canvas.getBoundingClientRect();
        
        if (canvasRect.width === 0 || canvasRect.height === 0) {
            return;
        }
        
        // 计算缩放比例（源图像640x480 -> 画布实际尺寸）
        const scaleX = canvasRect.width / 640;
        const scaleY = canvasRect.height / 480;
        
        // 缩放人脸框
        const [x, y, w, h] = faceBox;
        const scaledBox = [x * scaleX, y * scaleY, w * scaleX, h * scaleY];
        
        // 缩放眼睛点
        let scaledEyePoints = [];
        if (eyePoints && eyePoints.length > 0) {
            scaledEyePoints = eyePoints.map(p => [p[0] * scaleX, p[1] * scaleY]);
        }
        
        // 缩放头部点
        let scaledHeadPoints = [];
        if (headPoints && headPoints.length > 0) {
            scaledHeadPoints = headPoints.map(p => [p[0] * scaleX, p[1] * scaleY]);
        }
        
        // 绘制
        drawModule.drawFaceBox(scaledBox, isFatigue, 0.95);
        
        if (scaledEyePoints.length > 0) {
            drawModule.drawEyePoints(scaledEyePoints);
        }
        
        if (scaledHeadPoints.length > 0) {
            drawModule.drawHeadPoints(scaledHeadPoints);
        }
        
        // 显示疲劳状态
        if (drawModule.showFatigueState) {
            if (isFatigue) {
                let fatigueType = 'normal';
                if (fatigueData?.isEyeTired && fatigueData?.isHeadTired) {
                    fatigueType = 'both';
                } else if (fatigueData?.isEyeTired) {
                    fatigueType = 'eye_fatigue';
                } else if (fatigueData?.isHeadTired) {
                    fatigueType = 'nod_fatigue';
                }
                drawModule.showFatigueState(fatigueType, fatigueData?.headAngle, fatigueData?.eyelidOpening);
            } else {
                drawModule.showFatigueState('normal');
            }
        }
        
        console.log('[CameraModule] 绘制完成, 人脸框:', scaledBox.map(v => v.toFixed(0)));
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('[CameraModule] DOM加载完成，初始化...');
    window.cameraModule = new CameraModule();
});
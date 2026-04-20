// draw.js - 完整美观版

class DrawModule {
    constructor() {
        this.canvas = document.getElementById('detectionCanvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.video = document.getElementById('videoElement');

        if (!this.canvas || !this.ctx) {
            console.error('画布初始化失败');
            return;
        }

        this.ctx.imageSmoothingEnabled = true;
        this.initResizeObserver();
        console.log('绘制模块初始化完成');
    }

    initResizeObserver() {
        if (!this.video) return;
        const resizeObserver = new ResizeObserver(() => this.resizeCanvas());
        resizeObserver.observe(this.video);
        setTimeout(() => this.resizeCanvas(), 100);
    }

    resizeCanvas() {
        if (!this.canvas || !this.video) return;
        const videoRect = this.video.getBoundingClientRect();
        if (this.canvas.width !== videoRect.width || this.canvas.height !== videoRect.height) {
            this.canvas.width = videoRect.width;
            this.canvas.height = videoRect.height;
            console.log(`画布尺寸调整为: ${videoRect.width}x${videoRect.height}`);
        }
    }

    clearCanvas() {
        if (!this.ctx || !this.canvas) return;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    /**
     * 绘制圆角矩形
     */
    drawRoundedRect(x, y, w, h, radius) {
        if (!this.ctx) return;
        this.ctx.beginPath();
        this.ctx.moveTo(x + radius, y);
        this.ctx.lineTo(x + w - radius, y);
        this.ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
        this.ctx.lineTo(x + w, y + h - radius);
        this.ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
        this.ctx.lineTo(x + radius, y + h);
        this.ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
        this.ctx.lineTo(x, y + radius);
        this.ctx.quadraticCurveTo(x, y, x + radius, y);
        this.ctx.closePath();
    }

    /**
     * 绘制渐变边框人脸框
     */
    drawFaceBox(box, isFatigue = false, confidence = 1.0) {
        if (!this.ctx || !box || box.length < 4) return;

        const [x, y, w, h] = box;
        
        // 根据疲劳程度选择颜色
        let color1, color2;
        if (isFatigue) {
            color1 = '#ff4444';
            color2 = '#ff8800';
        } else {
            color1 = '#00aaff';
            color2 = '#00ffcc';
        }
        
        // 创建线性渐变
        const gradient = this.ctx.createLinearGradient(x, y, x + w, y + h);
        gradient.addColorStop(0, color1);
        gradient.addColorStop(1, color2);
        
        this.ctx.save();
        
        // 绘制外发光效果
        this.ctx.shadowBlur = 10;
        this.ctx.shadowColor = isFatigue ? 'rgba(255, 68, 68, 0.5)' : 'rgba(0, 170, 255, 0.5)';
        
        // 绘制圆角矩形边框
        this.ctx.strokeStyle = gradient;
        this.ctx.lineWidth = 3;
        this.drawRoundedRect(x, y, w, h, 12);
        this.ctx.stroke();
        
        // 关闭阴影
        this.ctx.shadowBlur = 0;
        
        // 绘制边框内层（双线效果）
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        this.ctx.lineWidth = 1;
        this.drawRoundedRect(x + 2, y + 2, w - 4, h - 4, 10);
        this.ctx.stroke();
        
        // 绘制角落装饰
        this.drawCornerDecorations(x, y, w, h, color1);
        
        // 绘制标签
        const labelText = isFatigue ? '⚠️ 疲劳预警' : '✓ 人脸检测';
        const labelBgWidth = this.ctx.measureText(labelText).width + 20;
        const labelBgHeight = 24;
        
        this.ctx.fillStyle = isFatigue ? 'rgba(255, 68, 68, 0.9)' : 'rgba(0, 100, 150, 0.9)';
        this.ctx.beginPath();
        this.drawRoundedRect(x + 5, y - labelBgHeight - 2, labelBgWidth, labelBgHeight, 6);
        this.ctx.fill();
        
        // 绘制标签文字
        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = 'bold 13px "Segoe UI", Arial, sans-serif';
        this.ctx.fillText(labelText, x + 12, y - 8);
        
        // 绘制置信度条
        if (confidence < 1.0) {
            const barWidth = w - 20;
            const barHeight = 4;
            const barX = x + 10;
            const barY = y + h + 8;
            
            this.ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
            this.ctx.fillRect(barX, barY, barWidth, barHeight);
            
            const confidenceGradient = this.ctx.createLinearGradient(barX, barY, barX + barWidth * confidence, barY);
            confidenceGradient.addColorStop(0, color1);
            confidenceGradient.addColorStop(1, color2);
            this.ctx.fillStyle = confidenceGradient;
            this.ctx.fillRect(barX, barY, barWidth * confidence, barHeight);
        }
        
        this.ctx.restore();
    }
    
    /**
     * 绘制角落装饰
     */
    drawCornerDecorations(x, y, w, h, color) {
        const cornerLength = 20;
        const lineWidth = 3;
        
        this.ctx.save();
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = lineWidth;
        
        // 左上角
        this.ctx.beginPath();
        this.ctx.moveTo(x, y + cornerLength);
        this.ctx.lineTo(x, y);
        this.ctx.lineTo(x + cornerLength, y);
        this.ctx.stroke();
        
        // 右上角
        this.ctx.beginPath();
        this.ctx.moveTo(x + w - cornerLength, y);
        this.ctx.lineTo(x + w, y);
        this.ctx.lineTo(x + w, y + cornerLength);
        this.ctx.stroke();
        
        // 左下角
        this.ctx.beginPath();
        this.ctx.moveTo(x, y + h - cornerLength);
        this.ctx.lineTo(x, y + h);
        this.ctx.lineTo(x + cornerLength, y + h);
        this.ctx.stroke();
        
        // 右下角
        this.ctx.beginPath();
        this.ctx.moveTo(x + w - cornerLength, y + h);
        this.ctx.lineTo(x + w, y + h);
        this.ctx.lineTo(x + w, y + h - cornerLength);
        this.ctx.stroke();
        
        this.ctx.restore();
    }

    /**
     * 绘制眼睛关键点（带光晕效果）
     */
    drawEyePoints(eyePoints) {
        if (!this.ctx || !eyePoints || !eyePoints.length) return;
        
        this.ctx.save();
        
        // 先绘制光晕
        eyePoints.forEach(point => {
            if (point && point.length >= 2) {
                const [x, y] = point;
                this.ctx.beginPath();
                this.ctx.arc(x, y, 6, 0, 2 * Math.PI);
                this.ctx.fillStyle = 'rgba(0, 255, 100, 0.2)';
                this.ctx.fill();
            }
        });
        
        // 再绘制点
        eyePoints.forEach(point => {
            if (point && point.length >= 2) {
                const [x, y] = point;
                
                // 外圈
                this.ctx.beginPath();
                this.ctx.arc(x, y, 4, 0, 2 * Math.PI);
                this.ctx.fillStyle = '#00ff66';
                this.ctx.fill();
                
                // 内圈
                this.ctx.beginPath();
                this.ctx.arc(x, y, 2, 0, 2 * Math.PI);
                this.ctx.fillStyle = '#ffffff';
                this.ctx.fill();
                
                // 高光
                this.ctx.beginPath();
                this.ctx.arc(x - 1, y - 1, 1, 0, 2 * Math.PI);
                this.ctx.fillStyle = '#ffffff';
                this.ctx.fill();
            }
        });
        
        this.ctx.restore();
    }

    /**
     * 绘制头部关键点
     */
    drawHeadPoints(headPoints) {
        if (!this.ctx || !headPoints || !headPoints.length) return;
        
        this.ctx.save();
        
        headPoints.forEach(point => {
            if (point && point.length >= 2) {
                const [x, y] = point;
                
                // 外圈
                this.ctx.beginPath();
                this.ctx.arc(x, y, 5, 0, 2 * Math.PI);
                this.ctx.fillStyle = 'rgba(255, 200, 0, 0.3)';
                this.ctx.fill();
                
                // 内圈
                this.ctx.beginPath();
                this.ctx.arc(x, y, 3, 0, 2 * Math.PI);
                this.ctx.fillStyle = '#ffcc00';
                this.ctx.fill();
                
                // 中心点
                this.ctx.beginPath();
                this.ctx.arc(x, y, 1.5, 0, 2 * Math.PI);
                this.ctx.fillStyle = '#ffffff';
                this.ctx.fill();
            }
        });
        
        this.ctx.restore();
    }

    /**
     * 显示疲劳状态文字
     */
    showFatigueState(state, headAngle = 0, eyelidOpening = 0) {
        if (!this.ctx || !this.canvas) return;
        
        this.ctx.save();
        
        // 根据状态选择样式
        let bgColor, textColor, icon, title;
        switch (state) {
            case 'eye_fatigue':
                bgColor = 'rgba(220, 38, 38, 0.85)';
                textColor = '#ffffff';
                icon = '😴';
                title = '眼睛疲劳';
                break;
            case 'nod_fatigue':
                bgColor = 'rgba(245, 158, 11, 0.85)';
                textColor = '#ffffff';
                icon = '😵';
                title = '点头疲劳';
                break;
            case 'both':
                bgColor = 'rgba(220, 38, 38, 0.95)';
                textColor = '#ffffff';
                icon = '⚠️';
                title = '严重疲劳';
                break;
            default:
                bgColor = 'rgba(5, 150, 105, 0.8)';
                textColor = '#ffffff';
                icon = '✅';
                title = '状态正常';
        }
        
        // 绘制背景卡片
        const cardWidth = 200;
        const cardHeight = 70;
        const cardX = 15;
        const cardY = 15;
        
        this.ctx.fillStyle = bgColor;
        this.ctx.shadowBlur = 10;
        this.ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
        this.ctx.beginPath();
        this.drawRoundedRect(cardX, cardY, cardWidth, cardHeight, 12);
        this.ctx.fill();
        
        // 绘制状态文字
        this.ctx.shadowBlur = 0;
        this.ctx.font = 'bold 20px "Segoe UI", Arial, sans-serif';
        this.ctx.fillStyle = textColor;
        this.ctx.fillText(`${icon} ${title}`, cardX + 15, cardY + 30);
        
        // 显示具体数据
        if (headAngle !== 0 || eyelidOpening !== 0) {
            this.ctx.font = '12px "Segoe UI", Arial, sans-serif';
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            this.ctx.fillText(
                `睁眼度: ${(eyelidOpening * 100).toFixed(0)}%  |  头部角度: ${headAngle.toFixed(1)}°`,
                cardX + 15,
                cardY + 52
            );
        }
        
        this.ctx.restore();
    }
}

// 添加 roundRect 方法
if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
        if (w < 2 * r) r = w / 2;
        if (h < 2 * r) r = h / 2;
        this.moveTo(x + r, y);
        this.lineTo(x + w - r, y);
        this.quadraticCurveTo(x + w, y, x + w, y + r);
        this.lineTo(x + w, y + h - r);
        this.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        this.lineTo(x + r, y + h);
        this.quadraticCurveTo(x, y + h, x, y + h - r);
        this.lineTo(x, y + r);
        this.quadraticCurveTo(x, y, x + r, y);
        return this;
    };
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    window.drawModule = new DrawModule();
});
#!/usr/bin/env python3
# YOLO训练脚本模板 - 使用Jinja2模板引擎生成

import os
import sys

# 添加ultralytics到路径
try:
    from ultralytics import YOLO
except ImportError:
    print("请安装ultralytics: pip install ultralytics")
    sys.exit(1)


def train_model():
    """执行YOLO模型训练"""
    # 获取数据配置文件路径（使用相对路径）
    data_yaml = 'train.yml'
    
    # 检查配置文件是否存在
    if not os.path.exists(data_yaml):
        print(f"配置文件不存在: {data_yaml}")
        return
    
    # 创建模型实例
    model = YOLO('yolov8n.pt')  # 默认使用yolov8n，可根据需要修改
    
    # 训练参数
    train_args = {
        'data': data_yaml,
{% if custom_params %}
        # 用户自定义参数（会覆盖默认参数）
{% for key, value in custom_params.items() %}
        '{{ key }}': {{ value }},
{% endfor %}
{% endif %}
{% if not custom_params or 'epochs' not in custom_params %}
        'epochs': 100,
{% endif %}
{% if not custom_params or 'batch' not in custom_params %}
        'batch': 16,
{% endif %}
{% if not custom_params or 'imgsz' not in custom_params %}
        'imgsz': 640,
{% endif %}
    }
    
    print(f"开始训练模型，参数: {train_args}")
    
    # 开始训练
    try:
        model.train(**train_args)
        print("训练完成!")
    except Exception as e:
        print(f"训练过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    train_model()

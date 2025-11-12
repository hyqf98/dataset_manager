#!/usr/bin/env python3
# YOLO训练脚本模板 - 使用Jinja2模板引擎生成

import os
import sys
import argparse

# 添加ultralytics到路径
try:
    from ultralytics import YOLO
except ImportError:
    print("请安装ultralytics: pip install ultralytics")
    sys.exit(1)


def find_best_model():
    """查找最佳模型文件"""
    best_model_path = 'runs/detect/train/weights/best.pt'
    
    if os.path.exists(best_model_path):
        return best_model_path
    return None


def train_model(custom_params=None):
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
        'epochs': 300,
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


def val_model(custom_params=None):
    """执行YOLO模型验证"""
    # 获取数据配置文件路径（使用相对路径）
    data_yaml = 'train.yml'
    
    # 检查配置文件是否存在
    if not os.path.exists(data_yaml):
        print(f"配置文件不存在: {data_yaml}")
        return
    
    # 查找最佳模型文件
    best_model_path = find_best_model()
    if not best_model_path or not os.path.exists(best_model_path):
        print("未找到最佳模型: runs/detect/train/weights/best.pt")
        return
    
    print(f"使用最佳模型: {best_model_path}")
    model = YOLO(best_model_path)
    
    # 验证参数
    val_args = {
        'data': data_yaml,
    }
    
    # 如果提供了自定义参数，则更新默认参数
    if custom_params:
        val_args.update(custom_params)
    
    print(f"开始验证模型，参数: {val_args}")
    
    # 开始验证
    try:
        results = model.val(**val_args)
        print("验证完成!")
        
        # 计算百分比指标
        map_percent = results.box.map * 100
        map50_percent = results.box.map50 * 100
        map75_percent = results.box.map75 * 100
        precision_percent = results.box.p.mean() * 100
        recall_percent = results.box.r.mean() * 100
        f1_percent = results.box.f1.mean() * 100
        
        # 打印关键指标（以百分比显示）
        print("\n=== 验证结果 ===")
        print(f"mAP: {map_percent:.2f}%")
        print(f"mAP50: {map50_percent:.2f}%")
        print(f"mAP75: {map75_percent:.2f}%")
        print(f"Precision: {precision_percent:.2f}%")
        print(f"Recall: {recall_percent:.2f}%")
        print(f"F1-Score: {f1_percent:.2f}%")
        
        # 模型质量评估和改进建议（基于mAP指标评估）
        print("\n=== 模型质量评估 ===")
        if map_percent >= 80:
            print("🟢 模型质量优秀 (mAP >= 80%)")
        elif map_percent >= 60:
            print("🟡 模型质量良好 (60% <= mAP < 80%)")
        elif map_percent >= 40:
            print("🟠 模型质量一般 (40% <= mAP < 60%)")
        else:
            print("🔴 模型质量较差 (mAP < 40%)")
            
        # 根据mAP50和mAP75的差异提供额外评估
        if map50_percent - map75_percent > 20:
            print("\n⚠️  注意: mAP50与mAP75差距较大，说明模型在定位精度上可能存在问题")
            
        if map_percent < 60:
            print("\n💡 改进建议:")
            print("1. 增加训练轮数 (epochs)")
            print("2. 调整学习率")
            print("3. 增加训练数据量和多样性")
            print("4. 尝试使用更大的模型")
            print("5. 检查标注质量")
            print("6. 调整数据增强策略")
            
        if precision_percent > 90 and recall_percent < 70:
            print("\n⚠️  注意: 精度过高但召回率较低，可能存在过拟合或漏检问题")
        elif recall_percent > 90 and precision_percent < 70:
            print("\n⚠️  注意: 召回率过高但精度较低，可能存在过多误检")
            
    except Exception as e:
        print(f"验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


def benchmark_model(custom_params=None):
    """执行YOLO模型基准测试"""
    # 查找最佳模型文件
    best_model_path = find_best_model()
    if not best_model_path or not os.path.exists(best_model_path):
        print("未找到最佳模型: runs/detect/train/weights/best.pt")
        return
    
    print(f"使用最佳模型: {best_model_path}")
    model = YOLO(best_model_path)
    
    # 基准测试参数
    bench_args = {
        'imgsz': 640,  # 默认图像尺寸
        'device': 0,   # 默认设备为GPU
    }
    
    # 如果提供了自定义参数，则更新默认参数
    if custom_params:
        bench_args.update(custom_params)
    
    print(f"开始基准测试，参数: {bench_args}")
    
    # 开始基准测试
    try:
        results = model.benchmark(**bench_args)
        print("基准测试完成!")
        
        # 打印关键指标
        print("\n=== 基准测试结果 ===")
        if hasattr(results, 'speed') and results.speed:
            print(f"推理速度: {results.speed:.2f} ms/img")
        if hasattr(results, 'fps') and results.fps:
            print(f"帧率: {results.fps:.2f} FPS")
            
        # 性能评估和改进建议
        print("\n=== 性能评估 ===")
        if hasattr(results, 'speed'):
            if results.speed <= 20:
                print("🟢 推理速度优秀 (<= 20ms/img)")
            elif results.speed <= 50:
                print("🟡 推理速度良好 (20-50ms/img)")
            elif results.speed <= 100:
                print("🟠 推理速度一般 (50-100ms/img)")
            else:
                print("🔴 推理速度较慢 (> 100ms/img)")
                
            if results.speed > 50:
                print("\n💡 性能优化建议:")
                print("1. 使用模型量化技术")
                print("2. 尝试更小的模型版本")
                print("3. 使用模型剪枝")
                print("4. 考虑使用TensorRT等推理优化工具")
                print("5. 降低输入图像尺寸")
                
    except Exception as e:
        print(f"基准测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


def parse_custom_params(param_list):
    """解析自定义参数列表"""
    custom_params = {}
    if param_list:
        for param in param_list:
            if '=' in param:
                key, value = param.split('=', 1)
                # 尝试转换为数字或布尔值
                if value.isdigit():
                    custom_params[key] = int(value)
                elif value.replace('.', '').isdigit():
                    custom_params[key] = float(value)
                elif value.lower() in ['true', 'false']:
                    custom_params[key] = value.lower() == 'true'
                else:
                    custom_params[key] = value
            else:
                print(f"警告: 参数 '{param}' 格式不正确，应为 key=value 形式")
    return custom_params


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YOLO模型训练、验证和基准测试脚本')
    parser.add_argument('mode', choices=['train', 'val', 'benchmark'], 
                        help='选择运行模式: train(训练), val(验证), benchmark(基准测试)')
    parser.add_argument('--params', nargs='*', 
                        help='自定义参数，格式为 key=value，例如 epochs=50 imgsz=640')
    
    args = parser.parse_args()
    
    # 解析自定义参数
    custom_params = parse_custom_params(args.params)
    
    # 根据模式调用相应函数
    if args.mode == 'train':
        train_model(custom_params)
    elif args.mode == 'val':
        val_model(custom_params)
    elif args.mode == 'benchmark':
        benchmark_model(custom_params)

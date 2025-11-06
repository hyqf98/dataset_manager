import os
import cv2
from PyQt5.QtCore import QRect, QPoint


def save_yolo_annotations(file_path, image_label, class_names):
    """
    保存YOLO格式的标注文件
    
    Args:
        file_path (str): 图片文件路径
        image_label (ImageLabel): 图片标注组件
        class_names (list): 类别名称列表
    """
    # 获取图片尺寸
    pixmap = image_label.pixmap
    if not pixmap:
        return
        
    img_width = pixmap.width()
    img_height = pixmap.height()
    
    # 获取标注信息
    annotations = image_label.get_annotations()
    
    if not annotations:
        # 如果没有标注，删除标注文件
        _remove_annotation_files(file_path)
        return
    
    # 创建labels目录
    labels_dir = os.path.join(os.path.dirname(file_path), 'labels')
    os.makedirs(labels_dir, exist_ok=True)
    
    # 生成类别名称文件到labels目录中
    classes_file = os.path.join(labels_dir, 'classes.txt')
    with open(classes_file, 'w', encoding='utf-8') as f:
        for class_name in class_names:
            f.write(f"{class_name}\n")
    
    # 生成标注文件
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    annotation_file = os.path.join(labels_dir, f"{base_name}.txt")
    
    with open(annotation_file, 'w', encoding='utf-8') as f:
        for annotation in annotations:
            if annotation['type'] == 'rectangle' and annotation.get('label'):
                # 获取类别ID
                class_id = _get_class_id(annotation['label'], class_names)
                
                # 计算YOLO格式的坐标 (中心点x, 中心点y, 宽度, 高度，都是归一化值)
                rect = annotation['rectangle']
                x_center = (rect.x() + rect.width() / 2) / img_width
                y_center = (rect.y() + rect.height() / 2) / img_height
                width = rect.width() / img_width
                height = rect.height() / img_height
                
                # 写入YOLO格式: class_id x_center y_center width height
                f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            elif annotation['type'] == 'polygon' and annotation.get('label'):
                # 获取类别ID
                class_id = _get_class_id(annotation['label'], class_names)
                
                # 写入多边形格式: class_id 0 points_count x1 y1 x2 y2 ...
                points = annotation['points']
                points_str = ' '.join([f"{p.x() / img_width:.6f} {p.y() / img_height:.6f}" for p in points])
                f.write(f"{class_id} 0 {len(points)} {points_str}\n")


def load_yolo_annotations(file_path, class_names, annotation_file=None):
    """
    加载YOLO格式的标注文件
    
    Args:
        file_path (str): 图片文件路径
        class_names (list): 类别名称列表
        annotation_file (str, optional): 标注文件路径，如果未提供则使用默认路径
        
    Returns:
        list: 标注信息列表
    """
    # 如果没有提供标注文件路径，则使用默认路径
    if annotation_file is None:
        # 生成标注文件路径
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        labels_dir = os.path.join(os.path.dirname(file_path), 'labels')
        annotation_file = os.path.join(labels_dir, f"{base_name}.txt")
    
    annotations = []
    
    # 检查标注文件是否存在
    if not os.path.exists(annotation_file):
        return annotations
    
    # 读取标注文件
    with open(annotation_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # 获取图片尺寸
    # 使用opencv获取图片尺寸
    img = cv2.imread(file_path)
    if img is not None:
        img_height, img_width = img.shape[:2]
    else:
        # 如果无法读取图片，返回空的标注列表
        return annotations
    
    # 解析每一行
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 5:
            continue
            
        class_id = int(float(parts[0]))
        
        # 获取类别名称
        if 0 <= class_id < len(class_names):
            label = class_names[class_id]
        else:
            label = f"unknown_{class_id}"
        
        # 判断是矩形还是多边形
        if len(parts) == 5 and parts[1] != '0':  # 矩形格式
            x_center, y_center, width, height = map(float, parts[1:])
            
            # 转换为像素坐标
            x = int((x_center - width / 2) * img_width)
            y = int((y_center - height / 2) * img_height)
            w = int(width * img_width)
            h = int(height * img_height)
            
            # 创建矩形标注信息
            rect = QRect(x, y, w, h)
            annotations.append({
                'type': 'rectangle',
                'rectangle': rect,
                'label': label
            })
        elif len(parts) >= 5 and parts[1] == '0':  # 多边形格式
            points_count = int(float(parts[2]))
            points_data = parts[3:]
            
            # 确保点数据完整
            if len(points_data) == points_count * 2:
                points = []
                for i in range(0, len(points_data), 2):
                    x = int(float(points_data[i]) * img_width)
                    y = int(float(points_data[i+1]) * img_height)
                    points.append(QPoint(x, y))
                
                # 创建多边形标注信息
                annotations.append({
                    'type': 'polygon',
                    'points': points,
                    'label': label
                })
    
    return annotations


def _get_class_id(class_name, class_names):
    """
    获取类别ID，如果不存在则添加到列表中
    
    Args:
        class_name (str): 类别名称
        class_names (list): 类别名称列表
        
    Returns:
        int: 类别ID
    """
    if class_name in class_names:
        return class_names.index(class_name)
    else:
        class_names.append(class_name)
        return len(class_names) - 1


def _remove_annotation_files(file_path):
    """
    删除标注文件
    
    Args:
        file_path (str): 图片文件路径
    """
    # 生成标注文件路径
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    labels_dir = os.path.join(os.path.dirname(file_path), 'labels')
    annotation_file = os.path.join(labels_dir, f"{base_name}.txt")
    classes_file = os.path.join(labels_dir, 'classes.txt')
    
    # 删除标注文件
    if os.path.exists(annotation_file):
        os.remove(annotation_file)
    
    # 如果labels目录为空，删除目录
    if os.path.exists(labels_dir) and not os.listdir(labels_dir):
        os.rmdir(labels_dir)
    
    # 检查是否还有其他标注文件，如果没有则删除classes.txt
    has_other_annotations = False
    if os.path.exists(labels_dir):
        for file in os.listdir(labels_dir):
            if file.endswith('.txt') and file != 'classes.txt':
                has_other_annotations = True
                break
    
    if not has_other_annotations and os.path.exists(classes_file):
        os.remove(classes_file)
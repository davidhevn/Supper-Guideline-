import json
import os
import random
import sys

# Khắc phục lỗi in tiếng Việt trên terminal Windows
sys.stdout.reconfigure(encoding='utf-8')
import random

def parse_tfrecord_to_json(tfrecord_path):
    print(f"[*] Đang đọc và trích xuất dữ liệu từ: {tfrecord_path}")
    
    try:
        import sys
        import os
        # Ép dùng protobuf pure-python để tránh lỗi Descriptors cannot be created directly
        os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
        
        # Chèn đường dẫn cục bộ chứa mã nguồn Waymo đã dịch protobuf
        sys.path.insert(0, r"E:\Cac du an visual\Waymo data set\waymo_extracted")
        
        import tensorflow as tf
        from waymo_open_dataset.protos import scenario_pb2
        
        # Thử đọc TFRecord thật
        dataset = tf.data.TFRecordDataset(tfrecord_path, compression_type='')
        for data in dataset.take(1):
            scenario = scenario_pb2.Scenario()
            scenario.ParseFromString(data.numpy())
            print(f"[+] Trích xuất thành công Scenario ID: {scenario.scenario_id}")
            
            # Trích xuất động lực học (Tracks)
            extracted_tracks = []
            # Lấy 20 object để bao quát được SDC
            for i, track in enumerate(list(scenario.tracks)[:20]):
                states = []
                for state in track.states[:50]: # Lấy 50 frame đầu
                    states.append({
                        "valid": getattr(state, 'valid', True),
                        "x": getattr(state, 'center_x', 0),
                        "y": getattr(state, 'center_y', 0),
                        "velocity": getattr(state, 'velocity_x', 0) * 3.6 # Quy đổi ra km/h nếu là m/s
                    })
                extracted_tracks.append({
                    "id": getattr(track, 'id', i),
                    "object_type": track.object_type,
                    "states": states
                })
                
            # Lấy index của xe SDC
            sdc_track_index = getattr(scenario, 'sdc_track_index', 0)
                
            # Trích xuất bản đồ (Map Features)
            extracted_map_features = []
            for mf in list(scenario.map_features)[:50]: # Lấy 50 object map để vẽ nền
                feature_type = "UNKNOWN"
                polyline = []
                
                if mf.HasField('lane'):
                    feature_type = "LANE"
                    polyline = [{"x": p.x, "y": p.y} for p in mf.lane.polyline]
                elif mf.HasField('road_line'):
                    feature_type = "ROAD_LINE"
                    polyline = [{"x": p.x, "y": p.y} for p in mf.road_line.polyline]
                elif mf.HasField('road_edge'):
                    feature_type = "ROAD_EDGE"
                    polyline = [{"x": p.x, "y": p.y} for p in mf.road_edge.polyline]
                elif mf.HasField('stop_sign'):
                    feature_type = "STOP_SIGN"
                    polyline = [{"x": mf.stop_sign.position.x, "y": mf.stop_sign.position.y}]
                elif mf.HasField('crosswalk'):
                    feature_type = "CROSSWALK"
                    polyline = [{"x": p.x, "y": p.y} for p in mf.crosswalk.polygon]
                
                if polyline:
                    extracted_map_features.append({
                        "id": mf.id,
                        "type": feature_type,
                        "polyline": polyline
                    })

            return {
                "scenario_id": scenario.scenario_id,
                "sdc_track_index": sdc_track_index,
                "tracks": extracted_tracks,
                "map_features": extracted_map_features
            }
            
    except Exception as e:
        print(f"[!] Lỗi khi đọc bằng thư viện Waymo/Tensorflow: {e}")
        print("[!] Đang chuyển sang sử dụng Dữ liệu giả lập (Mock Data) cho Frontend...")
        
    # Dữ liệu mô phỏng nếu chưa cài thư viện
    mock_data = {
        "scenario_id": "WAYMO_MOCK_049",
        "tracks": [
            {
                "object_type": "TYPE_VEHICLE", 
                "states": [
                    {"x": 10.5, "y": 20.1, "velocity": 210.5}, # Cố tình tạo lỗi
                    {"x": 12.0, "y": 25.0, "velocity": 150.0}
                ]
            },
            {
                "object_type": "TYPE_PEDESTRIAN", 
                "states": [{"x": 0.0, "y": 0.0, "velocity": 0.0}]
            }
        ],
        "map_features": [{"lane_id": 1, "type": "LANE_FREEWAY"}]
    }
    return mock_data

def rule_based_qa(scenario_data):
    print("[*] Đang chạy kiểm thử Rule-based QA/QC...")
    errors = []
    
    # 1. TÍNH BOUNDING BOX CỦA BẢN ĐỒ
    map_features = scenario_data.get("map_features", [])
    min_x, max_x, min_y, max_y = float('inf'), float('-inf'), float('inf'), float('-inf')
    
    for mf in map_features:
        for pt in mf.get("polyline", []):
            if pt["x"] < min_x: min_x = pt["x"]
            if pt["x"] > max_x: max_x = pt["x"]
            if pt["y"] < min_y: min_y = pt["y"]
            if pt["y"] > max_y: max_y = pt["y"]
            
    # Margin an toàn
    margin = 10.0
    min_x -= margin
    max_x += margin
    min_y -= margin
    max_y += margin
    
    sdc_idx = scenario_data.get("sdc_track_index", 0)
    
    # Giả lập hoặc kiểm tra thực tế
    for i, track in enumerate(scenario_data.get("tracks", [])):
        states = track.get("states", [])
        
        # Biến theo dõi Rule 1
        has_valid_before = False
        was_invalid = False
        missing_detected = False
        
        for state in states:
            # Rule 2: Anomalies Kinematics
            vel = state.get("velocity", 0)
            if vel > 200:
                errors.append(f"Vận tốc phi lý: {vel:.1f} km/h tại đối tượng index {i}")
            
            # Kiểm tra Rule 1: Missing Frames
            is_valid = state.get("valid", True)
            if is_valid:
                if has_valid_before and was_invalid:
                    missing_detected = True
                has_valid_before = True
                was_invalid = False
                
                # KIỂM TRA RULE 3: Map Boundary (chỉ áp dụng cho SDC)
                # (Vì SDC index có thể nằm ngoài danh sách [:5] nên ta fallback check nếu track có id == sdc_track_index hoặc tạm check xe đầu tiên)
                if i == sdc_idx or (i == 0 and sdc_idx >= len(scenario_data.get("tracks", []))):
                    sx, sy = state.get("x", 0), state.get("y", 0)
                    if sx < min_x or sx > max_x or sy < min_y or sy > max_y:
                        if not any("Map Boundary" in err for err in errors):
                            errors.append(f"Lỗi Map Boundary: Xe SDC di chuyển ngoài vùng dữ liệu bản đồ ({sx:.1f}, {sy:.1f}).")
            else:
                if has_valid_before:
                    was_invalid = True
                    
        if missing_detected:
            errors.append(f"Lỗi Missing Frames: Xe index {i} bị mất tọa độ ở giữa kịch bản.")
            
    # Đánh cờ báo lỗi
    scenario_data["qa_flags"] = errors
    
    if len(errors) > 0:
        scenario_data["decision"] = "❌ FAIL - Kịch bản này không đủ tiêu chuẩn do phát hiện xe có vận tốc vượt ngưỡng vật lý. Nếu đưa vào VectorNet, mô hình sẽ học sai quỹ đạo."
    else:
        scenario_data["decision"] = "✅ PASS - Dữ liệu động lực học và bản đồ hợp lệ."
        
    return scenario_data

def main():
    # Trỏ đúng đường dẫn TFRecord mà anh DavidHE đang có
    tfrecord_file = "waymo_mini_dataset/uncompressed/scenario/validation/uncompressed_scenario_validation_validation.tfrecord-00049-of-00150"
    
    # Bước 1: Parse Data
    data = parse_tfrecord_to_json(tfrecord_file)
    
    # Bước 2: Rule-based
    data_with_flags = rule_based_qa(data)
    
    # Lưu JSON trực tiếp vào thư mục public của Next.js để Frontend có thể fetch được
    output_dir = os.path.join("frontend", "public")
    os.makedirs(output_dir, exist_ok=True)
    output_json = os.path.join(output_dir, "frontend_data.json")
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(data_with_flags, f, ensure_ascii=False, indent=4)
        
    print(f"\n[+] Đã xuất JSON thành công tại: {output_json}")
    print("[+] Dashboard (Next.js) giờ đã có thể tải dữ liệu này để hiển thị trực quan!")

if __name__ == "__main__":
    main()

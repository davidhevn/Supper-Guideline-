import tensorflow as tf
from waymo_open_dataset.protos import scenario_pb2

# Tên tệp TFRecord bạn vừa tải
FILE_NAME = 'uncompressed_scenario_validation_validation.tfrecord-00049-of-00150'

# Khởi tạo đối tượng đọc dữ liệu từ TensorFlow
dataset = tf.data.TFRecordDataset(FILE_NAME, compression_type='')

# Đọc thử kịch bản (scenario) ĐẦU TIÊN trong tệp
for data in dataset.take(1):
    # Khởi tạo đối tượng Scenario từ thư viện protobuf của Waymo
    scenario = scenario_pb2.Scenario()
    
    # Giải mã dữ liệu nhị phân thành cấu trúc có thể đọc được
    scenario.ParseFromString(data.numpy())
    
    # In ra các thông tin cơ bản
    print(f"Mã kịch bản (Scenario ID): {scenario.scenario_id}")
    print(f"Số lượng đối tượng tham gia giao thông (Tracks): {len(scenario.tracks)}")
    print(f"Số lượng yếu tố bản đồ vector (Map Features): {len(scenario.map_features)}")
    
    # In thử thông tin của đối tượng đầu tiên (Agent Dynamics)
    print("\n--- Thông tin đối tượng đầu tiên ---")
    print(f"Loại đối tượng: {scenario.tracks[0].object_type}")
    print(f"Số lượng trạng thái quỹ đạo lịch sử: {len(scenario.tracks[0].states)}")

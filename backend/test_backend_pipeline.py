import unittest
from backend_pipeline import rule_based_qa, parse_tfrecord_to_json

class TestBackendPipeline(unittest.TestCase):

    def test_rule_based_qa_with_invalid_velocity(self):
        """Test rule_based_qa correctly identifies velocity > 200km/h"""
        # 1. Arrange: Chuẩn bị dữ liệu đầu vào (Input)
        scenario_data = {
            "tracks": [
                {
                    "object_type": "TYPE_VEHICLE",
                    "states": [{"velocity": 250.0}]  # Lỗi vận tốc phi lý
                }
            ]
        }
        
        # 2. Act: Thực thi hàm cần test
        result = rule_based_qa(scenario_data)
        
        # 3. Assert: Kiểm tra đầu ra kỳ vọng (Output)
        self.assertTrue(len(result.get("qa_flags", [])) > 0, "Nên có ít nhất 1 cờ báo lỗi")
        self.assertIn("FAIL", result["decision"], "Quyết định phải là FAIL")
        self.assertTrue(any("250.0" in flag for flag in result["qa_flags"]), "Nội dung lỗi phải chứa vận tốc 250.0")

    def test_rule_based_qa_with_valid_velocity(self):
        """Test rule_based_qa passes valid velocities"""
        # 1. Arrange
        scenario_data = {
            "tracks": [
                {
                    "object_type": "TYPE_VEHICLE",
                    "states": [{"velocity": 60.0}]  # Tốc độ an toàn
                }
            ]
        }
        
        # 2. Act
        result = rule_based_qa(scenario_data)
        
        # 3. Assert
        self.assertEqual(len(result.get("qa_flags", [])), 0, "Không nên có cờ báo lỗi nào")
        self.assertIn("PASS", result["decision"], "Quyết định phải là PASS")

    def test_parse_tfrecord_to_json_fallback(self):
        """Test parse_tfrecord_to_json returns mock data when waymo package is missing or tfrecord is invalid"""
        # 1. Arrange & Act
        result = parse_tfrecord_to_json("dummy_invalid_path.tfrecord")
        
        # 2. Assert
        self.assertIn("scenario_id", result)
        self.assertEqual(result["scenario_id"], "WAYMO_MOCK_049", "Phải trả về Mock Data ID")
        self.assertTrue(len(result["tracks"]) > 0, "Mock data phải có chứa các track đối tượng")

if __name__ == '__main__':
    unittest.main()

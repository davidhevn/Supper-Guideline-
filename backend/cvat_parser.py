import json
import xml.etree.ElementTree as ET

# =====================================================================
# CVAT QA/QC Adapter - Traffic Sign Labeling
# Guideline V1.2 | GTSDB Standard | 6 Rules
# =====================================================================

IOU_THRESHOLD = 0.7
VALID_LABELS = {"prohibitory", "mandatory", "danger", "other"}
VALID_READABLE = {"yes", "no", "uncertain"}

# =====================================================================
# RULE 5: FAMILY-CLASS MAPPING TRAP (GTSDB)
# Key = sign_class, Value = (correct_label, wrong_labels_to_catch, reason)
# =====================================================================
FAMILY_MAPPING_TRAP = {
    # Bien trong giong Cấm (Prohibitory) nhung GTSDB bat buoc la OTHER
    "stop":                       ("other",     {"prohibitory"},          "Stop (GTSDB #14) thuoc nhom 'other', khong phai 'prohibitory'. Day la bay anh xa pho bien nhat!"),
    "give_way":                   ("other",     {"danger", "prohibitory"}, "Give Way (GTSDB #13) thuoc nhom 'other', khong phai 'danger' hay 'prohibitory'."),
    "no_entry":                   ("other",     {"prohibitory"},          "No Entry (GTSDB #17) thuoc nhom 'other', khong phai 'prohibitory'."),
    "priority_road":              ("other",     {"danger"},               "Priority Road (GTSDB #12) thuoc nhom 'other', khong phai 'danger'."),
    "end_of_speed_limit_80":      ("other",     {"prohibitory"},          "Bien Het Cam (End-of-restriction) thuoc nhom 'other', khong phai 'prohibitory'."),
    "end_of_no_overtaking":       ("other",     {"prohibitory"},          "Bien Het Cam vuot (End-of-no-overtaking) thuoc nhom 'other'."),
    "end_of_all_restrictions":    ("other",     {"prohibitory"},          "Bien Het Tat Ca Han Che (GTSDB #42) thuoc nhom 'other'."),
    # Bay nguoc: Bien trong giong Other nhung GTSDB bat buoc la DANGER
    "priority_next_intersection": ("danger",    {"other"},                "Priority Next Intersection (GTSDB #11) thuoc nhom 'danger', khong phai 'other'."),
}

# =====================================================================
# UTILITY
# =====================================================================

def calculate_iou(box1, box2):
    """Tinh IoU giua 2 Bounding Box [x_min, y_min, x_max, y_max]."""
    x1, y1 = max(box1[0], box2[0]), max(box1[1], box2[1])
    x2, y2 = min(box1[2], box2[2]), min(box1[3], box2[3])
    if x2 < x1 or y2 < y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0

def box_area(box):
    return (box[2] - box[0]) * (box[3] - box[1])

def get_box_size(box):
    return (box[2] - box[0]), (box[3] - box[1])

# =====================================================================
# RULE IMPLEMENTATIONS
# =====================================================================

def rule1_iou(user_box, gt_box, case_type):
    """Rule 1: Kiem tra do lech Bounding Box."""
    iou = calculate_iou(user_box, gt_box)
    if iou >= IOU_THRESHOLD:
        return None

    gt_w, gt_h = get_box_size(gt_box)
    user_w, user_h = get_box_size(user_box)
    is_too_small = user_w < gt_w * 0.85 or user_h < gt_h * 0.85

    if is_too_small:
        direction = "BI THUT (qua nho so voi chuan)"
        if case_type == "occlusion":
            hint = ("Guideline V1.2 - Phan 5.4: Bien bi che < 50% -> Van phai ve box\n"
                    "  bao TRON BO hinh dang thuc te (ke ca phan bi che). KHONG chi ve phan nhin thay.")
        else:
            hint = "Guideline V1.2 - Phan 5.5: Box phai vua khit mep bien bao (5px padding)."
    else:
        direction = "QUA RONG"
        if case_type == "cluster":
            hint = ("Guideline V1.2 - Quy tac Atomic (5.1): Moi mat bien = 1 box rieng.\n"
                    "  KHONG duoc gom nhieu bien vao 1 box.")
        else:
            hint = "Guideline V1.2 - Phan 5.1: Box khong bao gom cot, day treo, be do bien."

    return {
        "rule": "Rule 1 - IoU",
        "status": "FAIL",
        "iou": round(iou, 3),
        "detail": f"Loi TOA DO: IoU={iou:.2f} < {IOU_THRESHOLD} | {direction}",
        "hint": hint
    }


def rule2_label(user_label, gt_label):
    """Rule 2: Kiem tra nhan chinh co sai khong."""
    if user_label == gt_label:
        return None
    return {
        "rule": "Rule 2 - Label Mismatch",
        "status": "FAIL",
        "detail": f"Loi SAI PHAN LOAI: User chon '{user_label}', dap an chuan la '{gt_label}'",
        "hint": ("Guideline V1.2 - Phan 2: Phan biet nhom theo hinh dang:\n"
                 "  prohibitory (tron do), mandatory (tron xanh), danger (tam giac vang), other (con lai).\n"
                 "  Hay doc ky Bay Anh Xa (phan 5.2) truoc khi quyet dinh!")
    }


def rule3_attributes(user_attrs, gt_attrs):
    """Rule 3: Kiem tra Attributes (sign_class, occluded, truncated, readable)."""
    errors = []

    # sign_class
    user_sc = user_attrs.get("sign_class", "").strip()
    gt_sc = gt_attrs.get("sign_class", "").strip()
    if not user_sc:
        errors.append({
            "attribute": "sign_class",
            "detail": "THIEU THUOC TINH: 'sign_class' dang de TRONG.",
            "hint": "Guideline V1.2 - Phan 3: Bat buoc nhap ma bien. Neu khong ro -> 'unknown'."
        })
    elif user_sc != gt_sc:
        errors.append({
            "attribute": "sign_class",
            "detail": f"SAI MA BIEN: User='{user_sc}', Chuan='{gt_sc}'",
            "hint": "Guideline V1.2 - Phan 4: Tham khao bang ma GTSDB."
        })

    # readable (3 gia tri hop le: yes/no/uncertain)
    user_readable = user_attrs.get("readable", "").strip().lower()
    if user_readable not in VALID_READABLE:
        errors.append({
            "attribute": "readable",
            "detail": f"GIA TRI SAI DINH DANG: 'readable'='{user_readable}'. Chi chap nhan: yes / no / uncertain.",
            "hint": "Guideline V1.2 - Phan 3: Them gia tri 'uncertain' khi bien qua mo nhung van nhin thay."
        })

    # occluded
    if gt_attrs.get("occluded") and not user_attrs.get("occluded"):
        errors.append({
            "attribute": "occluded",
            "detail": "QUEN TICH: Bien nay BI CHE KHUAT nhung khong tich 'occluded'.",
            "hint": "Guideline V1.2 - Phan 3: Tich khi bat ky vat the nao che bien, du 1 phan nho."
        })
    elif not gt_attrs.get("occluded") and user_attrs.get("occluded"):
        errors.append({
            "attribute": "occluded",
            "detail": "TICH SAI: Bien KHONG bi che nhung User tich 'occluded = True'.",
            "hint": "Guideline V1.2 - Phan 3: Chi tich 'occluded' khi bien thuc su bi vat the khac che."
        })

    # truncated
    if gt_attrs.get("truncated") and not user_attrs.get("truncated"):
        errors.append({
            "attribute": "truncated",
            "detail": "QUEN TICH: Bien bi cat o mep anh nhung khong tich 'truncated'.",
            "hint": "Guideline V1.2 - Phan 5.5: Khi bien bi can o canh anh, tich 'truncated = True'."
        })

    if errors:
        return {
            "rule": "Rule 3 - Attribute Mismatch",
            "status": "FAIL",
            "detail": f"Phat hien {len(errors)} loi Attribute",
            "attribute_errors": errors
        }
    return None


def rule4_atomic_check(user_box, all_gt_boxes):
    """
    Rule 4: Phat hien gop cum - User ve 1 box bao trum >= 2 GT boxes.
    """
    overlapping_count = 0
    for gt_box in all_gt_boxes:
        if calculate_iou(user_box, gt_box) > 0.3:
            overlapping_count += 1

    if overlapping_count >= 2:
        return {
            "rule": "Rule 4 - Atomic Violation",
            "status": "FAIL",
            "detail": f"Loi GOP CUM: Box nay dang bao trum {overlapping_count} bien bao cua Ground Truth.",
            "hint": ("Guideline V1.2 - Quy tac Atomic (5.1): Moi MAT BIEN BAO = 1 Bounding Box rieng biet.\n"
                     "  Cum bien xep chong KHONG BAO GIO duoc gop chung 1 box.")
        }
    return None


def rule5_family_mapping_trap(user_label, user_sign_class):
    """
    Rule 5: Bay anh xa nhan (GTSDB Label Mapping Trap).
    Kiem tra cac truong hop bien trong giong 1 nhom nhung thuc ra thuoc nhom khac.
    """
    sign_class = user_sign_class.strip().lower()

    # Normalize: strip so toc do (speed_limit_50 -> speed_limit)
    normalized = sign_class
    for prefix in ["speed_limit_", "end_of_speed_limit_"]:
        if sign_class.startswith(prefix):
            normalized = prefix.rstrip("_")
            break

    trap = FAMILY_MAPPING_TRAP.get(sign_class) or FAMILY_MAPPING_TRAP.get(normalized)
    if not trap:
        return None

    correct_label, wrong_labels, reason = trap

    if user_label in wrong_labels:
        return {
            "rule": "Rule 5 - Family Mapping Trap",
            "status": "FAIL",
            "detail": (f"BAY ANH XA NHAN! sign_class='{sign_class}' phai co label='{correct_label}' "
                       f"nhung User chon '{user_label}'."),
            "hint": f"Guideline V1.2 - Phan 5.2 (Bang Bay): {reason}"
        }
    return None


def rule6_attribute_format(user_attrs):
    """
    Rule 6: Kiem tra dinh dang / gia tri hop le cua cac Attributes.
    """
    errors = []

    readable_val = str(user_attrs.get("readable", "")).strip().lower()
    if readable_val not in VALID_READABLE:
        errors.append({
            "attribute": "readable",
            "detail": f"GIA TRI KHONG HOP LE: 'readable'='{readable_val}'. Chi chap nhan: yes / no / uncertain.",
            "hint": "Guideline V1.2 - Phan 3: Them 'uncertain' cho bien nhin thay nhung mo."
        })

    sign_class_val = str(user_attrs.get("sign_class", "")).strip()
    if len(sign_class_val) == 0:
        errors.append({
            "attribute": "sign_class",
            "detail": "DINH DANG SAI: 'sign_class' khong duoc de trong.",
            "hint": "Guideline V1.2 - Phan 3: Neu khong ro bien gi -> dien 'unknown'."
        })

    if errors:
        return {
            "rule": "Rule 6 - Attribute Format Validation",
            "status": "FAIL",
            "detail": f"Phat hien {len(errors)} loi dinh dang Attribute",
            "attribute_errors": errors
        }
    return None


# =====================================================================
# MAIN EVALUATION ENGINE & PARSERS
# =====================================================================

def parse_coco_json(json_str):
    """Parse COCO JSON hoac Internal Mock JSON."""
    try:
        data = json.loads(json_str)
        # Dinh dang Mock noi bo
        if "annotations" in data and "categories" not in data:
            return data["annotations"]
            
        # Dinh dang COCO JSON chuan (export tu CVAT)
        annotations = []
        if "categories" in data and "annotations" in data:
            cat_map = {c["id"]: c["name"] for c in data.get("categories", [])}
            img_map = {img["id"]: img["file_name"] for img in data.get("images", [])}
            
            for ann in data["annotations"]:
                # COCO bbox la [x, y, width, height]
                x, y, w, h = ann.get("bbox", [0,0,0,0])
                bbox = [x, y, x + w, y + h]
                label = cat_map.get(ann.get("category_id"), "unknown")
                attributes = ann.get("attributes", {})
                image_name = img_map.get(ann.get("image_id"), "unknown_image")
                
                annotations.append({
                    "id": ann.get("id"),
                    "image_name": image_name,
                    "label": label,
                    "bbox": bbox,
                    "attributes": attributes
                })
            return annotations
    except Exception as e:
        print(f"Error parsing JSON: {e}")
    return []

def parse_cvat_xml(xml_str):
    """Parse CVAT for images 1.1 (XML)."""
    annotations = []
    try:
        root = ET.fromstring(xml_str)
        for image in root.findall('image'):
            for box in image.findall('box'):
                label = box.get('label', 'unknown')
                x_min = float(box.get('xtl', 0))
                y_min = float(box.get('ytl', 0))
                x_max = float(box.get('xbr', 0))
                y_max = float(box.get('ybr', 0))
                
                attributes = {}
                for attr in box.findall('attribute'):
                    name = attr.get('name')
                    value = attr.text
                    if value and value.lower() == 'true':
                        value = True
                    elif value and value.lower() == 'false':
                        value = False
                    attributes[name] = value
                
                annotations.append({
                    "id": int(box.get('id', len(annotations) + 1)),
                    "label": label,
                    "bbox": [x_min, y_min, x_max, y_max],
                    "attributes": attributes
                })
    except Exception as e:
        print(f"Error parsing XML: {e}")
    return annotations

def parse_annotations(content_str):
    """Tu dong nhan dien format va parse thanh Unified Object."""
    content_str = content_str.strip()
    if content_str.startswith('<'):
        return parse_cvat_xml(content_str)
    elif content_str.startswith('{') or content_str.startswith('['):
        return parse_coco_json(content_str)
    return []

def evaluate_annotations(user_content_str, gt_content_str):
    """
    Ham danh gia chinh: Ap dung toan bo 6 Rules len User Annotations.
    Ho tro ca format CVAT XML va COCO JSON.
    """
    gt_list = parse_annotations(gt_content_str)
    user_list = parse_annotations(user_content_str)
    
    def calculate_iou(box1, box2):
        x_min_inter = max(box1[0], box2[0])
        y_min_inter = max(box1[1], box2[1])
        x_max_inter = min(box1[2], box2[2])
        y_max_inter = min(box1[3], box2[3])

        if x_min_inter >= x_max_inter or y_min_inter >= y_max_inter:
            return 0.0

        inter_area = (x_max_inter - x_min_inter) * (y_max_inter - y_min_inter)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = area1 + area2 - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    # Gom nhom theo image_name
    user_by_image = {}
    for u in user_list:
        img = u.get("image_name", "unknown_image")
        if img not in user_by_image:
            user_by_image[img] = []
        user_by_image[img].append(u)

    gt_by_image = {}
    for g in gt_list:
        img = g.get("image_name", "unknown_image")
        if img not in gt_by_image:
            gt_by_image[img] = []
        gt_by_image[img].append(g)

    all_results = []
    pass_count = 0
    fail_count = 0

    for gt_obj in gt_list:
        obj_id = gt_obj.get("id", "GT")
        image_name = gt_obj.get("image_name", "unknown_image")
        gt_box = gt_obj["bbox"]
        gt_label = gt_obj["label"]
        gt_attrs = gt_obj.get("attributes", {})
        case_type = gt_obj.get("case_type", "general")
        all_gt_boxes = [g["bbox"] for g in gt_by_image.get(image_name, gt_list)]

        obj_errors = []
        
        # Tim box User co IoU cao nhat trong cung 1 anh
        user_candidates = user_by_image.get(image_name, [])
        best_user_obj = None
        best_iou = 0.0
        
        for cand in user_candidates:
            iou = calculate_iou(cand["bbox"], gt_box)
            if iou > best_iou:
                best_iou = iou
                best_user_obj = cand

        # Neu khong co user box nao co IoU > 0.0, coi nhu bi thieu object
        if not best_user_obj or best_iou == 0.0:
            fail_count += 1
            all_results.append({
                "id": f"{obj_id} (Missing)", "gt_label": gt_label, "status": "FAIL",
                "errors": [{
                    "rule": "Missing Object",
                    "status": "FAIL",
                    "detail": "Bo sot: Khong tim thay annotation nay hoac ve lech hoan toan khoi muc tieu.",
                    "hint": "Guideline V1.2 - Phan 5.4: Bien > 15x15px deu phai dan nhan."
                }]
            })
            continue

        user_obj = best_user_obj

        user_box = user_obj["bbox"]
        user_label = user_obj.get("label", "")
        user_attrs = user_obj.get("attributes", {})
        user_sc = user_attrs.get("sign_class", "")

        # Ap dung tung Rule theo thu tu
        for check_fn, args in [
            (rule1_iou,               (user_box, gt_box, case_type)),
            (rule2_label,             (user_label, gt_label)),
            (rule3_attributes,        (user_attrs, gt_attrs)),
            (rule4_atomic_check,      (user_box, all_gt_boxes)),
            (rule5_family_mapping_trap, (user_label, user_sc)),
            (rule6_attribute_format,  (user_attrs,)),
        ]:
            result = check_fn(*args)
            if result:
                obj_errors.append(result)

        if obj_errors:
            fail_count += 1
            all_results.append({
                "id": obj_id, "gt_label": gt_label,
                "user_label": user_label, "status": "FAIL",
                "errors": obj_errors
            })
        else:
            pass_count += 1
            all_results.append({
                "id": obj_id, "gt_label": gt_label, "status": "PASS", "errors": []
            })

    total = pass_count + fail_count
    score = round((pass_count / total) * 100, 1) if total > 0 else 0

    # 1. Attribute Completion Rate
    total_attrs = len(user_list) * 5
    filled_attrs = 0
    for u_obj in user_list:
        attrs = u_obj.get("attributes", {})
        filled_attrs += 3 # occluded, truncated, relevant_to_ego are checkboxes (always bool)
        sc = str(attrs.get("sign_class", "")).strip()
        rd = str(attrs.get("readable", "")).strip().lower()
        if sc: filled_attrs += 1
        if rd in VALID_READABLE: filled_attrs += 1
    
    attr_completion_rate = round((filled_attrs / total_attrs) * 100, 1) if total_attrs > 0 else 0.0

    # 2. Precision & Recall per class
    metrics = {
        "attribute_completion_rate": attr_completion_rate,
        "precision_per_class": {},
        "recall_per_class": {}
    }
    
    gt_counts = {lbl: 0 for lbl in VALID_LABELS}
    pred_counts = {lbl: 0 for lbl in VALID_LABELS}
    tp_counts = {lbl: 0 for lbl in VALID_LABELS}
    
    for gt_obj in gt_list:
        lbl = gt_obj.get("label", "")
        if lbl in gt_counts:
            gt_counts[lbl] += 1
            
    for u_obj in user_list:
        lbl = u_obj.get("label", "")
        if lbl in pred_counts:
            pred_counts[lbl] += 1
            
    for result in all_results:
        gt_lbl = result.get("gt_label", "")
        user_lbl = result.get("user_label", "")
        if gt_lbl == user_lbl and gt_lbl in VALID_LABELS:
            tp_counts[gt_lbl] += 1
            
    for lbl in VALID_LABELS:
        p = (tp_counts[lbl] / pred_counts[lbl] * 100) if pred_counts[lbl] > 0 else 0.0
        r = (tp_counts[lbl] / gt_counts[lbl] * 100) if gt_counts[lbl] > 0 else 0.0
        metrics["precision_per_class"][lbl] = round(p, 1)
        metrics["recall_per_class"][lbl] = round(r, 1)

    return {
        "summary": {
            "total_objects": total,
            "pass": pass_count,
            "fail": fail_count,
            "score_percent": score,
            "verdict": "PASS" if score >= 80 else "FAIL"
        },
        "metrics": metrics,
        "qa_flags": [r for r in all_results if r["status"] == "FAIL"],
        "details": all_results
    }


# =====================================================================
# MOCK TEST — V1.2 (Test cac bay Rule 4, 5, 6)
# =====================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CVAT QA/QC Evaluation Engine")
    parser.add_argument("--gt", type=str, help="Path to Ground Truth JSON/XML file")
    parser.add_argument("--sub", type=str, help="Path to Labeler Submission JSON/XML file")
    
    args = parser.parse_args()
    
    if args.gt and args.sub:
        with open(args.gt, 'r', encoding='utf-8') as f:
            gt_content = f.read()
        with open(args.sub, 'r', encoding='utf-8') as f:
            sub_content = f.read()
    else:
        # Fallback to Mock Data if no args provided
        gt_content = json.dumps({
            "annotations": [
                {  "id": 1, "label": "other", "bbox": [120, 80, 180, 140], "case_type": "general",
                   "attributes": {"readable": "yes", "sign_class": "stop", "occluded": False, "truncated": False, "relevant_to_ego": True}},
                {  "id": 2, "label": "prohibitory", "bbox": [300, 100, 380, 180], "case_type": "cluster",
                   "attributes": {"readable": "yes", "sign_class": "speed_limit_50", "occluded": False, "truncated": False, "relevant_to_ego": True}},
                {  "id": 3, "label": "other", "bbox": [300, 185, 380, 230], "case_type": "cluster",
                   "attributes": {"readable": "yes", "sign_class": "supplementary_distance", "occluded": False, "truncated": False, "relevant_to_ego": False}},
                {  "id": 4, "label": "danger", "bbox": [500, 100, 580, 180], "case_type": "general",
                   "attributes": {"readable": "yes", "sign_class": "priority_next_intersection", "occluded": False, "truncated": False, "relevant_to_ego": True}}
            ]
        })
        sub_content = json.dumps({
            "annotations": [
                {  "id": 1, "label": "prohibitory", "bbox": [122, 82, 178, 138],
                   "attributes": {"readable": "yes", "sign_class": "stop", "occluded": False, "truncated": False, "relevant_to_ego": True}},
                {  "id": 2, "label": "prohibitory", "bbox": [295, 95, 385, 235],
                   "attributes": {"readable": "yes", "sign_class": "speed_limit_50", "occluded": False, "truncated": False, "relevant_to_ego": True}},
                {  "id": 4, "label": "danger", "bbox": [502, 102, 578, 178],
                   "attributes": {"readable": "clear", "sign_class": "priority_next_intersection", "occluded": False, "truncated": False, "relevant_to_ego": True}}
            ]
        })

    print("=" * 68)
    print("  CVAT QA/QC — Guideline V1.2 | GTSDB Standard | 6 Rules")
    print("=" * 68)

    report = evaluate_annotations(sub_content, gt_content)
    s = report["summary"]
    verdict_icon = "PASS" if s["verdict"] == "PASS" else "FAIL"
    print(f"\n[TONG KET] Diem: {s['score_percent']}% | Ket qua: {verdict_icon}")
    print(f"  Dat chuan: {s['pass']}/{s['total_objects']}")
    print(f"  Loi      : {s['fail']}/{s['total_objects']}")

    m = report["metrics"]
    print(f"\n[METRICS]")
    print(f"  Attribute Completion Rate: {m['attribute_completion_rate']}%")
    print(f"  Precision (prohibitory): {m['precision_per_class'].get('prohibitory')}% | Recall: {m['recall_per_class'].get('prohibitory')}%")
    print(f"  Precision (other):       {m['precision_per_class'].get('other')}% | Recall: {m['recall_per_class'].get('other')}%")
    
    for flag in report["qa_flags"]:
        print(f"\n{'='*65}")
        print(f"  Object #{flag['id']} | GT Label: {flag.get('gt_label')} | FAIL")
        for err in flag["errors"]:
            print(f"\n  [{err['rule']}]")
            print(f"    {err['detail']}")
            if "hint" in err:
                for line in err["hint"].split("\n"):
                    print(f"    {line}")
            if "attribute_errors" in err:
                for ae in err["attribute_errors"]:
                    print(f"\n    [{ae['attribute']}] {ae['detail']}")
                    print(f"      {ae['hint']}")
    print(f"\n{'='*68}")

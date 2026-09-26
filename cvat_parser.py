import json

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
# MAIN EVALUATION ENGINE
# =====================================================================

def evaluate_annotations(user_json_str, gt_json_str):
    """
    Ham danh gia chinh: Ap dung toan bo 6 Rules len User Annotations.
    """
    user_data = json.loads(user_json_str)
    gt_data = json.loads(gt_json_str)

    gt_list = gt_data.get("annotations", [])
    user_list = user_data.get("annotations", [])
    user_map = {item["id"]: item for item in user_list}
    all_gt_boxes = [obj["bbox"] for obj in gt_list]

    all_results = []
    pass_count = 0
    fail_count = 0

    for gt_obj in gt_list:
        obj_id = gt_obj["id"]
        gt_box = gt_obj["bbox"]
        gt_label = gt_obj["label"]
        gt_attrs = gt_obj.get("attributes", {})
        case_type = gt_obj.get("case_type", "general")

        obj_errors = []
        user_obj = user_map.get(obj_id)

        if not user_obj:
            fail_count += 1
            all_results.append({
                "id": obj_id, "gt_label": gt_label, "status": "FAIL",
                "errors": [{
                    "rule": "Missing Object",
                    "status": "FAIL",
                    "detail": "Bo sot: Khong tim thay annotation nay.",
                    "hint": "Guideline V1.2 - Phan 5.4: Bien > 15x15px deu phai dan nhan."
                }]
            })
            continue

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

    return {
        "summary": {
            "total_objects": total,
            "pass": pass_count,
            "fail": fail_count,
            "score_percent": score,
            "verdict": "PASS" if score >= 80 else "FAIL"
        },
        "qa_flags": [r for r in all_results if r["status"] == "FAIL"],
        "details": all_results
    }


# =====================================================================
# MOCK TEST — V1.2 (Test cac bay Rule 4, 5, 6)
# =====================================================================
if __name__ == "__main__":
    ground_truth = json.dumps({
        "annotations": [
            {  # Test Rule 5: Stop phai la 'other' khong phai 'prohibitory'
                "id": 1, "label": "other", "bbox": [120, 80, 180, 140],
                "case_type": "general",
                "attributes": {"readable": "yes", "sign_class": "stop",
                               "occluded": False, "truncated": False, "relevant_to_ego": True}
            },
            {  # Test Rule 4: 2 bien nay se bi gom lai boi User
                "id": 2, "label": "prohibitory", "bbox": [300, 100, 380, 180],
                "case_type": "cluster",
                "attributes": {"readable": "yes", "sign_class": "speed_limit_50",
                               "occluded": False, "truncated": False, "relevant_to_ego": True}
            },
            {
                "id": 3, "label": "other", "bbox": [300, 185, 380, 230],
                "case_type": "cluster",
                "attributes": {"readable": "yes", "sign_class": "supplementary_distance",
                               "occluded": False, "truncated": False, "relevant_to_ego": False}
            },
            {  # Test Rule 6: readable sai dinh dang
                "id": 4, "label": "danger", "bbox": [500, 100, 580, 180],
                "case_type": "general",
                "attributes": {"readable": "yes", "sign_class": "priority_next_intersection",
                               "occluded": False, "truncated": False, "relevant_to_ego": True}
            },
        ]
    })

    user_label = json.dumps({
        "annotations": [
            {  # Rule 5 TRAP: Chon sai label prohibitory cho bien stop
                "id": 1, "label": "prohibitory",
                "bbox": [122, 82, 178, 138],
                "attributes": {"readable": "yes", "sign_class": "stop",
                               "occluded": False, "truncated": False, "relevant_to_ego": True}
            },
            {  # Rule 4: Gom ca 2 bien (id=2 va id=3) vao 1 box to
                "id": 2, "label": "prohibitory",
                "bbox": [295, 95, 385, 235],
                "attributes": {"readable": "yes", "sign_class": "speed_limit_50",
                               "occluded": False, "truncated": False, "relevant_to_ego": True}
            },
            {  # id=3 bi bo sot (vi da gop vao id=2)
            },
            {  # Rule 6: readable dien sai (dung "clear" thay vi yes/no/uncertain)
                "id": 4, "label": "danger",
                "bbox": [502, 102, 578, 178],
                "attributes": {"readable": "clear",  # <-- SAI DINH DANG
                               "sign_class": "priority_next_intersection",
                               "occluded": False, "truncated": False, "relevant_to_ego": True}
            },
        ]
    })

    # Loc bo None
    user_parsed = json.loads(user_label)
    user_parsed["annotations"] = [a for a in user_parsed["annotations"] if a]
    user_label = json.dumps(user_parsed)

    print("=" * 68)
    print("  CVAT QA/QC — Guideline V1.2 | GTSDB Standard | 6 Rules")
    print("=" * 68)

    report = evaluate_annotations(user_label, ground_truth)
    s = report["summary"]
    verdict_icon = "PASS" if s["verdict"] == "PASS" else "FAIL"
    print(f"\n[TONG KET] Diem: {s['score_percent']}% | Ket qua: {verdict_icon}")
    print(f"  Dat chuan: {s['pass']}/{s['total_objects']}")
    print(f"  Loi      : {s['fail']}/{s['total_objects']}")

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

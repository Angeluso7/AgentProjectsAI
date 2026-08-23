import math
from typing import List, Dict, Any, Tuple, Optional
from rapidfuzz.distance import Levenshtein

def compute_box_iou(boxA: List[float], boxB: List[float]) -> float:
    """Calcula Intersection over Union (IoU) para dos cajas [x0, y0, x1, y1]."""
    if not boxA or not boxB or len(boxA) < 4 or len(boxB) < 4:
        return 0.0
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interWidth = max(0.0, xB - xA)
    interHeight = max(0.0, yB - yA)
    interArea = interWidth * interHeight

    boxAArea = max(0.0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(0.0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    unionArea = boxAArea + boxBArea - interArea
    if unionArea <= 0.0:
        return 0.0
    return interArea / unionArea


class MetricsCalculator:
    """Calculador determinístico de métricas perceptuales y decisionales para auditoría de planos."""

    # =========================================================================
    # A. MÉTRICAS PERCEPTUALES
    # =========================================================================

    @staticmethod
    def calculate_ocr_metrics(pred_texts: List[Dict[str, Any]], gt_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula CER, WER, precisión en textos críticos y error promedio de BBox."""
        if not gt_items:
            return {"cer": 0.0, "wer": 0.0, "critical_f1": 1.0, "bbox_mae": 0.0, "sample_count": 0}

        pred_full_text = " ".join([p.get("text", "").strip() for p in pred_texts if p.get("text")])
        gt_full_text = " ".join([g.get("text", "").strip() for g in gt_items if g.get("text")])

        # 1. CER (Character Error Rate)
        total_chars = max(1, len(gt_full_text))
        char_dist = Levenshtein.distance(pred_full_text, gt_full_text)
        cer = min(1.0, char_dist / total_chars)

        # 2. WER (Word Error Rate)
        pred_words = pred_full_text.split()
        gt_words = gt_full_text.split()
        total_words = max(1, len(gt_words))
        word_dist = Levenshtein.distance(" ".join(pred_words), " ".join(gt_words))
        wer = min(1.0, word_dist / total_words)

        # 3. Precisión / Recall en textos marcados como critical
        critical_gt = [g for g in gt_items if g.get("criticality") == "critical"]
        matched_critical = 0
        bbox_errors = []

        for c_gt in critical_gt:
            gt_t = c_gt.get("text", "").lower().strip()
            gt_box = c_gt.get("bbox", [0, 0, 0, 0])
            for p in pred_texts:
                p_t = p.get("text", "").lower().strip()
                p_box = p.get("bbox", [0, 0, 0, 0])
                if gt_t in p_t or p_t in gt_t:
                    matched_critical += 1
                    # Calcular error de coordenadas (L1 distance)
                    if len(gt_box) == 4 and len(p_box) == 4:
                        mae = sum(abs(g - b) for g, b in zip(gt_box, p_box)) / 4.0
                        bbox_errors.append(mae)
                    break

        critical_recall = (matched_critical / len(critical_gt)) if critical_gt else 1.0
        critical_precision = (matched_critical / max(1, len(pred_texts))) if critical_gt else 1.0
        critical_f1 = (2 * critical_precision * critical_recall / (critical_precision + critical_recall)) if (critical_precision + critical_recall) > 0 else 0.0

        avg_bbox_mae = sum(bbox_errors) / max(1, len(bbox_errors)) if bbox_errors else 0.0

        return {
            "cer": round(cer, 4),
            "wer": round(wer, 4),
            "critical_recall": round(critical_recall, 4),
            "critical_precision": round(critical_precision, 4),
            "critical_f1": round(critical_f1, 4),
            "bbox_mae": round(avg_bbox_mae, 4),
            "sample_count": len(gt_items)
        }

    @staticmethod
    def calculate_layout_metrics(pred_regions: List[Dict[str, Any]], gt_regions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula IoU por macro-región y Mean IoU."""
        if not gt_regions:
            return {"mean_iou": 1.0, "by_region_iou": {}, "sample_count": 0}

        region_ious: Dict[str, List[float]] = {}
        for gt in gt_regions:
            r_type = gt.get("region_type", "drawing_area")
            gt_box = gt.get("bbox", [0, 0, 0, 0])
            best_iou = 0.0
            for pred in pred_regions:
                if pred.get("region_type") == r_type:
                    iou = compute_box_iou(gt_box, pred.get("bbox", [0, 0, 0, 0]))
                    if iou > best_iou:
                        best_iou = iou
            region_ious.setdefault(r_type, []).append(best_iou)

        avg_by_region = {r: round(sum(ious) / len(ious), 4) for r, ious in region_ious.items()}
        all_ious = [iou for sub in region_ious.values() for iou in sub]
        mean_iou = sum(all_ious) / max(1, len(all_ious))

        return {
            "mean_iou": round(mean_iou, 4),
            "by_region_iou": avg_by_region,
            "sample_count": len(gt_regions)
        }

    @staticmethod
    def calculate_title_block_metrics(pred_fields: Dict[str, Any], gt_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula exactitud de campo, completitud de campos requeridos y precisión normalizada."""
        if not gt_fields:
            return {"exact_match_ratio": 1.0, "required_completeness": 1.0, "sample_count": 0}

        total_fields = len(gt_fields)
        exact_matches = 0
        normalized_matches = 0
        required_count = 0
        required_present = 0

        for gt in gt_fields:
            fname = gt.get("field_name")
            expected = str(gt.get("expected_value", "")).strip().lower()
            normalized = str(gt.get("normalized_value") or expected).strip().lower()
            is_req = gt.get("required", True)

            pred_val = str(pred_fields.get(fname, "")).strip().lower()

            if is_req:
                required_count += 1
                if pred_val:
                    required_present += 1

            if pred_val == expected:
                exact_matches += 1
                normalized_matches += 1
            elif pred_val and (pred_val in normalized or normalized in pred_val):
                normalized_matches += 1

        exact_ratio = exact_matches / max(1, total_fields)
        norm_ratio = normalized_matches / max(1, total_fields)
        req_completeness = (required_present / required_count) if required_count > 0 else 1.0

        return {
            "exact_match_ratio": round(exact_ratio, 4),
            "normalized_accuracy": round(norm_ratio, 4),
            "required_completeness": round(req_completeness, 4),
            "sample_count": total_fields
        }

    @staticmethod
    def calculate_table_metrics(pred_tables: List[Dict[str, Any]], gt_tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula detección de tablas (IoU), exactitud de celdas y encabezados."""
        if not gt_tables:
            return {"table_detection_iou": 1.0, "cell_accuracy": 1.0, "header_accuracy": 1.0, "sample_count": 0}

        table_ious = []
        cell_matches = 0
        cell_total = 0
        header_matches = 0
        header_total = 0

        for gt in gt_tables:
            gt_box = gt.get("bbox", [0, 0, 0, 0])
            best_pred = None
            best_iou = 0.0

            for pt in pred_tables:
                iou = compute_box_iou(gt_box, pt.get("bbox", [0, 0, 0, 0]))
                if iou > best_iou:
                    best_iou = iou
                    best_pred = pt

            table_ious.append(best_iou)

            if best_pred:
                pred_cells = {(c.get("row_index"), c.get("col_index")): str(c.get("cell_text", "")).strip().lower() for c in best_pred.get("cells", [])}
                gt_cells = gt.get("cells", [])
                cell_total += len(gt_cells)
                for gc in gt_cells:
                    key = (gc.get("row_index"), gc.get("col_index"))
                    gt_txt = str(gc.get("cell_text", "")).strip().lower()
                    if pred_cells.get(key) == gt_txt:
                        cell_matches += 1

                gt_headers = [str(h).strip().lower() for h in gt.get("headers", [])]
                pred_headers = [str(h).strip().lower() for h in best_pred.get("headers", [])]
                header_total += len(gt_headers)
                for gh in gt_headers:
                    if gh in pred_headers:
                        header_matches += 1

        avg_table_iou = sum(table_ious) / max(1, len(table_ious))
        cell_acc = cell_matches / max(1, cell_total) if cell_total > 0 else 1.0
        head_acc = header_matches / max(1, header_total) if header_total > 0 else 1.0

        return {
            "table_detection_iou": round(avg_table_iou, 4),
            "cell_accuracy": round(cell_acc, 4),
            "header_accuracy": round(head_acc, 4),
            "sample_count": len(gt_tables)
        }

    @staticmethod
    def calculate_symbol_metrics(pred_symbols: List[Dict[str, Any]], gt_symbols: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula Precisión, Recall, F1 por clase, Conteo MAE y mAP@0.5:0.95 cuando hay bboxes suficientes."""
        if not gt_symbols:
            return {"precision": 1.0, "recall": 1.0, "f1_score": 1.0, "count_mae": 0.0, "sample_count": 0}

        pred_counts: Dict[str, int] = {}
        for ps in pred_symbols:
            c = ps.get("symbol_type") or ps.get("label", "unknown")
            pred_counts[c] = pred_counts.get(c, 0) + 1

        gt_counts: Dict[str, int] = {}
        for gs in gt_symbols:
            c = gs.get("class_name", "unknown")
            gt_counts[c] = gt_counts.get(c, 0) + gs.get("count", 1)

        all_classes = set(pred_counts.keys()).union(set(gt_counts.keys()))
        tp_total, fp_total, fn_total = 0, 0, 0
        count_errors = []

        by_class_metrics: Dict[str, Dict[str, Any]] = {}
        for c in all_classes:
            pc = pred_counts.get(c, 0)
            gc = gt_counts.get(c, 0)
            tp = min(pc, gc)
            fp = max(0, pc - gc)
            fn = max(0, gc - pc)

            tp_total += tp
            fp_total += fp
            fn_total += fn
            c_err = abs(pc - gc)
            count_errors.append(c_err)

            c_prec = tp / max(1, tp + fp)
            c_rec = tp / max(1, tp + fn)
            c_f1 = (2 * c_prec * c_rec / (c_prec + c_rec)) if (c_prec + c_rec) > 0 else 0.0

            by_class_metrics[c] = {
                "precision": round(c_prec, 4),
                "recall": round(c_rec, 4),
                "f1_score": round(c_f1, 4),
                "count_mae": c_err,
                "gt_count": gc,
                "pred_count": pc
            }

        precision = tp_total / max(1, tp_total + fp_total)
        recall = tp_total / max(1, tp_total + fn_total)
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        count_mae = sum(count_errors) / max(1, len(count_errors))

        # mAP@0.50 opcional si ambos tienen bboxes anotados
        gt_with_boxes = [g for g in gt_symbols if g.get("bbox") and len(g["bbox"]) == 4]
        pred_with_boxes = [p for p in pred_symbols if p.get("bbox") and len(p["bbox"]) == 4]
        map_50 = None
        if gt_with_boxes and pred_with_boxes:
            matched_boxes = 0
            for g in gt_with_boxes:
                for p in pred_with_boxes:
                    if compute_box_iou(g["bbox"], p["bbox"]) >= 0.50:
                        matched_boxes += 1
                        break
            map_50 = round(matched_boxes / max(1, len(gt_with_boxes)), 4)

        result = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "count_mae": round(count_mae, 4),
            "by_class_metrics": by_class_metrics,
            "sample_count": len(gt_symbols)
        }
        if map_50 is not None:
            result["map_50"] = map_50
        return result

    # =========================================================================
    # B. MÉTRICAS DECISIONALES (REGLAS QA/QC, SEVERIDAD Y HITL)
    # =========================================================================

    @staticmethod
    def calculate_rules_metrics(pred_findings: List[Dict[str, Any]], gt_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcula matriz de confusión (pass/fail/insufficient_evidence), FPR, FNR y exactitud de severidad."""
        if not gt_rules:
            return {
                "precision": 1.0, "recall": 1.0, "f1_score": 1.0,
                "fpr": 0.0, "fnr": 0.0, "confusion_matrix": {},
                "severity_accuracy": 1.0, "sample_count": 0
            }

        # Indexar hallazgos predichos por rule_code
        pred_by_rule = {p.get("rule_code"): p for p in pred_findings if p.get("rule_code")}

        tp = 0 # GT era Fail y Predicho fue Fail
        fp = 0 # GT era Pass y Predicho fue Fail
        tn = 0 # GT era Pass y Predicho fue Pass
        fn = 0 # GT era Fail y Predicho fue Pass

        correct_severity_count = 0
        total_fails = 0

        for gt in gt_rules:
            rcode = gt.get("rule_code")
            expected_outcome = gt.get("expected_outcome", "pass") # pass, fail, insufficient_evidence
            expected_sev = gt.get("expected_severity", "medium")

            pred_f = pred_by_rule.get(rcode)
            pred_outcome = "fail" if pred_f else "pass"

            if expected_outcome == "fail":
                total_fails += 1
                if pred_outcome == "fail":
                    tp += 1
                    if pred_f.get("severity") == expected_sev:
                        correct_severity_count += 1
                else:
                    fn += 1
            else: # pass o insufficient_evidence
                if pred_outcome == "fail":
                    fp += 1
                else:
                    tn += 1

        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        fpr = fp / max(1, fp + tn)
        fnr = fn / max(1, fn + tp)
        sev_acc = (correct_severity_count / total_fails) if total_fails > 0 else 1.0

        confusion_matrix = {
            "true_positive": tp,
            "false_positive": fp,
            "true_negative": tn,
            "false_negative": fn
        }

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "fpr": round(fpr, 4),
            "fnr": round(fnr, 4),
            "severity_accuracy": round(sev_acc, 4),
            "confusion_matrix": confusion_matrix,
            "sample_count": len(gt_rules)
        }

    @staticmethod
    def calculate_hitl_metrics(resolutions: List[Dict[str, Any]], total_findings: int) -> Dict[str, Any]:
        """Calcula tasas de confirmación, dismissed, accepted risk y desacuerdo con auditor."""
        if not resolutions or total_findings == 0:
            return {
                "confirmation_rate": 0.0,
                "dismissed_rate": 0.0,
                "accepted_risk_rate": 0.0,
                "disagreement_rate": 0.0,
                "sample_count": total_findings
            }

        confirmed = sum(1 for r in resolutions if r.get("action") == "confirm")
        dismissed = sum(1 for r in resolutions if r.get("action") == "dismiss")
        accepted_risk = sum(1 for r in resolutions if r.get("action") == "accept_risk")

        # Desacuerdo: cuando el auditor descarta un hallazgo generado por IA/regla
        disagreed = dismissed

        return {
            "confirmation_rate": round(confirmed / total_findings, 4),
            "dismissed_rate": round(dismissed / total_findings, 4),
            "accepted_risk_rate": round(accepted_risk / total_findings, 4),
            "disagreement_rate": round(disagreed / total_findings, 4),
            "sample_count": total_findings
        }

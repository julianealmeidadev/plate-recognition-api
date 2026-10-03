import sys
import json
import re
import os
import cv2
import easyocr
import numpy as np
from collections import defaultdict

# Inicializa o OCR uma única vez
reader = easyocr.Reader(["en"], gpu=False)


def normalize_plate(text):
    """
    Remove caracteres inválidos e padroniza a placa.
    """
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def detect_plate_format(plate):
    """
    Identifica os principais padrões brasileiros.
    """

    # Modelo antigo: ABC1234
    old_pattern = r"^[A-Z]{3}[0-9]{4}$"

    # Mercosul: ABC1D23
    mercosul_pattern = r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$"

    if re.match(mercosul_pattern, plate):
        return "MERCOSUL"

    if re.match(old_pattern, plate):
        return "BRAZILIAN_OLD"

    return None

def correct_perspective(image):
    """
    Tenta corrigir a perspectiva de uma possível placa.
    Se não encontrar um quadrilátero adequado, retorna a imagem original.
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(
        blurred,
        50,
        150
    )

    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    contours = sorted(
        contours,
        key=cv2.contourArea,
        reverse=True
    )

    plate_contour = None

    for contour in contours[:20]:
        perimeter = cv2.arcLength(contour, True)

        approx = cv2.approxPolyDP(
            contour,
            0.02 * perimeter,
            True
        )

        if len(approx) == 4:
            _, _, w, h = cv2.boundingRect(approx)

            if h == 0:
                continue

            aspect_ratio = w / float(h)

            if 2.0 <= aspect_ratio <= 6.5:
                plate_contour = approx
                break

    if plate_contour is None:
        return image

    points = plate_contour.reshape(4, 2).astype("float32")

    rect = order_points(points)

    top_left, top_right, bottom_right, bottom_left = rect

    width_top = ((top_right[0] - top_left[0]) ** 2 +
                 (top_right[1] - top_left[1]) ** 2) ** 0.5

    width_bottom = ((bottom_right[0] - bottom_left[0]) ** 2 +
                    (bottom_right[1] - bottom_left[1]) ** 2) ** 0.5

    max_width = int(max(width_top, width_bottom))

    height_left = ((bottom_left[0] - top_left[0]) ** 2 +
                   (bottom_left[1] - top_left[1]) ** 2) ** 0.5

    height_right = ((bottom_right[0] - top_right[0]) ** 2 +
                    (bottom_right[1] - top_right[1]) ** 2) ** 0.5

    max_height = int(max(height_left, height_right))

    if max_width <= 0 or max_height <= 0:
        return image

    destination = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1]
    ], dtype="float32")

    matrix = cv2.getPerspectiveTransform(
        rect,
        destination
    )

    warped = cv2.warpPerspective(
        image,
        matrix,
        (max_width, max_height)
    )

    return warped
  
def order_points(points):
    """
    Ordena os 4 pontos:
    topo-esquerda, topo-direita,
    baixo-direita, baixo-esquerda.
    """

    rect = np.zeros((4, 2), dtype="float32")

    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)

    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]

    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]

    return rect
  
def rotate_image(image, angle):
    height, width = image.shape[:2]

    center = (width // 2, height // 2)

    matrix = cv2.getRotationMatrix2D(
        center,
        angle,
        1.0
    )

    rotated = cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )

    return rotated
  
  
def generate_variants(image):
    variants = []

    # Testa pequenas correções de inclinação
    angles = [-4, -2, 0, 2, 4]

    for angle in angles:
        rotated = rotate_image(image, angle)

        gray = cv2.cvtColor(
            rotated,
            cv2.COLOR_BGR2GRAY
        )

        gray = cv2.resize(
            gray,
            None,
            fx=8,
            fy=8,
            interpolation=cv2.INTER_CUBIC
        )

        gray = cv2.bilateralFilter(
            gray,
            7,
            50,
            50
        )

        # Original em escala de cinza
        variants.append(gray)

        # CLAHE
        clahe = cv2.createCLAHE(
            clipLimit=3.0,
            tileGridSize=(8, 8)
        )

        contrast = clahe.apply(gray)
        variants.append(contrast)

        # Otsu
        _, otsu = cv2.threshold(
            contrast,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        variants.append(otsu)

    return variants


def find_plate_regions(image):
    """
    Procura regiões retangulares que podem ser placas.
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blurred = cv2.bilateralFilter(gray, 11, 17, 17)

    edges = cv2.Canny(blurred, 30, 200)

    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    candidates = []

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)

        if h == 0:
            continue

        aspect_ratio = w / float(h)
        area = w * h

        # Faixa mais permissiva para placas
        if (
            1.8 <= aspect_ratio <= 6.5
            and w >= 50
            and h >= 15
            and area >= 1500
        ):
                # pequena margem ao redor
                margin_x = int(w * 0.8)
                margin_y = int(h * 0.4)

                x1 = max(0, x - margin_x)
                y1 = max(0, y - margin_y)
                x2 = min(image.shape[1], x + w + margin_x)
                y2 = min(image.shape[0], y + h + margin_y)

                plate_region = image[y1:y2, x1:x2]

                candidates.append({
                    "image": plate_region,
                    "box": [x1, y1, x2 - x1, y2 - y1]
                })

    return candidates


def run_ocr(image):
    """
    Executa OCR e retorna os textos encontrados.
    """

    results = reader.readtext(
        image,
        allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        detail=1,
        paragraph=False,
        decoder="greedy",
        text_threshold=0.4,
        low_text=0.2,
        link_threshold=0.2,
        mag_ratio=2
    )

    detected = []

    for _, text, confidence in results:
        normalized = normalize_plate(text)

        if normalized:
            detected.append({
                "text": text,
                "normalized": normalized,
                "confidence": float(confidence)
            })

    return detected


def choose_best_plate(results):
    """
    Escolhe a melhor placa válida encontrada considerando:
    - formato válido
    - repetição entre variantes
    - confiança do OCR
    """
    grouped = defaultdict(lambda: {
        "count": 0,
        "confidence_sum": 0,
        "best_confidence": 0,
        "detectedText": ""
    })

    for result in results:
        plate = result["normalized"]
        format_type = detect_plate_format(plate)

        # Ignora leituras que não têm formato de placa válido
        if not format_type:
            continue
  
        confidence = result["confidence"]
        
        grouped[plate]["count"] += 1
        grouped[plate]["confidence_sum"] += confidence
        
        if confidence > grouped[plate]["best_confidence"]:
            grouped[plate]["best_confidence"] = confidence
            grouped[plate]["detectedText"] = result["text"]
            
        grouped[plate]["format"] = format_type

    if not grouped:
        return None
      
    candidates = []

    for plate, data in grouped.items():
        average_confidence = (
            data["confidence_sum"] / data["count"]
        )
        
        # Score combina repetição + confiança
        score = (
            data["count"] * 0.6
            + average_confidence * 0.4
        )

        candidates.append({
            "plate": plate,
            "format": data["format"],
            "confidence": data["best_confidence"],
            "averageConfidence": average_confidence,
            "occurrences": data["count"],
            "score": score,
            "detectedText": data["detectedText"]
        })
         
    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return candidates[0]


def recognize_plate(image_path):
    """
    Fluxo principal de reconhecimento.
    """

    image = cv2.imread(image_path)

    if image is None:
        return {
            "success": False,
            "error": "INVALID_IMAGE"
        }

    all_results = []

    # Primeiro tenta encontrar possíveis regiões de placa
    plate_regions = find_plate_regions(image)
    
    os.makedirs("debug", exist_ok=True)

    for index, region in enumerate(plate_regions):
        original_region = region["image"]

        corrected_region = correct_perspective(
            original_region
        )

        cv2.imwrite(
            f"debug/region_{index}.png",
            original_region
        )

        cv2.imwrite(
            f"debug/region_{index}_corrected.png",
            corrected_region
        )

        # OCR na região original
        for variant in generate_variants(original_region):
            results = run_ocr(variant)
            all_results.extend(results)
        
        # Só processa a corrigida se realmente for diferente
        if not np.array_equal(
          original_region,
          corrected_region
        ):
        # OCR na região corrigida
            for variant in generate_variants(corrected_region):
                results = run_ocr(variant)
                all_results.extend(results)

    # Também tenta OCR na imagem inteira
    for variant in generate_variants(image):
        results = run_ocr(variant)
        all_results.extend(results)
            
    valid_candidates = [
        result
        for result in all_results
        if detect_plate_format(result["normalized"])
    ]
    
    print(
        json.dumps({
            "valid_candidates": valid_candidates
        }),
        file=sys.stderr
    )
    
    best_plate = choose_best_plate(all_results)

    if not best_plate:
        return {
            "success": False,
            "error": "PLATE_NOT_FOUND"
        }

    return {
        "success": True,
        "plate": best_plate["plate"],
        "format": best_plate["format"],
        "confidence": round(best_plate["confidence"], 4),
        "detectedText": best_plate["detectedText"]
    }


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print(json.dumps({
                "success": False,
                "error": "IMAGE_PATH_REQUIRED"
            }))

            sys.exit(1)

        image_path = sys.argv[1]

        result = recognize_plate(image_path)

        # IMPORTANTE:
        # stdout precisa conter apenas JSON
        print(json.dumps(result))

    except Exception as error:
        print(json.dumps({
            "success": False,
            "error": "OCR_ERROR",
            "message": str(error)
        }))

        sys.exit(1)

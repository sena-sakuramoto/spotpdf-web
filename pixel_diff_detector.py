
import cv2
import numpy as np
from PIL import Image
import fitz  # PyMuPDF
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict

class PixelDiffDetector:
    """ピクセルレベル差分検出クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.default_pixel_threshold = 10
        self.noise_filter_size = 2
        self.dpi = 300
        self.added_color = (0, 255, 0)
        self.removed_color = (0, 0, 255)

    def create_pixel_diff_output(self, old_pdf_path: str, new_pdf_path: str, 
                                output_dir: str = "pixel_diff_output", 
                                progress_callback=None, settings: Dict = None) -> Dict:
        
        def log(message):
            self.logger.info(message)
            if progress_callback:
                progress_callback(message)

        if settings is None: settings = {}

        pixel_threshold = settings.get("sensitivity", self.default_pixel_threshold)
        display_filter = settings.get("display_filter", {"added": True, "removed": True})
        export_all = settings.get("export_all_patterns", False)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_stem = Path(old_pdf_path).stem
        new_stem = Path(new_pdf_path).stem
        sub_dir_name = f"{old_stem}_vs_{new_stem}_{timestamp}"
        output_path = Path(output_dir) / sub_dir_name
        output_path.mkdir(exist_ok=True, parents=True)
        base_filename = f"{old_stem}_vs_{new_stem}"

        log(f"差分検出を開始 (感度: {pixel_threshold})")
        log(f"結果はフォルダ '{output_path}' に保存されます")

        results = {"diff_images": [], "summary_pdf": None, "total_changes": 0, "output_path": str(output_path)}
        
        try:
            old_doc, new_doc = fitz.open(old_pdf_path), fitz.open(new_pdf_path)
            max_pages = max(len(old_doc), len(new_doc))
            summary_images = []
            
            for page_num in range(max_pages):
                log(f"ページ {page_num + 1}/{max_pages} を解析中...")
                old_image, new_image = self._get_high_res_page(old_doc, page_num), self._get_high_res_page(new_doc, page_num)
                
                if old_image is not None and new_image is not None:
                    diff_data = self._detect_pixel_differences(old_image, new_image, pixel_threshold)
                    if diff_data["has_changes"]:
                        log(f"  - ページ {page_num + 1}: {diff_data['change_count']} ピクセルの変更を検出")
                        results["total_changes"] += diff_data['change_count']
                        
                        # --- 画像生成ロジック ---
                        if export_all:
                            # 全パターン出力
                            filters_to_export = {
                                "both": {"added": True, "removed": True},
                                "added": {"added": True, "removed": False},
                                "removed": {"added": False, "removed": True},
                            }
                            main_diff_image = None
                            for name, current_filter in filters_to_export.items():
                                diff_image = self._create_precise_diff_display(diff_data, current_filter)
                                diff_filename = f"{base_filename}_p{page_num + 1:03d}_{name}.png"
                                self._save_image(diff_image, output_path / diff_filename, results)
                                if name == "both": main_diff_image = diff_image
                            if main_diff_image is not None: summary_images.append(main_diff_image)
                        else:
                            # 選択されたパターンのみ出力
                            diff_image = self._create_precise_diff_display(diff_data, display_filter)
                            diff_filename = f"{base_filename}_p{page_num + 1:03d}.png"
                            self._save_image(diff_image, output_path / diff_filename, results)
                            summary_images.append(diff_image)
                    else:
                        log(f"  - ページ {page_num + 1}: 差分は見つかりませんでした")

            if summary_images:
                log("差分画像の統合PDFを作成中...")
                results["summary_pdf"] = str(self._create_summary_pdf(summary_images, output_path, base_filename))
            
            old_doc.close(); new_doc.close()
            log(f"差分検出完了: {results['total_changes']} 箇所の変更を検出")
            return results
        except Exception as e:
            self.logger.error(f"差分検出エラー: {e}"); log(f"エラー: {e}"); raise

    def _detect_pixel_differences(self, old_image: np.ndarray, new_image: np.ndarray, pixel_threshold: int) -> Dict:
        old_aligned, new_aligned = self._align_images_precise(old_image, new_image)
        old_gray = cv2.cvtColor(old_aligned, cv2.COLOR_RGB2GRAY)
        new_gray = cv2.cvtColor(new_aligned, cv2.COLOR_RGB2GRAY)
        pixel_diff = cv2.absdiff(old_gray, new_gray)
        _, diff_mask = cv2.threshold(pixel_diff, pixel_threshold, 255, cv2.THRESH_BINARY)
        if self.noise_filter_size > 0:
            kernel = np.ones((self.noise_filter_size, self.noise_filter_size), np.uint8)
            diff_mask = cv2.morphologyEx(diff_mask, cv2.MORPH_OPEN, kernel)
        change_count = np.count_nonzero(diff_mask)
        if change_count == 0: return {"has_changes": False}
        return {"has_changes": True, "change_count": change_count, "base_image": new_aligned, "old_gray": old_gray, "new_gray": new_gray, "diff_mask": diff_mask}

    def _create_precise_diff_display(self, diff_data: Dict, display_filter: Dict) -> np.ndarray:
        result = diff_data["base_image"].copy()
        if not display_filter.get("added") and not display_filter.get("removed"): return result
        diff_pixels_coords = np.where(diff_data["diff_mask"] > 0)
        for y, x in zip(diff_pixels_coords[0], diff_pixels_coords[1]):
            old_val = int(diff_data["old_gray"][y, x])
            new_val = int(diff_data["new_gray"][y, x])
            if (new_val > old_val) and display_filter.get("added"): result[y, x] = self.added_color
            elif (new_val < old_val) and display_filter.get("removed"): result[y, x] = self.removed_color
        return result

    def _save_image(self, image: np.ndarray, path: Path, results_dict: Dict):
        Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(path, dpi=(self.dpi, self.dpi), quality=95)
        results_dict["diff_images"].append(str(path))

    def _get_high_res_page(self, doc, page_num: int):
        if not doc or page_num >= len(doc): return None
        try:
            page = doc[page_num]; mat = fitz.Matrix(self.dpi/72, self.dpi/72); pix = page.get_pixmap(matrix=mat)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4: return cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
            elif pix.n == 1: return cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
            return img_array
        except Exception as e: self.logger.error(f"高解像度ページ {page_num} 取得エラー: {e}"); return None

    def _align_images_precise(self, img1: np.ndarray, img2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        h1, w1 = img1.shape[:2]; h2, w2 = img2.shape[:2]; max_h, max_w = max(h1, h2), max(w1, w2)
        img1_aligned = np.full((max_h, max_w, 3), 255, dtype=np.uint8); img2_aligned = np.full((max_h, max_w, 3), 255, dtype=np.uint8)
        y1, x1 = (max_h - h1) // 2, (max_w - w1) // 2; y2, x2 = (max_h - h2) // 2, (max_w - w2) // 2
        img1_aligned[y1:y1+h1, x1:x1+w1] = img1; img2_aligned[y2:y2+h2, x2:x2+w2] = img2
        return img1_aligned, img2_aligned

    def _create_summary_pdf(self, diff_images: List[np.ndarray], output_path: Path, base_filename: str) -> Path:
        pdf_path = output_path / f"{base_filename}_summary.pdf"
        if diff_images:
            images_to_save = [Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)) for img in diff_images]
            images_to_save[0].save(pdf_path, save_all=True, append_images=images_to_save[1:], dpi=(self.dpi, self.dpi))
        return pdf_path

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if Path("test_docu.pdf").exists() and Path("test_docuv2.pdf").exists():
        detector = PixelDiffDetector()
        test_settings = {"sensitivity": 20, "display_filter": {"added": True, "removed": True}, "export_all_patterns": True}
        results = detector.create_pixel_diff_output("test_docu.pdf", "test_docuv2.pdf", settings=test_settings)
        print(f"=== ピクセルレベル差分検出結果 ==="); print(f"差分画像: {len(results['diff_images'])} 個"); print(f"統合PDF: {results['summary_pdf']}")

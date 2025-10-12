"""
Spotection Performance Monitor
Tracks accuracy, speed, and system metrics
"""

import json
import time
import psutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor and log system performance"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics = {
            "detection_times": [],
            "frame_rates": [],
            "accuracy_scores": [],
            "memory_usage": [],
            "cpu_usage": [],
            "timestamps": []
        }
        
    def start_timer(self) -> float:
        """Start performance timer"""
        return time.time()
    
    def end_timer(self, start_time: float) -> float:
        """End timer and return elapsed time"""
        return time.time() - start_time
    
    def log_detection(self, detection_time: float, num_spots: int, 
                     accuracy: float = None):
        """Log single detection metrics"""
        
        self.metrics["detection_times"].append(detection_time)
        self.metrics["frame_rates"].append(1.0 / detection_time if detection_time > 0 else 0)
        self.metrics["timestamps"].append(datetime.now().isoformat())
        
        if accuracy is not None:
            self.metrics["accuracy_scores"].append(accuracy)
        
        # System metrics
        self.metrics["memory_usage"].append(psutil.virtual_memory().percent)
        self.metrics["cpu_usage"].append(psutil.cpu_percent(interval=0.1))
        
        logger.info(f"Detection: {detection_time:.3f}s, "
                   f"FPS: {1.0/detection_time:.1f}, "
                   f"Spots: {num_spots}")
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics"""
        
        if not self.metrics["detection_times"]:
            return {}
        
        return {
            "avg_detection_time": np.mean(self.metrics["detection_times"]),
            "min_detection_time": np.min(self.metrics["detection_times"]),
            "max_detection_time": np.max(self.metrics["detection_times"]),
            "avg_fps": np.mean(self.metrics["frame_rates"]),
            "avg_memory": np.mean(self.metrics["memory_usage"]),
            "avg_cpu": np.mean(self.metrics["cpu_usage"]),
            "total_detections": len(self.metrics["detection_times"])
        }
    
    def save_metrics(self, filename: str = None):
        """Save metrics to JSON"""
        
        if filename is None:
            filename = f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.log_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        
        logger.info(f"Metrics saved: {filepath}")
    
    def generate_report(self, output_path: str = None):
        """Generate performance report with visualizations"""
        
        if not self.metrics["detection_times"]:
            logger.warning("No metrics to report")
            return
        
        if output_path is None:
            output_path = self.log_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Spotection Performance Report', fontsize=16)
        
        # Detection times
        ax = axes[0, 0]
        ax.plot(self.metrics["detection_times"], 'b-', linewidth=2)
        ax.set_title('Detection Times')
        ax.set_xlabel('Detection #')
        ax.set_ylabel('Time (seconds)')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=np.mean(self.metrics["detection_times"]), 
                   color='r', linestyle='--', label=f'Avg: {np.mean(self.metrics["detection_times"]):.3f}s')
        ax.legend()
        
        # Frame rates
        ax = axes[0, 1]
        ax.plot(self.metrics["frame_rates"], 'g-', linewidth=2)
        ax.set_title('Frame Rate (FPS)')
        ax.set_xlabel('Detection #')
        ax.set_ylabel('FPS')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=np.mean(self.metrics["frame_rates"]), 
                   color='r', linestyle='--', label=f'Avg: {np.mean(self.metrics["frame_rates"]):.1f} FPS')
        ax.legend()
        
        # Resource usage
        ax = axes[1, 0]
        ax.plot(self.metrics["memory_usage"], 'r-', linewidth=2, label='Memory')
        ax.plot(self.metrics["cpu_usage"], 'orange', linewidth=2, label='CPU')
        ax.set_title('Resource Usage')
        ax.set_xlabel('Detection #')
        ax.set_ylabel('Usage (%)')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Summary statistics
        ax = axes[1, 1]
        ax.axis('off')
        
        stats = self.get_summary_stats()
        summary_text = f"""
        SUMMARY STATISTICS
        
        Total Detections: {stats['total_detections']}
        
        Detection Time:
          Average: {stats['avg_detection_time']:.3f}s
          Min: {stats['min_detection_time']:.3f}s
          Max: {stats['max_detection_time']:.3f}s
        
        Frame Rate:
          Average: {stats['avg_fps']:.1f} FPS
        
        Resources:
          CPU: {stats['avg_cpu']:.1f}%
          Memory: {stats['avg_memory']:.1f}%
        """
        
        ax.text(0.1, 0.9, summary_text, transform=ax.transAxes,
               fontsize=11, verticalalignment='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Report saved: {output_path}")
        
        return output_path


class AccuracyValidator:
    """Validate detection accuracy against ground truth"""
    
    def __init__(self, ground_truth_path: str = "data/ground_truth.json"):
        self.ground_truth_path = Path(ground_truth_path)
        self.ground_truth = self.load_ground_truth()
        
    def load_ground_truth(self) -> Dict:
        """Load ground truth annotations"""
        
        if not self.ground_truth_path.exists():
            logger.warning(f"Ground truth not found: {self.ground_truth_path}")
            return {}
        
        with open(self.ground_truth_path, 'r') as f:
            return json.load(f)
    
    def validate_detection(self, detection_results: List[Dict]) -> Dict:
        """Validate detection results against ground truth"""
        
        if not self.ground_truth:
            logger.warning("No ground truth available for validation")
            return {}
        
        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0
        
        for result in detection_results:
            spot_id = result["id"]
            detected_status = result["status"]
            
            if spot_id in self.ground_truth:
                actual_status = self.ground_truth[spot_id]
                
                if detected_status == "OCCUPIED" and actual_status == "OCCUPIED":
                    true_positives += 1
                elif detected_status == "OCCUPIED" and actual_status == "FREE":
                    false_positives += 1
                elif detected_status == "FREE" and actual_status == "FREE":
                    true_negatives += 1
                elif detected_status == "FREE" and actual_status == "OCCUPIED":
                    false_negatives += 1
        
        total = true_positives + false_positives + true_negatives + false_negatives
        
        if total == 0:
            return {}
        
        accuracy = (true_positives + true_negatives) / total
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        metrics = {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "false_negatives": false_negatives,
            "total_samples": total
        }
        
        logger.info("\nACCURACY METRICS:")
        logger.info(f"  Accuracy: {accuracy:.2%}")
        logger.info(f"  Precision: {precision:.2%}")
        logger.info(f"  Recall: {recall:.2%}")
        logger.info(f"  F1 Score: {f1_score:.3f}")
        
        return metrics
    
    def create_ground_truth(self, image_path: str, output_path: str = None):
        """Interactive tool to create ground truth annotations"""
        
        import cv2
        
        if output_path is None:
            output_path = self.ground_truth_path
        
        # Load spot layout
        with open("data/spot_layout.json", 'r') as f:
            spots = json.load(f)
        
        image = cv2.imread(image_path)
        ground_truth = {}
        current_idx = 0
        
        def draw_spot(img, spot, status):
            polygon = np.array(spot["polygon"], dtype=np.int32)
            color = (0, 0, 255) if status == "OCCUPIED" else (0, 255, 0)
            cv2.polylines(img, [polygon], True, color, 2)
            
            center_x = int(np.mean([p[0] for p in spot["polygon"]]))
            center_y = int(np.mean([p[1] for p in spot["polygon"]]))
            cv2.putText(img, f"{spot['id']}: {status}", (center_x - 30, center_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        print("Ground Truth Annotation Tool")
        print("Press 'o' for OCCUPIED, 'f' for FREE, 's' to save and quit")
        
        while current_idx < len(spots):
            display = image.copy()
            spot = spots[current_idx]
            
            # Draw current spot highlighted
            polygon = np.array(spot["polygon"], dtype=np.int32)
            cv2.polylines(display, [polygon], True, (255, 255, 0), 3)
            
            # Draw already annotated spots
            for spot_id, status in ground_truth.items():
                for s in spots:
                    if s["id"] == spot_id:
                        draw_spot(display, s, status)
            
            cv2.putText(display, f"Annotating: {spot['id']} ({current_idx + 1}/{len(spots)})",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            cv2.imshow("Ground Truth Annotation", display)
            key = cv2.waitKey(0) & 0xFF
            
            if key == ord('o'):
                ground_truth[spot["id"]] = "OCCUPIED"
                current_idx += 1
            elif key == ord('f'):
                ground_truth[spot["id"]] = "FREE"
                current_idx += 1
            elif key == ord('s'):
                break
            elif key == ord('q'):
                return
        
        cv2.destroyAllWindows()
        
        # Save ground truth
        with open(output_path, 'w') as f:
            json.dump(ground_truth, f, indent=2)
        
        logger.info(f"Ground truth saved: {output_path}")
        logger.info(f"Annotated {len(ground_truth)} spots")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance Monitor")
    parser.add_argument("--create-ground-truth", action="store_true",
                       help="Create ground truth annotations")
    parser.add_argument("--image", help="Image for ground truth creation")
    parser.add_argument("--validate", help="Validate results JSON file")
    parser.add_argument("--report", action="store_true",
                       help="Generate performance report")
    
    args = parser.parse_args()
    
    if args.create_ground_truth:
        if not args.image:
            print("--image required for ground truth creation")
            return
        
        validator = AccuracyValidator()
        validator.create_ground_truth(args.image)
    
    elif args.validate:
        validator = AccuracyValidator()
        
        with open(args.validate, 'r') as f:
            results = json.load(f)
        
        if "spots" in results:
            metrics = validator.validate_detection(results["spots"])
            
            # Save metrics
            output_path = Path(args.validate).parent / "validation_metrics.json"
            with open(output_path, 'w') as f:
                json.dump(metrics, f, indent=2)
            print(f"Validation metrics saved: {output_path}")
    
    elif args.report:
        monitor = PerformanceMonitor()
        
        # Load recent metrics
        log_files = sorted(monitor.log_dir.glob("metrics_*.json"))
        if log_files:
            with open(log_files[-1], 'r') as f:
                monitor.metrics = json.load(f)
            monitor.generate_report()
        else:
            print("No metrics found to generate report")
    
    else:
        print("Performance Monitor")
        print("\nUsage:")
        print("  Create ground truth: python performance_monitor.py --create-ground-truth --image <image>")
        print("  Validate results:    python performance_monitor.py --validate <results.json>")
        print("  Generate report:     python performance_monitor.py --report")


if __name__ == "__main__":
    main()

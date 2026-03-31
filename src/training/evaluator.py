"""
Evaluator Module
Evaluate model performance with WER/CER metrics
"""

from typing import List, Dict
import jiwer


class Evaluator:
    """Model evaluation with WER and CER"""
    
    def __init__(self):
        self.references = []
        self.predictions = []
    
    def add_sample(self, reference: str, prediction: str):
        """Add a sample for evaluation"""
        self.references.append(reference)
        self.predictions.append(prediction)
    
    def compute_wer(self) -> float:
        """Compute Word Error Rate"""
        if not self.references:
            return 1.0
        
        return jiwer.wer(self.references, self.predictions)
    
    def compute_cer(self) -> float:
        """Compute Character Error Rate"""
        if not self.references:
            return 1.0
        
        return jiwer.cer(self.references, self.predictions)
    
    def compute_all_metrics(self) -> Dict:
        """Compute all evaluation metrics"""
        return {
            "wer": self.compute_wer(),
            "cer": self.compute_cer(),
            "samples": len(self.references)
        }
    
    def clear(self):
        """Clear all samples"""
        self.references = []
        self.predictions = []
    
    def get_detailed_report(self) -> str:
        """Get detailed evaluation report"""
        metrics = self.compute_all_metrics()
        
        report = f"""
        === Evaluation Report ===
        Samples: {metrics['samples']}
        Word Error Rate (WER): {metrics['wer']:.2%}
        Character Error Rate (CER): {metrics['cer']:.2%}
        
        Sample comparisons:
        """
        
        for i in range(min(5, len(self.references))):
            report += f"
[{i+1}] Ref: {self.references[i]}"
            report += f"
    Pred: {self.predictions[i]}
"
        
        return report

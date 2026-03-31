"""
Improvement Tracker Module
Track model improvement over time
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


class ImprovementTracker:
    """Track model performance improvements over time"""
    
    def __init__(self, database_manager):
        self.db = database_manager
        self.metrics = defaultdict(list)
    
    def record_metric(self, metric_name: str, value: float, version: str = None):
        """
        Record a metric value
        
        Args:
            metric_name: Name of the metric (wer, cer, speed, etc.)
            value: Metric value
            version: Model version associated with this metric
        """
        self.metrics[metric_name].append({
            "timestamp": datetime.now(),
            "value": value,
            "version": version
        })
    
    def get_trend(self, metric_name: str, days: int = 30) -> List[Dict]:
        """
        Get trend data for a metric over time
        
        Args:
            metric_name: Name of the metric
            days: Number of days to look back
            
        Returns:
            List of metric records
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        return [
            m for m in self.metrics.get(metric_name, [])
            if m["timestamp"] >= cutoff
        ]
    
    def get_improvement_rate(self, metric_name: str) -> float:
        """
        Calculate improvement rate per day
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Improvement rate (negative means improvement)
        """
        data = self.get_trend(metric_name, days=30)
        
        if len(data) < 2:
            return 0.0
        
        oldest = data[0]["value"]
        newest = data[-1]["value"]
        days = (data[-1]["timestamp"] - data[0]["timestamp"]).days
        
        if days == 0:
            return 0.0
        
        return (newest - oldest) / days
    
    def get_best_wer(self) -> float:
        """Get the best WER recorded"""
        wer_data = self.metrics.get("wer", [])
        if not wer_data:
            return 0.0
        
        return min(m["value"] for m in wer_data)
    
    def get_improvement_summary(self) -> Dict:
        """Get a summary of all improvements"""
        return {
            "best_wer": self.get_best_wer(),
            "wer_improvement_rate": self.get_improvement_rate("wer"),
            "total_metrics_recorded": sum(len(v) for v in self.metrics.values()),
            "metrics_tracked": list(self.metrics.keys())
        }
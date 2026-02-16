"""
Configuration Handler for MEA Analysis
Reads and manages YAML configuration files
"""

import yaml
import numpy as np
from pathlib import Path


class ConfigHandler:
    """Handles loading and accessing configuration files"""
    
    def __init__(self, project_root=None):
        """
        Initialize the config handler
        
        Parameters:
        -----------
        project_root : str or Path, optional
            Root directory of the project. If None, assumes current directory.
        """
        if project_root is None:
            # Get the directory where this script is located, then go up one level
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = Path(project_root)
        
        self.config_dir = self.project_root / "config"
        self.metrics_config = None
        
    def load_metrics_config(self):
        """
        Load the metrics configuration file
        
        Returns:
        --------
        dict : Dictionary containing metric categorizations
        """
        config_path = self.config_dir / "metrics_config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as file:
            self.metrics_config = yaml.safe_load(file)
        
        print(f"✓ Loaded metrics config from: {config_path}")
        return self.metrics_config
    
    def get_metric_type(self, metric_name):
        """
        Get the type of a specific metric (count, rate, interval_duration, or derived)
        
        Parameters:
        -----------
        metric_name : str
            Name of the metric to check
            
        Returns:
        --------
        str : Type of metric ('count', 'rate', 'interval_duration', 'derived', or 'unknown')
        """
        if self.metrics_config is None:
            self.load_metrics_config()
        
        metrics = self.metrics_config['metrics']
        
        if metric_name in metrics['count_metrics']:
            return 'count'
        elif metric_name in metrics['rate_metrics']:
            return 'rate'
        elif metric_name in metrics['interval_duration_metrics']:
            return 'interval_duration'
        elif metric_name in metrics['derived_metrics']:
            return 'derived'
        else:
            return 'unknown'
    
    def get_all_metrics(self):
        """
        Get a list of all configured metrics
        
        Returns:
        --------
        list : All metric names
        """
        if self.metrics_config is None:
            self.load_metrics_config()
        
        all_metrics = []
        metrics = self.metrics_config['metrics']
        
        for category in ['count_metrics', 'rate_metrics', 
                        'interval_duration_metrics', 'derived_metrics']:
            all_metrics.extend(metrics[category])
        
        return all_metrics
    
    def get_missing_value_strategy(self, metric_name):
        """
        Get the appropriate missing value replacement for a metric
        
        Parameters:
        -----------
        metric_name : str
            Name of the metric
            
        Returns:
        --------
        Value to use for missing data (0 or NaN)
        """
        
        metric_type = self.get_metric_type(metric_name)
        
        if metric_type in ['count', 'rate']:
            return 0
        elif metric_type in ['interval_duration', 'derived']:
            return np.nan
        else:
            print(f"⚠ Warning: Unknown metric '{metric_name}', using NaN for missing values")
            return np.nan
    
    def print_config_summary(self):
        """Print a summary of the loaded configuration"""
        if self.metrics_config is None:
            self.load_metrics_config()
        
        metrics = self.metrics_config['metrics']
        
        print("\n" + "="*50)
        print("METRICS CONFIGURATION SUMMARY")
        print("="*50)
        
        print(f"\n📊 COUNT METRICS (missing = 0):")
        for m in metrics['count_metrics']:
            print(f"  • {m}")
        
        print(f"\n📈 RATE METRICS (missing = 0):")
        for m in metrics['rate_metrics']:
            print(f"  • {m}")
        
        print(f"\n⏱️  INTERVAL/DURATION METRICS (missing = NaN):")
        for m in metrics['interval_duration_metrics']:
            print(f"  • {m}")
        
        print(f"\n🔬 DERIVED METRICS (missing = NaN):")
        for m in metrics['derived_metrics']:
            print(f"  • {m}")
        
        print(f"\n📋 TOTAL: {len(self.get_all_metrics())} metrics configured")
        print("="*50 + "\n")


# Example usage
if __name__ == "__main__":
    # Create config handler
    config = ConfigHandler()
    
    # Load and display configuration
    config.load_metrics_config()
    config.print_config_summary()
    
    # Test getting metric types
    print("\nTesting metric type detection:")
    test_metrics = [
        "Number of Bursts",
        "Weighted Mean Firing Rate (Hz)",
        "Burst Duration - Avg (sec)",
        "Synchrony Index"
    ]
    
    for metric in test_metrics:
        metric_type = config.get_metric_type(metric)
        missing_strategy = config.get_missing_value_strategy(metric)
        print(f"  {metric}: type='{metric_type}', missing={missing_strategy}")
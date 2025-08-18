"""State management for the movformer GUI application."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class GUIStateManager:
    """Manages the GUI state, loading from and saving to gui_state.yaml."""
    
    def __init__(self, state_file_path: Optional[str] = None):
        """Initialize the state manager.
        
        Args:
            state_file_path: Path to the state file. If None, uses default location.
        """
        # Leave hard coded for now
        self.state_file_path = Path(r"C:\Users\Admin\Documents\Akseli\Code\movformer-gui\gui_state.yaml")

        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:

        with open(self.state_file_path, 'r', encoding='utf-8') as f:
            current_state = yaml.safe_load(f) or {}

        return current_state
    
    def _save_state(self, state: Dict[str, Any]):
        """Save state to YAML file."""
        try:
            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                yaml.dump(state, f, default_flow_style=False, sort_keys=False)     
        except Exception as e:
            print(f"Error saving state file: {e}")
    

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the state."""
        return self.state.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a value in the state and save to file."""
        self.state[key] = value
        self._save_state(self.state)
    
    def update(self, updates: Dict[str, Any]):
        """Update multiple values in the state and save to file."""
        self.state.update(updates)
        self._save_state(self.state)
    
    def get_value(self, key: str, default: Any = None, dtype: Optional[type] = None) -> Any:
        """Get a value from the state, optionally casting to dtype."""
        value = self.state.get(key, default)
        if dtype is not None and value is not None:
            try:
                return dtype(value)
            except Exception:
                return default
        return value

    def set_value(self, key: str, value: Any):
        """Set a value in the state and save to file."""
        self.set(key, value)
    
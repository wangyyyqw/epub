from abc import ABC, abstractmethod
import argparse

class BasePlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin description"""
        pass

    @abstractmethod
    def register_arguments(self, parser: argparse.ArgumentParser):
        """Register plugin-specific arguments"""
        pass

    @abstractmethod
    def run(self, args: argparse.Namespace):
        """Execute the plugin logic"""
        pass
